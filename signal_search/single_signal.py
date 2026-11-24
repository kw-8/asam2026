"""One-signal tests: coverage, the p.258 screen, a top-minus-bottom spread, Fama-MacBeth, comovement."""
import numpy as np, pandas as pd
from scipy import stats
from .portfolio import Strategy, form_universe, rank, build_holdings, bh_returns
from .evaluate import to_annual, annual_factors, nw_ols, deflated_sharpe
from .diagnostics import screen, fama_macbeth, comove, _in_period

CONTROLS = {'vol36': False, 'gprof': True, 'debt_at': False, 'ep': True, 'mom': True, 'me': False, 'bm': True}

def add_signal(crsp, path, cols):
  """Left-merge signal columns from a permno x month-end file (parquet or csv) into the panel."""
  s = pd.read_parquet(path) if str(path).endswith('.parquet') else pd.read_csv(path, parse_dates=['date'])
  s = s[['permno', 'date', *cols]].copy()
  s['permno'] = s['permno'].astype('int64')
  s['date'] = pd.to_datetime(s['date']) + pd.offsets.MonthEnd(0)
  return crsp.drop(columns=[c for c in cols if c in crsp]).merge(s, on=['permno', 'date'], how='left')

def coverage(col, data, cfg):
  """Per formation cohort: universe size, stocks with the signal, and their share of universe market cap."""
  f = form_universe(data.crsp, cfg['form_month'], cfg)
  has = f[col].notna()
  return pd.DataFrame({'universe': f.groupby('cohort').size(), 'with signal': has.groupby(f['cohort']).sum(),
                       'cap share': f['me'].where(has, 0).groupby(f['cohort']).sum() / f.groupby('cohort')['me'].sum()})

def zip_stats(z, fa, factors):
  """Mean, Sharpe, NW alpha and t of an annual zero-investment return series z."""
  z = z.dropna()
  if len(z) < 4:
    return {'years': len(z)}
  b, t, t_ols = nw_ols(z.to_numpy(), fa.loc[z.index, list(factors)].to_numpy())
  return {'years': len(z), 'mean %/yr': 100 * z.mean(), 't(mean) NW': nw_ols(z.to_numpy(), np.empty((len(z), 0)))[1][0],
          'Sharpe': z.mean() / z.std(), 'alpha %/yr': 100 * b[0], 't(alpha) NW': t[0], 't(alpha) OLS': t_ols[0],
          'share of years > 0': (z > 0).mean()}

def spread(col, higher_better, data, cfg, q=0.2, weight='EW', period=None):
  """Annual top-q minus bottom-q return (hold-year compounded) and its stats; period=None keeps all years."""
  f = form_universe(data.crsp, cfg['form_month'], cfg)
  r = rank(f, col, higher_better)
  legs = [Strategy('top', lambda g: r.loc[g.index].where(r.loc[g.index] > 1 - q), weight, n=10**9, sector_cap=1.0),
          Strategy('bot', lambda g: (-r.loc[g.index]).where(r.loc[g.index] <= q), weight, n=10**9, sector_cap=1.0)]
  A = to_annual(bh_returns(build_holdings(f, legs, data, cfg, add_ew_univ=False), data.ret_lookup, cfg['horizon']),
                cfg['form_month'])
  z = (A['top'] - A['bot']).dropna()
  if period is not None:
    z = z[_in_period(z.index, cfg, period)]
  fa = annual_factors(data.ff, cfg['form_month'])
  return z, zip_stats(z, fa, cfg['factor_model'])

def dsr_haircut(sr, z, sr_trials, n_trials):
  """Deflated Sharpe of one annual ZIP (sr per year) against the spread of all trials' Sharpe ratios."""
  return deflated_sharpe(sr, len(z), stats.skew(z), stats.kurtosis(z, fisher=False), sr_trials, n_trials)

def test_signal(col, higher_better, data, cfg, controls=None, q=0.2, period='DESIGN', comove_with=None):
  """All one-signal tests on one period; returns a dict of tables (nothing printed)."""
  controls = {c: hb for c, hb in (CONTROLS if controls is None else controls).items() if c in data.crsp and c != col}
  out = {'coverage': coverage(col, data, cfg)}
  out['screen'] = screen({col: higher_better}, data, cfg, q=q, period=period)
  z, s = spread(col, higher_better, data, cfg, q=q, period=period)
  out['spread'], out['spread_series'] = pd.DataFrame({f'{col} top-bottom q={q:.2f}': s}).T, z
  out['fm_alone'], _ = fama_macbeth({col: higher_better}, data, cfg, period=period)
  out['fm_controls'], out['fm_slopes'] = fama_macbeth({col: higher_better, **controls}, data, cfg, period=period)
  if comove_with:
    start = pd.Timestamp(cfg['first_form']) - pd.offsets.MonthEnd(1)
    panel = data.crsp.loc[data.crsp[col].notna(), ['date', col, *comove_with]]
    _, wide, _ = comove(panel, [col, *comove_with], start=start)
    out['comove'] = wide[[c for c in wide if c.startswith(col + '~')]].mean().rename('mean Spearman').to_frame()
  return out
