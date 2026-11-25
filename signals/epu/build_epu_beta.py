"""Stock exposures to EPU shocks: rolling OLS of excess return on mktrf and the log change of an EPU index.

Run from the repo root: python signals/epu/build_epu_beta.py
In:  public_data/epu_monthly.csv, public_data/ff_factors_monthly.csv, the panel (mthret)
Out: data/epu/epu_beta_monthly.parquet (permno, date, epu_beta, epu_trade_beta, epu_natsec_beta, epu_beta36, mkt_beta60, n_obs, ...)
Value at month-end t uses months t-W .. t-1 only (month t's EPU is posted in month t+1).
"""
from pathlib import Path
import numpy as np, pandas as pd

PANEL, OUT = Path('crsp_monthly_ratios_clean.parquet'), Path('data/epu')
SIG = {'epu_beta': ('epu_news', 60), 'epu_trade_beta': ('epu_trade_policy', 60),
       'epu_natsec_beta': ('epu_national_security', 60), 'epu_beta36': ('epu_news', 36)}
MIN_OBS = {60: 36, 36: 24}
CHUNK = 2000
SOURCE = 'public_data/epu_monthly.csv (Baker-Bloom-Davis EPU) + panel mthret + FF mktrf, rf'

def roll_beta(Y, m, u, win, min_obs):
  """Per column of month x permno Y: OLS of Y on [1, m, u] over the previous win months (t-win..t-1)."""
  ok = Y.notna().to_numpy() & ~np.isnan(m)[:, None] & ~np.isnan(u)[:, None]
  y = np.where(ok, Y.to_numpy(), 0.0)
  M, U, one = np.where(ok, m[:, None], 0.0), np.where(ok, u[:, None], 0.0), ok.astype(float)
  def rs(a):
    """Rolling sum over the previous win rows, excluding the current row."""
    c = np.vstack([np.zeros((1, a.shape[1])), np.cumsum(a, 0)])
    s = c[1:] - np.vstack([np.zeros((win, a.shape[1])), c[1:-win]]) if len(a) > win else c[1:]
    return np.vstack([np.zeros((1, a.shape[1])), s[:-1]])
  n, sm, su, smm, smu, suu = rs(one), rs(M), rs(U), rs(M * M), rs(M * U), rs(U * U)
  sy, smy, suy = rs(y), rs(M * y), rs(U * y)
  with np.errstate(invalid='ignore', divide='ignore'):     # closed-form OLS on demeaned sums (batched linalg.solve gave zeros)
    Smm, Suu, Smu = smm - sm * sm / n, suu - su * su / n, smu - sm * su / n
    Smy, Suy = smy - sm * sy / n, suy - su * sy / n
    det = Smm * Suu - Smu * Smu
    bu, bm = (Smm * Suy - Smu * Smy) / det, (Suu * Smy - Smu * Suy) / det
  good = (n >= min_obs) & (det > 0)
  return np.where(good, bu, np.nan), np.where(good, bm, np.nan), n

def build(panel, epu, ff):
  """Long permno-month file of the exposures."""
  months = pd.date_range(panel['date'].min(), panel['date'].max(), freq='ME')
  ff = ff.reindex(months)
  W = panel.pivot(index='date', columns='permno', values='mthret').reindex(months)
  W = pd.DataFrame(W.to_numpy() - ff['rf'].to_numpy()[:, None], months, W.columns)   # numpy: W.sub(rf, axis=0) dropped 1/3 of cells (pandas 2.2.3)
  m = ff['mktrf'].to_numpy()
  out = {}
  for name, (idx, win) in SIG.items():
    u = np.log(epu[idx]).diff().reindex(months).to_numpy()
    parts = {'beta': [], 'mkt': [], 'n': []}
    for i in range(0, W.shape[1], CHUNK):
      bu, bm, n = roll_beta(W.iloc[:, i:i + CHUNK], m, u, win, MIN_OBS[win])
      parts['beta'].append(bu); parts['mkt'].append(bm); parts['n'].append(n)
    out[name] = pd.DataFrame(np.hstack(parts['beta']), months, W.columns).stack()
    if name == 'epu_beta':
      out['mkt_beta60'] = pd.DataFrame(np.hstack(parts['mkt']), months, W.columns).stack()
      out['n_obs'] = pd.DataFrame(np.hstack(parts['n']), months, W.columns).stack()
  s = pd.concat(out, axis=1).rename_axis(['date', 'permno']).reset_index()
  s = s.merge(panel[['permno', 'date']], on=['permno', 'date']).dropna(subset=list(SIG), how='all')
  s['period_end'] = s['date'] - pd.offsets.MonthEnd(1)    # last EPU month used
  s['published_date'], s['date_source'], s['source'] = s['date'], 'assumed', SOURCE
  return s.sort_values(['permno', 'date']).reset_index(drop=True)

if __name__ == '__main__':
  p = pd.read_parquet(PANEL, columns=['permno', 'date', 'mthret'])
  p['permno'] = p['permno'].astype('int64')
  p['date'] = pd.to_datetime(p['date']) + pd.offsets.MonthEnd(0)
  p['mthret'] = pd.to_numeric(p['mthret'], errors='coerce').astype('float64')
  p = p.drop_duplicates(['permno', 'date'])
  epu = pd.read_csv('public_data/epu_monthly.csv', index_col='date', parse_dates=True)
  ff = pd.read_csv('public_data/ff_factors_monthly.csv', index_col='date', parse_dates=True)
  ff.index = ff.index + pd.offsets.MonthEnd(0)
  OUT.mkdir(parents=True, exist_ok=True)
  s = build(p, epu, ff)
  s.to_parquet(OUT / 'epu_beta_monthly.parquet', index=False)
  print(f'rows {len(s):,} | permnos {s.permno.nunique():,} | {s.date.min():%Y-%m} to {s.date.max():%Y-%m}')
  print(s[list(SIG) + ['mkt_beta60']].describe().round(3).to_string())
