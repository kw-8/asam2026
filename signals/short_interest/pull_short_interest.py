"""Pull Compustat short interest and the CRSP-Compustat link from WRDS (read-only).

Run from the repo root: python signals/short_interest/pull_short_interest.py [--user YOUR_WRDS_USERNAME]
You type your WRDS username (if not passed) and password at the prompt; it never goes into this file.
Out: data/short_interest/sec_shortint.parquet, data/short_interest/ccm_links.parquet
"""
import argparse
from pathlib import Path
import wrds

OUT = Path('data/short_interest')
SI_SQL = "SELECT gvkey, iid, datadate, shortint, shortintadj, splitadjdate FROM comp.sec_shortint"
CCM_SQL = """SELECT gvkey, liid, lpermno AS permno, linkdt, linkenddt, linktype, linkprim
FROM crsp.ccmxpf_lnkhist WHERE linktype IN ('LU', 'LC') AND lpermno IS NOT NULL"""

if __name__ == '__main__':
  a = argparse.ArgumentParser(); a.add_argument('--user'); u = a.parse_args().user
  OUT.mkdir(parents=True, exist_ok=True)
  db = wrds.Connection(wrds_username=u) if u else wrds.Connection()
  si = db.raw_sql(SI_SQL, date_cols=['datadate', 'splitadjdate'])
  si.to_parquet(OUT / 'sec_shortint.parquet', index=False)
  print(f'sec_shortint: {len(si):,} rows, {si.gvkey.nunique():,} gvkeys, {si.datadate.min():%Y-%m-%d} to {si.datadate.max():%Y-%m-%d}')
  ccm = db.raw_sql(CCM_SQL, date_cols=['linkdt', 'linkenddt'])
  ccm.to_parquet(OUT / 'ccm_links.parquet', index=False)
  print(f'ccm_links: {len(ccm):,} rows')
  db.close()
