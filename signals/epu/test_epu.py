"""EPU-beta single-signal tests (cohorts Dec 1988-Dec 2024: design 1989-2005, holdout 2006-2025).

Run from the repo root: python signals/epu/test_epu.py
In:  data/epu/epu_beta_monthly.parquet, the panel
Out: signals/epu/test_results.md
"""
import sys; sys.path.insert(0, '.')
import pandas as pd
from signal_search import *
from signal_search.single_signal import spread, zip_stats, dsr_haircut, CONTROLS

OUT = 'signals/epu/'
CFG = {**DEFAULT_CFG, 'extra_cols': ['bm'], 'first_form': '1988-12-31'}
SIGS = ['epu_beta', 'epu_trade_beta', 'epu_natsec_beta']
CTRL = {**CONTROLS, 'mkt_beta60': False}

def md(df, title, fmt='{:.3f}'):
  """One titled table as a fenced text block."""
  return f'\n### {title}\n```\n{df.to_string(float_format=fmt.format)}\n```\n'

if __name__ == '__main__':
  crsp, ff = load_data(CFG)
  data = prepare(add_signal(crsp, 'data/epu/epu_beta_monthly.parquet', SIGS + ['epu_beta36', 'mkt_beta60']), ff)
  rep = ['# EPU beta test results\n', f'Run {pd.Timestamp.now():%Y-%m-%d %H:%M}. Cohorts Dec 1988-Dec 2024, design hold years 1989-2005, '
         'holdout 2006-2025. higher_better=False (low beta = long). Default universe. Controls: lab set + mkt_beta60.\n']
  for c in SIGS:
    rep.append(f'\n## {c}\n')
    for p in ['DESIGN', 'HOLDOUT']:
      o = test_signal(c, False, data, CFG, controls=CTRL, period=p,
                      comove_with=[x for x in SIGS + ['mkt_beta60', 'vol36', 'me', 'bm', 'mom'] if x != c] if p == 'DESIGN' else None)
      if p == 'DESIGN':
        rep += [md(o['coverage'].iloc[::4].T, 'Coverage, every 4th cohort', '{:.2f}'), md(o['comove'], f'Mean Spearman of {c} with')]
      rep += [md(o['screen'].T, f'{p}: p.258 screen'), md(o['spread'].T, f'{p}: low-minus-high quintile, EW'),
              md(o['fm_alone'], f'{p}: FM alone'), md(o['fm_controls'], f'{p}: FM with controls (avg R2 {o["fm_controls"].attrs["avg R2"]:.3f})')]
  V = {'epu_beta q5 EW': ('epu_beta', 0.2, 'EW'), 'epu_trade_beta q5 EW': ('epu_trade_beta', 0.2, 'EW'),
       'epu_natsec_beta q5 EW': ('epu_natsec_beta', 0.2, 'EW'), 'epu_beta VW': ('epu_beta', 0.2, 'VW'),
       'epu_trade_beta VW': ('epu_trade_beta', 0.2, 'VW'), 'epu_natsec_beta VW': ('epu_natsec_beta', 0.2, 'VW'),
       'epu_beta terciles': ('epu_beta', 1 / 3, 'EW'), 'epu_beta36 q5 EW': ('epu_beta36', 0.2, 'EW'),
       'mkt_beta60 q5 EW (reference)': ('mkt_beta60', 0.2, 'EW')}
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
  dsr, sr0 = dsr_haircut(sr.iloc[0], Z['epu_beta q5 EW'], sr.to_numpy(), len(tr))
  rep.append(f'\n### Deflated Sharpe (FULL)\nn_trials = {len(tr)} EPU variants (mkt_beta60 is a reference, not counted). '
             f'Primary epu_beta Sharpe {sr.iloc[0]:.2f}/yr, hurdle {sr0:.2f}, DSR {dsr:.2f}. Best: {sr.idxmax()} {sr.max():.2f}.\n')
  open(OUT + 'test_results.md', 'w').write(''.join(rep))
  print(''.join(rep))
