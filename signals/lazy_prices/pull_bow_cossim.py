"""
pull_bow_cossim.py
==================
Step 7 (Pull) of prompts/data_acquisition.md for signals/lazy_prices.
Version 3 (2026-11-14): adds the English-words-only measures, see "Why version 3".
Version 2 (2026-11-14): pulls lookback 1-4, see "Why version 2" below.

Why version 3
  Step 9 found a filing-format change in 2010-2013: the median 10-K grew from
  ~53,000 to ~200,000 words, mostly non-English tokens, reaching the largest
  firms first. `cosine` then flags big firms as "changers" for a format reason.
  WRDS also provides the same measures on English words only (`cosine_eng`,
  `jaccard_eng`, `mineditdist_eng`); Step 8 checks, without looking at
  returns, whether `cosine_eng` removes the distortion.

Decisions it follows (progress.md, approved 2026-11-13):
  - Case 1: download from wrdssec.bow_cossim (WRDS SEC Analytics, Bag of Words).
  - Definition B: 10-Ks only (no amendments); each 10-K compared with the firm's
    previous year's 10-K. The signal is `cosine`, or `cosine_eng` if Step 8's
    pre-declared size-tilt rule picks it (approved 2026-11-14). The other
    measures are pulled for data checks only, never as the signal.
  - Sample: filings up to 2024-12-31 (where bow_cossim ends).
  - Timing: SEC acceptance date + time (New York time). Applied in Step 8.

Why version 2
  Run 1 showed that `lookback` counts every earlier filing in the 10-K family,
  amendments (10-K/A) included. So for 16.5% of 10-Ks, lookback = 1 is an
  amendment, often a short partial filing. Those rows score low on cosine for
  no real reason (median 0.923 vs 0.990) and made up 47% of the bottom fifth.
  This version pulls lookback 1-4 so Step 8 can use, for each 10-K, the most
  recent ORIGINAL 10-K. It also catches the small-business forms spelled
  without a hyphen (10KSB, 10KSB40, 10KT405), which version 1 missed; the
  `form` column is kept, so Step 8 can still drop them.

Part A - check (printed only)
  A1. Which form types bow_cossim has.
Part B - pulls (saved under data/lazy_prices/, which Git ignores)
  B1. bow_cossim_10k.parquet  10-K-family rows (no amendments), lookback 1-4,
                              plus form and dates of each compared filing
  B2. ciklink.parquet         wrdssec.wciklink_gvkey (CIK -> gvkey, with dates)
  B3. ccm_links.parquet       crsp.ccmxpf_lnkhist (research-quality, primary)
  B4. trading_days.parquet    NYSE trading days, from CRSP daily data
Part C - what was pulled (printed only)
  For each 10-K, the most recent original 10-K among lookback 1-4: how often
  one exists, which lookback it is, months apart, cosine by year; Apple's rows;
  how many filers have a valid CIK-gvkey link.

Everything printed is also saved to data/lazy_prices/pull_log.txt
(earlier logs are kept as pull_log_v1.txt, pull_log_v2.txt, ...).

Run from the repo root, with the .venv active:
    python signals\\lazy_prices\\pull_bow_cossim.py --user YOUR_WRDS_USERNAME

You type your WRDS password at the prompt (and approve Duo if asked).
The password never goes into this file, the chat, or the log.
Takes about 5-15 minutes. Re-running overwrites the files.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd
import wrds

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "lazy_prices"
LOG = OUT / "pull_log.txt"


LIB = "wrdssec"
END = "2024-12-31"
APPLE_CIK = "0000320193"
LOOKBACKS = (1, 2, 3, 4)
TIMEOUT_S = 600                 # per query

# 10-K family without amendments: 10-K, 10-K405, 10-KT, 10KSB, 10KSB40, 10KT405 ... not 10-K/A
TENK = "form ~ '^10-?K' AND POSITION('/A' IN form) = 0"
LB = ", ".join(str(k) for k in LOOKBACKS)

SQL_A1 = f"""
    SELECT sample, form, COUNT(*) AS n, MIN(fdate) AS first, MAX(fdate) AS last
    FROM {LIB}.bow_cossim
    WHERE lookback = 1
    GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 30
"""

SQL_B1 = f"""
    SELECT sample, form, cik, coname, accession, CAST(lookback AS INTEGER) AS lookback, accession2,
           fdate, rdate, secadate, CAST(secatime AS TEXT) AS secatime,
           wcnt, engwcnt, cosine, jaccard, mineditdist,
           cosine_eng, jaccard_eng, mineditdist_eng
    FROM {LIB}.bow_cossim
    WHERE lookback IN ({LB}) AND {TENK} AND fdate <= '{END}'
"""

SQL_B1_PREV = f"""
    SELECT cik, accession AS accession2, form AS form_prev, fdate AS fdate_prev, rdate AS rdate_prev
    FROM {LIB}.wrds_forms
    WHERE accession IN (SELECT accession2 FROM {LIB}.bow_cossim
                        WHERE lookback IN ({LB}) AND {TENK} AND fdate <= '{END}')
"""

SQL_B2 = f"""
    SELECT cik, gvkey, source, link_desc,
           sec_start_date, sec_end_date, link_start_date, link_end_date, n10k, n10q
    FROM {LIB}.wciklink_gvkey
"""

SQL_B3 = """
    SELECT gvkey, lpermno AS permno, lpermco AS permco,
           linktype, linkprim, linkdt, linkenddt
    FROM crsp.ccmxpf_lnkhist
    WHERE linktype IN ('LU', 'LC') AND linkprim IN ('P', 'C')
"""

# Days on which Apple (14593) or Microsoft (10107) traded = NYSE/Nasdaq trading days.
SQL_B4 = """
    SELECT DISTINCT dlycaldt AS date
    FROM crsp.dsf_v2
    WHERE permno IN (14593, 10107) AND dlycaldt BETWEEN '1993-01-01' AND '2026-12-31'
    ORDER BY 1
"""

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 30)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
class Tee:
    """Print to the terminal and to the log file at the same time."""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            st.write(s)

    def flush(self):
        for st in self.streams:
            st.flush()


def query(db, sql: str, date_cols=(), timeout_s: int = TIMEOUT_S) -> pd.DataFrame:
    """Run a SELECT and return a DataFrame. Raises on error.

    Uses the database cursor directly: with this repo's requirements
    (pandas 3.x + wrds 3.1.6 + SQLAlchemy 1.4), wrds' own raw_sql() fails
    with "'Connection' object has no attribute 'cursor'".
    """
    conn = db.connection.connection
    cur = conn.cursor()
    try:
        try:
            cur.execute(f"SET statement_timeout = {int(timeout_s * 1000)}")
        except Exception:  # noqa: BLE001  (timeouts not allowed: run without one)
            conn.rollback()
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        df = pd.DataFrame(cur.fetchall(), columns=cols)
    except Exception:
        conn.rollback()     # a failed query blocks the next one until rollback
        raise
    finally:
        cur.close()
    for c in date_cols:
        df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


def numeric(df: pd.DataFrame, cols) -> pd.DataFrame:
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    return df


def save(df: pd.DataFrame, name: str) -> None:
    path = OUT / f"{name}.parquet"
    df.to_parquet(path, index=False)
    print(f"  saved {path.relative_to(REPO)}  ({len(df):,} rows)")


def show(df: pd.DataFrame, indent: int = 4) -> None:
    pad = " " * indent
    print(pad + df.to_string(index=False).replace("\n", "\n" + pad))


def section(title: str) -> None:
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


def step(label: str, fn):
    """Run one part; report time; on error print it and return None (other parts still run)."""
    t0 = time.time()
    print(f"\n{label} ...")
    try:
        out = fn()
        print(f"  done in {time.time() - t0:.0f}s")
        return out
    except Exception as e:  # noqa: BLE001
        msg = str(e).strip().splitlines()[0] if str(e).strip() else ""
        print(f"  FAILED after {time.time() - t0:.0f}s: {type(e).__name__}: {msg[:250]}")
        return None


# ----------------------------------------------------------------------------
# Part C: describe what was pulled
# ----------------------------------------------------------------------------
def latest_original(d: pd.DataFrame) -> pd.DataFrame:
    """For each 10-K: the row with the smallest lookback whose compared filing is an
    original 10-K-family filing (no /A). Step 8 may refine this rule; here it only
    shows what the rule gives."""
    ok = d["form_prev"].notna() & ~d["form_prev"].astype(str).str.contains("/A", regex=False)
    return (d[ok].sort_values(["cik", "accession", "lookback"])
                 .drop_duplicates(["cik", "accession"], keep="first"))


def summarize(tenk: pd.DataFrame | None, cik: pd.DataFrame | None, days: pd.DataFrame | None) -> None:
    section("C. What was pulled")
    if tenk is None or tenk.empty:
        print("  No 10-K rows; nothing to summarize.")
        return
    d = tenk.copy()
    n_filings = d[["cik", "accession"]].drop_duplicates().shape[0]
    print(f"\n  C1. Rows: {len(d):,}   10-K filings: {n_filings:,}   firms (cik): {d['cik'].nunique():,}")
    dup = d.duplicated(["cik", "accession", "lookback"], keep=False).sum()
    print(f"      duplicate (cik, accession, lookback) rows: {dup:,} (should be 0)")
    print(f"      missing cosine: {d['cosine'].isna().mean():.2%}   "
          f"cosine outside [0, 1]: {((d['cosine'] < 0) | (d['cosine'] > 1)).mean():.2%}")
    print("      rows per lookback: " + ", ".join(f"{k}: {n:,}" for k, n in d["lookback"].value_counts().sort_index().items()))
    print("\n  Form types pulled (one row per filing):")
    show(d.drop_duplicates(["cik", "accession"])["form"].value_counts().rename_axis("form").reset_index(name="n"))

    if "form_prev" not in d:
        print("\n  Compared filings could not be looked up (B1b failed); Step 8 cannot pick originals yet.")
        return
    c = latest_original(d)
    c = c.assign(months=((c["fdate"] - c["fdate_prev"]).dt.days / 30.44).round(),
                 year=c["fdate"].dt.year)
    print(f"\n  C2. 10-Ks with an ORIGINAL 10-K among lookback 1-4: {len(c):,} of {n_filings:,} "
          f"({len(c) / n_filings:.1%})")
    print("      ... at lookback: " + ", ".join(f"{k}: {n:,}" for k, n in c["lookback"].value_counts().sort_index().items()))
    lb1 = d[d["lookback"] == 1]
    amend1 = lb1["form_prev"].astype(str).str.contains("/A", regex=False)
    print(f"      (lookback 1 was an amendment for {amend1.mean():.1%} of 10-Ks; median cosine "
          f"{lb1.loc[amend1, 'cosine'].median():.3f} vs {lb1.loc[~amend1, 'cosine'].median():.3f})")
    print("      Months between a 10-K and that original 10-K:")
    mo = c["months"].clip(upper=36).value_counts().sort_index()
    show(mo[mo / mo.sum() >= 0.002].rename_axis("months").reset_index(name="n"), indent=6)
    print(f"      9-15 months: {c['months'].between(9, 15).mean():.1%}   under 9: {(c['months'] < 9).mean():.1%}   "
          f"over 15: {(c['months'] > 15).mean():.1%}")

    t = c["secatime"].astype(str).str[:8]
    has_time = c["secatime"].notna() & (t.str.len() >= 5)
    c = c.assign(has_time=has_time, after_close=has_time & (t > "16:00:00"))
    by_year = c.groupby("year").agg(
        filings=("accession", "size"),
        with_time=("has_time", "mean"),
        after_4pm=("after_close", "mean"),
        cosine_p10=("cosine", lambda s: s.quantile(0.10)),
        cosine_median=("cosine", "median"),
        cosine_p90=("cosine", lambda s: s.quantile(0.90)),
        eng_p10=("cosine_eng", lambda s: s.quantile(0.10)),
        eng_median=("cosine_eng", "median"),
    ).reset_index()
    for col in ("with_time", "after_4pm"):
        by_year[col] = by_year[col].map("{:.0%}".format)
    for col in ("cosine_p10", "cosine_median", "cosine_p90", "eng_p10", "eng_median"):
        by_year[col] = by_year[col].round(3)
    print("\n  C3. By filing year, each 10-K vs its latest original 10-K "
          "(after_4pm = accepted after 4:00 p.m. New York time):")
    show(by_year)

    print("\n  C4. Apple's latest 10-Ks (latest original comparison):")
    ap = c[c["cik"] == APPLE_CIK].sort_values("fdate", ascending=False).head(6)
    show(ap[["form", "fdate", "secadate", "secatime", "lookback", "accession", "accession2",
             "form_prev", "fdate_prev", "cosine"]])

    if cik is not None and not cik.empty:
        valid = cik[cik["link_desc"].astype(str).str.startswith("Valid")]
        any_link = cik[cik["source"].astype(str) != "No Link"]
        f = c["cik"]
        print(f"\n  C5. Of these 10-Ks, filer has a 'Valid CIK-GVKEY Link': {f.isin(set(valid['cik'])).mean():.1%}; "
              f"any link incl. name mismatch: {f.isin(set(any_link['cik'])).mean():.1%}")
    if days is not None and not days.empty:
        n = days.groupby(days["date"].dt.year).size()
        print(f"\n  C6. Trading days: {days['date'].min():%Y-%m-%d} to {days['date'].max():%Y-%m-%d}; "
              f"per full year {n.iloc[1:-1].min()}-{n.iloc[1:-1].max()} (expect ~250-253)")


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="Step 7 pull for lazy_prices (bow_cossim, 10-Ks).")
    ap.add_argument("--user", required=True, help="your WRDS username")
    a = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    if LOG.exists():                             # keep earlier logs: pull_log_v1.txt, _v2.txt, ...
        k = 1
        while (OUT / f"pull_log_v{k}.txt").exists():
            k += 1
        LOG.replace(OUT / f"pull_log_v{k}.txt")
    print("Connecting to WRDS. Type your password at the prompt; approve Duo if asked.")
    db = wrds.Connection(wrds_username=a.user)   # connect before logging, so nothing about login is saved

    with open(LOG, "w", encoding="utf-8") as f:
        sys.stdout = Tee(sys.__stdout__, f)
        try:
            print(f"lazy_prices Step 7 pull (version 3: lookback 1-4, English-only measures), {pd.Timestamp.now():%Y-%m-%d %H:%M}")

            section("A. Check")
            a1 = step("A1. Form types in bow_cossim (lookback = 1)",
                      lambda: query(db, SQL_A1, date_cols=["first", "last"]))
            if a1 is not None:
                show(a1)

            section("B. Pulls")
            tenk = step(f"B1. 10-K similarities (lookback {LB})",
                        lambda: query(db, SQL_B1, date_cols=["fdate", "rdate", "secadate"]))
            if tenk is not None:
                tenk = numeric(tenk, ["wcnt", "engwcnt", "cosine", "jaccard", "mineditdist",
                                      "cosine_eng", "jaccard_eng", "mineditdist_eng"])
                tenk["lookback"] = pd.to_numeric(tenk["lookback"]).astype("int64")
                prev = step("B1b. Form and dates of each compared filing (wrdssec.wrds_forms)",
                            lambda: query(db, SQL_B1_PREV, date_cols=["fdate_prev", "rdate_prev"]))
                if prev is not None:
                    prev = (prev.sort_values(["cik", "accession2", "fdate_prev"])
                                .drop_duplicates(["cik", "accession2"]))
                    tenk = tenk.merge(prev, on=["cik", "accession2"], how="left")
                save(tenk, "bow_cossim_10k")
            cik = step("B2. CIK-gvkey link (wrdssec.wciklink_gvkey)",
                       lambda: query(db, SQL_B2, date_cols=["sec_start_date", "sec_end_date",
                                                           "link_start_date", "link_end_date"]))
            if cik is not None:
                cik = numeric(cik, ["n10k", "n10q"])
                save(cik, "ciklink")
            ccm = step("B3. CRSP-Compustat link (crsp.ccmxpf_lnkhist)",
                       lambda: query(db, SQL_B3, date_cols=["linkdt", "linkenddt"]))
            if ccm is not None:
                ccm["permno"] = pd.to_numeric(ccm["permno"]).astype("int64")
                save(ccm, "ccm_links")
            days = step("B4. Trading days (crsp.dsf_v2)", lambda: query(db, SQL_B4, date_cols=["date"]))
            if days is not None:
                save(days, "trading_days")

            summarize(tenk, cik, days)
            failed = [n for n, x in [("B1", tenk), ("B2", cik), ("B3", ccm), ("B4", days)] if x is None]
            print("\n" + ("All pulls saved." if not failed else f"FAILED: {', '.join(failed)} (see above)."))
            print("Reply 'done' in the chat; Claude will read data/lazy_prices/pull_log.txt.")
        finally:
            sys.stdout = sys.__stdout__
            db.close()
    print(f"\nSaved: {LOG.relative_to(REPO)}")


if __name__ == "__main__":
    main()
