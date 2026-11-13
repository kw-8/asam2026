"""
pull_filedates.py
=================
Step 7 (Pull), part 2, for signals/capex_intensity.

Downloads, read-only, the filing dates Compustat records for each fiscal period
(comp.co_filedate: one row per gvkey x datadate x source document, with the
filing date and, where known, the time of day as text, which appears to be UTC:
NVIDIA's 4:20 p.m. ET releases show as 21:20 in winter and 20:20 in summer).
Step 6 chose the 10-K date as the "published" date for capex.

Saves data/capex_intensity/co_filedate.parquet and prints checks we need before
Step 8: which source-document types exist, how far back 10-K dates go, how many
of our capex rows get an exact date, and a few known filings to eyeball.

Run from the repo root, with the .venv active (after pull_compustat.py):
    python signals\\capex_intensity\\pull_filedates.py --user YOUR_WRDS_USERNAME
"""
from __future__ import annotations

import argparse

import pandas as pd
import wrds

from pull_compustat import OUT, START, query, save

FILEDATE_SQL = f"""
SELECT gvkey, datadate, srctype, filedate,
       CAST(filedatetime AS text) AS filetime_utc
FROM comp.co_filedate
WHERE consol = 'C' AND popsrc = 'D'
  AND datadate >= '{START}'
"""

CHECK_NAMES = ["MICROSOFT CORP", "NVIDIA CORP"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--user", required=True, help="your WRDS username")
    a = ap.parse_args()

    print("Connecting to WRDS. Type your password at the prompt; approve Duo if asked.")
    db = wrds.Connection(wrds_username=a.user)
    try:
        print("\nCompustat filing dates (comp.co_filedate) ...")
        fd = query(db, FILEDATE_SQL, date_cols=["datadate", "filedate"])
    finally:
        db.close()
    save(fd, "co_filedate")

    print("\n--- Source-document types (srctype), most common first ---")
    print(fd["srctype"].value_counts(dropna=False).head(20).to_string())

    is10k = fd["srctype"].astype(str).str.upper().str.replace("-", "").str.startswith("10K")
    k = fd[is10k].copy()
    k["decade"] = (k["datadate"].dt.year // 10) * 10
    print("\n--- 10-K-type rows by decade of fiscal year-end ---")
    print(k.groupby("decade").agg(rows=("gvkey", "size"),
                                  with_time=("filetime_utc", lambda s: s.notna().mean()))
           .to_string(float_format=lambda x: f"{x:.0%}"))

    funda = pd.read_parquet(OUT / "funda_raw.parquet")
    funda = funda[funda["capx"].notna() & funda["sale"].notna()]
    first10k = k.groupby(["gvkey", "datadate"], as_index=False)["filedate"].min()
    m = funda.merge(first10k, on=["gvkey", "datadate"], how="left")
    m["decade"] = (m["datadate"].dt.year // 10) * 10
    print("\n--- Share of capex+sales rows that get an exact 10-K date ---")
    print(m.groupby("decade")["filedate"].apply(lambda s: s.notna().mean())
           .to_string(float_format=lambda x: f"{x:.0%}"))

    company = pd.read_parquet(OUT / "company.parquet")
    gv = company.loc[company["conm"].isin(CHECK_NAMES), ["gvkey", "conm"]]
    chk = (fd.merge(gv, on="gvkey")
             .query("datadate >= '2023-01-01'")
             .sort_values(["conm", "datadate", "filedate"]))
    print("\n--- Eyeball check (recent filings) ---")
    print(chk[["conm", "datadate", "srctype", "filedate", "filetime_utc"]].to_string(index=False))
    print("\nDone. Reply 'done' in the chat and I'll check the output.")


if __name__ == "__main__":
    main()
