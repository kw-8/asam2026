"""
probe_wrds.py
=============
Steps 3 and 5 (Case + Inventory) of prompts/data_acquisition.md for
signals/lazy_prices. Read-only: it looks at what your WRDS account can see
and downloads nothing big.

It answers four questions:
  1. Can your account see the WRDS SEC Analytics Suite (library wrdssec)?
  2. Are ready-made filing-similarity scores there (WRDS "Bag of Words":
     cosine, Jaccard, minimum edit distance)? If yes, we can likely
     download the signal (Case 1) instead of building it (Case 2).
  3. Is there a list of 10-K / 10-Q filings with dates, and a CIK-to-gvkey link?
  4. Does comp.co_filedate have filing times for 10-Qs as well as 10-Ks?

Everything printed is also saved to data/lazy_prices/probe_output.txt
(Git ignores data/), so Claude can read the results directly.

Run from the repo root, with the .venv active:
    python signals\\lazy_prices\\probe_wrds.py --user YOUR_WRDS_USERNAME

You type your WRDS password at the prompt (and approve Duo if asked).
The password never goes into this file, the chat, or the output file.
Takes about 2-5 minutes.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd
import wrds

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "lazy_prices"
LOG = OUT / "probe_output.txt"

EXAMPLE_CIK = "320193"   # Apple, for the eyeball checks
SIM_COLS = "(cosine|cossim|cos_sim|jaccard|jacc|simil|edit_?dist|mindist)"   # similarity-looking columns
SIM_TABLES = "(bow|bagofword|bag_of|simil|cosine|cossim|jaccard)"           # similarity-looking tables
SEC_LIB = re.compile(r"(^sec|wrdssec|_sec_|_sec$)", re.IGNORECASE).search    # not 'taqmsec' (trade data)
IS_SIM = re.compile(SIM_COLS, re.IGNORECASE).search
MAX_TABLES = 15                                                # detail at most this many hit tables
ID_COLS = ("cik", "gvkey", "coname", "conm", "form", "fdate", "rdate", "fname", "filename",
           "accession", "period", "secpdate", "secadate", "fyear", "year", "date")
FORMS = ("10-K", "10-K405", "10-KSB", "10-KT", "10-Q", "10-QSB")

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 30)
pd.set_option("display.max_colwidth", 60)


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


def query(db, sql: str) -> pd.DataFrame:
    """Run a SELECT and return a DataFrame.

    Uses the database cursor directly: with this repo's requirements
    (pandas 3.x + wrds 3.1.6 + SQLAlchemy 1.4), wrds' own raw_sql() fails
    with "'Connection' object has no attribute 'cursor'".
    """
    cur = db.connection.connection.cursor()
    try:
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)
    finally:
        cur.close()


def run(db, sql: str) -> pd.DataFrame | None:
    """query(), but print the error and carry on instead of stopping."""
    try:
        return query(db, sql)
    except Exception as e:  # noqa: BLE001
        msg = str(e).strip().splitlines()[0] if str(e).strip() else ""
        print(f"  query failed: {type(e).__name__}: {msg[:200]}")
        try:
            db.connection.connection.rollback()   # a failed query blocks the next one until rollback
        except Exception:  # noqa: BLE001
            pass
        return None


def columns_of(db, lib: str, table: str) -> list[str]:
    try:
        return [str(c).lower() for c in db.describe_table(library=lib, table=table)["name"]]
    except Exception as e:  # noqa: BLE001
        print(f"  could not describe {lib}.{table}: {e}")
        return []


def pick(cols: list[str], *candidates: str) -> str | None:
    """First candidate that is a column, else None."""
    return next((c for c in candidates if c in cols), None)


def cik_filter(col: str) -> str:
    # CIK may be stored as a number or as zero-padded text; this matches both.
    return f"LTRIM(CAST({col} AS TEXT), '0') = '{EXAMPLE_CIK}'"


def section(title: str) -> None:
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


# ----------------------------------------------------------------------------
# The four checks
# ----------------------------------------------------------------------------
def check_libraries(db) -> list[str]:
    section("1. Which SEC-related libraries can your account see?")
    try:
        libs = sorted(db.list_libraries())
    except Exception:  # noqa: BLE001
        libs = sorted(db.insp.get_schema_names())
    sec = [lib for lib in libs if SEC_LIB(lib)]
    print(f"  {len(libs)} libraries visible in total.")
    print(f"  SEC-related: {sec or 'none'}")
    for lib in sec:
        try:
            tables = sorted(db.list_tables(library=lib))
            print(f"\n  {lib}: {len(tables)} tables")
            for i in range(0, len(tables), 4):
                print("    " + "   ".join(f"{t:<28s}" for t in tables[i:i + 4]))
        except Exception as e:  # noqa: BLE001
            print(f"  {lib}: listed, but tables not accessible ({type(e).__name__})")
    return sec


def check_similarity(db) -> pd.DataFrame:
    section("2. Ready-made similarity scores anywhere your account can read?")
    sql_cols = f"""
        SELECT n.nspname AS library, c.relname AS table_name, a.attname AS column_name
        FROM pg_catalog.pg_attribute a
        JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE a.attnum > 0 AND NOT a.attisdropped
          AND c.relkind IN ('r', 'v', 'm', 'f', 'p')
          AND has_schema_privilege(n.oid, 'USAGE')
          AND (a.attname ~* '{SIM_COLS}' OR c.relname ~* '{SIM_TABLES}')
        ORDER BY 1, 2, 3
    """
    hits = run(db, sql_cols)
    if hits is None:   # fall back to the slower, standard view
        hits = run(db, f"""
            SELECT table_schema AS library, table_name, column_name
            FROM information_schema.columns
            WHERE column_name ~* '{SIM_COLS}' OR table_name ~* '{SIM_TABLES}'
            ORDER BY 1, 2, 3
        """)
    if hits is None or hits.empty:
        print("  None found through this connection.")
        return pd.DataFrame(columns=["library", "table_name", "column_name"])

    groups = list(hits.groupby(["library", "table_name"]))
    # SEC libraries first (other vendors use "similar" for unrelated things, e.g. PitchBook's
    # similar companies), then tables with similarity-looking columns
    groups.sort(key=lambda kv: (not SEC_LIB(kv[0][0]),
                                not any(IS_SIM(c) for c in kv[1]["column_name"])))
    if len(groups) > MAX_TABLES:
        print(f"  {len(groups)} tables matched; details for the first {MAX_TABLES}. Others:")
        print("    " + ", ".join(f"{a}.{b}" for (a, b), _ in groups[MAX_TABLES:]))
    for (lib, tbl), g in groups[:MAX_TABLES]:
        sim = [c for c in g["column_name"] if IS_SIM(c)]
        print(f"\n  {lib}.{tbl}")
        cols = columns_of(db, lib, tbl)
        print(f"    all columns ({len(cols)}): {', '.join(cols)}")
        print(f"    similarity-looking columns: {sim or 'none (table name matched)'}")
        if not sim:
            continue
        datecol = pick(cols, "fdate", "filing_date", "date_filed", "rdate", "date")
        if datecol:
            cov = run(db, f"SELECT MIN({datecol}) AS first, MAX({datecol}) AS last FROM {lib}.{tbl}")
            if cov is not None:
                print(f"    coverage of {datecol}: {cov.iloc[0, 0]} to {cov.iloc[0, 1]}")
        cikcol = pick(cols, "cik")
        if cikcol:
            show = [c for c in cols if c in ID_COLS or c.startswith(("prev", "lag", "comp"))] + sim
            show = list(dict.fromkeys(show))[:14]
            order = f" ORDER BY {datecol} DESC" if datecol else ""
            ex = run(db, f"SELECT {', '.join(show)} FROM {lib}.{tbl} "
                         f"WHERE {cik_filter(cikcol)}{order} LIMIT 8")
            if ex is not None:
                print(f"    Apple (CIK {EXAMPLE_CIK}), latest rows:")
                print("    " + ex.to_string(index=False).replace("\n", "\n    "))
    return hits


def check_filings(db) -> None:
    section("3. List of 10-K / 10-Q filings, and the CIK-to-gvkey link")
    cols = columns_of(db, "wrdssec", "wrds_forms")
    if not cols:
        print("  wrdssec.wrds_forms not readable; we would use comp.co_filedate or the EDGAR index.")
    else:
        print(f"  wrdssec.wrds_forms columns: {', '.join(cols)}")
        formcol = pick(cols, "form", "form_type", "formtype")
        datecol = pick(cols, "fdate", "filing_date", "date_filed", "rdate")
        timecol = next((c for c in cols if "time" in c or "accept" in c), None)
        print(f"  form column: {formcol}; filing-date column: {datecol}; time column: {timecol}")
        if formcol and datecol:
            forms = ", ".join(f"'{f}'" for f in FORMS)
            n = run(db, f"""
                SELECT EXTRACT(YEAR FROM {datecol})::int AS year, {formcol} AS form, COUNT(*) AS n
                FROM wrdssec.wrds_forms
                WHERE {formcol} IN ({forms})
                GROUP BY 1, 2 ORDER BY 1, 2
            """)
            if n is not None and not n.empty:
                n["form"] = n["form"].astype(str).str.upper().str[:4]   # 10-K405, 10-KSB -> 10-K
                tab = n.groupby(["year", "form"])["n"].sum().unstack(fill_value=0)
                print("\n  10-K and 10-Q filings per year (all variants combined):")
                print("  " + tab.to_string().replace("\n", "\n  "))
            cikcol = pick(cols, "cik")
            if cikcol:
                show = [c for c in cols if c in ID_COLS or c == timecol][:12]
                ex = run(db, f"""
                    SELECT {', '.join(show)} FROM wrdssec.wrds_forms
                    WHERE {cik_filter(cikcol)} AND {formcol} IN ({forms})
                    ORDER BY {datecol} DESC LIMIT 6
                """)
                if ex is not None:
                    print("\n  Apple, latest 10-K / 10-Q rows:")
                    print("  " + ex.to_string(index=False).replace("\n", "\n  "))

    lcols = columns_of(db, "wrdssec", "wciklink_gvkey")
    if lcols:
        print(f"\n  wrdssec.wciklink_gvkey columns: {', '.join(lcols)}")
        cikcol = pick(lcols, "cik")
        if cikcol:
            ex = run(db, f"SELECT {', '.join(lcols[:10])} FROM wrdssec.wciklink_gvkey "
                         f"WHERE {cik_filter(cikcol)} LIMIT 5")
            if ex is not None:
                print("  Apple rows:")
                print("  " + ex.to_string(index=False).replace("\n", "\n  "))
    else:
        print("  wrdssec.wciklink_gvkey not readable; comp.company has a (current-only) cik instead.")


def check_co_filedate(db) -> None:
    section("4. Compustat filing dates: 10-Q as well as 10-K? With times?")
    s = run(db, """
        SELECT srctype, COUNT(*) AS n, MIN(filedate) AS first, MAX(filedate) AS last,
               AVG(CASE WHEN filedatetime IS NULL THEN 0.0 ELSE 1.0 END) AS share_with_time
        FROM comp.co_filedate
        GROUP BY srctype ORDER BY n DESC LIMIT 25
    """)
    if s is not None:
        s["share_with_time"] = pd.to_numeric(s["share_with_time"]).map("{:.0%}".format)
        print("  " + s.to_string(index=False).replace("\n", "\n  "))


def verdict(sim_hits: pd.DataFrame, sec_libs: list[str]) -> None:
    section("Summary")
    tables = sorted({f"{a}.{b}" for a, b, c in sim_hits.itertuples(index=False)
                     if SEC_LIB(a) and (IS_SIM(str(c)) or IS_SIM(b))})
    if tables:
        print(f"  Ready-made similarity columns found in: {', '.join(tables)}")
        print("  -> Case 1 (download) looks possible. Next we check what each filing is")
        print("     compared with (the paper compares with the SAME filing a year earlier).")
    elif sec_libs:
        print("  SEC libraries are visible, but no similarity scores through this connection.")
        print("  They may still exist as a WRDS web query (Analytics > SEC > Bag of Words)")
        print("  or as files on the WRDS server. Otherwise -> Case 2 (build from text).")
    else:
        print("  No SEC Analytics libraries visible -> Case 2 (build from text),")
        print("  using filing dates from comp.co_filedate.")
    print("\n  Reply 'done' in the chat; Claude will read data/lazy_prices/probe_output.txt.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Read-only WRDS check for the lazy_prices signal.")
    ap.add_argument("--user", required=True, help="your WRDS username")
    a = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    print("Connecting to WRDS. Type your password at the prompt; approve Duo if asked.")
    db = wrds.Connection(wrds_username=a.user)   # connect before logging, so nothing about login is saved

    with open(LOG, "w", encoding="utf-8") as f:
        sys.stdout = Tee(sys.__stdout__, f)
        try:
            print(f"lazy_prices WRDS probe, {pd.Timestamp.now():%Y-%m-%d %H:%M}")
            sec = check_libraries(db)
            sim = check_similarity(db)
            check_filings(db)
            check_co_filedate(db)
            verdict(sim, sec)
        finally:
            sys.stdout = sys.__stdout__
            db.close()
    print(f"\nSaved: {LOG.relative_to(REPO)}")


if __name__ == "__main__":
    main()
