"""Fake panel, factors and ETFs for testing the code without the real data."""
import numpy as np, pandas as pd
from .data import clean_panel
from .signals import vw_market

def make_synthetic_panel(n_firms=1500, start='1975-01-31', end='2025-12-31', seed=0):
  rng = np.random.default_rng(seed)
  dates = pd.date_range(start, end, freq='ME'); T = len(dates)
  mkt = rng.normal(0.007, 0.045, T)
  vol_i  = rng.lognormal(np.log(0.08), 0.45, n_firms)          # idiosyncratic monthly vol
  beta   = np.clip(0.6 + 4 * vol_i + rng.normal(0, 0.2, n_firms), 0.2, 2.5)
  gprof0 = rng.normal(0.3, 0.25, n_firms)
  debt0  = rng.beta(2, 6, n_firms)
  ep0    = rng.normal(0.04, 0.06, n_firms)
  # small "defensive" premium: profitable, low-debt, cheap names earn a bit more
  alpha = 0.002 * (gprof0 - 0.3) / 0.25 - 0.001 * (debt0 - 0.25) / 0.15 + 0.001 * (ep0 - 0.04) / 0.06
  R = beta[None, :] * mkt[:, None] + alpha[None, :] + vol_i[None, :] * rng.standard_normal((T, n_firms))
  R = np.maximum(R, -0.95)
  entry = rng.integers(-T // 2, T - 40, n_firms).clip(0)
  exit_ = np.minimum(entry + rng.integers(60, 2 * T, n_firms), T)
  t = np.arange(T)[:, None]
  alive = (t >= entry) & (t < exit_)
  me0 = rng.lognormal(np.log(800), 1.5, n_firms) * 1e3                  # $000s, as in CRSP
  me = me0 * np.cumprod(1 + np.where(alive, R, 0), axis=0)
  shares = me0 / rng.uniform(8, 80, n_firms)
  drift = lambda x0, s: x0 + np.cumsum(rng.normal(0, s, (T, n_firms)), axis=0) * 0.1
  sic_pool = np.array([2000, 2500, 3500, 1300, 2810, 3570, 4810, 4910, 5300, 2834, 6020, 7000, 1500])
  df = pd.DataFrame({
    'permno': np.tile(np.arange(10000, 10000 + n_firms), T),
    'date': np.repeat(dates, n_firms),
    'primaryexch': np.tile(np.where(rng.random(n_firms) < 0.4, 'N', 'Q'), T),
    'siccd': np.tile(rng.choice(sic_pool, n_firms), T).astype(float),
    'mthret': R.ravel(),
    'prc': (me / shares).ravel(),
    'me': me.ravel(),
    'me_lag': np.vstack([np.full(n_firms, np.nan), me[:-1]]).ravel(),
    'gprof': drift(gprof0, 0.02).ravel(),
    'debt_at': np.clip(drift(debt0, 0.01), 0, None).ravel(),
    'ep': drift(ep0, 0.005).ravel(),
    'ticker': np.tile([f'S{i:04d}' for i in range(n_firms)], T),
  })
  df = df[alive.ravel()]
  return clean_panel(df)

def make_synthetic_factors(crsp, seed=1):
  rng = np.random.default_rng(seed)
  vw = vw_market(crsp)
  ff = pd.DataFrame({'rf': 0.003}, index=vw.index)
  ff['mktrf'] = vw - ff['rf']
  for c in ['smb', 'hml', 'umd']:
    ff[c] = rng.normal(0.002, 0.03, len(ff))
  return ff

def make_synthetic_etfs(index, seed=2):
  rng = np.random.default_rng(seed)
  idx = index[index >= '2002-07-31']
  return pd.DataFrame({'IEF': rng.normal(0.003, 0.019, len(idx)),
            'TLT': rng.normal(0.004, 0.038, len(idx)),
            'GLD': rng.normal(0.007, 0.048, len(idx))}, index=idx)
