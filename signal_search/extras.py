"""Robustness (formation month, staggered cohorts), multi-asset mix, and the current portfolio."""
import numpy as np, pandas as pd
from .portfolio import run, form_universe, select, build_holdings
from .evaluate import perf

def by_formation_month(strategies, data, cfg, months=range(1, 13)):
  """Annual Sharpe per formation month, plus the staggered portfolio (average of the 12 monthly-formed books)."""
  names = [s.name for s in strategies] + ['EW_UNIV']
  sharpe, stag = {}, []
  for fm in months:
    r, _, _ = run(strategies, data, {**cfg, 'form_month': fm})
    sharpe[fm] = perf(r[names], data.ff, cfg['factor_model'], form_month=fm)['Sharpe']
    stag.append(r[names])
  stag = pd.concat(stag).groupby(level=0).mean()
  stag = stag[stag.index >= pd.Timestamp(cfg['first_form']) + pd.offsets.MonthEnd(12)]
  stag_tbl = perf(stag, data.ff, cfg['factor_model'], form_month=12)[['Sharpe', 'z vs EW_UNIV']]
  return pd.DataFrame(sharpe).T.rename_axis('formation month'), stag_tbl

def bh_mix(R, W, horizon=12):
  """Buy-and-hold mix of sleeves. R: monthly sleeve returns; W: initial weights per cohort (index = formation dates)."""
  out = []
  for c, w in W.iterrows():
    dates = pd.date_range(c + pd.offsets.MonthEnd(1), periods=horizon, freq='ME')
    r = R.reindex(dates)[w.index].fillna(0.0)
    v = w.to_numpy() * np.vstack([np.ones(len(w)), (1 + r).cumprod().to_numpy()[:-1]])
    out.append(pd.Series((v * r.to_numpy()).sum(1) / v.sum(1), index=dates))
  return pd.concat(out)

def multi_asset(rets, etf_r, data, cfg, stock_sleeve, etfs=('IEF', 'GLD'), start='2006-12-31', vol_win=36):
  """Inverse-vol mix of the stock sleeve and ETFs vs a 60/40 EW_UNIV/bond mix, rebalanced each December."""
  S = pd.concat([rets[[stock_sleeve, 'EW_UNIV']], etf_r[list(etfs)]], axis=1)
  cohorts = list(pd.date_range(start, rets.index.max() - pd.offsets.MonthEnd(1), freq='12ME'))
  vol = S.rolling(vol_win, min_periods=24).std()
  W_rp = 1 / vol.loc[cohorts, [stock_sleeve, *etfs]]
  W_rp = W_rp.div(W_rp.sum(axis=1), axis=0)
  W_6040 = pd.DataFrame({'EW_UNIV': 0.6, etfs[0]: 0.4}, index=cohorts)
  M = pd.DataFrame({'MULTI_RP': bh_mix(S, W_rp), '60/40': bh_mix(S, W_6040)})
  M = M.join(S[[stock_sleeve, 'EW_UNIV', *etfs]]).dropna()
  tbl = perf(M, data.ff, cfg['factor_model'], form_month=12)
  return M, tbl[['years', 'ann ret %', 'vol %', 'Sharpe', 'z vs EW_UNIV', 'max DD %']], W_rp

def current_portfolio(strategy, data, cfg, names=None, show_cols=('vol36', 'gprof', 'debt_at', 'ep', 'me', 'prc')):
  """Form the strategy on the latest month in the panel (same screens/score/cap/weights as the backtest)."""
  latest = data.crsp['date'].max()
  f_now = form_universe(data.crsp, latest.month, cfg)
  f_now = f_now[f_now['cohort'] == latest]
  print(f'Formation date: {latest:%Y-%m-%d} | eligible: {len(f_now)} | scored: {strategy.score(f_now).notna().sum()}')
  if latest.month != cfg['form_month']:
    print(f'Note: strategy forms in month {cfg["form_month"]}; this is a preview on the latest month.')
  f_now = f_now.assign(score=strategy.score(f_now))
  h = build_holdings(f_now, [strategy], data, cfg, add_ew_univ=False)
  rec = h.merge(f_now, on=['cohort', 'permno'])
  if names is not None:
    rec = rec.drop(columns=[c for c in names.columns if c in rec and c != 'permno']).merge(names, on='permno', how='left')
  id_cols = [c for c in ['ticker', 'company', 'comnam', 'conm'] if c in rec]
  rec = rec.sort_values('score', ascending=False).reset_index(drop=True)
  rec.index += 1
  out = rec[['permno', *id_cols, 'sector', 'w0', 'score', *[c for c in show_cols if c in rec]]].copy()
  out['w0'] *= 100
  out = out.rename(columns={'w0': 'weight %'})

  # changes vs last year's portfolio formed in the same month
  prev = latest - pd.offsets.MonthEnd(12)
  f_prev = form_universe(data.crsp, prev.month, cfg)
  f_prev = f_prev[f_prev['cohort'] == prev]
  if len(f_prev):
    p = set(select(f_prev, strategy.score(f_prev), strategy.n or cfg['n_hold'],
                   cfg['sector_cap'] if strategy.sector_cap is None else strategy.sector_cap)['permno'])
    c = set(out['permno'])
    print(f'vs {prev:%Y-%m}: keep {len(c & p)}, buy {len(c - p)}, sell {len(p - c)}')
    if id_cols:
      print('new buys:', sorted(out.loc[out['permno'].isin(c - p), id_cols[0]].dropna().astype(str)))
  return out, f_now
