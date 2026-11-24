"""
pull_nci_find_leases.py
=======================
Step 7, Part 2b (Pull) of prompts/data_acquisition.md for signals/net_operating_assets.

Part 2 (pull_compustat_leases.py) found that the operating-lease items are not in
the `comp` library, while the noncontrolling-interest items are in comp.funda.
This run, read-only:
  1. downloads mibn (nonredeemable noncontrolling interest) and mibt (total) from
     comp.funda, to confirm the minority-interest fix used in `noa_adj`;
  2. searches every WRDS library you can see for the operating-lease items
     (llc, lllt, rouant, and any comp-library column starting with "ll"/"rou" or
     containing "lease"), and lists Compustat Snapshot libraries and whether you
     have access. It does not download lease data: if they turn up, we look at
     where they are first.

Saves data/net_operating_assets/funda_nci.parquet and pull_nci_log.txt.

Run from the repo root, with the .venv active:
    python signals\\net_operating_assets\\pull_nci_find_leases.py --user YOUR_WRDS_USERNAME
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "net_operating_assets"
START = "1975-01-01"

NCI_SQL = f"""
SELECT gvkey, datadate, mibn, mibt
FROM comp.funda
WHERE indfmt = 'INDL' AND datafmt = 'STD' AND popsrc = 'D' AND consol = 'C'
  AND datadate >= '{START}'
"""

LEASE_NAMES = ["llc", "lllt", "rouant", "llcur", "lltot"]
SEARCH_SQL = f"""
SELECT table_schema, table_name, column_name
FROM information_schema.columns
WHERE column_name IN ({", ".join(f"'{c}'" for c in LEASE_NAMES)})
   OR (table_schema LIKE 'comp%%'
       AND (column_name LIKE 'll%%' OR column_name LIKE 'rou%%' OR column_name LIKE '%%lease%%'))
ORDER BY table_schema, table_name, column_name
"""

SCHEMA_SQL = """
SELECT nspname AS library, has_schema_privilege(nspname, 'USAGE') AS you_have_access
FROM pg_namespace
WHERE nspname ILIKE '%snap%' OR nspname ILIKE 'comp%'
ORDER BY nspname
"""

KEYS_SQL = """
SELECT column_name
FROM information_schema.columns
WHERE table_schema = '{schema}' AND table_name = '{table}'
  AND column_name IN ('gvkey', 'datadate', 'indfmt', 'datafmt', 'popsrc', 'consol', 'fyear')
"""


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
    """Same cursor workaround as the other pull scripts (raw_sql() fails with this
    repo's pandas 3 + wrds 3.1.6). '%%' in the SQL is a literal '%'."""
    cur = db.connection.connection.cursor()
    try:
        cur.execute(sql.replace("%%", "%"))
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
    try:
        db.connection.connection.rollback()
    except Exception:  # noqa: BLE001
        pass


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--user", required=True, help="your WRDS username")
    a = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    sys.stdout = Tee(OUT / "pull_nci_log.txt")
    import wrds

    print("Connecting to WRDS. Type your password at the prompt; approve Duo if asked.")
    db = wrds.Connection(wrds_username=a.user)
    try:
        print("\n1/3 Noncontrolling interest (comp.funda mibn, mibt) ...")
        nci = query(db, NCI_SQL, date_cols=["datadate"], num_cols=["mibn", "mibt"])
        nci["gvkey"] = nci["gvkey"].astype(str)
        path = OUT / "funda_nci.parquet"
        nci.to_parquet(path, index=False)
        print(f"  saved {path.relative_to(REPO)}  ({len(nci):,} rows; duplicates "
              f"{nci.duplicated(['gvkey', 'datadate']).sum()})")

        print("\n2/3 Compustat and Snapshot libraries on WRDS:")
        try:
            libs = query(db, SCHEMA_SQL)
            print(libs.to_string(index=False) if not libs.empty else "  none found")
        except Exception as e:  # noqa: BLE001
            rollback(db)
            print(f"  could not list libraries ({str(e).strip().splitlines()[0][:80]})")

        print("\n3/3 Where are the operating-lease items? (every library you can see)")
        try:
            hits = query(db, SEARCH_SQL)
        except Exception as e:  # noqa: BLE001
            rollback(db)
            hits = pd.DataFrame(columns=["table_schema", "table_name", "column_name"])
            print(f"  search failed ({str(e).strip().splitlines()[0][:80]})")
        if hits.empty:
            print("  not found in any table you have access to")
        else:
            with pd.option_context("display.width", 200, "display.max_rows", 200):
                print(hits.to_string(index=False))
            print("\n  key columns in each table that has a lease item:")
            for (s, t), _ in hits.groupby(["table_schema", "table_name"]):
                try:
                    k = query(db, KEYS_SQL.format(schema=s, table=t))["column_name"].tolist()
                except Exception:  # noqa: BLE001
                    rollback(db)
                    k = ["?"]
                print(f"  {s}.{t}: {', '.join(sorted(k)) if k else '(no gvkey/datadate)'}")
    finally:
        db.close()

    # ---- checks on the minority-interest fix ----
    f = pd.read_parquet(OUT / "funda_noa.parquet")
    f["gvkey"] = f["gvkey"].astype(str)
    f["datadate"] = pd.to_datetime(f["datadate"]).astype("datetime64[ns]")
    nci["datadate"] = nci["datadate"].astype("datetime64[ns]")
    f = f.merge(nci, on=["gvkey", "datadate"], how="left")
    f = f[(f["at"] > 0) & f["ceq"].notna()].copy()
    f["yr"] = f["datadate"].dt.year
    f["gap"] = f["at"] - f["lt"] - f["ceq"] - f["pstk"].fillna(0.0) - f["mib"].fillna(0.0)

    print("\nShare of firm-years (at > 0 and ceq) with mibn / mibt present, by fiscal year-end:")
    print(f[f["yr"].between(2005, 2026)].groupby("yr")[["mibn", "mibt"]]
          .agg(lambda s: s.notna().mean()).to_string(float_format=lambda x: f"{x:.0%}"))

    both = f[(f["yr"] >= 2010)].dropna(subset=["lt", "mibn"])
    close = (both["gap"] - both["mibn"]).abs() <= 0.01 * both["at"]
    print(f"\nfiscal 2010+: gap (at - lt - ceq - pstk - mib) within 1% of assets of mibn: "
          f"{close.mean():.1%} of {len(both):,} firm-years")
    big = both["gap"].abs() > 0.01 * both["at"]
    print(f"  among firm-years with a gap > 1% of assets ({big.sum():,}): within 1% of mibn "
          f"{close[big].mean():.1%}")
    t = both.dropna(subset=["mibt"])
    print(f"  mibt = mib + mibn (within $1M): {((t['mibt'] - t['mib'].fillna(0) - t['mibn']).abs() <= 1).mean():.1%}")
    pre = f[f["yr"].between(2000, 2008)].dropna(subset=["lt"])
    print(f"fiscal 2000-2008: gap within 1% of assets of zero: {(pre['gap'].abs() <= 0.01 * pre['at']).mean():.1%}")

    co = pd.read_parquet(REPO / "data" / "capex_intensity" / "company.parquet")
    co["gvkey"] = co["gvkey"].astype(str)
    s = f.merge(co[["gvkey", "conm"]], on="gvkey", how="left")
    chk = s[(s["conm"] == "WALMART INC") & s["fyear"].between(2017, 2025)].sort_values("fyear")
    print("\nWalmart ($ millions; FY2025 10-K: redeemable NCI 271, nonredeemable NCI 6,408):")
    print(chk[["fyear", "datadate", "at", "lt", "ceq", "mib", "mibn", "mibt", "gap"]]
          .to_string(index=False, float_format=lambda x: f"{x:,.0f}"))
    print("\nDone. Reply 'done' in the chat and I'll check the files.")


if __name__ == "__main__":
    main()
