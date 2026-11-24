"""Per-permno signal helpers (rolling stats, lags, momentum), FF12 sectors, VW market."""
import numpy as np, pandas as pd

def by_permno(crsp, col):
  return crsp.groupby('permno', sort=False)[col]

def roll(crsp, col, win, fn='mean', min_periods=None):
  # rolling stat per permno, aligned to crsp rows; fn = 'mean', 'std', 'sum', 'max', ...
  r = by_permno(crsp, col).rolling(win, min_periods=min_periods or win)
  return getattr(r, fn)().reset_index(level=0, drop=True)

def lag(crsp, col, k=1):
  return by_permno(crsp, col).shift(k)

def add_volatility(crsp, win=36, min_periods=24, name='vol36'):
  crsp[name] = roll(crsp, 'mthret', win, 'std', min_periods)
  return crsp

def add_momentum(crsp, skip=1, look=11, name='mom'):
  # cumulative return over months t-look-skip+1 ... t-skip (default 12-1), requiring no calendar gaps
  mi = crsp['date'].dt.year * 12 + crsp['date'].dt.month
  lr = np.log1p(lag(crsp, 'mthret', skip))
  s = lr.groupby(crsp['permno'], sort=False).rolling(look, min_periods=look).sum().reset_index(level=0, drop=True)
  gm = mi.groupby(crsp['permno'])
  span = gm.shift(skip) - gm.shift(skip + look - 1)
  gap = mi - gm.shift(skip)
  crsp[name] = np.where((span == look - 1) & (gap == skip), np.expm1(s), np.nan)
  return crsp

FF12 = {
  'NoDur': [(100, 999), (2000, 2399), (2700, 2749), (2770, 2799), (3100, 3199), (3940, 3989)],
  'Durbl': [(2500, 2519), (2590, 2599), (3630, 3659), (3710, 3711), (3714, 3714), (3716, 3716),
       (3750, 3751), (3792, 3792), (3900, 3939), (3990, 3999)],
  'Manuf': [(2520, 2589), (2600, 2699), (2750, 2769), (3000, 3099), (3200, 3569), (3580, 3629),
       (3700, 3709), (3712, 3713), (3715, 3715), (3717, 3749), (3752, 3791), (3793, 3799),
       (3830, 3839), (3860, 3899)],
  'Enrgy': [(1200, 1399), (2900, 2999)],
  'Chems': [(2800, 2829), (2840, 2899)],
  'BusEq': [(3570, 3579), (3660, 3692), (3694, 3699), (3810, 3829), (7370, 7379)],
  'Telcm': [(4800, 4899)],
  'Utils': [(4900, 4949)],
  'Shops': [(5000, 5999), (7200, 7299), (7600, 7699)],
  'Hlth':  [(2830, 2839), (3693, 3693), (3840, 3859), (8000, 8099)],
  'Money': [(6000, 6999)],
}

def add_ff12(crsp, name='sector'):
  sic = pd.to_numeric(crsp['siccd'], errors='coerce')
  out = np.full(len(crsp), 'Other', dtype=object)
  for sec, ranges in FF12.items():
    m = np.zeros(len(crsp), bool)
    for lo, hi in ranges:
      m |= sic.between(lo, hi).to_numpy()
    out[m] = sec
  crsp[name] = out
  return crsp

def vw_market(crsp):
  v = crsp.dropna(subset=['mthret', 'me_lag'])
  v = v[v['me_lag'] > 0]
  return (v['mthret'] * v['me_lag']).groupby(v['date']).sum() / v['me_lag'].groupby(v['date']).sum()
