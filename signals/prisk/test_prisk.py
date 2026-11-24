"""PRisk single-signal tests (pre-registered in progress.md) + joint Fama-MacBeth with earnings stability.

Run from the repo root: python signals/prisk/test_prisk.py
In:  data/prisk/prisk_monthly.parquet, data/earn_stability/earn_stability_monthly.parquet, the panel
Out: signals/prisk/test_results.md, signals/prisk/test_prisk.png
"""
import sys; sys.path.insert(0, '.')
import numpy as np, pandas as pd, matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from signal_search import *
from signal_search.single_signal import spread, zip_stats, dsr_haircut

OUT = 'signals/prisk/'
CFG = {**DEFAULT_CFG, 'extra_cols': ['bm'], 'first_form': '2002-12-31', 'design_end': '2012-12-31', 'windows': {'overlap': ('2003-01-01', '2021-12-31')}}
PR = ['prisk', 'prisk4', 'nprisk4', 'risk4', 'prisk_dm', 'prisk_dm4']
ST = ['roa_sd5', 'gprof_sd5']

def md(df, title, fmt='{:.3f}'):
  """One titled table as a fenced text block."""
  return f'\n### {title}\n```\n{df.to_string(float_format=fmt.format)}\n```\n'

def uni_col(data, cfg, name, fn):
  """Compute a new column on the formation universe (fn(f) -> Series on f) and merge it into data.crsp."""
  f = form_universe(data.crsp, cfg['form_month'], cfg)
  v = f[['permno', 'cohort']].assign(**{name: fn(f)}).rename(columns={'cohort': 'date'})
  data.crsp = data.crsp.drop(columns=[name], errors='ignore').merge(v, on=['permno', 'date'], how='left')

def resid_rank(f, y, x):
  """Per cohort: residual of rank(y) on rank(x), stocks with both."""
  r = pd.concat([rank(f, y), rank(f, x), f['cohort']], axis=1, keys=['y', 'x', 'c']).dropna()
  e = r.groupby('c', group_keys=False).apply(lambda g: g['y'] - np.polyval(np.polyfit(g['x'], g['y'], 1), g['x']))
  return e.reindex(f.index)

def periods(z, cfg):
  """ZIP stats for DESIGN, HOLDOUT, FULL."""
  fa = annual_factors(data.ff, cfg['form_month'])
  return {p: zip_stats(z[z.index <= cfg['design_end']] if p == 'DESIGN' else z[z.index > cfg['design_end']] if p == 'HOLDOUT' else z,
                       fa, cfg['factor_model']) for p in ['DESIGN', 'HOLDOUT', 'FULL']}

if __name__ == '__main__':
  crsp, ff = load_data(CFG)
  crsp = add_signal(crsp, 'data/prisk/prisk_monthly.parquet', PR)
  crsp = add_signal(crsp, 'data/earn_stability/earn_stability_monthly.parquet', ST)
  data = prepare(crsp, ff)
  uni_col(data, CFG, 'prisk4_ind', lambda f: f.groupby(['cohort', 'sector'])['prisk4'].rank(pct=True))
  uni_col(data, CFG, 'prisk4_o_np', lambda f: resid_rank(f, 'prisk4', 'nprisk4'))
  uni_col(data, CFG, 'prisk4_o_risk', lambda f: resid_rank(f, 'prisk4', 'risk4'))
  rep = ['# PRisk test results\n', f'Run {pd.Timestamp.now():%Y-%m-%d %H:%M}. Cohorts Dec 2002-Dec 2020; design hold years 2003-2012, '
         'holdout 2013-2021. Annual top-minus-bottom ZIPs; alpha on mktrf/smb/hml/umd, NW t. Default universe '
         '(NYSE median size, price >= $5, vol36). Ranks among stocks with the signal.\n']

  # 1. primary, pre-registered
  for p in ['DESIGN', 'HOLDOUT']:
    o = test_signal('prisk4', True, data, CFG, period=p, comove_with=['nprisk4', 'risk4', 'vol36', 'roa_sd5', 'gprof', 'bm', 'me', 'mom'] if p == 'DESIGN' else None)
    if p == 'DESIGN':
      rep += [md(o['coverage'].T, 'Coverage per cohort (universe stocks, with prisk4, their cap share)', '{:.2f}'), md(o['comove'], 'Mean Spearman of prisk4 with')]
    rep += [md(o['screen'].T, f'{p}: p.258 screen (short ZIP = bottom minus top)'), md(o['spread'].T, f'{p}: prisk4 top-minus-bottom quintile, EW'),
            md(o['fm_alone'], f'{p}: Fama-MacBeth, prisk4 alone'), md(o['fm_controls'], f'{p}: Fama-MacBeth with controls (avg R2 {o["fm_controls"].attrs["avg R2"]:.3f})')]

  # 2. variants (every one is a trial)
  V = {'primary prisk4 q5 EW': ('prisk4', True, {}, 0.2, 'EW'), 'VW legs': ('prisk4', True, {}, 0.2, 'VW'),
       'no size screen': ('prisk4', True, {'size_pct': 0.0}, 0.2, 'EW'), 'terciles': ('prisk4', True, {}, 1 / 3, 'EW'),
       'raw prisk (last call)': ('prisk', True, {}, 0.2, 'EW'), 'prisk_dm4 (vs own past)': ('prisk_dm4', True, {}, 0.2, 'EW'),
       'prisk_dm (last call vs past)': ('prisk_dm', True, {}, 0.2, 'EW'), 'FF12-neutral rank': ('prisk4_ind', True, {}, 0.2, 'EW'),
       'orth to NPRisk': ('prisk4_o_np', True, {}, 0.2, 'EW'), 'orth to Risk (all risk words)': ('prisk4_o_risk', True, {}, 0.2, 'EW')}
  Z, rows = {}, {}
  for name, (col, hb, over, q, w) in V.items():
    cfg = {**CFG, **over}
    Z[name], _ = spread(col, hb, data, cfg, q=q, weight=w)
    for p, s in periods(Z[name], cfg).items():
      rows[(name, p)] = s
  T = pd.DataFrame(rows).T[['years', 'mean %/yr', 't(mean) NW', 'alpha %/yr', 't(alpha) NW', 'Sharpe', 'share of years > 0']]
  rep.append(md(T.unstack(1).swaplevel(0, 1, axis=1).sort_index(axis=1).reindex(V), 'Variants: top-minus-bottom ZIP by period', '{:.2f}'))

  # 3. subperiods of the primary
  z = Z['primary prisk4 q5 EW']; y = z.index.year
  sub = {'all': z, 'excl 2008-09': z[~y.isin([2008, 2009])], 'excl 2020': z[y != 2020], 'excl 2008-09, 2020': z[~y.isin([2008, 2009, 2020])],
         '2003-2007': z[y <= 2007], '2010-2019': z[(y >= 2010) & (y <= 2019)]}
  fa = annual_factors(data.ff, CFG['form_month'])
  rep.append(md(pd.DataFrame({k: zip_stats(v, fa, CFG['factor_model']) for k, v in sub.items()}).T, 'Primary ZIP by subperiod (hold years)', '{:.2f}'))
  rep.append(md(z.rename('prisk4 ZIP %').mul(100).to_frame().set_index(z.index.year), 'Primary ZIP per hold year (%)', '{:.1f}'))

  # 4. deflated Sharpe over the PRisk variants
  sr = pd.Series({k: v.mean() / v.std() for k, v in Z.items()})
  dsr, sr0 = dsr_haircut(sr.iloc[0], z, sr.to_numpy(), len(Z))
  rep.append(f'\n### Deflated Sharpe (FULL, annual)\nn_trials = {len(Z)} PRisk variants. Primary Sharpe {sr.iloc[0]:.2f}/yr, '
             f'hurdle SR0 {sr0:.2f}, DSR {dsr:.2f} (p.247: with many tries one t of 2 is expected by chance).\n')

  # 5. joint Fama-MacBeth on the overlap: does PRisk survive vol36 and earnings stability? does stability add to vol36?
  J = {'PRisk+NPRisk+vol36+roa_sd5': {'prisk4': True, 'nprisk4': True, 'vol36': False, 'roa_sd5': False},
       '+ controls': {'prisk4': True, 'nprisk4': True, 'vol36': False, 'roa_sd5': False, 'gprof': True, 'debt_at': False, 'ep': True, 'mom': True, 'me': False, 'bm': True},
       'vol36 + roa_sd5 only': {'vol36': False, 'roa_sd5': False}, 'roa_sd5 alone': {'roa_sd5': False}, 'vol36 alone': {'vol36': False}}
  for k, spec in J.items():
    s, _ = fama_macbeth(spec, data, CFG, period='overlap')
    rep.append(md(s, f'Joint FM 2003-2021 hold years: {k} (avg R2 {s.attrs["avg R2"]:.3f})'))

  # plot: quintile mean returns and the primary ZIP per year
  f = form_universe(data.crsp, CFG['form_month'], CFG); r = rank(f, 'prisk4')
  legs = [Strategy(f'Q{i + 1}', (lambda i: lambda g: r.loc[g.index].where((r.loc[g.index] > i / 5) & (r.loc[g.index] <= (i + 1) / 5)))(i), 'EW', n=10**9, sector_cap=1.0) for i in range(5)]
  A = to_annual(bh_returns(build_holdings(f, legs, data, CFG, add_ew_univ=False), data.ret_lookup, CFG['horizon']), CFG['form_month']).dropna()
  rep.append(md(pd.DataFrame({p: 100 * A[A.index <= CFG['design_end'] if p == 'DESIGN' else A.index > CFG['design_end']].mean() for p in ['DESIGN', 'HOLDOUT']}).T,
                'prisk4 quintile mean annual return % (Q5 = highest PRisk)', '{:.1f}'))
  fig, ax = plt.subplots(1, 2, figsize=(11, 4))
  (100 * A.mean()).plot.bar(ax=ax[0], color='0.5'); ax[0].set_title('prisk4 quintiles: mean annual return %, 2003-2021')
  ax[1].bar(z.index.year, 100 * z, color=['tab:blue' if d <= pd.Timestamp(CFG['design_end']) else 'tab:orange' for d in z.index])
  ax[1].axhline(0, color='k', lw=.5); ax[1].set_title('Q5-Q1 per hold year % (blue design, orange holdout)')
  fig.tight_layout(); fig.savefig(OUT + 'test_prisk.png', dpi=120)
  open(OUT + 'test_results.md', 'w').write(''.join(rep))
  print(''.join(rep))
