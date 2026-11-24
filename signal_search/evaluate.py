"""Evaluation. Returns are compounded to annual holding years; volatility comes from monthly excess returns."""
import numpy as np, pandas as pd
from scipy import stats
from IPython.display import display

# ---- frequency helpers
def hold_year(index, form_month=12):
  """Formation year of the cohort that holds each month (Jan-Dec Y -> Y-1 when form_month=12)."""
  return (pd.DatetimeIndex(index) - pd.offsets.MonthEnd(form_month)).year

def to_annual(R, form_month=12):
  """Compound monthly returns within each holding year; keep full 12-month years; index = last month held."""
  yr = hold_year(R.index, form_month)
  A = (1 + R).groupby(yr).prod(min_count=1) - 1
  A = A.where(R.notna().groupby(yr).sum() == 12)
  A.index = pd.to_datetime([f'{y + 1}-{form_month:02d}-01' for y in A.index]) + pd.offsets.MonthEnd(0)
  return A.dropna(how='all')

def annual_factors(ff, form_month=12):
  """Annual factors: mktrf = compounded market minus compounded rf; long-short factors compounded."""
  rf = to_annual(ff[['rf']], form_month)['rf']
  mkt = to_annual((ff['mktrf'] + ff['rf']).to_frame('m'), form_month)['m'] - rf
  other = to_annual(ff.drop(columns=['mktrf', 'rf']), form_month)
  return other.assign(mktrf=mkt, rf=rf)

def excess(R, ff):
  """Subtract rf (same frequency as R)."""
  return R.sub(ff['rf'].reindex(R.index), axis=0)

# ---- statistics
def max_dd(r):
  """Largest peak-to-trough fall of the monthly wealth path."""
  w = (1 + r.fillna(0)).cumprod()
  return (w / w.cummax() - 1).min()

def nw_ols(y, X, lags=None):
  """OLS coefficients with Newey-West (Bartlett) and plain OLS t-stats; lags=None -> floor(4 (T/100)^(2/9))."""
  X = np.column_stack([np.ones(len(X)), X])
  T, k = X.shape
  if lags is None:
    lags = int(4 * (T / 100) ** (2 / 9))
  b = np.linalg.lstsq(X, y, rcond=None)[0]
  e = y - X @ b
  XtXi = np.linalg.inv(X.T @ X)
  S = (X * e[:, None]).T @ (X * e[:, None])
  for L in range(1, lags + 1):
    G = (X[L:] * e[L:, None]).T @ (X[:-L] * e[:-L, None])
    S += (1 - L / (lags + 1)) * (G + G.T)
  t_nw = b / np.sqrt(np.diag(XtXi @ S @ XtXi))
  t_ols = b / np.sqrt(np.diag(XtXi) * (e @ e) / (T - k))
  return b, t_nw, t_ols

def jk_test(a, b):
  """Jobson-Korkie/Memmel z for the difference of two Sharpe ratios."""
  a, b = np.asarray(a, dtype='float64'), np.asarray(b, dtype='float64')
  T = len(a)
  s1, s2 = a.mean() / a.std(ddof=1), b.mean() / b.std(ddof=1)
  rho = np.corrcoef(a, b)[0, 1]
  var = (2 - 2 * rho + 0.5 * (s1**2 + s2**2 - 2 * s1 * s2 * rho**2)) / T
  return (s1 - s2) / np.sqrt(var)

# ---- performance tables
def perf(R, ff, factors=('mktrf', 'smb', 'hml', 'umd'), bench='EW_UNIV', form_month=12):
  """Annual table: returns, alpha, t-stats per holding year; vol from monthly excess x sqrt(12); max DD monthly."""
  R = R.loc[R.index.intersection(ff.dropna(subset=list(factors) + ['rf']).index)]
  A, fa = to_annual(R, form_month), annual_factors(ff, form_month)
  exA, exM = excess(A, fa), excess(R, ff)
  yrM = pd.Series(hold_year(R.index, form_month), index=R.index)
  rows = {}
  for p in R.columns:
    e = exA[p].dropna()
    T = len(e)
    em = exM[p][yrM.isin(hold_year(e.index, form_month))].dropna()
    vol = em.std() * np.sqrt(12)
    sr = e.mean() / vol
    b, t, t_ols = nw_ols(e.to_numpy(), fa.loc[e.index, list(factors)].to_numpy())
    z = jk_test(*exA[[p, bench]].dropna().to_numpy().T) if bench in R and p != bench else np.nan
    rows[p] = {
      'years': T,
      'ann ret %': 100 * ((1 + A.loc[e.index, p]).prod() ** (1 / T) - 1),
      'mean excess %': 100 * e.mean(),
      'vol %': 100 * vol,
      'Sharpe': sr,
      'SE': np.sqrt((1 + 0.5 * sr**2) / T),
      f'z vs {bench}': z,
      'max DD %': 100 * max_dd(R[p]),
      'beta': b[1],
      'alpha %/yr': 100 * b[0], 't(alpha) NW': t[0], 't(alpha) OLS': t_ols[0],
    }
  return pd.DataFrame(rows).T

def perf_monthly(R, ff, factors=('mktrf', 'smb', 'hml', 'umd'), bench='EW_UNIV'):
  """Monthly-frequency table (the version checked against the book's tables)."""
  R = R.loc[R.index.intersection(ff.dropna(subset=list(factors) + ['rf']).index)]
  ex = excess(R, ff)
  rows = {}
  for p in R.columns:
    e = ex[p].dropna()
    r = R.loc[e.index, p]
    srm = e.mean() / e.std()
    b, t, t_ols = nw_ols(e.to_numpy(), ff.loc[e.index, list(factors)].to_numpy())
    z = jk_test(*ex[[p, bench]].dropna().to_numpy().T) if bench in R and p != bench else np.nan
    rows[p] = {
      'ann ret %': 100 * ((1 + r).prod() ** (12 / len(r)) - 1),
      'vol %': 100 * e.std() * np.sqrt(12),
      'Sharpe': srm * np.sqrt(12),
      'SE': np.sqrt((1 + 0.5 * srm**2) / len(e)) * np.sqrt(12),
      f'z vs {bench}': z,
      'max DD %': 100 * max_dd(R[p]),
      'beta': b[1],
      'alpha %/yr': 1200 * b[0], 't(alpha) NW': t[0], 't(alpha) OLS': t_ols[0],
    }
  return pd.DataFrame(rows).T

def split(R, cfg):
  """DESIGN, HOLDOUT, FULL, plus the reporting windows in cfg['windows']."""
  out = {'FULL': R, 'DESIGN': R[R.index <= cfg['design_end']], 'HOLDOUT': R[R.index > cfg['design_end']]}
  out.update({k: R.loc[a:b] for k, (a, b) in cfg.get('windows', {}).items()})
  return out

def report(R, data, cfg, periods=('DESIGN',)):
  """Print the annual table for each named period (design sample by default)."""
  for name in periods:
    P = split(R, cfg)[name]
    print(f'{name}: {P.index.min():%Y-%m} to {P.index.max():%Y-%m}, {len(P) // 12} years')
    display(perf(P, data.ff, cfg['factor_model'], form_month=cfg['form_month']))

# ---- multiple testing
def deflated_sharpe(sr, T, sk, ku, sr_trials, n_trials):
  """Bailey & Lopez de Prado (2014) DSR; all Sharpe ratios annual, T in years. Returns (DSR, hurdle)."""
  em = 0.5772156649
  sr0 = np.std(sr_trials, ddof=1) * ((1 - em) * stats.norm.ppf(1 - 1 / n_trials)
                                     + em * stats.norm.ppf(1 - 1 / (n_trials * np.e)))
  z = (sr - sr0) * np.sqrt(T - 1) / np.sqrt(1 - sk * sr + (ku - 1) / 4 * sr**2)
  return stats.norm.cdf(z), sr0

def dsr_table(R, data, cfg, strat_names):
  """DSR per strategy from the annual Sharpe in perf(); skew/kurtosis of annual excess returns."""
  P = perf(R[strat_names], data.ff, cfg['factor_model'], bench='none', form_month=cfg['form_month'])
  exA = excess(to_annual(R[strat_names], cfg['form_month']), annual_factors(data.ff, cfg['form_month']))
  out = {}
  for p in strat_names:
    e = exA[p].dropna()
    dsr, sr0 = deflated_sharpe(P.loc[p, 'Sharpe'], len(e), stats.skew(e), stats.kurtosis(e, fisher=False),
                               P['Sharpe'].to_numpy(), cfg['n_trials'])
    out[p] = {'Sharpe': P.loc[p, 'Sharpe'], 'SR hurdle': sr0, 'DSR': dsr}
  return pd.DataFrame(out).T

# ---- holdings descriptives
def name_turnover(hold, strat_names):
  """Average share of names replaced at each annual rebalance."""
  out = {}
  for p, d in hold[hold['port'].isin(strat_names)].groupby('port'):
    sets = d.groupby('cohort')['permno'].apply(set).sort_index()
    out[p] = np.mean([1 - len(a & b) / len(b) for a, b in zip(sets.iloc[:-1], sets.iloc[1:])])
  return pd.Series(out, name='share of names replaced per rebalance')

def weight_summary(hold, strat_names):
  """Median number of names and median largest weight per cohort."""
  h = hold[hold['port'].isin(strat_names)]
  g = h.groupby(['port', 'cohort'])['w0']
  return pd.DataFrame({'names (median)': g.size().groupby('port').median(),
                       'max weight (median)': g.max().groupby('port').median()})
