"""Baker-Bloom-Davis EPU indices -> public_data/epu_monthly.csv (one row per month-end).

Run from the repo root: python signals/epu/build_epu.py
In:  policyuncertainty.com US_Policy_Uncertainty_Data.xlsx, Categorical_EPU_Data.xlsx (downloaded to data/epu/ if missing)
Out: public_data/epu_monthly.csv (date, epu_news, epu_3comp, 11 category indices epu_<topic>)
Source: Baker, Bloom & Davis (2016), Measuring Economic Policy Uncertainty, QJE 131(4), 1593-1636; www.PolicyUncertainty.com.
"""
from pathlib import Path
import urllib.request
import pandas as pd

RAW, OUT = Path('data/epu'), Path('public_data/epu_monthly.csv')
URL = 'https://www.policyuncertainty.com/media/'
FILES = ['US_Policy_Uncertainty_Data.xlsx', 'Categorical_EPU_Data.xlsx']
CAT = ['epu_cat', 'monetary', 'fiscal', 'taxes', 'gov_spending', 'health_care', 'national_security',
       'entitlements', 'regulation', 'financial_regulation', 'trade_policy', 'sovereign_debt_fx']

def fetch(f):
  """Download one raw file unless it is already in data/epu/."""
  p = RAW / f
  if not p.exists():
    RAW.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(URL + f, headers={'User-Agent': 'Mozilla/5.0'})
    p.write_bytes(urllib.request.urlopen(req).read())
  return p

def clean(df):
  """Drop the source-note row; Year/Month -> month-end date index."""
  df = df[pd.to_numeric(df['Year'], errors='coerce').notna()].copy()
  df['date'] = pd.to_datetime(dict(year=df['Year'].astype(int), month=df['Month'].astype(int), day=1)) + pd.offsets.MonthEnd(0)
  return df.drop(columns=['Year', 'Month']).set_index('date').sort_index()

def build():
  """Join the news index, the legacy 3-component index and the 11 category indices."""
  us, cat = fetch(FILES[0]), fetch(FILES[1])
  n = clean(pd.read_excel(us, sheet_name='Main News Index')).rename(columns={'News_Based_Policy_Uncert_Index': 'epu_news'})
  l = clean(pd.read_excel(us, sheet_name='Legacy Three Component EPU'))[['Three_Component_Index']].rename(columns={'Three_Component_Index': 'epu_3comp'})
  c = clean(pd.read_excel(cat, sheet_name='Indices'))
  c.columns = CAT
  c = c.drop(columns='epu_cat').add_prefix('epu_')
  return n.join(l).join(c).round(3)

if __name__ == '__main__':
  out = build()
  out.to_csv(OUT)
  print(f'{OUT}: {out.shape}, {out.index.min():%Y-%m} to {out.index.max():%Y-%m}; categories from {out["epu_trade_policy"].first_valid_index():%Y-%m}')
