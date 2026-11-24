"""Signal diagnostics: sanity screen, annual Fama-MacBeth, and signal comovement."""
from itertools import combinations
import numpy as np, pandas as pd
from .portfolio import Strategy, form_universe, rank, build_holdings, bh_returns
from .evaluate import to_annual, annual_factors, nw_ols, split

def _in_period(dates, cfg, period):
  """Boolean mask: which hold-end dates fall in the named period (DESIGN, HOLDOUT, FULL, or a window)."""
  s = pd.Series(1, index=pd.DatetimeIndex(dates)).sort_index()
  keep = split(s, cfg)[period].index
  return pd.DatetimeIndex(dates).isin(keep)

def _leg(col, higher_better, top, q):
  """Score for one screen leg: the top (or bottom) q of the cohort by the signal; NaN elsewhere."""
  def score(f):
    r = rank(f, col, higher_better)
    return r.where(r > 1 - q) if top else (-r).where(r <= q)
  return score

def screen(spec, data, cfg, q=0.2, period='DESIGN', rule='A'):
  """Book p.258 screen: fail a signal if SHORTING it (bottom q minus top q, EW, annual) earns positive alpha consistently."""
  f = form_universe(data.crsp, cfg['form_month'], cfg)
  legs = []
  for col, hb in spec.items():
    legs += [Strategy(f'{col}|top', _leg(col, hb, True, q), 'EW', n=10**9, sector_cap=1.0),
             Strategy(f'{col}|bot', _leg(col, hb, False, q), 'EW', n=10**9, sector_cap=1.0)]
  hold = build_holdings(f, legs, data, cfg, add_ew_univ=False)
  A = to_annual(bh_returns(hold, data.ret_lookup, cfg['horizon']), cfg['form_month'])
  A = A[_in_period(A.index, cfg, period)]
  fa = annual_factors(data.ff, cfg['form_month']).reindex(A.index)
  rows = {}
  for col in spec:
    z = (A[f'{col}|bot'] - A[f'{col}|top']).dropna()           # short-the-signal ZIP, one return per year
    b, t, t_ols = nw_ols(z.to_numpy(), fa.loc[z.index, cfg['factor_model']].to_numpy())
    fail_A = (b[0] > 0) and (t[0] > 2)                          # rule A: significant positive alpha
    fail_B = (z > 0).mean() > 0.5                               # rule B: short side wins in most years
    rows[col] = {'years': len(z), 'short ZIP mean %/yr': 100 * z.mean(), 'alpha %/yr': 100 * b[0],
                 't(alpha) NW': t[0], 't(alpha) OLS': t_ols[0], 'share of years short wins': (z > 0).mean(),
                 'verdict': 'FAIL' if (fail_A if rule == 'A' else fail_B) else 'pass',
                 'flag': 'short side wins most years (rule B)' if fail_B else ''}
  return pd.DataFrame(rows).T

def hold_returns(f, data, horizon=12):
  """Each stock's buy-and-hold return over its hold year; 0% after its first missing month, as in bh_returns."""
  h = f[['cohort', 'permno']].merge(pd.DataFrame({'k': np.arange(1, horizon + 1)}), how='cross')
  h['date'] = (h['cohort'].dt.to_period('M') + h['k']).dt.to_timestamp(how='end').dt.normalize()
  h = h.merge(data.ret_lookup, on=['permno', 'date'], how='left').sort_values(['cohort', 'permno', 'k'])
  key = [h['cohort'], h['permno']]
  alive = h['mthret'].notna().astype(int).groupby(key).cumprod().astype(bool)
  out = (1 + h['mthret'].where(alive, 0.0)).groupby(key).prod() - 1
  out[~alive.groupby(key).first()] = np.nan                     # no return in the first month: not investable
  return f[['cohort', 'permno']].merge(out.rename('ret_hold').reset_index(), on=['cohort', 'permno'], how='left')['ret_hold']

def fama_macbeth(spec, data, cfg, period='DESIGN'):
  """Annual Fama-MacBeth: each cohort, regress hold-year return on ALL signals' percentile ranks together; NW t on yearly slopes."""
  f = form_universe(data.crsp, cfg['form_month'], cfg)
  last = data.crsp['date'].max() - pd.offsets.MonthEnd(cfg['horizon'])
  f = f[f['cohort'] <= last].reset_index(drop=True)             # cohorts with a full hold year of data
  X = pd.concat({c: rank(f, c, hb) for c, hb in spec.items()}, axis=1)
  d = pd.concat([f[['cohort']], X, hold_returns(f, data, cfg['horizon']).rename('y')], axis=1).dropna()
  cols = list(spec)
  rows = {}
  for c, g in d.groupby('cohort'):
    Z = np.column_stack([np.ones(len(g)), g[cols].to_numpy()])
    b, *_ = np.linalg.lstsq(Z, g['y'].to_numpy(), rcond=None)
    e = g['y'].to_numpy() - Z @ b
    rows[c + pd.offsets.MonthEnd(cfg['horizon'])] = dict(zip(['const'] + cols, b), R2=1 - e.var() / g['y'].var(ddof=0), n=len(g))
  slopes = pd.DataFrame(rows).T
  slopes = slopes[_in_period(slopes.index, cfg, period)]
  summ = {}
  for c in cols:
    b, t, t_ols = nw_ols(slopes[c].to_numpy(), np.empty((len(slopes), 0)))
    summ[c] = {'slope %/yr (top vs bottom rank)': 100 * b[0], 't NW': t[0], 't OLS': t_ols[0], 'years': len(slopes)}
  summ = pd.DataFrame(summ).T
  summ.attrs['avg R2'] = slopes['R2'].mean()
  return summ, slopes

def comove(panel, signals, start=None, min_stocks=30):
  """Monthly cross-sectional Spearman corr per signal pair, then mean over the 12 months of each year."""
  if start is not None:
    panel = panel[panel['date'] > pd.Timestamp(start)]
  rows = []
  for month, stocks in panel.groupby('date'):              # stocks: all rows in that month
    for s1, s2 in combinations(signals, 2):                # every pair of signals
      both = stocks[[s1, s2]].dropna()                     # stocks with both signals
      if len(both) >= min_stocks:
        rho = both[s1].rank().corr(both[s2].rank())        # Spearman = Pearson on ranks
        rows.append({'date': month, 'pair': f'{s1}~{s2}', 'rho': rho, 'n_stocks': len(both)})
  monthly = pd.DataFrame(rows)
  monthly['year'] = monthly['date'].dt.year
  annual = monthly.groupby(['year', 'pair'])['rho'].agg(rho='mean', sd='std', months='size')
  annual_wide = annual['rho'].unstack('pair')              # year x pair table of mean rho
  return monthly, annual_wide, annual
