"""
pull_compustat_noa.py
=====================
Step 7 (Pull) of prompts/data_acquisition.md for signals/net_operating_assets.

Downloads, read-only, from WRDS:
  comp.funda   one row per firm (gvkey) x fiscal year-end, fiscal years ending
               1975 onward, standard filters (INDL / STD / D / C), with
     - keys and timing fields: gvkey, datadate, fyear, fyr, curcd
     - NOA (Definition A, Hirshleifer-Hou-Teoh-Zhang 2004):
           at   total assets             che   cash and short-term investments
           dlc  debt in current liabs    dltt  long-term debt
           mib  minority interest        pstk  preferred stock
           ceq  common equity
     - the parts of NOA (channel columns approved in Step 1):
           rect receivables   invt inventory   ppent net PP&E
           intan intangibles (incl. goodwill)  gdwl goodwill
           ap   accounts payable               lt   total liabilities

Reused from disk, not downloaded again:
  data/capex_intensity/co_filedate.parquet         10-K filing dates (Step 6)
  data/capex_intensity/ccm_links.parquet           CRSP-Compustat links
  data/capex_intensity/company.parquet             company names, Compustat SIC
  data/lazy_prices/trading_days.parquet            trading days 1993+
  data/rd_to_market/trading_days_pre1993.parquet   trading days 1975-1992

Saves data/net_operating_assets/funda_noa.parquet (Git ignores data/), plus a
copy of everything printed in data/net_operating_assets/pull_log.txt.

Run from the repo root, with the .venv active:
    python signals\\net_operating_assets\\pull_compustat_noa.py --user YOUR_WRDS_USERNAME

You type your WRDS password at the prompt (and approve Duo if asked).
The password never goes into this file, the chat, or anywhere else.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "net_operating_assets"
START = "1975-01-01"

NOA_ITEMS = ["at", "che", "dlc", "dltt", "mib", "pstk", "ceq"]
PART_ITEMS = ["rect", "invt", "ppent", "intan", "gdwl", "ap", "lt"]
ITEMS = NOA_ITEMS + PART_ITEMS

FUNDA_SQL = f"""
SELECT gvkey, datadate, fyear, fyr, curcd, {", ".join(ITEMS)}
FROM comp.funda
WHERE indfmt = 'INDL' AND datafmt = 'STD' AND popsrc = 'D' AND consol = 'C'
  AND datadate >= '{START}'
"""

CHECK_NAMES = ["MICROSOFT CORP", "WALMART INC", "BOEING CO"]


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
    signals/capex_intensity/pull_compustat.py and rd_to_market).

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


def preview_noa(f: pd.DataFrame) -> pd.DataFrame:
    """Definition A on the raw pull, only to see the pull is sane (Step 8 builds
    the real thing with publish dates). Previous fiscal year = the firm's last
    report whose year-end is 10-14 months earlier."""
    f = f.sort_values(["gvkey", "datadate"]).copy()
    z = lambda c: f[c].fillna(0.0)   # noqa: E731  (missing = 0, as in HHTZ / OSAP)
    f["noa_raw"] = f["ceq"] + z("pstk") + z("mib") + z("dltt") + z("dlc") - z("che")
    g = f.groupby("gvkey", sort=False)
    gap = (f["datadate"] - g["datadate"].shift(1)).dt.days
    f["at_prev"] = g["at"].shift(1).where(gap.between(300, 430))
    ok = (f["at"] > 0) & f["ceq"].notna() & (f["at_prev"] > 0)
    f["noa"] = (f["noa_raw"] / f["at_prev"]).where(ok)
    f["noa_at_cur"] = (f["noa_raw"] / f["at"]).where((f["at"] > 0) & f["ceq"].notna())
    return f


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
        print("\nCompustat annual balance sheet (comp.funda) ...")
        funda = query(db, FUNDA_SQL, date_cols=["datadate"], num_cols=["fyear", "fyr"] + ITEMS)
    finally:
        db.close()
    funda["gvkey"] = funda["gvkey"].astype(str)
    funda[["fyear", "fyr"]] = funda[["fyear", "fyr"]].astype("Int64")
    path = OUT / "funda_noa.parquet"
    funda.to_parquet(path, index=False)
    print(f"  saved {path.relative_to(REPO)}  ({len(funda):,} rows)")

    # ---- quick checks, so we can see the pull looks sane (not a test of the signal) ----
    print("\n--- Summary ---")
    print(f"firms (gvkey): {funda['gvkey'].nunique():,}; firm-years: {len(funda):,}; "
          f"fiscal years {int(funda['fyear'].min())} to {int(funda['fyear'].max())}")
    dup = funda.duplicated(["gvkey", "datadate"]).sum()
    print(f"duplicate gvkey + datadate: {dup}")
    print("currencies: " + ", ".join(f"{k} {v:.1%}" for k, v in
                                     funda["curcd"].value_counts(normalize=True, dropna=False).items()))

    f = preview_noa(funda)
    f["decade"] = (f["datadate"].dt.year // 10) * 10
    gd = f.groupby("decade")
    cover = pd.DataFrame({"firm_years": gd.size()})
    cover["at>0 & ceq"] = gd.apply(lambda d: ((d["at"] > 0) & d["ceq"].notna()).mean())
    cover["noa (A)"] = gd["noa"].apply(lambda s: s.notna().mean())
    for c in ITEMS[1:]:
        if c != "ceq":
            cover[f"{c} missing"] = gd[c].apply(lambda s: s.isna().mean())
    print("\nCoverage by decade of fiscal year-end (all Compustat firms; missing items "
          "other than at/ceq count as 0 in NOA):")
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(cover.to_string(float_format=lambda x: f"{x:.1%}"))

    neg = {c: int((funda[c] < 0).sum()) for c in ITEMS}
    print("\nnegative values (expected only for ceq, sometimes ap/lt data errors): "
          + ", ".join(f"{k} {v:,}" for k, v in neg.items() if v))
    big = (funda["gdwl"] > funda["intan"] + 0.5).sum()
    print(f"goodwill larger than total intangibles (should be ~0): {big:,}")

    q = f["noa"].quantile([0.01, 0.25, 0.5, 0.75, 0.99])
    print("NOA (A) percentiles, all firm-years: " + ", ".join(f"p{int(k*100)} {v:.2f}" for k, v in q.items()))
    q = f["noa_at_cur"].quantile([0.01, 0.25, 0.5, 0.75, 0.99])
    print("NOA / this year's assets (B) percentiles: " + ", ".join(f"p{int(k*100)} {v:.2f}" for k, v in q.items()))

    company = pd.read_parquet(REPO / "data" / "capex_intensity" / "company.parquet")
    company["gvkey"] = company["gvkey"].astype(str)
    chk = (f.merge(company[["gvkey", "conm"]], on="gvkey")
             .loc[lambda d: d["conm"].str.upper().isin(CHECK_NAMES)]
             .query("fyear >= 2021")
             .sort_values(["conm", "fyear"]))
    print("\nSpot-check ($ millions; compare with their 10-K balance sheets):")
    cols = ["conm", "fyear", "datadate", "at", "che", "dlc", "dltt", "mib", "pstk", "ceq", "noa", "noa_at_cur"]
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(chk[cols].to_string(index=False, float_format=lambda x: f"{x:,.2f}" if abs(x) < 10 else f"{x:,.0f}"))
    print("\nDone. Reply 'done' in the chat and I'll check the files.")


if __name__ == "__main__":
    main()
