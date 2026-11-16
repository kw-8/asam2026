"""
probe_insiders.py
=================
Step 7, part 1 (probe) for signals/issuance_insider, signal 2: insider_cluster.
Read-only: only SELECTs, small samples. Finds where the insider-trading data sits
in YOUR WRDS subscription and what its columns look like, so the real pull can be
written against the actual names (not guessed ones).

What it checks
  P1. Libraries you can see whose names suggest insider data (LSEG / Thomson
      Reuters "Insider Filing Data", e.g. tr_insiders, tfn, ...).
  P2. In those libraries: tables, columns, approximate row counts.
  P3. The stock-transactions table ("Table 1"): a few Apple rows, and for one
      recent year the values of the transaction code, buy/sell flag, role code,
      data-quality ("cleanse") flag and form type, plus how many days pass from
      trade to filing.
  P4. CRSP CIZ security-info history: is there a CUSIP column (to link insider
      data, which is keyed by CUSIP, to permno)?
  P5. CRSP CIZ daily data: trading days 1986-1992 (we only have 1993-2025).

Everything printed is also saved to data/issuance_insider/probe_insiders_log.txt.

Run from the repo root, with the .venv active:
    python signals\\issuance_insider\\probe_insiders.py --user YOUR_WRDS_USERNAME
Type your WRDS password at the prompt (approve Duo if asked). About 2-10 minutes.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "issuance_insider"
LOG = OUT / "probe_insiders_log.txt"
TIMEOUT_S = 300

LIB_PATTERN = re.compile(r"insider|^tfn|^tr_|lseg|refinitiv|thomson|2iq|ownership", re.I)
TABLE1_PATTERN = re.compile(r"table1|^t1$|stock_?trans|nonderiv", re.I)
APPLE_CUSIP6 = "037833"
APPLE_PERMNO = 14593
CAL_PERMNO = 12490            # IBM: traded every NYSE day since well before 1986
PROBE_YEAR = 2024

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_colwidth", 40)


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            st.write(s)

    def flush(self):
        for st in self.streams:
            st.flush()


def query(db, sql: str, timeout_s: int = TIMEOUT_S) -> pd.DataFrame:
    """SELECT via the raw cursor (wrds' raw_sql fails with this repo's pandas 3 / SQLAlchemy 1.4)."""
    conn = db.connection.connection
    cur = conn.cursor()
    try:
        try:
            cur.execute(f"SET statement_timeout = {int(timeout_s * 1000)}")
        except Exception:  # noqa: BLE001
            conn.rollback()
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def show(df: pd.DataFrame, indent: int = 4) -> None:
    pad = " " * indent
    print(pad + df.to_string(index=False).replace("\n", "\n" + pad))


def section(title: str) -> None:
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


def step(label: str, fn):
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


def cols_of(db, lib: str, table: str) -> list[str]:
    return [str(c).lower() for c in db.describe_table(library=lib, table=table)["name"]]


def approx_rows(db, lib: str, table: str) -> str:
    try:
        r = query(db, f"SELECT reltuples::bigint AS n FROM pg_class c JOIN pg_namespace n "
                      f"ON n.oid = c.relnamespace WHERE n.nspname = '{lib}' AND c.relname = '{table}'", 30)
        return f"{int(r['n'].iloc[0]):,}" if len(r) and r["n"].iloc[0] is not None else "?"
    except Exception:  # noqa: BLE001
        return "?"


def pick(cols: list[str], *cands: str) -> str | None:
    for c in cands:
        if c in cols:
            return c
    return None


# ----------------------------------------------------------------------------
def find_libraries(db) -> list[str]:
    libs = sorted(str(x) for x in db.list_libraries())
    hits = [x for x in libs if LIB_PATTERN.search(x)]
    print(f"  you can see {len(libs)} libraries; names suggesting insider data: {hits or 'NONE'}")
    return hits


def list_tables(db, libs: list[str]) -> list[tuple[str, str]]:
    found = []
    for lib in libs:
        try:
            tabs = sorted(str(t) for t in db.list_tables(library=lib))
        except Exception as e:  # noqa: BLE001
            print(f"  {lib}: cannot list tables ({type(e).__name__}) - probably not in your subscription")
            continue
        print(f"  {lib}: {len(tabs)} tables: {', '.join(tabs[:40])}{' ...' if len(tabs) > 40 else ''}")
        for t in tabs:
            if TABLE1_PATTERN.search(t):
                found.append((lib, t))
    print(f"  candidate stock-transaction tables: {found or 'NONE'}")
    return found


def describe_candidates(db, cands: list[tuple[str, str]]) -> dict:
    info = {}
    for lib, t in cands:
        try:
            c = cols_of(db, lib, t)
        except Exception as e:  # noqa: BLE001
            print(f"  {lib}.{t}: cannot describe ({type(e).__name__}: {str(e)[:120]})")
            continue
        info[(lib, t)] = c
        print(f"\n  {lib}.{t}: ~{approx_rows(db, lib, t)} rows; {len(c)} columns:\n    {', '.join(c)}")
    return info


def sample_table1(db, lib: str, t: str, c: list[str]) -> None:
    cus6 = pick(c, "cusip6", "cusip_6")
    cus = pick(c, "cusip", "cusip8", "cusipx")
    trd = pick(c, "trandate", "tran_date", "transactiondate", "trade_date")
    fil = pick(c, "fdate", "filedate", "filingdate", "secdate")
    code = pick(c, "trancode", "tran_code", "transactioncode")
    acq = pick(c, "acqdisp", "acq_disp")
    role = pick(c, "rolecode1", "role1", "rolecode")
    cln = pick(c, "cleanse", "cleansecode", "cleanse_code")
    form = pick(c, "formtype", "form_type", "form")
    print(f"  using: cusip6={cus6}, cusip={cus}, trade date={trd}, filing date={fil}, code={code}, "
          f"acq/disp={acq}, role={role}, cleanse={cln}, form={form}")

    if cus6 or cus:
        where = f"{cus6} = '{APPLE_CUSIP6}'" if cus6 else f"{cus} LIKE '{APPLE_CUSIP6}%'"
        order = f" ORDER BY {trd} DESC" if trd else ""
        d = query(db, f"SELECT * FROM {lib}.{t} WHERE {where}{order} LIMIT 6")
        print(f"\n  Apple (CUSIP {APPLE_CUSIP6}), latest 6 rows:")
        show(d, indent=4)
    if not trd:
        print("  no trade-date column recognised; skipping the year profile")
        return
    yr = f"{trd} BETWEEN '{PROBE_YEAR}-01-01' AND '{PROBE_YEAR}-12-31'"
    for col in [x for x in (code, acq, role, cln, form) if x]:
        d = query(db, f"SELECT {col} AS value, COUNT(*) AS n FROM {lib}.{t} WHERE {yr} "
                      f"GROUP BY {col} ORDER BY n DESC LIMIT 15")
        print(f"\n  {PROBE_YEAR}: {col}")
        show(d, indent=6)
    if fil and code:
        d = query(db, f"SELECT ({fil}::date - {trd}::date) AS days, COUNT(*) AS n FROM {lib}.{t} "
                      f"WHERE {yr} AND {code} = 'P' GROUP BY 1 ORDER BY 1 LIMIT 40")
        print(f"\n  {PROBE_YEAR}: days from trade ({trd}) to filing ({fil}), open-market purchases (code P):")
        show(d, indent=6)
        d = query(db, f"SELECT ({fil}::date - {trd}::date) AS days, COUNT(*) AS n FROM {lib}.{t} "
                      f"WHERE {trd} BETWEEN '1995-01-01' AND '1995-12-31' AND {code} = 'P' "
                      f"GROUP BY 1 ORDER BY n DESC LIMIT 12")
        print(f"\n  1995 (before the 2-day rule): most common trade-to-filing gaps, purchases:")
        show(d, indent=6)
    if code:
        for y in (1986, 1995, 2005, 2015, 2024):
            d = query(db, f"SELECT COUNT(*) AS n FROM {lib}.{t} WHERE {trd} BETWEEN '{y}-01-01' AND "
                          f"'{y}-12-31' AND {code} = 'P'")
            print(f"  open-market purchases (P) with trade date in {y}: {int(d['n'].iloc[0]):,}")


def crsp_cusip(db) -> None:
    c = cols_of(db, "crsp", "stksecurityinfohist")
    cc = [x for x in c if "cusip" in x]
    print(f"  crsp.stksecurityinfohist CUSIP columns: {cc or 'NONE'}")
    if cc:
        d = query(db, f"SELECT permno, secinfostartdt, secinfoenddt, {', '.join(cc)}, ticker "
                      f"FROM crsp.stksecurityinfohist WHERE permno = {APPLE_PERMNO} ORDER BY secinfostartdt DESC LIMIT 5")
        show(d, indent=4)
    for alt in ("stocknames_v2", "stocknames"):
        try:
            a = cols_of(db, "crsp", alt)
            print(f"  crsp.{alt} CUSIP columns: {[x for x in a if 'cusip' in x]}")
        except Exception:  # noqa: BLE001
            print(f"  crsp.{alt}: not available")


def crsp_calendar(db) -> None:
    c = cols_of(db, "crsp", "dsf_v2")
    dcol = pick(c, "dlycaldt", "caldt", "date")
    d = query(db, f"SELECT COUNT(*) AS days, MIN({dcol}) AS first, MAX({dcol}) AS last FROM crsp.dsf_v2 "
                  f"WHERE permno = {CAL_PERMNO} AND {dcol} BETWEEN '1986-01-01' AND '1992-12-31'")
    print(f"  crsp.dsf_v2 date column: {dcol}; IBM (permno {CAL_PERMNO}) 1986-1992:")
    show(d, indent=4)


def main() -> None:
    ap = argparse.ArgumentParser(description="Step 7 probe for insider_cluster (read-only).")
    ap.add_argument("--user", required=True, help="your WRDS username")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    import wrds
    print("Connecting to WRDS. Type your password at the prompt; approve Duo if asked.")
    db = wrds.Connection(wrds_username=a.user)
    with open(LOG, "w", encoding="utf-8") as fh:
        sys.stdout = Tee(sys.__stdout__, fh)
        try:
            print(f"insider_cluster Step 7 probe, {pd.Timestamp.now():%Y-%m-%d %H:%M}")
            section("P1. Libraries")
            libs = step("P1", lambda: find_libraries(db)) or []
            section("P2. Tables and columns")
            cands = step("P2", lambda: list_tables(db, libs)) or []
            info = step("P2b", lambda: describe_candidates(db, cands)) or {}
            section("P3. Stock-transaction table: samples and profile")
            for (lib, t), c in info.items():
                step(f"P3 {lib}.{t}", lambda lib=lib, t=t, c=c: sample_table1(db, lib, t, c))
            section("P4. CRSP CUSIP history")
            step("P4", lambda: crsp_cusip(db))
            section("P5. CRSP trading days 1986-1992")
            step("P5", lambda: crsp_calendar(db))
            print("\nDone. Reply 'done' in the chat; Claude will read data/issuance_insider/probe_insiders_log.txt.")
        finally:
            sys.stdout = sys.__stdout__
            db.close()
    print(f"\nSaved: {LOG.relative_to(REPO)}")


if __name__ == "__main__":
    main()
