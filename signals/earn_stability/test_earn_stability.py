"""Earnings-stability single-signal tests on the lab default sample (design 1986-2005, holdout 2006-2025).

Run from the repo root: python signals/earn_stability/test_earn_stability.py
In:  data/earn_stability/earn_stability_monthly.parquet, the panel
Out: signals/earn_stability/test_results.md
"""
import sys; sys.path.insert(0, '.')
import pandas as pd
from signal_search import *
from signal_search.single_signal import spread, zip_stats, dsr_haircut

OUT = 'signals/earn_stability/'
CFG = {**DEFAULT_CFG, 'extra_cols': ['bm']}

def md(df, title, fmt='{:.3f}'):
  """One titled table as a fenced text block."""
  return f'\n### {title}\n```\n{df.to_string(float_format=fmt.format)}\n```\n'

if __name__ == '__main__':
  crsp, ff = load_data(CFG)
  data = prepare(add_signal(crsp, OUT.replace('signals', 'data') + 'earn_stability_monthly.parquet', ['roa_sd5', 'gprof_sd5']), ff)
  rep = ['# Earnings stability test results\n', f'Run {pd.Timestamp.now():%Y-%m-%d %H:%M}. Lab default: cohorts Dec 1985-Dec 2024, '
         'design hold years 1986-2005, holdout 2006-2025. higher_better=False (low std = stable = long). Default universe.\n']
  for p in ['DESIGN', 'HOLDOUT']:
    o = test_signal('roa_sd5', False, data, CFG, period=p, comove_with=['gprof_sd5', 'vol36', 'gprof', 'debt_at', 'ep', 'me', 'bm', 'mom'] if p == 'DESIGN' else None)
    if p == 'DESIGN':
      rep += [md(o['coverage'].iloc[::5].T, 'Coverage, every 5th cohort', '{:.2f}'), md(o['comove'], 'Mean Spearman of roa_sd5 with')]
    rep += [md(o['screen'].T, f'{p}: p.258 screen'), md(o['spread'].T, f'{p}: roa_sd5 low-minus-high quintile, EW'),
            md(o['fm_alone'], f'{p}: FM roa_sd5 alone'), md(o['fm_controls'], f'{p}: FM with controls incl. vol36 (avg R2 {o["fm_controls"].attrs["avg R2"]:.3f})')]
    s, _ = fama_macbeth({'vol36': False, 'roa_sd5': False}, data, CFG, period=p)
    rep.append(md(s, f'{p}: FM vol36 + roa_sd5 only'))
  V = {'roa_sd5 q5 EW': ('roa_sd5', 0.2, 'EW'), 'roa_sd5 VW': ('roa_sd5', 0.2, 'VW'), 'roa_sd5 terciles': ('roa_sd5', 1 / 3, 'EW'),
       'gprof_sd5 q5 EW (check)': ('gprof_sd5', 0.2, 'EW'), 'vol36 q5 EW (reference)': ('vol36', 0.2, 'EW')}
  fa, Z, rows = annual_factors(data.ff, CFG['form_month']), {}, {}
  for k, (c, q, w) in V.items():
    Z[k], _ = spread(c, False, data, CFG, q=q, weight=w)
    for p, z in split(Z[k], CFG).items():
      if p in ('DESIGN', 'HOLDOUT', 'FULL'):
        rows[(k, p)] = zip_stats(z, fa, CFG['factor_model'])
  T = pd.DataFrame(rows).T[['years', 'mean %/yr', 't(mean) NW', 'alpha %/yr', 't(alpha) NW', 't(alpha) OLS', 'Sharpe']]
  rep.append(md(T, 'Variants: low-minus-high ZIP by period', '{:.2f}'))
  tr = {k: v for k, v in Z.items() if 'reference' not in k}
  sr = pd.Series({k: v.mean() / v.std() for k, v in tr.items()})
  dsr, sr0 = dsr_haircut(sr.iloc[0], Z['roa_sd5 q5 EW'], sr.to_numpy(), len(tr))
  rep.append(f'\n### Deflated Sharpe (FULL)\nn_trials = {len(tr)} stability variants (vol36 is a reference, not counted). '
             f'Primary Sharpe {sr.iloc[0]:.2f}/yr, hurdle {sr0:.2f}, DSR {dsr:.2f}.\n')
  open(OUT + 'test_results.md', 'w').write(''.join(rep))
  print(''.join(rep))
