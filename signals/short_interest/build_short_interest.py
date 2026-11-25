"""Short interest per stock-month: si_ratio = shares short / shares outstanding; dtc = days to cover.

Run from the repo root: python signals/short_interest/build_short_interest.py
In:  data/short_interest/sec_shortint.parquet, data/short_interest/ccm_links.parquet, the panel
Out: data/short_interest/si_events.parquet, data/short_interest/si_monthly.parquet
"""
from pathlib import Path
import numpy as np, pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import CustomBusinessDay

D = Path('data/short_interest')
PUB_LAG = 8            # business days from settlement date to publication (exchange/FINRA schedule; assumed)
STALE_DAYS = 45        # a settlement date older than this at the month-end is not used (data are twice a month)
SOURCE = 'Compustat comp.sec_shortint (WRDS); shares outstanding and volume from the panel'

def link(si, ccm):
  """(gvkey, iid) -> permno through the CCM link, valid on the settlement date."""
  ccm = ccm.assign(linkenddt=ccm['linkenddt'].fillna(pd.Timestamp('2099-12-31')), permno=ccm['permno'].astype('int64'))
  m = si.merge(ccm, left_on=['gvkey', 'iid'], right_on=['gvkey', 'liid'])
  m = m[(m['datadate'] >= m['linkdt']) & (m['datadate'] <= m['linkenddt'])]
  return m.sort_values('linkprim').drop_duplicates(['permno', 'datadate'])   # P before C/J if a permno links twice

def build(si, ccm, panel):
  """Event file (one row per permno x settlement date) and the monthly file."""
  e = link(si, ccm)
  # shares/volume from the last panel month-end on or before the settlement date (end-of-month settlements, day >= 25,
  # use that month): shares short and shares outstanding then sit on the same side of a split
  e['month'] = (e['datadate'] + pd.offsets.MonthEnd(0)).where(e['datadate'].dt.day >= 25, e['datadate'] - pd.offsets.MonthEnd(1))
  e = e.merge(panel[['permno', 'date', 'shrout', 'mthvol']].rename(columns={'date': 'month'}), on=['permno', 'month'], how='left')
  si_, sh, vol = (e[c].astype('float64') for c in ['shortint', 'shrout', 'mthvol'])
  e['si_ratio'] = si_ / (sh * 1000)
  e['dtc'] = (si_ / (vol / 21)).replace(np.inf, np.nan)              # days of average daily volume to cover
  e['period_end'] = e['datadate']
  e['published_date'] = e['datadate'] + PUB_LAG * CustomBusinessDay(calendar=USFederalHolidayCalendar())
  e['date_source'], e['source'], e['version'] = 'assumed', SOURCE, 'original'
  e = e[['permno', 'gvkey', 'iid', 'period_end', 'published_date', 'date_source', 'source', 'version',
         'shortint', 'shrout', 'mthvol', 'si_ratio', 'dtc']].sort_values(['published_date', 'permno']).reset_index(drop=True)
  p = panel[['permno', 'gvkey', 'date']].dropna(subset=['date']).sort_values('date')
  p = p[p['date'] >= e['published_date'].min()]
  m = pd.merge_asof(p, e.drop(columns=['gvkey', 'iid', 'version']), left_on='date', right_on='published_date', by='permno', direction='backward')
  m = m[(m['date'] - m['period_end']).dt.days <= STALE_DAYS]
  cols = ['permno', 'gvkey', 'date', 'si_ratio', 'dtc', 'period_end', 'published_date', 'date_source', 'source']
  return e, m[cols].sort_values(['permno', 'date']).reset_index(drop=True)

if __name__ == '__main__':
  si = pd.read_parquet(D / 'sec_shortint.parquet')
  ccm = pd.read_parquet(D / 'ccm_links.parquet')
  panel = pd.read_parquet('crsp_monthly_ratios_clean.parquet', columns=['permno', 'gvkey', 'date', 'shrout', 'mthvol'])
  panel['permno'] = panel['permno'].astype('int64')
  panel['date'] = pd.to_datetime(panel['date']) + pd.offsets.MonthEnd(0)
  e, m = build(si, ccm, panel)
  e.to_parquet(D / 'si_events.parquet', index=False); m.to_parquet(D / 'si_monthly.parquet', index=False)
  print(f'events {len(e):,} | monthly {len(m):,} rows, {m.permno.nunique():,} permnos, {m.date.min():%Y-%m} to {m.date.max():%Y-%m}')
