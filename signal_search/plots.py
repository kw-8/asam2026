"""Charts: log growth of every strategy on one axis, drawdowns, rolling Sharpe."""
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
from .evaluate import excess

def _mark(ax, cfg):
  """Dashed line at the design/holdout split; dotted lines at each reporting-window start."""
  ax.axvline(pd.Timestamp(cfg['design_end']), color='k', ls='--', lw=0.8)
  for a, _ in cfg.get('windows', {}).values():
    ax.axvline(pd.Timestamp(a), color='grey', ls=':', lw=0.8)

def plot_log_growth(R, cfg, names=None, title='Cumulative log growth (log of $1 invested)'):
  """All strategies on one log-growth axis, so slopes compare directly."""
  W = np.log((1 + R[names or list(R.columns)].fillna(0)).cumprod())
  ax = W.plot(figsize=(13, 5), title=title)
  _mark(ax, cfg); ax.axhline(0, color='k', lw=0.5)
  ax.legend(loc='upper left', ncol=2, fontsize=8); plt.show()

def plot_perf(R, ff, cfg, roll_win=60):
  """Drawdowns and rolling Sharpe ratio (monthly path)."""
  W = (1 + R.fillna(0)).cumprod()
  ax = (W / W.cummax() - 1).plot(figsize=(13, 3.5), title='Drawdown', legend=False)
  _mark(ax, cfg); plt.show()
  rs = excess(R, ff).rolling(roll_win).apply(lambda x: x.mean() / x.std() * np.sqrt(12), raw=True)
  ax = rs.plot(figsize=(13, 3.5), title=f'Rolling {roll_win}-month Sharpe ratio', legend=False)
  ax.axhline(0, color='k', lw=0.8); _mark(ax, cfg); plt.show()
