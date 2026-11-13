"""
pull_compustat.py
=================
Step 7 (Pull) of prompts/data_acquisition.md for signals/capex_intensity.

Downloads, read-only, from WRDS:
  1. comp.funda      annual capex, sales, book equity (+ assets, PP&E for the
                     Step 9 cross-check), standard filters, fiscal years ending
                     1975 onward (3 prior years + lag before the panel starts in 1980)
  2. comp.company    company names, CIK and SIC (for spot-checks and for linking
                     to SEC filing dates)
  3. crsp.ccmxpf_lnkhist   CRSP-Compustat links, research-quality and primary only
Then it looks for a table with 10-K filing dates (Step 6, Option 1) and prints
what it finds, so we can pick the right one before pulling it.

Everything is saved under data/capex_intensity/ (Git ignores data/).

Run from the repo root, with the .venv active:
    python signals\\capex_intensity\\pull_compustat.py --user YOUR_WRDS_USERNAME

You type your WRDS password at the prompt (and approve Duo if asked).
The password never goes into this file, the chat, or anywhere else.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import wrds

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "capex_intensity"
START = "1975-01-01"

FUNDA_SQL = f"""
SELECT gvkey, datadate, fyear, fyr, curcd,
       capx, sale, ceq, at, ppent
FROM comp.funda
WHERE indfmt = 'INDL' AND datafmt = 'STD' AND popsrc = 'D' AND consol = 'C'
  AND datadate >= '{START}'
"""

COMPANY_SQL = """
SELECT gvkey, conm, cik, sic, fic
FROM comp.company
"""

CCM_SQL = """
SELECT gvkey, lpermno AS permno, lpermco AS permco,
       linktype, linkprim, linkdt, linkenddt
FROM crsp.ccmxpf_lnkhist
WHERE linktype IN ('LU', 'LC') AND linkprim IN ('P', 'C')
"""

AI_NAMES = ["NVIDIA CORP", "MICROSOFT CORP", "ALPHABET INC",
            "AMAZON.COM INC", "META PLATFORMS INC"]


def query(db, sql: str, date_cols=(), num_cols=()) -> pd.DataFrame:
    """Run a SELECT and return a DataFrame.

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


def save(df: pd.DataFrame, name: str) -> None:
    path = OUT / f"{name}.parquet"
    df.to_parquet(path, index=False)
    print(f"  saved {path.relative_to(REPO)}  ({len(df):,} rows)")


def find_filing_date_tables(db) -> None:
    """Print where 10-K filing dates might live. Read-only; changes nothing."""
    print("\n--- Looking for 10-K filing dates (Step 6, Option 1) ---")
    try:
        comp_tables = db.list_tables(library="comp")
        hits = [t for t in comp_tables if "file" in t or "filing" in t]
        print("comp tables with 'file' in the name:", hits or "none")
        for t in hits:
            cols = db.describe_table("comp", t)
            print(f"  comp.{t} columns:", list(cols["name"]))
    except Exception as e:  # noqa: BLE001
        print("  could not list comp tables:", e)

    schemas = db.insp.get_schema_names()
    sec = [s for s in schemas if "sec" in s.lower()]
    print("libraries with 'sec' in the name:", sec or "none")
    if "wrdssec" in schemas:
        try:
            tables = db.list_tables(library="wrdssec")
            cand = [t for t in tables if any(k in t for k in ("form", "link", "filing"))]
            print("  wrdssec tables (forms/links):", cand[:40])
        except Exception as e:  # noqa: BLE001
            print("  wrdssec exists but you may not have access:", e)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--user", required=True, help="your WRDS username")
    a = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    print("Connecting to WRDS. Type your password at the prompt; approve Duo if asked.")
    db = wrds.Connection(wrds_username=a.user)
    try:
        print("\n1/3 Compustat annual (comp.funda) ...")
        funda = query(db, FUNDA_SQL, date_cols=["datadate"],
                      num_cols=["fyear", "fyr", "capx", "sale", "ceq", "at", "ppent"])
        funda[["fyear", "fyr"]] = funda[["fyear", "fyr"]].astype("Int64")
        save(funda, "funda_raw")

        print("2/3 Company header (comp.company) ...")
        company = query(db, COMPANY_SQL)
        save(company, "company")

        print("3/3 CRSP-Compustat links (crsp.ccmxpf_lnkhist) ...")
        ccm = query(db, CCM_SQL, date_cols=["linkdt", "linkenddt"])
        save(ccm, "ccm_links")

        # Quick summary so we can check the pull looks sane.
        print("\n--- Summary ---")
        print(f"firms (gvkey): {funda['gvkey'].nunique():,}")
        print(f"fiscal years: {int(funda['fyear'].min())} to {int(funda['fyear'].max())}")
        both = funda["capx"].notna() & funda["sale"].notna()
        print(f"rows with both capx and sale: {both.mean():.1%}")

        ai = (funda.merge(company[["gvkey", "conm"]], on="gvkey")
                   .query("conm in @AI_NAMES and fyear >= 2021")
                   .assign(capex_to_sales=lambda d: d["capx"] / d["sale"])
                   .sort_values(["conm", "fyear"]))
        print("\nSpot-check, AI spenders ($ millions):")
        print(ai[["conm", "fyear", "datadate", "sale", "capx", "capex_to_sales"]]
              .to_string(index=False, float_format=lambda x: f"{x:,.2f}"))

        find_filing_date_tables(db)
    finally:
        db.close()
    print("\nDone. Reply 'done' in the chat and I'll check the files.")


if __name__ == "__main__":
    main()
