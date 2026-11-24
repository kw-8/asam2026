"""Step-9 checks on data/prisk/prisk_monthly.parquet. Run from the repo root."""
import numpy as np, pandas as pd

ev = pd.read_parquet('data/prisk/prisk_events.parquet')
mo = pd.read_parquet('data/prisk/prisk_monthly.parquet')
panel = pd.read_parquet('crsp_monthly_ratios_clean.parquet', columns=['permno', 'gvkey', 'date', 'me'])
panel['date'] = pd.to_datetime(panel['date']) + pd.offsets.MonthEnd(0)
win = panel[(panel['date'] >= '2003-01-31') & (panel['date'] <= '2020-12-31')]

print('1. duplicate permno+date:', mo.duplicated(['permno', 'date']).sum())
us = ev[ev['hqcountrycode'] == 'US']
g = set(panel['gvkey'].dropna())
print(f'2. match: events gvkey in panel {ev.gvkey.isin(g).mean():.1%} (US HQ {us.gvkey.isin(g).mean():.1%})')
miss = us[~us.gvkey.isin(g)]
print('   unmatched US examples:', miss.drop_duplicates('gvkey')[['gvkey', 'company_name', 'ticker']].head(5).to_dict('records'))
print('3. published_date >= period_end:', (mo.published_date >= mo.period_end).mean(),
      '| published_date <= date:', (mo.published_date <= mo.date).mean(), '| share assumed:', (mo.date_source == 'assumed').mean())
dec = win[win['date'].dt.month == 12].merge(mo[['permno', 'date', 'prisk4']], on=['permno', 'date'], how='left')
c = dec.groupby(dec['date'].dt.year).apply(lambda x: pd.Series({
  'stocks': len(x), 'share with prisk4': x['prisk4'].notna().mean(),
  'share of mkt cap': x.loc[x['prisk4'].notna(), 'me'].sum() / x['me'].sum()}))
print('4. December coverage vs panel:\n', c.round(3).to_string())
q = mo['prisk'].quantile([0.5, 0.9, 0.99, 0.999, 1])
print('5. prisk quantiles:', q.round(0).to_dict(), '| zeros:', (mo['prisk'] == 0).mean().round(3))
print('   top outliers:', ev.nlargest(3, 'prisk')[['company_name', 'call_date', 'prisk']].to_dict('records'))
for t in ['AAPL', 'XOM', 'LMT']:
  gv = ev.loc[ev['ticker'] == t, 'gvkey'].mode()
  s = mo[mo.gvkey.isin(gv) & (mo.date.dt.month == 12)].drop_duplicates('date').set_index('date')['prisk4']
  print(f'6. {t} December prisk4:', s.round(0).loc['2007':'2020'].to_dict() if len(s) else 'none')
# ticker change: Google -> Alphabet (GOOGL, 2015), same gvkey
gv = ev.loc[ev['ticker'].isin(['GOOG', 'GOOGL']), 'gvkey'].unique()
print('7. ticker change GOOG/GOOGL gvkeys:', gv, '| permnos in monthly:', mo.loc[mo.gvkey.isin(gv), 'permno'].unique()[:5])
print('8. split check: prisk is a word-count share, no per-share units -> splits cannot move it.')
