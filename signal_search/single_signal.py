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

# ---- monthly mode: formation every month-end, so annual and monthly runs of one signal can be compared ----

def legs(f, col, higher_better, q=0.2, weight='EW', avoid=False):
  """Top-q and bottom-q legs (avoid=True: universe without the bottom q, and the whole universe)."""
  r = rank(f, col, higher_better)                           # high rank = good side of the signal
  if avoid:
    return [Strategy('long', lambda g: pd.Series(1.0, g.index).where(~(r.loc[g.index] <= q)), weight, n=10**9, sector_cap=1.0),
            Strategy('short', lambda g: pd.Series(1.0, g.index), weight, n=10**9, sector_cap=1.0)]
  return [Strategy('long', lambda g: r.loc[g.index].where(r.loc[g.index] > 1 - q), weight, n=10**9, sector_cap=1.0),
          Strategy('short', lambda g: (-r.loc[g.index]).where(r.loc[g.index] <= q), weight, n=10**9, sector_cap=1.0)]

def zip_returns(f, col, higher_better, data, cfg, horizon, q=0.2, weight='EW', avoid=False):
  """Monthly long-minus-short returns of buy-and-hold cohorts formed in f."""
  R = bh_returns(build_holdings(f, legs(f, col, higher_better, q, weight, avoid), data, cfg, add_ew_univ=False),
                 data.ret_lookup, horizon)
  return (R['long'] - R['short']).dropna()

def monthly_universe(data, cfg, first_form=None):
  """Formation universe at every month-end (form_universe for months 1-12, stacked)."""
  c = cfg if first_form is None else {**cfg, 'first_form': first_form}
  return pd.concat([form_universe(data.crsp, m, c) for m in range(1, 13)], ignore_index=True)

def monthly_stats(z, ff, factors):
  """Monthly ZIP z: annualized mean, NW t, alpha with NW and OLS t, annualized Sharpe, share of months > 0."""
  z = z[z.index.isin(ff.dropna().index)]
  if len(z) < 12:
    return {'months': len(z)}
  b, t, t_ols = nw_ols(z.to_numpy(), ff.loc[z.index, list(factors)].to_numpy())
  return {'months': len(z), 'mean %/yr': 1200 * z.mean(), 't(mean) NW': nw_ols(z.to_numpy(), np.empty((len(z), 0)))[1][0],
          'alpha %/yr': 1200 * b[0], 't(alpha) NW': t[0], 't(alpha) OLS': t_ols[0], 'Sharpe': np.sqrt(12) * z.mean() / z.std(),
          'share > 0': (z > 0).mean()}

def by_period(z, fn, cfg):
  """fn on DESIGN, HOLDOUT, FULL (split of z's dates at cfg['design_end'])."""
  return {'DESIGN': fn(z[z.index <= cfg['design_end']]), 'HOLDOUT': fn(z[z.index > cfg['design_end']]), 'FULL': fn(z)}

def decay(f, col, higher_better, data, cfg, ks=(1, 2, 3, 6, 12), q=0.2, weight='EW'):
  """Long-minus-short return in month k after formation only, for each k (cohorts in f)."""
  h = build_holdings(f, legs(f, col, higher_better, q, weight), data, cfg, add_ew_univ=False)
  out = {}
  for k in ks:
    R = bh_returns(h.assign(cohort=h['cohort'] + pd.offsets.MonthEnd(k - 1)), data.ret_lookup, 1)   # skip k-1 months
    z = (R['long'] - R['short']).dropna()
    out[f'month {k}'] = {'mean %/yr': 1200 * z.mean(), 't NW': nw_ols(z.to_numpy(), np.empty((len(z), 0)))[1][0]}
  return pd.DataFrame(out).T

def compare(col, higher_better, data, cfg, q=0.2, weight='EW', avoid=False, first_form_monthly=None):
  """Annual (form_month, 12-month hold) vs monthly (every month-end, 1-month hold) ZIP by period, one table."""
  zA = to_annual(zip_returns(form_universe(data.crsp, cfg['form_month'], cfg), col, higher_better, data, cfg,
                             cfg['horizon'], q, weight, avoid).to_frame('z'), cfg['form_month'])['z'].dropna()
  zM = zip_returns(monthly_universe(data, cfg, first_form_monthly), col, higher_better, data, cfg, 1, q, weight, avoid)
  fa = annual_factors(data.ff, cfg['form_month'])
  rows = {}
  for p, s in by_period(zA, lambda z: zip_stats(z, fa, cfg['factor_model']), cfg).items():
    rows[('annual', p)] = {'n': s.pop('years'), **{k.replace('share of years > 0', 'share > 0'): v for k, v in s.items()}}
  for p, s in by_period(zM, lambda z: monthly_stats(z, data.ff, cfg['factor_model']), cfg).items():
    rows[('monthly', p)] = {'n': s.pop('months'), **s}
  cols = ['n', 'mean %/yr', 't(mean) NW', 'alpha %/yr', 't(alpha) NW', 't(alpha) OLS', 'Sharpe', 'share > 0']
  return pd.DataFrame(rows).T.reindex(columns=cols), zA, zM
