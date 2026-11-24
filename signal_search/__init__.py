"""Strategy lab: everything the notebook calls. `from lab import *` brings in the names below."""
import numpy as np, pandas as pd
from .config import DEFAULT_CFG
from .data import load_data, load_panel, load_ff_factors, load_etf_returns, load_names
from .synthetic import make_synthetic_panel, make_synthetic_factors, make_synthetic_etfs
from .signals import roll, lag, add_volatility, add_momentum, add_ff12, vw_market
from .portfolio import (Strategy, prepare, run, form_universe, rank, composite, mom_ok, select,
                        build_holdings, bh_returns, WEIGHTS)
from .evaluate import (perf, perf_monthly, report, split, to_annual, annual_factors, excess,
                       dsr_table, name_turnover, weight_summary)
from .diagnostics import screen, fama_macbeth, comove
from .plots import plot_log_growth, plot_perf
from .extras import by_formation_month, multi_asset, current_portfolio
