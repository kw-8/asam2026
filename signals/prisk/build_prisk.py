"""Build the PRisk event file and monthly signal file from the Hassan et al. firm-quarter download.

Run from the repo root: python signals/prisk/build_prisk.py
In:  data/prisk/firmquarter_2021q1.csv (firmlevelrisk.com, through 2021-03), crsp_monthly_ratios_clean.parquet
Out: data/prisk/prisk_events.parquet, data/prisk/prisk_monthly.parquet
"""
from pathlib import Path
import numpy as np, pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

RAW, PANEL, OUT = Path('data/prisk/firmquarter_2021q1.csv'), Path('crsp_monthly_ratios_clean.parquet'), Path('data/prisk')
SOURCE = 'firmlevelrisk.com firmquarter_2021q1 (Hassan, Hollander, van Lent & Tahoun 2019)'
STALE_MONTHS = 6                                   # a call older than this at month-end is not used
TOPICS = ['economic', 'trade', 'tax', 'environment', 'institutions', 'health', 'security', 'technology']
BDAY = pd.offsets.CustomBusinessDay(calendar=USFederalHolidayCalendar())

def load_events():
  """One row per firm-call: raw scores, call date, published_date = next business day (call time unknown)."""
  cols = ['gvkey', 'date', 'date_earningscall', 'PRisk', 'NPRisk', 'Risk', 'PSentiment', 'company_name',
          'hqcountrycode', 'ticker'] + [f'PRiskT_{t}' for t in TOPICS]
  d = pd.read_csv(RAW, sep='\t', dtype={'gvkey': str}, usecols=cols)
  d['call_date'] = pd.to_datetime(d['date_earningscall'], format='%d-%b-%Y')
  d['published_date'] = d['call_date'] + BDAY       # after-close rule: tradable the next trading day
  d = d.rename(columns={'PRisk': 'prisk', 'NPRisk': 'nprisk', 'Risk': 'risk', 'PSentiment': 'psent',
                        **{f'PRiskT_{t}': f'priskt_{t}' for t in TOPICS}})
  d = d.sort_values(['gvkey', 'call_date']).drop_duplicates(['gvkey', 'call_date'], keep='last')
  g = d.groupby('gvkey')
  for c in ['prisk', 'nprisk', 'risk', 'psent'] + [f'priskt_{t}' for t in TOPICS]:
    d[f'{c}4'] = g[c].transform(lambda s: s.rolling(4, min_periods=3).mean())   # last 4 calls (>=3)
  past = g['prisk'].transform(lambda s: s.shift(1).rolling(8, min_periods=4).mean())
  d['prisk_dm'] = d['prisk'] - past                 # surprise vs the firm's own previous 8 calls
  d['prisk_dm4'] = d['prisk4'] - past
  d['period_end'] = d['call_date']                  # the information is the call itself
  d['date_source'], d['source'], d['version'] = 'exact', SOURCE, 'original'
  return d.drop(columns=['date', 'date_earningscall'])

def to_monthly(ev, panel):
  """Panel rows with a gvkey get the latest call published by month-end, if not older than STALE_MONTHS."""
  p = panel.dropna(subset=['gvkey']).sort_values('date')
  e = ev.sort_values('published_date')
  m = pd.merge_asof(p, e, left_on='date', right_on='published_date', by='gvkey', direction='backward')
  stale = m['published_date'] < m['date'] - pd.DateOffset(months=STALE_MONTHS)
  sig = [c for c in ev.columns if c.startswith(('prisk', 'nprisk', 'risk', 'psent'))]
  m.loc[stale, sig] = np.nan
  m = m.dropna(subset=['prisk'])
  keep = ['permno', 'gvkey', 'date'] + sig + ['period_end', 'published_date', 'date_source', 'source']
  return m[keep].sort_values(['permno', 'date']).reset_index(drop=True)

if __name__ == '__main__':
  ev = load_events()
  ev.to_parquet(OUT / 'prisk_events.parquet', index=False)
  panel = pd.read_parquet(PANEL, columns=['permno', 'gvkey', 'date'])
  panel['permno'] = panel['permno'].astype('int64')
  panel['gvkey'] = panel['gvkey'].astype('string').astype(object)
  panel['date'] = pd.to_datetime(panel['date']) + pd.offsets.MonthEnd(0)
  panel = panel[(panel['date'] >= '2002-04-30') & (panel['date'] <= '2021-12-31')]
  mo = to_monthly(ev, panel)
  mo.to_parquet(OUT / 'prisk_monthly.parquet', index=False)
  print(f'events {len(ev):,} | monthly rows {len(mo):,} | permnos {mo.permno.nunique():,} | '
        f'{mo.date.min():%Y-%m} to {mo.date.max():%Y-%m}')
