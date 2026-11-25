"""
pull_compustat_payout.py
========================
Step 7 (Pull) of prompts/data_acquisition.md for signals/shareholder_yield.

Downloads, read-only, from WRDS:
  comp.funda   one row per firm (gvkey) x fiscal year-end, fiscal years ending
               1975 onward, standard filters (INDL / STD / D / C), with
     - keys and timing fields: gvkey, datadate, fyear, fyr, curcd
     - payout items (Definition A, Boudoukh, Michaely, Richardson & Roberts 2007):
           dvc     common dividends declared            (Compustat item 21)
           prstkc  purchase of common and preferred stock (item 115, cash-flow statement)
           sstk    sale of common and preferred stock     (item 108, cash-flow statement)
           pstkrv  preferred stock, redemption value      (item 56, balance sheet)
     - flag: ceq (common equity; for the ceq <= 0 flag, not a filter)

Reused from disk, not downloaded again (Steps 6 and 8):
  data/capex_intensity/co_filedate.parquet         10-K filing dates
  data/capex_intensity/ccm_links.parquet           CRSP-Compustat links
  data/capex_intensity/company.parquet             company names, Compustat SIC
  data/issuance_insider/crsp_monthly.parquet       permco, to add up share classes
  data/lazy_prices/trading_days.parquet            trading days 1993+
  data/rd_to_market/trading_days_pre1993.parquet   trading days 1975-1992
  data/rd_to_market/exrt_mth.parquet               exchange rates (non-USD reporters)

Saves data/shareholder_yield/funda_payout.parquet (Git ignores data/), plus a
copy of everything printed in data/shareholder_yield/pull_log.txt.

Run from the repo root, with the .venv active:
    python signals\\shareholder_yield\\pull_compustat_payout.py --user YOUR_WRDS_USERNAME

You type your WRDS password at the prompt (and approve Duo if asked).
The password never goes into this file, the chat, or anywhere else.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "shareholder_yield"
START = "1975-01-01"

PAYOUT_ITEMS = ["dvc", "prstkc", "sstk", "pstkrv"]
FLAG_ITEMS = ["ceq"]
ITEMS = PAYOUT_ITEMS + FLAG_ITEMS

FUNDA_SQL = f"""
SELECT gvkey, datadate, fyear, fyr, curcd, {", ".join(ITEMS)}
FROM comp.funda
WHERE indfmt = 'INDL' AND datafmt = 'STD' AND popsrc = 'D' AND consol = 'C'
  AND datadate >= '{START}'
"""

# Spot-check firms by gvkey (names change; gvkeys don't): big buybacks (Apple,
# Microsoft), dividends + buybacks (ExxonMobil), an issuer with no dividends
# (Tesla), and a bank with preferred stock (Bank of America: preferred adjustment
# and the financial flag).
CHECK_GVKEYS = {"001690": "Apple", "012141": "Microsoft", "004503": "ExxonMobil",
                "184996": "Tesla", "007647": "Bank of America"}


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
    signals/net_operating_assets/pull_compustat_noa.py).

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


def pull(db) -> pd.DataFrame:
    """The one WRDS query, typed as the rest of the team's pulls."""
    funda = query(db, FUNDA_SQL, date_cols=["datadate"], num_cols=["fyear", "fyr"] + ITEMS)
    funda["gvkey"] = funda["gvkey"].astype(str)
    funda[["fyear", "fyr"]] = funda[["fyear", "fyr"]].astype("Int64")
    return funda


def preview_payout(f: pd.DataFrame) -> pd.DataFrame:
    """Definition A's numerators on the raw pull, only to see the pull is sane
    (Step 8 builds the real thing with publish dates and market cap).
    Previous fiscal year = the firm's last report whose year-end is 10-14 months
    earlier (same rule as NOA). A missing preferred-stock change counts as 0 (as OSAP);
    a missing dvc, prstkc or sstk leaves the payout missing (Step 4b, setting 4)."""
    f = f.sort_values(["gvkey", "datadate"]).copy()
    g = f.groupby("gvkey", sort=False)
    gap = (f["datadate"] - g["datadate"].shift(1)).dt.days
    f["pstkrv_prev"] = g["pstkrv"].shift(1).where(gap.between(300, 430))
    chg = f["pstkrv"] - f["pstkrv_prev"]
    f["pref_down"] = (-chg).clip(lower=0).fillna(0.0)
    f["pref_up"] = chg.clip(lower=0).fillna(0.0)
    f["gross_payout"] = f["dvc"] + f["prstkc"] + f["pref_down"]
    f["issuance"] = f["sstk"] - f["pref_up"]
    f["net_payout"] = f["gross_payout"] - f["issuance"]
    return f


def report(funda: pd.DataFrame, company: pd.DataFrame | None) -> None:
    """Quick checks, so we can see the pull looks sane (not a test of the signal)."""
    print("\n--- Summary ---")
    print(f"firms (gvkey): {funda['gvkey'].nunique():,}; firm-years: {len(funda):,}; "
          f"fiscal years {int(funda['fyear'].min())} to {int(funda['fyear'].max())}")
    dup = funda.duplicated(["gvkey", "datadate"]).sum()
    print(f"duplicate gvkey + datadate: {dup}")
    print("currencies: " + ", ".join(f"{k} {v:.1%}" for k, v in
                                     funda["curcd"].value_counts(normalize=True, dropna=False).items()))
    future = funda["datadate"] > pd.Timestamp.today()
    print(f"fiscal year-ends in the future (should be ~0, harmless if blank): {int(future.sum())}")

    f = preview_payout(funda)
    f["decade"] = (f["datadate"].dt.year // 10) * 10
    gd = f.groupby("decade")
    cover = pd.DataFrame({"firm_years": gd.size()})
    for c in PAYOUT_ITEMS + FLAG_ITEMS:
        cover[f"{c} missing"] = gd[c].apply(lambda s: s.isna().mean())
    cover["all 3 flows"] = gd["net_payout"].apply(lambda s: s.notna().mean())
    print("\nCoverage by decade of fiscal year-end (all Compustat firms, linked or not;\n"
          "'all 3 flows' = dvc, prstkc and sstk all present, so the yields can be computed):")
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(cover.to_string(float_format=lambda x: f"{x:.1%}"))

    ok = f[f["net_payout"].notna()]
    go = ok.groupby("decade")
    shape = pd.DataFrame({
        "firm_years": go.size(),
        "pays nothing (gross = 0)": go["gross_payout"].apply(lambda s: (s == 0).mean()),
        "pays dividends": go["dvc"].apply(lambda s: (s > 0).mean()),
        "buys back": go["prstkc"].apply(lambda s: (s > 0).mean()),
        "issues": go["sstk"].apply(lambda s: (s > 0).mean()),
        "net > 0": go["net_payout"].apply(lambda s: (s > 0).mean()),
        "net = 0": go["net_payout"].apply(lambda s: (s == 0).mean()),
        "net < 0": go["net_payout"].apply(lambda s: (s < 0).mean()),
        "preferred change used": go["pstkrv_prev"].apply(lambda s: s.notna().mean()),
    })
    print("\nPayout shape where the yields can be computed (share of firm-years):")
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(shape.to_string(float_format=lambda x: f"{x:.1%}"))

    neg = {c: int((funda[c] < 0).sum()) for c in PAYOUT_ITEMS}
    print("\nnegative values (dvc, prstkc, sstk, pstkrv should all be >= 0; a few data errors are normal): "
          + ", ".join(f"{k} {v:,}" for k, v in neg.items()))
    print(f"ceq <= 0 (flag only): {int((funda['ceq'] <= 0).sum()):,} firm-years")

    if company is not None:
        chk = (f[f["gvkey"].isin(CHECK_GVKEYS)]
               .merge(company[["gvkey", "conm"]], on="gvkey", how="left")
               .query("fyear >= 2021")
               .sort_values(["gvkey", "fyear"]))
        print("\nSpot-check ($ millions; compare with each 10-K's cash-flow statement, financing section):")
        cols = ["conm", "fyear", "datadate", "curcd", "dvc", "prstkc", "sstk", "pstkrv", "pstkrv_prev",
                "gross_payout", "net_payout"]
        with pd.option_context("display.width", 250, "display.max_columns", 30):
            print(chk[cols].to_string(index=False, float_format=lambda x: f"{x:,.0f}"))
        missing = sorted(set(CHECK_GVKEYS) - set(chk["gvkey"]))
        if missing:
            print("  not found for fiscal 2021+: " + ", ".join(f"{k} ({CHECK_GVKEYS[k]})" for k in missing))
    print("\nDone. Reply 'done' in the chat and I'll check the files.")


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
        print("\nCompustat annual payout items (comp.funda) ...")
        funda = pull(db)
    finally:
        db.close()
    path = OUT / "funda_payout.parquet"
    funda.to_parquet(path, index=False)
    print(f"  saved {path.relative_to(REPO)}  ({len(funda):,} rows)")

    company_path = REPO / "data" / "capex_intensity" / "company.parquet"
    company = None
    if company_path.exists():
        company = pd.read_parquet(company_path)
        company["gvkey"] = company["gvkey"].astype(str)
    else:
        print(f"(no {company_path.relative_to(REPO)}: spot-check names skipped)")
    report(funda, company)


if __name__ == "__main__":
    main()
