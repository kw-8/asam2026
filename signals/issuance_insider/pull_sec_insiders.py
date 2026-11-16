"""
pull_sec_insiders.py
====================
Step 7 (Pull) for signals/issuance_insider, signal 2: insider_cluster.
Data source (decided 2026-11-15): SEC "Insider Transactions Data Sets" - free,
official, extracted by the SEC from the XML of Forms 3, 4 and 5 ("as filed", not
cleaned). One zip per quarter; we use 2006 Q1 to 2025 Q4 (80 files, ~1 GB).
No WRDS login needed.

What it does
  1. Downloads each quarter's zip from www.sec.gov into data/issuance_insider/sec_raw/
     (skips files already there, so a re-run only fetches what is missing).
     The SEC asks every automated downloader to identify itself with a name and
     e-mail in the request header (its "fair access" rule); you pass them with
     --name and --email. They are sent only to sec.gov and are not saved anywhere.
     At most ~2 requests per second (SEC limit: 10).
  2. From each zip reads three tab-delimited tables, joined on ACCESSION_NUMBER:
       NONDERIV_TRANS  stock (non-derivative) transactions  -> kept: codes P and S
       SUBMISSION      one row per filing: filing date, form type, issuer CIK, ticker
       REPORTINGOWNER  the insider(s) on each filing: CIK, name, relationship, title
     SUBMISSION and REPORTINGOWNER are kept only for filings with a P or S row.
  3. Saves to data/issuance_insider/:
       sec_trans.parquet       (P and S transactions)
       sec_submissions.parquet (their filings)
       sec_owners.parquet      (their insiders)
     and prints checks: rows per year, form types, transaction codes, insider
     relationships, trade-to-filing gaps, duplicates, and Apple's latest filings.

Everything printed is also saved to data/issuance_insider/pull_sec_log.txt.

Run from the repo root, with the .venv active (no WRDS password):
    python signals\\issuance_insider\\pull_sec_insiders.py --name "Your Name" --email you@example.edu
About 10-30 minutes the first time (download), about 2-5 minutes on re-runs.
"""
from __future__ import annotations

import argparse
import io
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "issuance_insider"
RAW = OUT / "sec_raw"
LOG = OUT / "pull_sec_log.txt"
URL = "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{q}_form345.zip"
FIRST_YEAR, LAST_YEAR = 2006, 2025
KEEP_CODES = {"P", "S"}
PAUSE_S = 0.5
APPLE_CIK = "320193"

TRANS_COLS = ["ACCESSION_NUMBER", "NONDERIV_TRANS_SK", "SECURITY_TITLE", "TRANS_DATE", "DEEMED_EXECUTION_DATE",
              "TRANS_CODE", "TRANS_TIMELINESS", "TRANS_SHARES", "TRANS_PRICEPERSHARE", "TRANS_ACQUIRED_DISP_CD",
              "SHRS_OWND_FOLWNG_TRANS", "DIRECT_INDIRECT_OWNERSHIP"]
SUB_COLS = ["ACCESSION_NUMBER", "FILING_DATE", "PERIOD_OF_REPORT", "DOCUMENT_TYPE", "ISSUERCIK", "ISSUERNAME",
            "ISSUERTRADINGSYMBOL", "AFF10B5ONE"]
OWN_COLS = ["ACCESSION_NUMBER", "RPTOWNERCIK", "RPTOWNERNAME", "RPTOWNER_RELATIONSHIP", "RPTOWNER_TITLE",
            "RPTOWNER_TXT"]

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 30)
pd.set_option("display.max_colwidth", 30)


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            st.write(s)

    def flush(self):
        for st in self.streams:
            st.flush()


def show(df: pd.DataFrame, indent: int = 4) -> None:
    pad = " " * indent
    print(pad + df.to_string(index=False).replace("\n", "\n" + pad))


def section(title: str) -> None:
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


def quarters() -> list[str]:
    return [f"{y}q{q}" for y in range(FIRST_YEAR, LAST_YEAR + 1) for q in range(1, 5)]


# ----------------------------------------------------------------------------
# 1. Download
# ----------------------------------------------------------------------------
def download(q: str, agent: str) -> Path | None:
    path = RAW / f"{q}_form345.zip"
    if path.exists() and path.stat().st_size > 0:
        return path
    req = urllib.request.Request(URL.format(q=q), headers={"User-Agent": agent, "Accept-Encoding": "identity"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            tmp = path.with_suffix(".part")
            tmp.write_bytes(data)
            tmp.replace(path)
            time.sleep(PAUSE_S)
            return path
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                print(f"    {q}: HTTP {e.code} (SEC rate limit or missing name/e-mail); waiting 10 s ...")
                time.sleep(10)
            elif e.code == 404:
                print(f"    {q}: not found on the SEC site (404)")
                return None
            else:
                print(f"    {q}: HTTP {e.code}; retrying")
                time.sleep(3)
        except Exception as e:  # noqa: BLE001
            print(f"    {q}: {type(e).__name__}: {str(e)[:120]}; retrying")
            time.sleep(3)
    print(f"    {q}: FAILED after 3 attempts")
    return None


# ----------------------------------------------------------------------------
# 2. Read one quarter
# ----------------------------------------------------------------------------
def _read_table(z: zipfile.ZipFile, table: str, cols: list[str]) -> pd.DataFrame:
    names = [n for n in z.namelist() if Path(n).name.upper().startswith(table) and
             Path(n).suffix.lower() in (".tsv", ".txt", ".csv", "")]
    # exact table, not e.g. NONDERIV_TRANS matching NONDERIV_TRANS_xxx: prefer the shortest name
    names = sorted(names, key=lambda n: len(Path(n).name))
    if not names:
        raise FileNotFoundError(f"{table} not found in zip (files: {z.namelist()})")
    with z.open(names[0]) as fh:
        raw = fh.read()
    df = pd.read_csv(io.BytesIO(raw), sep="\t", dtype=str, quoting=3, keep_default_na=False,
                     encoding="utf-8", encoding_errors="replace", on_bad_lines="warn")
    df.columns = [c.strip().upper() for c in df.columns]
    for c in cols:
        if c not in df:
            df[c] = ""
    return df[cols]


def read_quarter(path: Path, q: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    with zipfile.ZipFile(path) as z:
        tr = _read_table(z, "NONDERIV_TRANS", TRANS_COLS)
        n_all = len(tr)
        tr = tr[tr["TRANS_CODE"].str.strip().str.upper().isin(KEEP_CODES)].copy()
        acc = set(tr["ACCESSION_NUMBER"])
        sub = _read_table(z, "SUBMISSION", SUB_COLS)
        n_sub = len(sub)
        sub = sub[sub["ACCESSION_NUMBER"].isin(acc)].copy()
        own = _read_table(z, "REPORTINGOWNER", OWN_COLS)
        own = own[own["ACCESSION_NUMBER"].isin(acc)].copy()
    for d in (tr, sub, own):
        d["quarter"] = q
    stats = {"quarter": q, "filings": n_sub, "stock_trans": n_all, "P": int((tr["TRANS_CODE"] == "P").sum()),
             "S": int((tr["TRANS_CODE"] == "S").sum())}
    return tr, sub, own, stats


# ----------------------------------------------------------------------------
# 3. Tidy and check
# ----------------------------------------------------------------------------
def to_date(s: pd.Series) -> pd.Series:
    s = s.str.strip()
    d = pd.to_datetime(s, format="%d-%b-%Y", errors="coerce")
    alt = pd.to_datetime(s.where(d.isna()), errors="coerce")      # any other format the SEC may have used
    return d.fillna(alt)


def tidy(tr: pd.DataFrame, sub: pd.DataFrame, own: pd.DataFrame):
    for c in ("TRANS_DATE", "DEEMED_EXECUTION_DATE"):
        tr[c] = to_date(tr[c])
    for c in ("TRANS_SHARES", "TRANS_PRICEPERSHARE", "SHRS_OWND_FOLWNG_TRANS"):
        tr[c] = pd.to_numeric(tr[c].str.replace(",", ""), errors="coerce")
    tr["TRANS_CODE"] = tr["TRANS_CODE"].str.strip().str.upper()
    for c in ("FILING_DATE", "PERIOD_OF_REPORT"):
        sub[c] = to_date(sub[c])
    sub["ISSUERCIK"] = sub["ISSUERCIK"].str.strip().str.lstrip("0")
    own["RPTOWNERCIK"] = own["RPTOWNERCIK"].str.strip().str.lstrip("0")
    tr.columns = [c.lower() for c in tr.columns]
    sub.columns = [c.lower() for c in sub.columns]
    own.columns = [c.lower() for c in own.columns]
    return tr, sub, own


def checks(tr: pd.DataFrame, sub: pd.DataFrame, own: pd.DataFrame, stats: pd.DataFrame) -> None:
    print("\n  Per year (all quarters summed): filings in the data sets, stock transactions, purchases P, sales S")
    y = stats.assign(year=stats["quarter"].str[:4]).groupby("year")[["filings", "stock_trans", "P", "S"]].sum()
    show(y.reset_index())
    print(f"\n  Kept: {len(tr):,} P/S transactions in {tr['accession_number'].nunique():,} filings; "
          f"{len(sub):,} submission rows; {len(own):,} owner rows")
    dup_sub = sub.duplicated("accession_number").sum()
    dup_tr = tr.duplicated(["accession_number", "nonderiv_trans_sk"]).sum()
    print(f"  duplicate filings across quarters: {dup_sub:,}; duplicate transactions: {dup_tr:,} (should be 0)")
    print("\n  Form types (filings with a P or S row):")
    show(sub["document_type"].value_counts().head(10).rename_axis("document_type").reset_index(name="filings"))
    print("\n  Transaction codes kept / acquired-disposed:")
    show(tr.groupby(["trans_code", "trans_acquired_disp_cd"]).size().reset_index(name="rows"))
    print("\n  Insider relationship values (top 12):")
    show(own["rptowner_relationship"].value_counts().head(12).rename_axis("relationship").reset_index(name="rows"))
    m = tr.merge(sub[["accession_number", "filing_date", "issuercik"]], on="accession_number", how="left")
    gap = (m["filing_date"] - m["trans_date"]).dt.days
    print(f"\n  Days from trade to filing, purchases (P): median {gap[m['trans_code'] == 'P'].median():.0f}; "
          f"share filed within 2 days {(gap[m['trans_code'] == 'P'] <= 2).mean():.1%}, within 5 days "
          f"{(gap[m['trans_code'] == 'P'] <= 5).mean():.1%}; negative (filed before trade) {(gap < 0).sum():,}; "
          f"missing filing date {m['filing_date'].isna().sum():,}; missing trade date {m['trans_date'].isna().sum():,}")
    print(f"  late flag (TRANS_TIMELINESS = L) on purchases: {(m.loc[m['trans_code'] == 'P', 'trans_timeliness'] == 'L').mean():.1%}")
    print(f"  filing dates {m['filing_date'].min():%Y-%m-%d} to {m['filing_date'].max():%Y-%m-%d}; "
          f"issuers {m['issuercik'].nunique():,}; insiders {own['rptownercik'].nunique():,}")
    a = m[m["issuercik"] == APPLE_CIK].sort_values("filing_date").tail(6)
    a = a.merge(own[["accession_number", "rptownername", "rptowner_relationship"]].drop_duplicates("accession_number"),
                on="accession_number", how="left")
    print("\n  Apple (CIK 320193), latest P/S rows:")
    show(a[["filing_date", "trans_date", "trans_code", "trans_shares", "trans_pricepershare", "rptownername",
            "rptowner_relationship"]], indent=4)


def main() -> None:
    ap = argparse.ArgumentParser(description="Download SEC insider transaction data sets (2006-2025).")
    ap.add_argument("--name", required=True, help='your name, for the SEC request header, e.g. "Jane Doe"')
    ap.add_argument("--email", required=True, help="your e-mail, for the SEC request header")
    a = ap.parse_args()
    agent = f"{a.name} {a.email} (UCLA Anderson student research)"
    RAW.mkdir(parents=True, exist_ok=True)
    with open(LOG, "w", encoding="utf-8") as fh:
        sys.stdout = Tee(sys.__stdout__, fh)
        try:
            print(f"insider_cluster Step 7 pull (SEC data sets), {pd.Timestamp.now():%Y-%m-%d %H:%M}")
            section("1. Download")
            qs = quarters()
            t0 = time.time()
            paths = {}
            for i, q in enumerate(qs, 1):
                p = download(q, agent)
                if p is not None:
                    paths[q] = p
                if i % 8 == 0:
                    print(f"    {i}/{len(qs)} quarters ready ({time.time() - t0:.0f}s)")
            missing = [q for q in qs if q not in paths]
            print(f"  {len(paths)}/{len(qs)} quarters available; missing: {missing or 'none'}")

            section("2. Read and filter (P and S)")
            trs, subs, owns, stats = [], [], [], []
            for q, p in paths.items():
                try:
                    tr, sub, own, st = read_quarter(p, q)
                except Exception as e:  # noqa: BLE001
                    print(f"    {q}: FAILED to read: {type(e).__name__}: {str(e)[:200]}")
                    continue
                trs.append(tr)
                subs.append(sub)
                owns.append(own)
                stats.append(st)
            tr, sub, own = tidy(pd.concat(trs, ignore_index=True), pd.concat(subs, ignore_index=True),
                                pd.concat(owns, ignore_index=True))
            stats = pd.DataFrame(stats)

            section("3. Save")
            for df, name in ((tr, "sec_trans"), (sub, "sec_submissions"), (own, "sec_owners")):
                df.to_parquet(OUT / f"{name}.parquet", index=False)
                print(f"  saved data/issuance_insider/{name}.parquet ({len(df):,} rows)")

            section("4. Checks")
            checks(tr, sub, own, stats)
            print("\nDone. Reply 'done' in the chat; Claude will read data/issuance_insider/pull_sec_log.txt.")
        finally:
            sys.stdout = sys.__stdout__
    print(f"\nSaved: {LOG.relative_to(REPO)}")


if __name__ == "__main__":
    main()
