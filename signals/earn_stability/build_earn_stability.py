"""Earnings stability from the panel: std of roa (and gprof) over the trailing 60 months, sampled every 3rd month.

Run from the repo root: python signals/earn_stability/build_earn_stability.py
In:  crsp_monthly_ratios_clean.parquet (roa, gprof; WRDS ratios, trailing-12-month, updated quarterly)
Out: data/earn_stability/earn_stability_monthly.parquet (permno, date, roa_sd5, gprof_sd5, n_q_roa, n_q_gprof, ...)
"""
from pathlib import Path
import numpy as np, pandas as pd

PANEL, OUT = Path('crsp_monthly_ratios_clean.parquet'), Path('data/earn_stability')
LAGS, MIN_Q = range(0, 60, 3), 12      # months t, t-3, ..., t-57 (20 quarters); need >= 12 non-missing
SOURCE = 'crsp_monthly_ratios_clean.parquet (WRDS Financial Ratios Suite roa, gprof)'

def trailing_sd(W):
  """Per column of a month x permno matrix: std over rows t, t-3, ..., t-57 with >= MIN_Q values (ddof=1)."""
  s = np.zeros(W.shape); ss = np.zeros(W.shape); n = np.zeros(W.shape)
  for k in LAGS:
    x = W.shift(k).to_numpy()
    ok = ~np.isnan(x)
    s += np.where(ok, x, 0); ss += np.where(ok, x * x, 0); n += ok
  with np.errstate(invalid='ignore', divide='ignore'):
    sd = np.sqrt(np.maximum(ss - s * s / n, 0) / (n - 1))
  return pd.DataFrame(np.where(n >= MIN_Q, sd, np.nan), W.index, W.columns), pd.DataFrame(n, W.index, W.columns)

def build(panel):
  """Long permno-month file with the two stability measures and their quarter counts."""
  months = pd.date_range(panel['date'].min(), panel['date'].max(), freq='ME')   # full calendar: shifts are true months
  out = []
  for c in ['roa', 'gprof']:
    W = panel.pivot(index='date', columns='permno', values=c).reindex(months)
    sd, n = trailing_sd(W)
    out.append(pd.concat({f'{c}_sd5': sd.stack(future_stack=True), f'n_q_{c}': n.stack(future_stack=True)}, axis=1))
  m = pd.concat(out, axis=1).rename_axis(['date', 'permno']).reset_index()
  m = m.merge(panel[['permno', 'date']], on=['permno', 'date'])                  # panel rows only
  m = m.dropna(subset=['roa_sd5', 'gprof_sd5'], how='all')
  m['period_end'] = m['date']; m['published_date'] = m['date']                  # panel ratios assumed public by month-end
  m['date_source'], m['source'] = 'assumed', SOURCE
  return m.sort_values(['permno', 'date']).reset_index(drop=True)

if __name__ == '__main__':
  p = pd.read_parquet(PANEL, columns=['permno', 'date', 'roa', 'gprof'])
  p['permno'] = p['permno'].astype('int64')
  p['date'] = pd.to_datetime(p['date']) + pd.offsets.MonthEnd(0)
  OUT.mkdir(parents=True, exist_ok=True)
  m = build(p)
  m.to_parquet(OUT / 'earn_stability_monthly.parquet', index=False)
  print(f'rows {len(m):,} | permnos {m.permno.nunique():,} | {m.date.min():%Y-%m} to {m.date.max():%Y-%m} | '
        f'roa_sd5 non-missing {m.roa_sd5.notna().mean():.1%}')
