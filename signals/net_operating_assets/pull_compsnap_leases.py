"""
pull_compsnap_leases.py
=======================
Step 7, Part 2c (Pull) of prompts/data_acquisition.md for signals/net_operating_assets.

Part 2b (pull_nci_find_leases.py) found the operating-lease items in the
Compustat Snapshot library `compsnap` (your account has access), table
wrds_csa_restated: annual, keyed gvkey + datadate, with the standard filter
columns. "restated" = the same current (restated) values as comp.funda, so the
items line up with funda_noa.parquet.

Downloads, read-only, fiscal years ending 2015 on (ASC 842 starts in 2019):
  llc     operating-lease liabilities, current
  lllt    operating-lease liabilities, long-term
  rouant  operating-lease right-of-use asset, net (for checks)

Saves data/net_operating_assets/funda_leases.parquet and pull_compsnap_log.txt.

Run from the repo root, with the .venv active:
    python signals\\net_operating_assets\\pull_compsnap_leases.py --user YOUR_WRDS_USERNAME
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "net_operating_assets"
TABLE = "compsnap.wrds_csa_restated"
START = "2015-01-01"
ITEMS = ["llc", "lllt", "rouant"]

PROBE_SQL = f"SELECT gvkey, datadate FROM {TABLE} LIMIT 1"
LEASE_SQL = f"""
SELECT gvkey, datadate, fyear, {", ".join(ITEMS)}
FROM {TABLE}
WHERE indfmt = 'INDL' AND datafmt = 'STD' AND popsrc = 'D' AND consol = 'C'
  AND datadate >= '{START}'
"""
CHECK = ["WALMART INC", "MCDONALD'S CORP", "MICROSOFT CORP"]


class Tee:
    """Print to the screen and to the log at the same time."""
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
    """Same cursor workaround as the other pull scripts."""
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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--user", required=True, help="your WRDS username")
    a = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    sys.stdout = Tee(OUT / "pull_compsnap_log.txt")
    import wrds

    print("Connecting to WRDS. Type your password at the prompt; approve Duo if asked.")
    db = wrds.Connection(wrds_username=a.user)
    try:
        print(f"\n1/2 Can this account read {TABLE}?")
        try:
            query(db, PROBE_SQL)
            print("  yes")
        except Exception as e:  # noqa: BLE001
            print(f"  no ({str(e).strip().splitlines()[0][:100]})")
            print("Nothing downloaded. Reply in the chat with this log: leases then become a known limitation.")
            return
        print(f"\n2/2 Operating-lease items from {TABLE} (standard filters, fiscal years ending {START[:4]} on) ...")
        lease = query(db, LEASE_SQL, date_cols=["datadate"], num_cols=["fyear"] + ITEMS)
    finally:
        db.close()
    lease["gvkey"] = lease["gvkey"].astype(str)
    lease["fyear"] = lease["fyear"].astype("Int64")
    dup = lease.duplicated(["gvkey", "datadate"], keep=False)
    path = OUT / "funda_leases.parquet"
    lease.to_parquet(path, index=False)
    print(f"  saved {path.relative_to(REPO)}  ({len(lease):,} rows; rows sharing a gvkey + datadate: {dup.sum():,})")
    if dup.any():
        print("  example of a repeated firm-year (we'll decide in Step 8 which to keep):")
        print(lease[dup].sort_values(["gvkey", "datadate"]).head(6).to_string(index=False))

    # ---- checks (not a test of the signal) ----
    f = pd.read_parquet(OUT / "funda_noa.parquet")
    f["gvkey"] = f["gvkey"].astype(str)
    f["datadate"] = pd.to_datetime(f["datadate"]).astype("datetime64[ns]")
    lease["datadate"] = lease["datadate"].astype("datetime64[ns]")
    one = lease.drop_duplicates(["gvkey", "datadate"], keep="last")
    f = f[(f["at"] > 0) & f["ceq"].notna() & (f["datadate"] >= START)].copy()
    m = f.merge(one[["gvkey", "datadate"] + ITEMS], on=["gvkey", "datadate"], how="left", indicator=True)
    m["yr"] = m["datadate"].dt.year
    print(f"\nfunda_noa firm-years since {START[:4]} (at > 0 and ceq) found in {TABLE}: "
          f"{(m['_merge'] == 'both').mean():.1%} of {len(m):,}")
    print("\nShare with each item present, by fiscal year-end:")
    print(m.groupby("yr")[ITEMS].agg(lambda s: s.notna().mean()).to_string(float_format=lambda x: f"{x:.0%}"))

    m["lease_liab"] = m[["llc", "lllt"]].sum(axis=1, min_count=1)
    m["debt"] = m["dlc"].fillna(0.0) + m["dltt"].fillna(0.0)
    post = m[(m["yr"] >= 2020) & (m["lease_liab"] > 0)]
    over = post["lease_liab"] > post["debt"] + 1
    print(f"\nfiscal 2020+, firms with lease liabilities: lease liabilities larger than Compustat debt in "
          f"{over.mean():.1%} of {len(post):,} firm-years (should be ~0 if Compustat put leases inside dlc/dltt)")
    lr = post["rouant"] / post["lease_liab"]
    print(f"right-of-use asset / lease liability: median {lr.median():.2f} (p10 {lr.quantile(0.1):.2f}, "
          f"p90 {lr.quantile(0.9):.2f}) — close to 1 is expected")

    co = pd.read_parquet(REPO / "data" / "capex_intensity" / "company.parquet")
    co["gvkey"] = co["gvkey"].astype(str)
    s = m.merge(co[["gvkey", "conm", "sic"]], on="gvkey", how="left")
    chk = s[s["conm"].isin(CHECK) & s["fyear"].between(2017, 2025)].sort_values(["conm", "fyear"])
    print("\nSpot-check ($ millions). Walmart FY2025 10-K (datadate 2025-01-31): operating leases due within "
          "one year 1,499, long-term 12,825:")
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(chk[["conm", "fyear", "datadate", "at", "dlc", "dltt"] + ITEMS]
              .to_string(index=False, float_format=lambda x: f"{x:,.0f}"))

    s["sic2"] = pd.to_numeric(s["sic"], errors="coerce") // 100
    s["debt_at"] = s["debt"] / s["at"]
    s["debt_ex_at"] = (s["debt"] - s["lease_liab"].fillna(0.0)) / s["at"]
    s = s.sort_values(["gvkey", "datadate"])
    g = s.groupby("gvkey")
    s["d1"] = g["debt_at"].diff()
    s["d2"] = g["debt_ex_at"].diff()
    retail = s["sic2"].between(53, 59)
    t = pd.DataFrame({"retail: debt/at": s[retail].groupby("fyear")["d1"].median(),
                      "retail: (debt - op. leases)/at": s[retail].groupby("fyear")["d2"].median(),
                      "others: debt/at": s[~retail].groupby("fyear")["d1"].median(),
                      "others: (debt - op. leases)/at": s[~retail].groupby("fyear")["d2"].median()}).loc[2016:2024]
    print("\nMedian change from the previous fiscal year (the 2019 jump should go away once leases are taken out):")
    print(t.to_string(float_format=lambda x: f"{x:+.3f}"))
    print("\nDone. Reply 'done' in the chat and I'll check the files.")


if __name__ == "__main__":
    main()
