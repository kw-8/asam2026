"""
probe_bow.py
============
Second read-only WRDS check for signals/lazy_prices (Steps 3 and 6 of
prompts/data_acquisition.md). The first check (probe_wrds.py) showed that our
WRDS account has the SEC Analytics "Bag of Words" tables. This one looks inside
them to answer the question that decides download vs. build:

    What is each filing compared with in wrdssec.bow_cossim?
    The paper compares each 10-K with the prior 10-K, and each 10-Q with the
    10-Q for the same quarter a year earlier. If WRDS compares with the
    immediately previous filing instead (e.g. a 10-Q with last quarter's 10-K),
    we compute the similarity ourselves from the word counts.

It also checks:
  - what the section-level tables (sec_item_scores, ...) hold, e.g. whether
    the risk-factors section (Item 1A) is there;
  - the time zone of wrds_forms.secatime (SEC acceptance time), by comparing
    Apple's filings with Compustat's filing times (which looked like UTC);
  - how many 10-K / 10-Q filings have an acceptance time, by year.

Everything printed is also saved to data/lazy_prices/probe_bow_output.txt
(Git ignores data/), so Claude can read it.

Run from the repo root, with the .venv active:
    python signals\\lazy_prices\\probe_bow.py --user YOUR_WRDS_USERNAME

You type your WRDS password at the prompt (and approve Duo if asked).
Takes about 3-10 minutes; each query gives up after a few minutes rather than hang.
"""
from __future__ import annotations

import argparse
import sys
from itertools import combinations
from pathlib import Path

import pandas as pd
import wrds

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "lazy_prices"
LOG = OUT / "probe_bow_output.txt"

LIB = "wrdssec"
APPLE_CIK, APPLE_GVKEY = "320193", "001690"
FORMS = ("10-K", "10-Q")
SAMPLE = 200_000            # rows used for quick distributions (first rows of a table)
TIMEOUT_S = 240             # per query

# (table, what to do): "pairs" = the key table; "detail" = columns + coverage + Apple rows;
# "peek" = columns + 3 rows (tables too big to filter)
TARGETS = [
    ("bow_cossim", "pairs"),
    ("bow_filingsummary", "detail"),
    ("sec_item_scores", "detail"),
    ("sec_item_scores_trans", "peek"),
    ("sec_item_words_filings", "peek"),
    ("sec_item_words_freq", "peek"),
    ("bow_wordsummary", "peek"),
    ("bow_2024", "peek"),
]

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_colwidth", 45)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
class Tee:
    """Print to the terminal and to the output file at the same time."""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            st.write(s)

    def flush(self):
        for st in self.streams:
            st.flush()


def run(db, sql: str, timeout_s: int = TIMEOUT_S) -> pd.DataFrame | None:
    """Run a SELECT and return a DataFrame; on error print it and carry on.

    Uses the database cursor directly: with this repo's requirements
    (pandas 3.x + wrds 3.1.6 + SQLAlchemy 1.4), wrds' own raw_sql() fails
    with "'Connection' object has no attribute 'cursor'".
    """
    conn = db.connection.connection
    cur = conn.cursor()
    try:
        try:
            cur.execute(f"SET statement_timeout = {int(timeout_s * 1000)}")
        except Exception:  # noqa: BLE001  (no timeout allowed: run without one)
            conn.rollback()
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)
    except Exception as e:  # noqa: BLE001
        msg = str(e).strip().splitlines()[0] if str(e).strip() else ""
        print(f"  query failed: {type(e).__name__}: {msg[:200]}")
        try:
            conn.rollback()   # a failed query blocks the next one until rollback
        except Exception:  # noqa: BLE001
            pass
        return None
    finally:
        cur.close()


def describe(db, table: str) -> pd.DataFrame | None:
    """Columns and types (lower-case names). Also prints WRDS' approximate row count."""
    try:
        d = db.describe_table(library=LIB, table=table)
    except Exception as e:  # noqa: BLE001
        print(f"  could not describe {LIB}.{table}: {type(e).__name__}: {str(e)[:150]}")
        return None
    d = d.assign(name=d["name"].astype(str).str.lower(), type=d["type"].astype(str).str.upper())
    return d[["name", "type"]]


def show(df: pd.DataFrame | None, title: str) -> None:
    if df is None:
        return
    print(f"\n  {title}" + (" (no rows)" if df.empty else ""))
    if not df.empty:
        print("    " + df.to_string(index=False).replace("\n", "\n    "))


def section(title: str) -> None:
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


def date_columns(d: pd.DataFrame) -> list[str]:
    by_type = d.loc[d["type"].str.contains("DATE|TIME"), "name"].tolist()
    by_name = [n for n in d["name"] if ("date" in n or n.endswith("dt")) and n not in by_type]
    return by_type + by_name


def file_columns(cols: list[str]) -> list[str]:
    """Columns that look like filing file names (e.g. fname, wrdsfname, prev_fname)."""
    return [c for c in cols if "fname" in c or "filename" in c or "file_name" in c]


def apple_filter(d: pd.DataFrame, apple: pd.DataFrame | None) -> str | None:
    """A WHERE clause that picks Apple's rows, using whatever ID the table has.
    Compares the column as stored (no functions on it), so an index can be used."""
    cols = d["name"].tolist()
    if "cik" in cols:
        t = d.loc[d["name"] == "cik", "type"].iloc[0]
        if any(k in t for k in ("CHAR", "TEXT", "STRING")):
            return f"cik IN ('{APPLE_CIK.zfill(10)}', '{APPLE_CIK}')"
        return f"cik = {APPLE_CIK}"
    acc = [c for c in cols if "accession" in c or c == "accno"]
    if acc and apple is not None and not apple.empty:
        ids = ", ".join(f"'{a}'" for a in apple["accession"].dropna().astype(str))
        return f"CAST({acc[0]} AS TEXT) IN ({ids})"
    files = file_columns(cols)
    if files:
        return f"CAST({files[0]} AS TEXT) ~ '0000{APPLE_CIK}-|/{APPLE_CIK}/'"
    if "gvkey" in cols:
        return f"CAST(gvkey AS TEXT) = '{APPLE_GVKEY}'"
    return None


# ----------------------------------------------------------------------------
# Checks
# ----------------------------------------------------------------------------
def apple_filings(db) -> pd.DataFrame | None:
    section("0. Apple's recent 10-K / 10-Q filings (reference for the checks below)")
    forms = ", ".join(f"'{f}'" for f in FORMS)
    a = run(db, f"""
        SELECT fdate, accession, form, rdate, secadate, secatime, fname, wrdsfname
        FROM {LIB}.wrds_forms
        WHERE cik = '{APPLE_CIK.zfill(10)}' AND form IN ({forms})   -- cik is zero-padded text (probe 1)
        ORDER BY fdate DESC LIMIT 12
    """)
    show(a, "Apple, latest 12 (rdate = period of report)")
    return a


def inspect_table(db, table: str, mode: str, apple: pd.DataFrame | None) -> None:
    section(f"{LIB}.{table}  [{mode}]")
    d = describe(db, table)
    if d is None:
        return
    cols = d["name"].tolist()
    print("  columns: " + ", ".join(f"{n} ({t.split('(')[0].lower()})" for n, t in d.itertuples(index=False)))
    pick = ", ".join(cols[:25])

    if mode == "peek":
        show(run(db, f"SELECT {pick} FROM {LIB}.{table} LIMIT 3"), "first 3 rows")
        return

    dates = date_columns(d)
    if dates:
        cov = run(db, f"SELECT MIN({dates[0]}) AS first, MAX({dates[0]}) AS last FROM {LIB}.{table}")
        if cov is not None and not cov.empty:
            print(f"\n  coverage of {dates[0]}: {cov.iloc[0, 0]} to {cov.iloc[0, 1]}")

    where = apple_filter(d, apple)
    if where:
        files = file_columns(cols)
        order = (f" ORDER BY {dates[0]} DESC" if dates
                 else f" ORDER BY {files[0]} DESC" if files else "")   # file names sort by date
        show(run(db, f"SELECT {pick} FROM {LIB}.{table} WHERE {where}{order} LIMIT 16"),
             "Apple rows (latest first)")
    else:
        print("  no cik / accession / file-name / gvkey column to find Apple; first rows instead:")
        show(run(db, f"SELECT {pick} FROM {LIB}.{table} LIMIT 5"), "first 5 rows")

    sub = f"(SELECT * FROM {LIB}.{table} LIMIT {SAMPLE}) s"
    if mode == "pairs":
        # What is each filing compared with? Gap between date columns, and form pairs.
        for a, b in list(combinations(dates, 2))[:3]:
            show(run(db, f"""
                SELECT ROUND((CAST({a} AS DATE) - CAST({b} AS DATE)) / 30.44) AS months_apart,
                       COUNT(*) AS n
                FROM {sub} GROUP BY 1 ORDER BY 2 DESC LIMIT 8
            """), f"months between {a} and {b} (first {SAMPLE:,} rows)")
        files = file_columns(cols)
        if len(dates) < 2 and len(files) >= 2:
            # No date pair in the table: look up both filings in wrds_forms instead.
            c1, c2 = files[0], files[1]
            for key in ("fname", "wrdsfname"):
                r = run(db, f"""
                    SELECT ROUND((f1.fdate - f2.fdate) / 30.44) AS months_apart,
                           f1.form AS form_{c1}, f2.form AS form_{c2}, COUNT(*) AS n
                    FROM (SELECT {c1}, {c2} FROM {LIB}.{table} LIMIT {SAMPLE}) s
                    JOIN {LIB}.wrds_forms f1 ON f1.{key} = s.{c1}
                    JOIN {LIB}.wrds_forms f2 ON f2.{key} = s.{c2}
                    GROUP BY 1, 2, 3 ORDER BY 4 DESC LIMIT 15
                """, timeout_s=420)
                if r is not None and not r.empty:
                    show(r, f"{c1} vs {c2}, matched to wrds_forms.{key}: months apart and forms")
                    break
            else:
                print(f"\n  could not match {c1} / {c2} to wrds_forms file names")
        forms = [c for c in cols if "form" in c]
        if forms:
            g = ", ".join(forms[:2])
            show(run(db, f"SELECT {g}, COUNT(*) AS n FROM {sub} GROUP BY {g} ORDER BY n DESC LIMIT 15"),
                 f"form combinations (first {SAMPLE:,} rows)")
    if "item" in table:
        items = [c for c in cols if "item" in c or "section" in c]
        if items:
            show(run(db, f"SELECT {items[0]}, COUNT(*) AS n FROM {sub} GROUP BY 1 ORDER BY 2 DESC LIMIT 30"),
                 f"values of {items[0]} (first {SAMPLE:,} rows)")


def check_acceptance_time(db, apple: pd.DataFrame | None) -> None:
    section("Acceptance time (wrds_forms.secatime): time zone and coverage")
    co = run(db, f"""
        SELECT srctype, filedate, CAST(filedatetime AS TEXT) AS compustat_time
        FROM comp.co_filedate
        WHERE gvkey = '{APPLE_GVKEY}' AND srctype IN ('10K', '10Q') AND filedate >= '2023-01-01'
    """)
    if apple is not None and co is not None and not apple.empty:
        a = apple[["fdate", "form", "secadate", "secatime"]].copy()
        a["fdate"] = pd.to_datetime(a["fdate"])
        co["filedate"] = pd.to_datetime(co["filedate"])
        m = a.merge(co, left_on="fdate", right_on="filedate", how="left").drop(columns="filedate")
        show(m, "Apple: SEC acceptance time vs Compustat's time "
                "(Compustat looked like UTC: 5 hours ahead of New York in winter, 4 in summer)")

    forms = ", ".join(f"'{f}'" for f in FORMS)
    cov = run(db, f"""
        SELECT EXTRACT(YEAR FROM fdate)::int AS year,
               COUNT(*) AS filings,
               AVG(CASE WHEN secatime IS NULL THEN 0.0 ELSE 1.0 END) AS share_with_time
        FROM {LIB}.wrds_forms
        WHERE form IN ({forms})
        GROUP BY 1 ORDER BY 1
    """, timeout_s=420)
    if cov is not None and not cov.empty:
        cov["share_with_time"] = pd.to_numeric(cov["share_with_time"]).map("{:.0%}".format)
        show(cov, "10-K + 10-Q filings with an acceptance time, by filing year")
    hours = run(db, f"""
        SELECT SUBSTRING(CAST(secatime AS TEXT) FROM 1 FOR 2) AS hour, COUNT(*) AS n
        FROM (SELECT secatime FROM {LIB}.wrds_forms
              WHERE form IN ({forms}) AND fdate >= '2020-01-01' LIMIT {SAMPLE}) s
        GROUP BY 1 ORDER BY 1
    """)
    show(hours, "hour of acceptance, recent 10-K/10-Q sample (EDGAR is open 06-22 New York time)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Second read-only WRDS check for lazy_prices.")
    ap.add_argument("--user", required=True, help="your WRDS username")
    a = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    print("Connecting to WRDS. Type your password at the prompt; approve Duo if asked.")
    db = wrds.Connection(wrds_username=a.user)   # connect before logging, so nothing about login is saved

    with open(LOG, "w", encoding="utf-8") as f:
        sys.stdout = Tee(sys.__stdout__, f)
        try:
            print(f"lazy_prices Bag-of-Words probe, {pd.Timestamp.now():%Y-%m-%d %H:%M}")
            apple = apple_filings(db)
            for table, mode in TARGETS:
                inspect_table(db, table, mode, apple)
            check_acceptance_time(db, apple)
            print("\nDone. Reply 'done' in the chat; Claude will read data/lazy_prices/probe_bow_output.txt.")
        finally:
            sys.stdout = sys.__stdout__
            db.close()
    print(f"\nSaved: {LOG.relative_to(REPO)}")


if __name__ == "__main__":
    main()
