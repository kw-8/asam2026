"""Short-interest tests (pre-registered in progress.md): annual December formation and monthly formation.

Run from the repo root: python signals/short_interest/test_short_interest.py
In:  data/short_interest/si_monthly.parquet, the panel
Out: signals/short_interest/test_results.md
"""
import sys; sys.path.insert(0, '.')
import numpy as np, pandas as pd
from scipy import stats
from signal_search import *
from signal_search.evaluate import deflated_sharpe, to_annual, annual_factors

OUT = 'signals/short_interest/'
CFG = {**DEFAULT_CFG, 'extra_cols': ['bm'], 'first_form': '2006-12-31', 'design_end': '2015-12-31',
       'windows': {'overlap': ('2007-01-01', '2025-12-31')}}
N_TRIALS = 9

def md(df, title, fmt='{:.3f}'):
  """One titled table as a fenced text block."""
  return f'\n### {title}\n```\n{df.to_string(float_format=fmt.format)}\n```\n'

if __name__ == '__main__':
  crsp, ff = load_data(CFG)
  data = prepare(add_signal(crsp, 'data/short_interest/si_monthly.parquet', ['si_ratio', 'dtc']), ff)
  rep = ['# Short interest test results\n', f'Run {pd.Timestamp.now():%Y-%m-%d %H:%M}. Pre-registered in progress.md. Low-minus-high short '
         'interest (long the least shorted). Default universe (NYSE-median size, price >= $5, vol36). Design = returns to 2015-12, holdout after.\n']

  # 1. annual, primary: the standard single-signal tests
  rep.append('\n## Annual (December formation, held 12 months)\n')
  for p in ['DESIGN', 'HOLDOUT']:
    o = test_signal('si_ratio', False, data, CFG, period=p, comove_with=['dtc', 'vol36', 'me', 'bm', 'mom', 'gprof'] if p == 'DESIGN' else None)
    if p == 'DESIGN':
      rep += [md(o['coverage'].T, 'Coverage per cohort', '{:.2f}'), md(o['comove'], 'Mean Spearman of si_ratio with')]
    rep += [md(o['screen'].T, f'{p}: p.258 screen'), md(o['spread'].T, f'{p}: si_ratio low-minus-high quintile, EW'),
            md(o['fm_alone'], f'{p}: Fama-MacBeth, si_ratio alone'), md(o['fm_controls'], f'{p}: Fama-MacBeth with controls (avg R2 {o["fm_controls"].attrs["avg R2"]:.3f})')]

  # 2. annual variants
  fA = form_universe(data.crsp, CFG['form_month'], CFG)
  fa = annual_factors(data.ff, CFG['form_month'])
  VA = {'si_ratio q5 EW (primary)': ('si_ratio', 0.2, 'EW', False), 'si_ratio q5 VW': ('si_ratio', 0.2, 'VW', False),
        'si_ratio terciles': ('si_ratio', 1 / 3, 'EW', False), 'dtc q5 EW': ('dtc', 0.2, 'EW', False),
        'avoid top-SI quintile vs EW universe': ('si_ratio', 0.2, 'EW', True)}
  ZA, rows = {}, {}
  for k, (c, q, w, av) in VA.items():
    ZA[k] = to_annual(zip_returns(fA, c, False, data, CFG, 12, q, w, av).to_frame('z'), CFG['form_month'])['z'].dropna()
    for p, s in by_period(ZA[k], lambda z: zip_stats(z, fa, CFG['factor_model']), CFG).items():
      rows[(k, p)] = s
  rep.append(md(pd.DataFrame(rows).T[['years', 'mean %/yr', 't(mean) NW', 'alpha %/yr', 't(alpha) NW', 't(alpha) OLS', 'Sharpe', 'share of years > 0']],
                'Annual variants: ZIP by period', '{:.2f}'))

  # 3. monthly formation, held 1 month
  rep.append('\n## Monthly (formation every month-end, held 1 month)\n')
  cmp, _, _ = compare('si_ratio', False, data, CFG, first_form_monthly='2006-08-31')
  rep.append(md(cmp, 'Primary (si_ratio q5 EW): annual vs monthly, by period', '{:.2f}'))
  fM = monthly_universe(data, CFG, '2006-08-31')
  VM = {'si_ratio q5 EW (primary)': ('si_ratio', 0.2, 'EW', False), 'si_ratio q5 VW': ('si_ratio', 0.2, 'VW', False),
        'dtc q5 EW': ('dtc', 0.2, 'EW', False), 'avoid top-SI quintile vs EW universe': ('si_ratio', 0.2, 'EW', True)}
  ZM, rows = {}, {}
  for k, (c, q, w, av) in VM.items():
    ZM[k] = zip_returns(fM, c, False, data, CFG, 1, q, w, av)
    for p, s in by_period(ZM[k], lambda z: monthly_stats(z, data.ff, CFG['factor_model']), CFG).items():
      rows[(k, p)] = s
  rep.append(md(pd.DataFrame(rows).T, 'Monthly variants: ZIP by period', '{:.2f}'))
  z = ZM['si_ratio q5 EW (primary)']
  rep.append(md((100 * z.groupby(z.index.year).apply(lambda x: (1 + x).prod() - 1)).to_frame('primary monthly ZIP, compounded % per year'),
                'Monthly primary, per calendar year', '{:.1f}'))

  # 4. how fast does it fade? monthly cohorts held 1..12 months, return in month k only
  rep.append(md(decay(fM, 'si_ratio', False, data, CFG), 'Decay: low-minus-high return in month k after formation (si_ratio q5 EW, monthly cohorts, FULL)', '{:.2f}'))

  # 5. deflated Sharpe, per frequency, n_trials = 9 across both
  srA = pd.Series({k: v.mean() / v.std() for k, v in ZA.items()})
  dA, sA = dsr_haircut(srA.iloc[0], ZA['si_ratio q5 EW (primary)'], srA.to_numpy(), N_TRIALS)
  srM = pd.Series({k: v.mean() / v.std() for k, v in ZM.items()})
  dM, sM = deflated_sharpe(srM.iloc[0], len(z), stats.skew(z), stats.kurtosis(z, fisher=False), srM.to_numpy(), N_TRIALS)
  rep.append(f'\n### Deflated Sharpe (FULL), n_trials = {N_TRIALS}\nAnnual primary: Sharpe {srA.iloc[0]:.2f}/yr, hurdle {sA:.2f}, DSR {dA:.2f}. '
             f'Monthly primary: Sharpe {srM.iloc[0]:.3f}/month ({np.sqrt(12) * srM.iloc[0]:.2f}/yr), hurdle {sM:.3f}/month, DSR {dM:.2f}.\n')
  open(OUT + 'test_results.md', 'w').write(''.join(rep))
  print(''.join(rep))
