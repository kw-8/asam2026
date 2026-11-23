"""
pull_compustat_rd.py
====================
Step 7 (Pull) of prompts/data_acquisition.md for signals/rd_to_market.

Downloads, read-only, from WRDS:
  1. comp.funda       annual R&D expense (xrd) with the keys and timing fields
                      Step 8 needs (gvkey, datadate, fyear, fyr, curcd) plus
                      sales (sale) for Step 9 sanity checks. Standard filters,
                      fiscal years ending 1975 onward (R&D accounting was
                      standardized in 1975; the panel starts in 1980).
  2. Trading days 1975-1992 (crsp.dsi; if that table isn't available, the days
                      IBM traded, from crsp.dsf_v2). Step 6 rule: a 10-K filed
                      after the 4:00 p.m. close, or with no time, counts from the
                      next trading day. data/lazy_prices/trading_days.parquet
                      only starts in 1993.
  3. comp.exrt_mth    monthly exchange rates (small). Only used if Step 8 decides
                      to convert non-USD reporters' R&D into dollars.

Reused from disk, not downloaded again:
  data/capex_intensity/co_filedate.parquet   10-K filing dates (Step 6)
  data/capex_intensity/ccm_links.parquet     CRSP-Compustat links
  data/capex_intensity/company.parquet       company names (spot-checks)

Saves to data/rd_to_market/ (Git ignores data/), plus a copy of everything
printed in data/rd_to_market/pull_log.txt.

Run from the repo root, with the .venv active:
    python signals\\rd_to_market\\pull_compustat_rd.py --user YOUR_WRDS_USERNAME

You type your WRDS password at the prompt (and approve Duo if asked).
The password never goes into this file, the chat, or anywhere else.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "rd_to_market"
START = "1975-01-01"
CAL_END = "1993-01-31"          # overlap one month with lazy_prices/trading_days
IBM_PERMNO = 12490              # traded every NYSE day since 1926

FUNDA_SQL = f"""
SELECT gvkey, datadate, fyear, fyr, curcd, xrd, sale
FROM comp.funda
WHERE indfmt = 'INDL' AND datafmt = 'STD' AND popsrc = 'D' AND consol = 'C'
  AND datadate >= '{START}'
"""

DSI_SQL = f"""
SELECT DISTINCT caldt AS date
FROM crsp.dsi
WHERE caldt BETWEEN '{START}' AND '{CAL_END}'
"""

IBM_SQL = f"""
SELECT DISTINCT dlycaldt AS date
FROM crsp.dsf_v2
WHERE permno = {IBM_PERMNO} AND dlycaldt BETWEEN '{START}' AND '{CAL_END}'
"""

EXRT_SQL = f"""
SELECT *
FROM comp.exrt_mth
WHERE datadate >= '{START}'
"""

CHECK_NAMES = ["MICROSOFT", "INTEL CORP", "MERCK & CO"]


class Tee:
    """Print to the screen and to pull_log.txt at the same time."""
    def __init__(self, path: Path):
        self.file = open(path, "w", encoding="utf-8")
        self.screen = sys.stdout

    def write(self, text):
        self.screen.write(text)
        self.file.write(text)

    def flush(self):
        self.screen.flush()
        self.file.flush()


def query(db, sql: str, date_cols=(), num_cols=()) -> pd.DataFrame:
    """Run a SELECT and return a DataFrame (same helper as
    signals/capex_intensity/pull_compustat.py).

    Uses the database cursor directly: with this repo's requirements
    (pandas 3.x + wrds 3.1.6 + SQLAlchemy 1.4), wrds' own raw_sql() fails
    with "'Connection' object has no attribute 'cursor'".
    """
    cur = db.connection.connection.cursor()
    try:
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        df = pd.DataFrame(cur.fetchall(), columns=cols)
    finally:
        cur.close()
    for c in date_cols:
        df[c] = pd.to_datetime(df[c])
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    return df


def rollback(db) -> None:
    """After a failed query Postgres refuses the next one until we roll back."""
    try:
        db.connection.connection.rollback()
    except Exception:  # noqa: BLE001
        pass


def save(df: pd.DataFrame, name: str) -> None:
    path = OUT / f"{name}.parquet"
    df.to_parquet(path, index=False)
    print(f"  saved {path.relative_to(REPO)}  ({len(df):,} rows)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--user", required=True, help="your WRDS username")
    a = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    sys.stdout = Tee(OUT / "pull_log.txt")
    import wrds

    print("Connecting to WRDS. Type your password at the prompt; approve Duo if asked.")
    db = wrds.Connection(wrds_username=a.user)
    try:
        print("\n1/3 Compustat annual R&D (comp.funda) ...")
        funda = query(db, FUNDA_SQL, date_cols=["datadate"],
                      num_cols=["fyear", "fyr", "xrd", "sale"])
        funda[["fyear", "fyr"]] = funda[["fyear", "fyr"]].astype("Int64")
        save(funda, "funda_rd")

        print("2/3 Trading days before 1993 ...")
        try:
            cal = query(db, DSI_SQL, date_cols=["date"])
            src = "crsp.dsi"
        except Exception as e:  # noqa: BLE001
            print(f"  crsp.dsi not available ({str(e).strip().splitlines()[0][:80]}); using IBM's trading days")
            rollback(db)
            cal = query(db, IBM_SQL, date_cols=["date"])
            src = f"crsp.dsf_v2, permno {IBM_PERMNO}"
        cal = cal.sort_values("date").reset_index(drop=True)
        print(f"  source: {src}; {cal['date'].min():%Y-%m-%d} to {cal['date'].max():%Y-%m-%d}")
        save(cal, "trading_days_pre1993")

        print("3/3 Exchange rates (comp.exrt_mth, optional) ...")
        try:
            fx = query(db, EXRT_SQL, date_cols=["datadate"])
            print(f"  columns: {list(fx.columns)}")
            save(fx, "exrt_mth")
        except Exception as e:  # noqa: BLE001
            print(f"  skipped ({str(e).strip().splitlines()[0][:80]}); Step 8 can leave non-USD R&D blank instead")
            rollback(db)
    finally:
        db.close()

    # ---- quick checks, so we can see the pull looks sane ----
    print("\n--- Summary ---")
    print(f"firms (gvkey): {funda['gvkey'].nunique():,}; firm-years: {len(funda):,}")
    print(f"fiscal years: {int(funda['fyear'].min())} to {int(funda['fyear'].max())}")
    f = funda.assign(decade=(funda["datadate"].dt.year // 10) * 10)
    status = pd.DataFrame({
        "firm_years": f.groupby("decade").size(),
        "xrd_missing": f.groupby("decade")["xrd"].apply(lambda s: s.isna().mean()),
        "xrd_zero": f.groupby("decade")["xrd"].apply(lambda s: (s == 0).mean()),
        "xrd_positive": f.groupby("decade")["xrd"].apply(lambda s: (s > 0).mean()),
        "xrd_negative": f.groupby("decade")["xrd"].apply(lambda s: (s < 0).mean()),
        "usd": f.groupby("decade")["curcd"].apply(lambda s: (s == "USD").mean()),
    })
    print("\nR&D status by decade of fiscal year-end (all Compustat firms):")
    print(status.to_string(float_format=lambda x: f"{x:.1%}"))

    company = pd.read_parquet(REPO / "data" / "capex_intensity" / "company.parquet")
    pat = "|".join(CHECK_NAMES)
    chk = (funda.merge(company[["gvkey", "conm"]], on="gvkey")
                .loc[lambda d: d["conm"].str.upper().str.contains(pat, regex=True)]
                .query("fyear >= 2020")
                .sort_values(["conm", "fyear"]))
    print("\nSpot-check, well-known R&D spenders ($ millions; compare with their 10-Ks):")
    print(chk[["conm", "gvkey", "fyear", "datadate", "curcd", "sale", "xrd"]]
          .to_string(index=False, float_format=lambda x: f"{x:,.0f}"))
    print("\nDone. Reply 'done' in the chat and I'll check the files.")


if __name__ == "__main__":
    main()
