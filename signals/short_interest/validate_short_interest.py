"""Step-9 checks on data/short_interest/si_monthly.parquet. Run from the repo root."""
import pandas as pd

D = 'data/short_interest/'
si = pd.read_parquet(D + 'sec_shortint.parquet')
ev = pd.read_parquet(D + 'si_events.parquet')
mo = pd.read_parquet(D + 'si_monthly.parquet')
panel = pd.read_parquet('crsp_monthly_ratios_clean.parquet', columns=['permno', 'date', 'me', 'prc', 'shrout'])
panel['date'] = pd.to_datetime(panel['date']) + pd.offsets.MonthEnd(0)

print('1. duplicate permno+date:', mo.duplicated(['permno', 'date']).sum())
print(f'2. match: settlement rows linked to a permno {len(ev) / len(si):.1%}; linked rows with panel shrout {ev.shrout.notna().mean():.1%}')
x = si[si.datadate <= '2025-12-31']
print(f'   of rows to 2025: linked {len(ev[ev.period_end <= "2025-12-31"]) / len(x):.1%} (unlinked = no CCM link for that iid, e.g. ADRs, funds, OTC)')
print('3. published_date >= period_end:', (mo.published_date >= mo.period_end).mean(), '| published <= date:', (mo.published_date <= mo.date).mean(),
      '| share assumed:', (mo.date_source == 'assumed').mean())
print('   days from settlement to month-end used:', (mo.date - mo.period_end).dt.days.describe()[['min', '50%', 'max']].to_dict())
dec = panel[(panel.date.dt.month == 12) & (panel.date >= '2006-12-31') & (panel.prc.abs() >= 5)].merge(mo[['permno', 'date', 'si_ratio']], on=['permno', 'date'], how='left')
c = dec.groupby(dec.date.dt.year).apply(lambda d: pd.Series({'stocks': len(d), 'share with si': d.si_ratio.notna().mean(),
                                                             'cap share': d.loc[d.si_ratio.notna(), 'me'].sum() / d.me.sum()}))
print('4. December coverage, price >= $5:\n', c.round(3).iloc[::3].to_string())
q = mo.si_ratio.quantile([0.01, 0.5, 0.9, 0.99, 0.999, 1])
print('5. si_ratio quantiles:', q.round(4).to_dict(), '| > 1:', (mo.si_ratio > 1).sum(), '| zeros:', (mo.si_ratio == 0).mean().round(3))
print('   dtc quantiles:', mo.dtc.quantile([0.5, 0.9, 0.99]).round(1).to_dict())
print('   top si_ratio:', ev.nlargest(5, 'si_ratio')[['permno', 'period_end', 'shortint', 'shrout', 'si_ratio']].to_string(index=False))
for name, p in {'AAPL': 14593, 'TSLA': 93436}.items():
  s = mo[(mo.permno == p) & (mo.date.dt.month == 12)].set_index(mo.date[(mo.permno == p) & (mo.date.dt.month == 12)].dt.year)['si_ratio']
  print(f'6. {name} December si_ratio %:', (100 * s).round(1).loc[2010:2025].to_dict())
# split: AAPL 4-for-1 on 2020-08-31; raw shortint and shrout are both pre/post split within the month
a = ev[(ev.permno == 14593) & (ev.period_end.between('2020-07-01', '2020-10-31'))][['period_end', 'shortint', 'shrout', 'si_ratio']]
print('7. AAPL around the 2020-08-31 4:1 split:\n', a.to_string(index=False))
