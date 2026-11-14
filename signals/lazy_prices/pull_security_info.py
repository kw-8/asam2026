"""
pull_security_info.py
=====================
Small extra pull for Step 8 of prompts/data_acquisition.md (signals/lazy_prices).

The panel has no column that says whether a permno is an ETF, and the prompt
says ETFs must be marked "n/a", not dropped. CRSP's security-information
history has that (securitysubtype = 'ETF', per reference/wrds_guide.md), plus
ticker and issuer-name history that Step 9 uses to trace a ticker change.

Saves data/lazy_prices/security_info.parquet (Git ignores data/):
    permno, secinfostartdt, secinfoenddt, sharetype, securitytype,
    securitysubtype, usincflg, issuertype, primaryexch, ticker, issuernm
(only the columns the table really has; the guide marks `ticker` as VERIFY).

It also prints the type codes of a few well-known ETFs (SPY, QQQ, IWM, GLD),
which wrds_guide.md asks us to check, and the log goes to
data/lazy_prices/pull_security_info_log.txt.

Run from the repo root, with the .venv active:
    python signals\\lazy_prices\\pull_security_info.py --user YOUR_WRDS_USERNAME

You type your WRDS password at the prompt (and approve Duo if asked).
Takes about 1 minute.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import wrds

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "lazy_prices"
LOG = OUT / "pull_security_info_log.txt"

WANTED = ["permno", "secinfostartdt", "secinfoenddt", "sharetype", "securitytype",
          "securitysubtype", "usincflg", "issuertype", "primaryexch", "ticker", "issuernm"]
KNOWN_ETFS = ("SPY", "QQQ", "IWM", "GLD")

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 20)


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


def query(db, sql: str) -> pd.DataFrame:
    """Run a SELECT via the cursor (wrds' raw_sql() fails with this repo's
    pandas 3.x + wrds 3.1.6 + SQLAlchemy 1.4)."""
    conn = db.connection.connection
    cur = conn.cursor()
    try:
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def show(df: pd.DataFrame) -> None:
    print("    " + df.to_string(index=False).replace("\n", "\n    "))


def main() -> None:
    ap = argparse.ArgumentParser(description="Pull CRSP security types (ETF flag) for lazy_prices.")
    ap.add_argument("--user", required=True, help="your WRDS username")
    a = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    print("Connecting to WRDS. Type your password at the prompt; approve Duo if asked.")
    db = wrds.Connection(wrds_username=a.user)   # connect before logging, so nothing about login is saved

    with open(LOG, "w", encoding="utf-8") as f:
        sys.stdout = Tee(sys.__stdout__, f)
        try:
            print(f"lazy_prices security-type pull, {pd.Timestamp.now():%Y-%m-%d %H:%M}")
            have = [str(c).lower() for c in
                    db.describe_table(library="crsp", table="stksecurityinfohist")["name"]]
            cols = [c for c in WANTED if c in have]
            missing = [c for c in WANTED if c not in have]
            print(f"  columns pulled: {', '.join(cols)}")
            if missing:
                print(f"  not in the table (skipped): {', '.join(missing)}")
            if "securitysubtype" not in cols:
                raise RuntimeError("crsp.stksecurityinfohist has no securitysubtype column; "
                                   "cannot flag ETFs. Show this message to Claude.")

            info = query(db, f"SELECT {', '.join(cols)} FROM crsp.stksecurityinfohist")
            for c in ("secinfostartdt", "secinfoenddt"):
                info[c] = pd.to_datetime(info[c], errors="coerce")
            info["permno"] = pd.to_numeric(info["permno"]).astype("int64")
            path = OUT / "security_info.parquet"
            info.to_parquet(path, index=False)
            print(f"  saved {path.relative_to(REPO)}  ({len(info):,} rows, {info['permno'].nunique():,} permnos)")

            print("\n  Rows by security type and subtype:")
            show(info.groupby(["securitytype", "securitysubtype"], dropna=False).size()
                     .reset_index(name="rows").sort_values("rows", ascending=False).head(25))

            if "ticker" in cols:
                etf = info[info["ticker"].isin(KNOWN_ETFS)].sort_values(["ticker", "secinfoenddt"])
                etf = etf.groupby("ticker").tail(1)
                show_cols = [c for c in ["ticker", "permno", "issuernm", "sharetype", "securitytype",
                                         "securitysubtype", "issuertype", "secinfostartdt", "secinfoenddt"]
                             if c in etf.columns]
                print(f"\n  Latest record of {', '.join(KNOWN_ETFS)} (check: securitysubtype should be ETF):")
                show(etf[show_cols])

            panel = REPO / "data" / "crsp_monthly_ratios_clean.parquet"
            if panel.exists():
                p = pd.read_parquet(panel, columns=["permno"])["permno"].astype("int64").unique()
                etf_permnos = set(info.loc[info["securitysubtype"] == "ETF", "permno"])
                in_panel = len(etf_permnos & set(p))
                print(f"\n  permnos ever flagged ETF: {len(etf_permnos):,}; of these in the panel: {in_panel:,}")
            print("\nDone. Next: python signals\\lazy_prices\\build_lazy_prices.py (no password needed).")
        finally:
            sys.stdout = sys.__stdout__
            db.close()
    print(f"\nSaved: {LOG.relative_to(REPO)}")


if __name__ == "__main__":
    main()
