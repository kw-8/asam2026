"""Default settings. The notebook copies these into CFG and overrides what it needs."""

DEFAULT_CFG = dict(
  panel_path   = 'crsp_monthly_ratios_clean.parquet',
  factors_path = 'public_data/ff_factors_monthly.csv', # cache; downloaded from Ken French if missing
  factor_model = ['mktrf', 'smb', 'hml', 'umd'],
  etf_path     = 'public_data/etf_monthly_returns.csv', # optional: date + one column per ticker
  names_path   = None,                       # optional: CSV with permno,ticker,company
  extra_cols   = [],                         # more panel columns to load for new signals

  form_month = 12,                 # December formation; each cohort is held Jan-Dec
  first_form = '1985-12-31',       # first cohort -> first return month Jan 1986
  design_end = '2005-12-31',       # returns up to here = design sample (1986-2005); after = holdout (2006-2025)
  horizon    = 12,                 # months held per cohort

  # reporting windows, all ending at the sample end (book p.342)
  windows = {'1986-2025': ('1986-01-01', '2025-12-31'),
             '2006-2025': ('2006-01-01', '2025-12-31'),
             '2016-2025': ('2016-01-01', '2025-12-31')},

  # universe
  size_pct   = 0.50,               # NYSE ME percentile screen
  min_price  = 5.0,
  universe_needs = ['vol36'],      # columns that must be non-missing to be in the universe

  # portfolio defaults (a Strategy can override n and sector_cap)
  n_hold     = 40,
  sector_cap = 0.30,

  # min-variance weights
  cov_win = 60, shrink = 0.5, mv_cap = 0.05,

  n_trials = 10,                   # strategies tried so far, across all signal sets (deflated Sharpe ratio)
)
