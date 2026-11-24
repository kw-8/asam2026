"""Load the stock panel, Fama-French factors, optional ETF returns and names."""
import io, zipfile, urllib.request
from pathlib import Path
import numpy as np, pandas as pd
from .signals import add_volatility, add_momentum, add_ff12

BASE_COLS = ['permno', 'date', 'primaryexch', 'siccd', 'mthret', 'prc', 'me', 'me_lag', 'gprof', 'debt_at', 'ep']
NAME_COLS = ['ticker', 'comnam', 'conm']
NUM_COLS  = ['mthret', 'prc', 'me', 'me_lag', 'gprof', 'debt_at', 'ep']

def load_panel(path, extra_cols=()):
  """Read the CRSP/Compustat panel with the base columns, extra_cols, and any name columns."""
  try:
    import pyarrow.parquet as pq
    avail = set(pq.read_schema(path).names)
  except ImportError:
    avail = set(pd.read_parquet(path).columns)
  missing = [c for c in BASE_COLS if c not in avail and c != 'siccd']
  assert not missing, f'missing columns: {missing}'
  want = [c for c in dict.fromkeys(BASE_COLS + list(extra_cols) + NAME_COLS) if c in avail]
  return clean_panel(pd.read_parquet(path, columns=want))

def clean_panel(df):
  """Types, month-end dates, sorted by permno then date."""
  df = df.copy()
  if 'siccd' not in df:
    df['siccd'] = np.nan
  df['permno'] = df['permno'].astype('int64')
  df['date'] = pd.to_datetime(df['date']) + pd.offsets.MonthEnd(0)
  for c in NUM_COLS:
    df[c] = pd.to_numeric(df[c], errors='coerce').astype('float64')
  return df.sort_values(['permno', 'date']).reset_index(drop=True)

# ---- Fama-French factors from Ken French's data library (public; same series as ff.factors_monthly on WRDS)
FRENCH = 'https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/'

def _read_french_zip(fname):
  """Monthly block of one Ken French CSV zip, in decimals."""
  raw = urllib.request.urlopen(FRENCH + fname, timeout=60).read()
  with zipfile.ZipFile(io.BytesIO(raw)) as z:
    txt = z.read(z.namelist()[0]).decode('latin-1')
  header, rows = None, []
  for line in txt.splitlines():
    parts = [p.strip() for p in line.split(',')]
    is_month = len(parts[0]) == 6 and parts[0].isdigit()
    if is_month:
      rows.append(parts)
    elif rows:                       # monthly block ended (annual block follows)
      break
    elif len(parts) > 1 and parts[0] == '':
      header = parts[1:]
  df = pd.DataFrame([r[1:] for r in rows], columns=header,
                    index=pd.to_datetime([r[0] for r in rows], format='%Y%m') + pd.offsets.MonthEnd(0))
  df = df.apply(pd.to_numeric, errors='coerce')
  return df.mask(df <= -99.99) / 100            # -99.99 / -999 = missing

def load_ff_factors(cache='ff_factors_monthly.csv', refresh=False):
  """Monthly mktrf, smb, hml, umd, rf; cached to CSV after the first download."""
  if cache and Path(cache).exists() and not refresh:
    return pd.read_csv(cache, index_col=0, parse_dates=True)
  f3  = _read_french_zip('F-F_Research_Data_Factors_CSV.zip')
  mom = _read_french_zip('F-F_Momentum_Factor_CSV.zip')
  ff = f3.join(mom, how='left')
  ff.columns = [c.lower().replace('-', '') for c in ff.columns]
  ff = ff.rename(columns={'mom': 'umd'})[['mktrf', 'smb', 'hml', 'umd', 'rf']]
  ff.index.name = 'date'
  if cache:
    ff.to_csv(cache)
  return ff

def load_etf_returns(path=None, tickers=None, source='csv'):
  """Monthly ETF total returns from a CSV (date + one column per ticker) or yfinance."""
  if source == 'yfinance':
    import yfinance as yf
    px = yf.download(tickers, start='2002-01-01', auto_adjust=True, progress=False)['Close']
    r = px.resample('ME').last().pct_change().dropna(how='all')
    if path:
      r.to_csv(path)
    return r
  if path is None or not Path(path).exists():
    return None
  r = pd.read_csv(path, index_col=0, parse_dates=True)
  r.index = r.index + pd.offsets.MonthEnd(0)
  return r.astype('float64')

def load_names(path):
  """Optional permno -> ticker/company lookup."""
  if path is None or not Path(path).exists():
    return None
  n = pd.read_csv(path)
  n['permno'] = n['permno'].astype('int64')
  return n.drop_duplicates('permno', keep='last')

def load_data(cfg, synthetic=False):
  """Panel with vol36, mom, sector added, plus monthly factors. Returns (crsp, ff)."""
  from .synthetic import make_synthetic_panel, make_synthetic_factors
  crsp = make_synthetic_panel() if synthetic else load_panel(cfg['panel_path'], cfg['extra_cols'])
  crsp = add_volatility(crsp, win=36, min_periods=24, name='vol36')
  crsp = add_momentum(crsp, name='mom')
  crsp = add_ff12(crsp)
  ff = make_synthetic_factors(crsp) if synthetic else load_ff_factors(cfg['factors_path'])
  return crsp, ff
