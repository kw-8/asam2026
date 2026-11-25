"""PRisk augmentation tests (pre-registered in signals/prisk/progress.md): design selection, then holdout for <= 2 finalists.

Run from the repo root: python signals/prisk/augment/test_augment.py [aug_monthly.parquet] [tag] [finalists]
Default: data/prisk/augment/aug_prisk_monthly.parquet, tag prisk (adds the 10 earlier PRisk trials to the DSR count).
finalists (e.g. 'A5,A1') skips selection and re-runs those on a new base (e.g. eprisk) as fixed signals.
Out: signals/prisk/augment/test_tables_<tag>.md
"""
import sys; sys.path.insert(0, '.')
import numpy as np, pandas as pd
from signal_search import *
from signal_search.single_signal import spread, zip_stats, dsr_haircut, CONTROLS
sys.path.insert(0, 'signals/prisk'); from test_prisk import uni_col, resid_rank, md

AUG = sys.argv[1] if len(sys.argv) > 1 else 'data/prisk/augment/aug_prisk_monthly.parquet'
TAG = sys.argv[2] if len(sys.argv) > 2 else 'prisk'
FIX = sys.argv[3].split(',') if len(sys.argv) > 3 else None
CFG = {**DEFAULT_CFG, 'extra_cols': ['bm'], 'first_form': '2002-12-31', 'design_end': '2012-12-31'}
CAND = {'A1': 'dm4_ind', 'A2': 'dm4_o_sent', 'A3': 'sys_dm4', 'A4': 'dm4_o_np', 'A5': 'dm4_z'}
PRIOR = {'primary prisk4 q5 EW': ('prisk4', {}, 0.2, 'EW'), 'VW legs': ('prisk4', {}, 0.2, 'VW'),
         'no size screen': ('prisk4', {'size_pct': 0.0}, 0.2, 'EW'), 'terciles': ('prisk4', {}, 1 / 3, 'EW'),
         'raw prisk': ('prisk', {}, 0.2, 'EW'), 'prisk_dm4': ('prisk_dm4', {}, 0.2, 'EW'), 'prisk_dm': ('prisk_dm', {}, 0.2, 'EW'),
         'FF12-neutral': ('prisk4_ind', {}, 0.2, 'EW'), 'orth NPRisk': ('prisk4_o_np', {}, 0.2, 'EW'), 'orth Risk': ('prisk4_o_risk', {}, 0.2, 'EW')}
COLS = ['years', 'mean %/yr', 't(mean) NW', 'alpha %/yr', 't(alpha) NW', 't(alpha) OLS', 'Sharpe', 'share of years > 0']

def add_beta60(crsp, ff):
  """60-month market beta of excess return on mktrf (>= 36 months), known at the month-end."""
  d = crsp[['permno', 'date', 'mthret']].merge(ff[['mktrf', 'rf']], left_on='date', right_index=True, how='left')
  d['y'], d['x'] = d['mthret'] - d['rf'], d['mktrf']
  d = d.dropna(subset=['y', 'x']).sort_values(['permno', 'date'])
  d['xy'], d['xx'] = d['x'] * d['y'], d['x'] ** 2
  r = d.groupby('permno')[['x', 'y', 'xy', 'xx']].rolling(60, min_periods=36).mean().reset_index(level=0, drop=True)
  d['beta60'] = (r['xy'] - r['x'] * r['y']) / (r['xx'] - r['x'] ** 2)
  return crsp.merge(d[['permno', 'date', 'beta60']], on=['permno', 'date'], how='left')

def stats_p(col, cfg, p, q=0.2, w='EW'):
  """ZIP stats of col (higher = long) for one period; returns (series, stats dict)."""
  return spread(col, True, data, cfg, q=q, weight=w, period=p)

def fm(col, p, extra=None):
  """FM slope and NW t of col with lab controls (+ extra), period p."""
  s, _ = fama_macbeth({col: True, **{c: hb for c, hb in CONTROLS.items() if c != col}, **(extra or {})}, data, CFG, period=p)
  return s.loc[col, 'slope %/yr (top vs bottom rank)'], s.loc[col, 't NW']

if __name__ == '__main__':
  crsp, ff = load_data(CFG)
  crsp = crsp[crsp['date'] >= '1995-01-01']
  crsp = add_signal(crsp, AUG, ['dm4', 'dm4_z', 'psent_dm4', 'nprisk_dm4', 'sys_dm4'])
  if TAG == 'prisk':
    crsp = add_signal(crsp, 'data/prisk/prisk_monthly.parquet', ['prisk', 'prisk4', 'nprisk4', 'risk4', 'prisk_dm', 'prisk_dm4'])
  data = prepare(add_beta60(crsp, ff), ff)
  uni_col(data, CFG, 'dm4_ind', lambda f: f.groupby(['cohort', 'sector'])['dm4'].rank(pct=True))
  for n, x in [('dm4_o_sent', 'psent_dm4'), ('dm4_o_np', 'nprisk_dm4')]:
    if data.crsp[x].notna().any():                     # EDGAR bases have no sentiment / NPRisk: those candidates are skipped
      uni_col(data, CFG, n, (lambda x: lambda f: resid_rank(f, 'dm4', x))(x))
  if TAG == 'prisk':
    uni_col(data, CFG, 'prisk4_ind', lambda f: f.groupby(['cohort', 'sector'])['prisk4'].rank(pct=True))
    uni_col(data, CFG, 'prisk4_o_np', lambda f: resid_rank(f, 'prisk4', 'nprisk4'))
    uni_col(data, CFG, 'prisk4_o_risk', lambda f: resid_rank(f, 'prisk4', 'risk4'))
  rep = [f'# PRisk augmentation tables ({TAG})\n', f'Run {pd.Timestamp.now():%Y-%m-%d %H:%M}. Q5-Q1 EW annual, Dec formation, lab universe. '
         'Design hold years 2003-2012. Holdout only for finalists.\n']

  # 1. DESIGN: candidates (+ dm4 reference) and the earlier trials' design Sharpe for the DSR dispersion
  rows, Zd = {}, {}
  for k, c in {**CAND, 'ref dm4': 'dm4'}.items():
    if c not in data.crsp or data.crsp[c].isna().all():
      continue
    Zd[k], s = stats_p(c, CFG, 'DESIGN')
    b, t = fm(c, 'DESIGN')
    rows[f'{k} {c}'] = {**s, 'FM ctrl slope': b, 'FM ctrl t': t}
  T = pd.DataFrame(rows).T[COLS + ['FM ctrl slope', 'FM ctrl t']]
  rep.append(md(T, 'DESIGN (2003-2012): candidates, Q5-Q1 EW; FM with lab controls', '{:.2f}'))
  srd = {k: z.mean() / z.std() for k, z in Zd.items() if k in CAND}
  if TAG == 'prisk':
    for k, (c, over, q, w) in PRIOR.items():
      z, _ = stats_p(c, {**CFG, **over}, 'DESIGN', q, w)
      srd[k] = z.mean() / z.std()
  sr_all = pd.Series(srd)
  rep.append(md(sr_all.rename('design Sharpe').to_frame(), f'Design Sharpe of all {len(sr_all)} trials', '{:.2f}'))

  # 2. finalists by the pre-registered rule (top 2 design Sharpe among A1-A5 with design mean > 0)
  ok = pd.Series({k: srd[k] for k in CAND if k in Zd and Zd[k].mean() > 0})
  fin = FIX or list(ok.sort_values(ascending=False).index[:2])
  ref = Zd['ref dm4'].mean() / Zd['ref dm4'].std()
  rep.append(f'\nFinalists: {fin}. Reference dm4 design Sharpe {ref:.2f}.\n')

  # 3. HOLDOUT / FULL for finalists only, DSR, disguise check
  rows, rows_fm, cm = {}, {}, {}
  for k in fin + ['ref dm4']:
    c = CAND.get(k, 'dm4')
    for p in ['DESIGN', 'HOLDOUT', 'FULL']:
      z, s = stats_p(c, CFG, p)
      rows[(f'{k} {c}', p)] = s
      if p != 'DESIGN' and k != 'ref dm4':
        n = len(sr_all) if TAG == 'prisk' else len(CAND)
        dsr, sr0 = dsr_haircut(z.mean() / z.std(), z, sr_all.to_numpy(), n)
        rows[(f'{k} {c}', p)].update({'DSR': dsr, 'hurdle': sr0})
      rows_fm[(f'{k} {c}', p)] = dict(zip(['ctrl slope', 'ctrl t'], fm(c, p)), **dict(zip(['ctrl+beta slope', 'ctrl+beta t'], fm(c, p, {'beta60': False}))))
    sg = [c] + [x for x in ['vol36', 'me', 'beta60', 'dm4'] if x != c]
    _, wide, _ = comove(data.crsp.loc[data.crsp[c].notna(), ['date', *sg]].dropna(), sg)
    cm[f'{k} {c}'] = wide[[x for x in wide if x.startswith(c + '~')]].mean().rename(lambda x: x.split('~')[1])
  for k in fin:
    dsr, sr0 = dsr_haircut(srd[k], Zd[k], sr_all.to_numpy(), len(sr_all))
    rows[(f'{k} {CAND[k]}', 'DESIGN')].update({'DSR': dsr, 'hurdle': sr0})
  rep.append(md(pd.DataFrame(rows).T, 'Finalists and dm4 reference by period (DSR vs all trials)', '{:.2f}'))
  rep.append(md(pd.DataFrame(rows_fm).T, 'FM slope %/yr, NW t: lab controls, and + beta60', '{:.2f}'))
  rep.append(md(pd.DataFrame(cm).T, 'Mean monthly Spearman with vol36, me, beta60, dm4', '{:.2f}'))
  open(f'signals/prisk/augment/test_tables_{TAG}.md', 'w').write(''.join(rep))
  print(''.join(rep))
