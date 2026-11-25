"""Build PRisk augmentation inputs (dm4, its z-score, sentiment/NPRisk/topic changes) for any base score.

Run from the repo root: python signals/prisk/augment/build_augment.py [base] [events.parquet] [out.parquet]
Default: base=prisk, data/prisk/prisk_events.parquet -> data/prisk/augment/aug_prisk_monthly.parquet
Events need: gvkey, published_date, <base>; optional psent, nprisk, priskt_{economic,trade,tax} (else those columns are NaN).
"""
import sys; sys.path.insert(0, '.')
from pathlib import Path
import numpy as np, pandas as pd

PANEL, STALE_MONTHS = Path('crsp_monthly_ratios_clean.parquet'), 6
SYS = ['priskt_economic', 'priskt_trade', 'priskt_tax']

def dm4(g, c):
  """Per firm: (mean of last 4 (>=3) minus mean of the 8 before (>=4), sd of the 8 before)."""
  b4 = g[c].transform(lambda s: s.rolling(4, min_periods=3).mean())
  p8 = g[c].transform(lambda s: s.shift(1).rolling(8, min_periods=4).mean())
  sd8 = g[c].transform(lambda s: s.shift(1).rolling(8, min_periods=4).std())
  return b4 - p8, sd8

def build_events(ev, base):
  """Event-level augmentation columns from one row per firm-event, sorted by event time."""
  ev = ev.sort_values(['gvkey', 'published_date']).copy()
  if all(c in ev for c in SYS):
    ev['sys'] = ev[SYS].sum(axis=1, min_count=len(SYS))
  g = ev.groupby('gvkey')
  ev['dm4'], sd8 = dm4(g, base)
  ev['dm4_z'] = ev['dm4'] / sd8.where(sd8 > 0)
  for c, n in [('psent', 'psent_dm4'), ('nprisk', 'nprisk_dm4'), ('sys', 'sys_dm4')]:
    ev[n] = dm4(g, c)[0] if c in ev else np.nan
  return ev[['gvkey', 'published_date', 'dm4', 'dm4_z', 'psent_dm4', 'nprisk_dm4', 'sys_dm4']]

def to_monthly(ev, panel):
  """Latest event published by month-end (not older than STALE_MONTHS) for each panel permno-month."""
  m = pd.merge_asof(panel.dropna(subset=['gvkey']).sort_values('date'), ev.sort_values('published_date'),
                    left_on='date', right_on='published_date', by='gvkey', direction='backward')
  m = m[m['published_date'] >= m['date'] - pd.DateOffset(months=STALE_MONTHS)]
  return m.dropna(subset=['dm4']).drop(columns=['gvkey']).sort_values(['permno', 'date']).reset_index(drop=True)

if __name__ == '__main__':
  base = sys.argv[1] if len(sys.argv) > 1 else 'prisk'
  src = sys.argv[2] if len(sys.argv) > 2 else 'data/prisk/prisk_events.parquet'
  out = sys.argv[3] if len(sys.argv) > 3 else f'data/prisk/augment/aug_{base}_monthly.parquet'
  ev = pd.read_parquet(src)
  ev['gvkey'] = ev['gvkey'].astype(str)
  panel = pd.read_parquet(PANEL, columns=['permno', 'gvkey', 'date'])
  panel['permno'] = panel['permno'].astype('int64')
  panel['gvkey'] = panel['gvkey'].astype('string').astype(object)
  panel['date'] = pd.to_datetime(panel['date']) + pd.offsets.MonthEnd(0)
  panel = panel[panel['date'] >= ev['published_date'].min()]
  mo = to_monthly(build_events(ev, base), panel)
  mo.to_parquet(out, index=False)
  print(f'{base}: rows {len(mo):,} | permnos {mo.permno.nunique():,} | {mo.date.min():%Y-%m} to {mo.date.max():%Y-%m} | '
        f'non-null: ' + ', '.join(f'{c} {mo[c].notna().mean():.2f}' for c in ['dm4', 'dm4_z', 'psent_dm4', 'nprisk_dm4', 'sys_dm4']))
