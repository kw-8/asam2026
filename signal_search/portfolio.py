"""Universe, scoring helpers, selection, weights, Strategy, buy-and-hold engine."""
from dataclasses import dataclass
from types import SimpleNamespace
import numpy as np, pandas as pd
from scipy import optimize
from .signals import vw_market

def form_universe(crsp, form_month, cfg):
  f = crsp[crsp['date'].dt.month == form_month].dropna(subset=['me', 'prc', *cfg['universe_needs']])
  f = f[(f['prc'].abs() >= cfg['min_price']) & (f['date'] >= pd.Timestamp(cfg['first_form']))]
  bp = f[f['primaryexch'] == 'N'].groupby('date')['me'].quantile(cfg['size_pct']).rename('me_bp')
  f = f.merge(bp, on='date')
  f = f[f['me'] >= f['me_bp']]
  return f.rename(columns={'date': 'cohort'}).reset_index(drop=True)

# ---- scoring helpers (all return Series aligned to f)
def rank(f, col, higher_better=True):
  return f.groupby('cohort')[col].rank(pct=True, ascending=higher_better)

def composite(f, spec, weights=None):
  # spec = {'vol36': False, 'gprof': True, ...}; True means higher is better. NaN if any input missing.
  R = pd.concat({c: rank(f, c, hb) for c, hb in spec.items()}, axis=1)
  if weights is None:
    return R.mean(axis=1, skipna=False)
  w = pd.Series(weights, dtype=float).reindex(R.columns)
  return R.mul(w, axis=1).sum(axis=1, min_count=len(w)) / w.sum()

def mom_ok(f, pct=0.10, col='mom'):
  return rank(f, col) > pct           # NaN momentum -> False

# ---- selection
def select(f, score, n, cap=None):
  # top-n per cohort by score with at most floor(cap*n) names per sector (greedy, vectorized)
  d = f.assign(_score=score).dropna(subset=['_score'])
  d = d.sort_values(['cohort', '_score', 'permno'], ascending=[True, False, True])   # ties -> lower permno
  if cap is not None and cap < 1:
    max_per = max(1, int(np.floor(cap * n)))
    d = d[d.groupby(['cohort', 'sector']).cumcount() < max_per]
  return d.groupby('cohort').head(n)

# ---- weights
def w_equal(sel, data, cfg):
  return pd.Series(1.0, index=sel.index)

def w_invvol(sel, data, cfg, col='vol36'):
  return 1 / sel[col]

def w_value(sel, data, cfg):
  return sel['me']

def shrunk_cov(R, shrink):
  S = R.cov(min_periods=24)
  sd = np.sqrt(np.diag(S.fillna(0).to_numpy()))
  sd = np.where(sd > 0, sd, np.nanmedian(sd[sd > 0]))
  C = S.to_numpy() / np.outer(sd, sd)
  rbar = np.nanmean(C[~np.eye(len(C), dtype=bool)])
  C = np.where(np.isnan(C), rbar, C)
  np.fill_diagonal(C, 1.0)
  C = (1 - shrink) * C + shrink * (rbar + (1 - rbar) * np.eye(len(C)))
  Sig = C * np.outer(sd, sd)
  ev, V = np.linalg.eigh(Sig)
  return (V * np.maximum(ev, 1e-4 * ev.max())) @ V.T

def min_var_weights(cohort, permnos, data, cfg):
  start = cohort - pd.offsets.MonthEnd(cfg['cov_win'] - 1)
  R = data.ret_by_date.loc[start:cohort]
  R = R[R['permno'].isin(permnos)].pivot_table(index='date', columns='permno', values='mthret')
  Sig = shrunk_cov(R.reindex(columns=permnos), cfg['shrink'])
  n = len(permnos)
  cap = max(cfg['mv_cap'], 1.0 / n)
  res = optimize.minimize(lambda w: w @ Sig @ w, np.full(n, 1 / n), jac=lambda w: 2 * Sig @ w,
              bounds=[(0, cap)] * n, constraints=[{'type': 'eq', 'fun': lambda w: w.sum() - 1}],
              method='SLSQP', options={'maxiter': 500, 'ftol': 1e-12})
  w = np.clip(res.x, 0, None)
  return w / w.sum()

def w_minvar(sel, data, cfg):
  parts = [pd.Series(min_var_weights(c, d['permno'].tolist(), data, cfg), index=d.index)
      for c, d in sel.groupby('cohort')]
  return pd.concat(parts)

WEIGHTS = {'EW': w_equal, 'IV': w_invvol, 'VW': w_value, 'MV': w_minvar}

@dataclass
class Strategy:
  name: str
  score: object                 # fn(f) -> Series, higher = better, NaN = ineligible
  weight: object = 'EW'         # 'EW' | 'IV' | 'VW' | 'MV' | fn(sel, data, cfg) -> Series
  n: int = None                 # default cfg['n_hold']
  sector_cap: float = None      # default cfg['sector_cap']; 1.0 = no cap

def prepare(crsp, ff):
  return SimpleNamespace(
    crsp=crsp, ff=ff,
    ret_lookup=crsp[['permno', 'date', 'mthret']],
    ret_by_date=crsp.set_index('date')[['permno', 'mthret']].sort_index(),
    vw_mkt=vw_market(crsp),
  )

def build_holdings(f, strategies, data, cfg, add_ew_univ=True):
  parts = []
  for s in strategies:
    n = s.n or cfg['n_hold']
    cap = cfg['sector_cap'] if s.sector_cap is None else s.sector_cap
    sel = select(f, s.score(f), n, cap)
    wfn = WEIGHTS[s.weight] if isinstance(s.weight, str) else s.weight
    w = pd.Series(wfn(sel, data, cfg), index=sel.index).astype('float64')
    parts.append(sel[['cohort', 'permno']].assign(w0=w, port=s.name))
  if add_ew_univ:
    parts.append(f[['cohort', 'permno']].assign(w0=1.0, port='EW_UNIV'))
  h = pd.concat(parts, ignore_index=True)
  h['w0'] = h['w0'] / h.groupby(['port', 'cohort'])['w0'].transform('sum')
  return h

def bh_returns(holdings, ret_lookup, horizon=12):
  h = holdings.merge(pd.DataFrame({'k': np.arange(1, horizon + 1)}), how='cross')
  h['date'] = (h['cohort'].dt.to_period('M') + h['k']).dt.to_timestamp(how='end').dt.normalize()
  h = h.merge(ret_lookup, on=['permno', 'date'], how='left').sort_values(['port', 'cohort', 'permno', 'k'])
  key = [h['port'], h['cohort'], h['permno']]
  h['alive'] = h['mthret'].notna().astype(int).groupby(key).cumprod().astype(bool)
  r = h['mthret'].where(h['alive'], 0.0)
  growth = (1 + r).groupby(key).cumprod()
  h['v'] = (h['w0'] * growth / (1 + r)).where(h['alive'], 0.0)
  h['vr'] = h['v'] * r
  agg = h.groupby(['port', 'date']).agg(vr=('vr', 'sum'), v=('v', 'sum'))
  return (agg['vr'] / agg['v']).unstack('port')

def run(strategies, data, cfg, form_month=None):
  # returns (monthly returns: strategies + EW_UNIV + VW_MKT, holdings, formation universe)
  f = form_universe(data.crsp, form_month or cfg['form_month'], cfg)
  hold = build_holdings(f, strategies, data, cfg)
  rets = bh_returns(hold, data.ret_lookup, cfg['horizon']).dropna(subset=['EW_UNIV'])
  rets['VW_MKT'] = data.vw_mkt.reindex(rets.index)
  cols = [s.name for s in strategies] + ['EW_UNIV', 'VW_MKT']
  return rets[cols], hold, f
