"""
pull_net_issuance.py
====================
Step 7 (Pull) of prompts/data_acquisition.md for signals/issuance_insider,
signal 1: net_issuance (plus the named checks comp_issuance, net_issuance_5y,
net_issuance_skip6). Read-only: it only runs SELECT queries on WRDS.

Decisions it follows (progress.md, approved 2026-11-14):
  - Case 2: build from CRSP CIZ monthly data (crsp.msf_v2).
  - A (primary): 12-month log change in split-adjusted shares outstanding.
    B: 12-month composite issuance (log market-value growth - log total-return
    growth). C: 5-year log change in split-adjusted shares.
  - Timing: skip 1 month (2 if the timing measurement says so); a 6-month-skip
    copy of A as a named check. Applied in Step 8, not here.

What it pulls, and why
  B1. crsp_monthly.parquet     Monthly shares outstanding (shrout, thousands),
                               the cumulative share-adjustment factor
                               (mthcumfacshr), price and total return, 1974-2025,
                               for the panel's permnos. Everything A, B and C need.
                               1974 so that C (5 years) and the skipped months have
                               history before the panel starts in 1980.
  B2. share_history.parquet    CRSP's share-count history (CIZ StkShares): each
                               count with its start date and source (OBS = from a
                               data source such as a filing, EV = event such as a
                               split). Needed for the Step 6 timing measurement.
  B3. distributions.parquet    CRSP events that change the share count (splits,
                               stock dividends, reverse splits; CIZ
                               StkDistributions, rows with a share factor). Used to
                               check which way the adjustment factor works (C2
                               below) and for the Step 9 split check.
  B4. filings_10kq.parquet     EDGAR filing dates of original 10-Ks and 10-Qs,
                               2002-2025 (wrdssec.wrds_forms). Step 6 measurement:
                               how long after CRSP's start date was the filing
                               that reported a new share count public?
  Reused, not pulled again: data/lazy_prices/ccm_links.parquet (gvkey link),
  data/lazy_prices/ciklink.parquet (CIK link), data/lazy_prices/security_info.parquet
  (ETF flag, tickers).

Checks it prints (Part C)
  C1. Monthly data: rows, duplicates, missing values, how much of the panel it covers.
  C2. Which way the adjustment factor works: across split months, is
      shrout x factor or shrout / factor the smooth one? Plus Apple (4-for-1,
      Aug 2020) and NVIDIA (10-for-1, June 2024) month by month.
  C3. Share history: sources and number of share changes per year.
  C4. Filings per year and form.

Everything printed is also saved to data/issuance_insider/pull_log.txt
(earlier logs are kept as pull_log_v1.txt, pull_log_v2.txt, ...).

Run from the repo root, with the .venv active:
    python signals\\issuance_insider\\pull_net_issuance.py --user YOUR_WRDS_USERNAME

You type your WRDS password at the prompt (and approve Duo if asked).
The password never goes into this file, the chat, or the log.
Takes roughly 5-15 minutes. Re-running overwrites the data files.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.tseries.offsets import MonthEnd

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "issuance_insider"
LOG = OUT / "pull_log.txt"
PANEL = REPO / "data" / "crsp_monthly_ratios_clean.parquet"
CIKLINK = REPO / "data" / "lazy_prices" / "ciklink.parquet"
CCM = REPO / "data" / "lazy_prices" / "ccm_links.parquet"

START, END = "1974-01-01", "2025-12-31"
FILINGS_START = "2002-01-01"
TIMEOUT_S = 1200                         # per query
YEARS_PER_CHUNK = 5
KNOWN_SPLITS = [(14593, "Apple 4-for-1", "2020-06-30", "2020-10-31"),
                (86580, "NVIDIA 10-for-1", "2024-04-30", "2024-08-31")]

# Columns wanted from each table; the script keeps only those the table has.
WANT_M = ["permno", "permco", "mthcaldt", "shrout", "mthcumfacshr", "mthcumfacpr",
          "mthprc", "mthret", "mthretx"]
NEED_M = ["permno", "mthcaldt", "shrout", "mthprc", "mthret"]
WANT_S = ["permno", "shrstartdt", "shrenddt", "shrout", "shrsource", "shrfactype", "shradrflg"]
WANT_D = ["permno", "disexdt", "disseqnbr", "distype", "disfreqtype", "dispaymenttype",
          "disdetailtype", "disfacpr", "disfacshr", "disdeclaredt", "disrecorddt", "dispaydt"]

# Original 10-K and 10-Q family (10-K, 10-K405, 10-KSB, 10KSB, 10-KT, 10-Q, 10-QSB, ...), no amendments.
SQL_B4 = f"""
    SELECT cik, accession, form, fdate, rdate, secadate, CAST(secatime AS TEXT) AS secatime
    FROM wrdssec.wrds_forms
    WHERE form ~ '^10-?(K|Q)' AND POSITION('/A' IN form) = 0
      AND fdate BETWEEN '{FILINGS_START}' AND '{END}'
"""

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 30)


# ----------------------------------------------------------------------------
# Helpers (same as the lazy_prices scripts)
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
        if c in df:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


def numeric(df: pd.DataFrame, cols) -> pd.DataFrame:
    for c in cols:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    return df


def to_permno(df: pd.DataFrame) -> pd.DataFrame:
    df["permno"] = pd.to_numeric(df["permno"], errors="coerce").astype("Int64")
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


def columns_of(db, lib: str, table: str) -> list[str]:
    return [str(c).lower() for c in db.describe_table(library=lib, table=table)["name"]]


def find_table(db, lib: str, exact: str, contains: str, prefer: str = "") -> str | None:
    """Exact table name if it exists; otherwise the best name containing `contains`."""
    tables = [str(t).lower() for t in db.list_tables(library=lib)]
    if exact in tables:
        return exact
    cands = sorted((t for t in tables if contains in t), key=lambda t: (prefer not in t, len(t)))
    print(f"    '{lib}.{exact}' not found; tables containing '{contains}': {cands[:10] or 'none'}")
    return cands[0] if cands else None


def year_chunks():
    y0, y1 = int(START[:4]), int(END[:4])
    for a in range(y0, y1 + 1, YEARS_PER_CHUNK):
        yield f"{a}-01-01", f"{min(a + YEARS_PER_CHUNK - 1, y1)}-12-31"


# ----------------------------------------------------------------------------
# Part A: what the tables look like
# ----------------------------------------------------------------------------
def check_tables(db) -> dict:
    t = {"monthly": "msf_v2"}
    t["shares"] = find_table(db, "crsp", "stkshares", "stkshares")
    t["dist"] = find_table(db, "crsp", "stkdistributions", "stkdist")
    for key in ("monthly", "shares", "dist"):
        if t[key]:
            cols = columns_of(db, "crsp", t[key])
            t[key + "_cols"] = cols
            print(f"    crsp.{t[key]}: {len(cols)} columns: {', '.join(cols)}")
    if t.get("monthly_cols") and "mthcumfacshr" not in t["monthly_cols"]:
        f = find_table(db, "crsp", "stkmthcumulativeadjfactor", "cumulativeadjfactor", prefer="mth")
        t["factor"] = f
        if f:
            t["factor_cols"] = columns_of(db, "crsp", f)
            print(f"    msf_v2 has no mthcumfacshr; factor table crsp.{f}: {', '.join(t['factor_cols'])}")
    return t


# ----------------------------------------------------------------------------
# Part B: pulls
# ----------------------------------------------------------------------------
def pull_monthly(db, t: dict, keep: set) -> pd.DataFrame:
    have = t.get("monthly_cols") or columns_of(db, "crsp", "msf_v2")
    cols = [c for c in WANT_M if c in have]
    missing = [c for c in NEED_M if c not in cols]
    if missing:
        raise RuntimeError(f"crsp.msf_v2 lacks {missing}. Show this message to Claude.")
    parts = []
    for a, b in year_chunks():
        d = query(db, f"SELECT {', '.join(cols)} FROM crsp.msf_v2 WHERE mthcaldt BETWEEN '{a}' AND '{b}'",
                  date_cols=["mthcaldt"])
        d = to_permno(d)
        d = d[d["permno"].isin(keep)]
        parts.append(numeric(d, [c for c in cols if c not in ("permno", "permco", "mthcaldt")]))
        print(f"    {a[:4]}-{b[:4]}: {len(d):,} rows (panel permnos)")
    m = pd.concat(parts, ignore_index=True)

    if "mthcumfacshr" not in m:
        f = t.get("factor")
        if not f:
            raise RuntimeError("No share-adjustment factor found (msf_v2 or a cumulative-factor table). "
                               "Show this message to Claude.")
        fc = t["factor_cols"]
        dcol = next((c for c in ("mthcaldt", "caldt", "mthdt", "date") if c in fc),
                    next((c for c in fc if c.endswith("dt")), None))
        want = [c for c in ("mthcumfacshr", "mthcumfacpr") if c in fc]
        if not dcol or "mthcumfacshr" not in want:
            raise RuntimeError(f"crsp.{f}: no date column or no mthcumfacshr ({fc}). Show this to Claude.")
        fparts = []
        for a, b in year_chunks():
            d = query(db, f"SELECT permno, {dcol} AS mthcaldt, {', '.join(want)} FROM crsp.{f} "
                          f"WHERE {dcol} BETWEEN '{a}' AND '{b}'", date_cols=["mthcaldt"])
            d = to_permno(d)
            fparts.append(numeric(d[d["permno"].isin(keep)], want))
        fac = pd.concat(fparts, ignore_index=True).drop_duplicates(["permno", "mthcaldt"])
        m = m.merge(fac, on=["permno", "mthcaldt"], how="left")
        print(f"    factor merged from crsp.{f}")

    m["date"] = m["mthcaldt"] + MonthEnd(0)       # panel convention: calendar month-end
    return m.sort_values(["permno", "date"]).reset_index(drop=True)


def pull_shares(db, t: dict, keep: set) -> pd.DataFrame:
    if not t.get("shares"):
        raise RuntimeError("No CRSP share-history table found. Show this message to Claude.")
    cols = [c for c in WANT_S if c in t["shares_cols"]]
    if not {"permno", "shrstartdt", "shrout"} <= set(cols):
        raise RuntimeError(f"crsp.{t['shares']} lacks permno/shrstartdt/shrout ({cols}). Show this to Claude.")
    end_filter = f"shrenddt >= '{START}' AND " if "shrenddt" in cols else ""
    parts = []
    for lo in range(10000, 100000, 10000):
        d = query(db, f"SELECT {', '.join(cols)} FROM crsp.{t['shares']} "
                      f"WHERE {end_filter}permno BETWEEN {lo} AND {lo + 9999}",
                  date_cols=["shrstartdt", "shrenddt"])
        d = to_permno(d)
        parts.append(numeric(d[d["permno"].isin(keep)], ["shrout"]))
    s = pd.concat(parts, ignore_index=True)
    return s.sort_values(["permno", "shrstartdt"]).reset_index(drop=True)


def pull_dist(db, t: dict, keep: set) -> pd.DataFrame:
    if not t.get("dist"):
        raise RuntimeError("No CRSP distributions table found. Show this message to Claude.")
    cols = [c for c in WANT_D if c in t["dist_cols"]]
    if not {"permno", "disexdt", "disfacshr"} <= set(cols):
        raise RuntimeError(f"crsp.{t['dist']} lacks permno/disexdt/disfacshr ({cols}). Show this to Claude.")
    d = query(db, f"SELECT {', '.join(cols)} FROM crsp.{t['dist']} "
                  f"WHERE disexdt >= '{START}' AND COALESCE(disfacshr, 0) <> 0",
              date_cols=["disexdt", "disdeclaredt", "disrecorddt", "dispaydt"])
    d = to_permno(d)
    d = numeric(d[d["permno"].isin(keep)], ["disfacpr", "disfacshr"])
    return d.sort_values(["permno", "disexdt"]).reset_index(drop=True)


def pull_filings(db) -> pd.DataFrame:
    f = query(db, SQL_B4, date_cols=["fdate", "rdate", "secadate"])
    f["cik"] = f["cik"].astype(str).str.zfill(10)
    return f.sort_values(["cik", "fdate"]).reset_index(drop=True)


# ----------------------------------------------------------------------------
# Part C: what was pulled
# ----------------------------------------------------------------------------
def summarize_monthly(m: pd.DataFrame, panel: pd.DataFrame) -> None:
    print(f"\n  C1. Monthly rows: {len(m):,}   permnos: {m['permno'].nunique():,}   "
          f"months: {m['date'].min():%Y-%m} to {m['date'].max():%Y-%m}")
    print(f"      duplicate (permno, month) rows: {m.duplicated(['permno', 'date']).sum():,} (should be 0)")
    miss = {c: m[c].isna().mean() for c in ("shrout", "mthcumfacshr", "mthprc", "mthret") if c in m}
    print("      missing: " + ", ".join(f"{c} {v:.2%}" for c, v in miss.items()))
    p = panel.merge(m[["permno", "date", "shrout"]], on=["permno", "date"], how="left")
    print(f"      panel rows with a CRSP row: {p['shrout'].notna().mean():.2%} of {len(panel):,}")
    before = m[m["date"] < "1980-01-01"]
    print(f"      1974-1979 rows (history before the panel): {len(before):,} "
          f"({before['permno'].nunique():,} permnos)")


def factor_check(m: pd.DataFrame, dist: pd.DataFrame | None) -> str:
    """Across months with a split or stock dividend, which of shrout*factor and
    shrout/factor stays flat? Returns MULTIPLY, DIVIDE or UNCLEAR."""
    print("\n  C2. Which way does the share-adjustment factor work?")
    if "mthcumfacshr" not in m or dist is None or dist.empty:
        print("      skipped (no factor or no distributions)")
        return "UNCLEAR"
    ev = dist[dist["disfacshr"] > 0].assign(date=lambda d: d["disexdt"] + MonthEnd(0))
    ev = ev.groupby(["permno", "date"], as_index=False)["disfacshr"].apply(lambda s: np.prod(1 + s) - 1)
    cols = ["permno", "date", "shrout", "mthcumfacshr"]
    cur = ev.merge(m[cols], on=["permno", "date"])
    prev = m[cols].assign(date=m["date"] + MonthEnd(1)).rename(
        columns={"shrout": "shrout0", "mthcumfacshr": "f0"})
    x = cur.merge(prev, on=["permno", "date"]).dropna()
    x = x[(x["shrout"] > 0) & (x["shrout0"] > 0) & (x["mthcumfacshr"] > 0) & (x["f0"] > 0)]
    if x.empty:
        print("      no split months with data on both sides")
        return "UNCLEAR"
    raw = np.log(x["shrout"] / x["shrout0"])
    mult = np.log(x["shrout"] * x["mthcumfacshr"] / (x["shrout0"] * x["f0"]))
    div = np.log((x["shrout"] / x["mthcumfacshr"]) / (x["shrout0"] / x["f0"]))
    expect = np.log1p(x["disfacshr"])
    tab = pd.DataFrame({
        "version": ["raw shrout", "shrout x factor", "shrout / factor", "(split size, for reference)"],
        "median |log change|": [raw.abs().median(), mult.abs().median(), div.abs().median(), expect.abs().median()],
        "share within 5%": [(raw.abs() < 0.05).mean(), (mult.abs() < 0.05).mean(), (div.abs() < 0.05).mean(), np.nan],
    }).round(4)
    print(f"      {len(x):,} split / stock-dividend months with data before and after:")
    show(tab, indent=6)
    if mult.abs().median() < 0.25 * raw.abs().median() and mult.abs().median() < div.abs().median():
        verdict = "MULTIPLY"
    elif div.abs().median() < 0.25 * raw.abs().median() and div.abs().median() < mult.abs().median():
        verdict = "DIVIDE"
    else:
        verdict = "UNCLEAR"
    print(f"      VERDICT: split-adjusted shares = shrout {'x' if verdict == 'MULTIPLY' else '/' if verdict == 'DIVIDE' else '?'} "
          f"mthcumfacshr  ({verdict})")
    for permno, name, a, b in KNOWN_SPLITS:
        k = m[(m["permno"] == permno) & m["date"].between(a, b)][["date", "shrout", "mthcumfacshr", "mthprc"]].copy()
        if k.empty:
            print(f"      {name} (permno {permno}): not in the pull")
            continue
        k["shrout_x_f"] = (k["shrout"] * k["mthcumfacshr"]).round(0)
        k["shrout_div_f"] = (k["shrout"] / k["mthcumfacshr"]).round(0)
        k["date"] = k["date"].dt.strftime("%Y-%m")
        print(f"      {name} (permno {permno}):")
        show(k, indent=8)
    return verdict


def summarize_shares(s: pd.DataFrame, keep: set) -> None:
    print(f"\n  C3. Share history rows: {len(s):,}   permnos: {s['permno'].nunique():,} "
          f"({s['permno'].nunique() / max(len(keep), 1):.1%} of panel permnos)")
    if "shrsource" in s:
        print("      rows by source (OBS = data source such as a filing, EV = event such as a split, NC = name change):")
        show(s["shrsource"].fillna("(missing)").value_counts().rename_axis("shrsource").reset_index(name="rows"),
             indent=6)
        obs = s[s["shrsource"] == "OBS"]
    else:
        obs = s
    y = obs.groupby(obs["shrstartdt"].dt.year).size()
    y = y[(y.index >= 1974) & (y.index <= 2025)]
    print("      OBS share counts starting each year: " +
          ", ".join(f"{int(k)}: {v:,}" for k, v in y.items() if k % 3 == 1 or k >= 2020))
    day = obs["shrstartdt"].dt.day
    print(f"      OBS start dates on the last day of a month: {(obs['shrstartdt'] == obs['shrstartdt'] + MonthEnd(0)).mean():.1%}; "
          f"median day of month {int(day.median()) if len(day) else 'n/a'}  "
          "(many month-ends would hint at quarter-end dating rather than cover-page dates)")


def summarize_filings(f: pd.DataFrame) -> None:
    print(f"\n  C4. Filings: {len(f):,} original 10-K/10-Q-family filings, {f['cik'].nunique():,} filers, "
          f"{f['fdate'].min():%Y-%m-%d} to {f['fdate'].max():%Y-%m-%d}")
    show(f["form"].value_counts().head(10).rename_axis("form").reset_index(name="n"), indent=6)
    y = f.groupby(f["fdate"].dt.year).size()
    print("      per year: " + ", ".join(f"{k}: {v:,}" for k, v in y.items()))


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="Step 7 pull for net_issuance (CRSP CIZ + filing dates).")
    ap.add_argument("--user", required=True, help="your WRDS username")
    a = ap.parse_args()

    if not PANEL.exists():
        sys.exit(f"Panel not found: {PANEL.relative_to(REPO)}. Put it in data/ first (SETUP.md).")
    panel = pd.read_parquet(PANEL, columns=["permno", "date"])
    panel["permno"] = pd.to_numeric(panel["permno"]).astype("Int64")
    panel["date"] = pd.to_datetime(panel["date"]) + MonthEnd(0)
    keep = set(panel["permno"].dropna().astype(int))

    OUT.mkdir(parents=True, exist_ok=True)
    if LOG.exists():                             # keep earlier logs: pull_log_v1.txt, _v2.txt, ...
        k = 1
        while (OUT / f"pull_log_v{k}.txt").exists():
            k += 1
        LOG.replace(OUT / f"pull_log_v{k}.txt")

    import wrds                                  # imported here so --help works without it
    print("Connecting to WRDS. Type your password at the prompt; approve Duo if asked.")
    db = wrds.Connection(wrds_username=a.user)   # connect before logging, so nothing about login is saved

    with open(LOG, "w", encoding="utf-8") as fh:
        sys.stdout = Tee(sys.__stdout__, fh)
        try:
            print(f"net_issuance Step 7 pull, {pd.Timestamp.now():%Y-%m-%d %H:%M}")
            print(f"  panel: {len(panel):,} rows, {len(keep):,} permnos")
            for p in (CCM, CIKLINK):
                print(f"  reuse {p.relative_to(REPO)}: {'found' if p.exists() else 'MISSING'}")

            section("A. Tables")
            t = step("A1. CRSP CIZ tables and columns", lambda: check_tables(db)) or {"monthly": "msf_v2"}

            section("B. Pulls")
            m = step("B1. Monthly shares, factor, price, return (crsp.msf_v2, 1974-2025)",
                     lambda: pull_monthly(db, t, keep))
            if m is not None:
                save(m, "crsp_monthly")
            s = step("B2. Share-count history (CIZ StkShares)", lambda: pull_shares(db, t, keep))
            if s is not None:
                save(s, "share_history")
            d = step("B3. Share-changing distributions (CIZ StkDistributions)", lambda: pull_dist(db, t, keep))
            if d is not None:
                save(d, "distributions")
            f = step(f"B4. 10-K / 10-Q filing dates (wrdssec.wrds_forms, {FILINGS_START[:4]}-{END[:4]})",
                     lambda: pull_filings(db))
            if f is not None:
                save(f, "filings_10kq")

            section("C. What was pulled")
            if m is not None:
                step("C1", lambda: summarize_monthly(m, panel))
                step("C2", lambda: factor_check(m, d))
            if s is not None:
                step("C3", lambda: summarize_shares(s, keep))
            if f is not None:
                step("C4", lambda: summarize_filings(f))

            failed = [n for n, x in [("B1", m), ("B2", s), ("B3", d), ("B4", f)] if x is None]
            print("\n" + ("All pulls saved." if not failed else f"FAILED: {', '.join(failed)} (see above)."))
            print("Reply 'done' in the chat; Claude will read data/issuance_insider/pull_log.txt.")
        finally:
            sys.stdout = sys.__stdout__
            db.close()
    print(f"\nSaved: {LOG.relative_to(REPO)}")


if __name__ == "__main__":
    main()
