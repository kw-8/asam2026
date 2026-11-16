"""
backtest_lazy_prices.py
=======================
Backtest of filing_sim (Lazy Prices, Cohen, Malloy & Nguyen 2020) as an AVOID SCREEN for ASAM:
hold the investable universe, leave out the bottom fifth (the biggest 10-K "changers").
The plan was fixed before any return was computed: signals/lazy_prices/backtest.md (2026-11-15).
This script follows it; it does not try variations.

Inputs (all local, no WRDS):
  data/crsp_monthly_ratios_clean.parquet           panel: returns, price, me, bm
  data/lazy_prices/lazy_prices_monthly.parquet     filing_sim, published_date, format_change_2010_14
  data/ff_monthly_kf.csv   Fama-French 5 factors + momentum + T-bill (Ken French, percent).
                           Downloaded from Ken French's data library if missing.

Outputs: data/lazy_prices/backtest/
  backtest_log.txt                everything printed
  portfolio_returns.csv           monthly returns of every portfolio and spread (by return month)
  fama_macbeth.csv                monthly Fama-MacBeth slopes
  annual_portfolio_returns.csv    December buy-and-hold check
  growth_1998.png, screen_effect.png   charts

Run from the repo root, with the .venv active (about a minute):
    python signals\\lazy_prices\\backtest_lazy_prices.py
"""
from __future__ import annotations

import io
import sys
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.tseries.offsets import MonthEnd

REPO = Path(__file__).resolve().parents[2]
D = REPO / "data" / "lazy_prices"
OUT = D / "backtest"
PANEL = REPO / "data" / "crsp_monthly_ratios_clean.parquet"
SIGNAL = D / "lazy_prices_monthly.parquet"
FF_CACHE = REPO / "data" / "ff_monthly_kf.csv"
KF_BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"

MIN_PRICE, MIN_ME = 5.0, 250_000          # me is in $ thousands -> $250 million
START = pd.Timestamp("1998-01-31")         # first formation month
LAST_FORM = pd.Timestamp("2025-11-30")     # last formation month (returns through 2025-12)
FLAG = "format_change_2010_14"
RECENT_MONTHS = 3                          # check (c): month of publication + next two
MIN_STOCKS = 50                            # skip a month if fewer stocks have a value (only bites in check (a))
NW_LAGS = 6
FACTORS = ["mktrf", "smb", "hml", "rmw", "cma", "umd"]
SUBPERIODS = [("1998-02", "2014-12"), ("2015-01", "2025-12")]
SUB_LABEL = {"1998-02": "1998-2014 (paper's sample)", "2015-01": "2015-2025 (out of sample)"}

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 40)


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            st.write(s)

    def flush(self):
        for st in self.streams:
            st.flush()


def show(df: pd.DataFrame, indent: int = 4, index: bool = True) -> None:
    pad = " " * indent
    print(pad + df.to_string(index=index).replace("\n", "\n" + pad))


def section(title: str) -> None:
    print("\n" + "=" * 90 + f"\n{title}\n" + "=" * 90)


# ----------------------------------------------------------------------------
# Statistics (numpy only: OLS with Newey-West standard errors)
# ----------------------------------------------------------------------------
def ols_nw(y: np.ndarray, X: np.ndarray, lags: int = NW_LAGS) -> tuple[np.ndarray, np.ndarray, float]:
    """OLS of y on X (X includes the constant). Returns coefficients, NW t-stats, R2."""
    y = np.asarray(y, dtype="float64")
    X = np.asarray(X, dtype="float64")
    n, k = X.shape
    xtx_inv = np.linalg.inv(X.T @ X)
    b = xtx_inv @ X.T @ y
    e = y - X @ b
    xe = X * e[:, None]
    s = xe.T @ xe
    for lag in range(1, min(lags, n - 1) + 1):
        w = 1 - lag / (lags + 1)
        g = xe[lag:].T @ xe[:-lag]
        s += w * (g + g.T)
    v = xtx_inv @ s @ xtx_inv
    with np.errstate(divide="ignore", invalid="ignore"):
        t = b / np.sqrt(np.diag(v))
    ss = (y - y.mean()) @ (y - y.mean())
    r2 = 1 - (e @ e) / ss if ss > 0 else np.nan
    return b, t, r2


def mean_t(s: pd.Series) -> tuple[float, float, int]:
    s = s.dropna()
    if len(s) < 12:
        return np.nan, np.nan, len(s)
    b, t, _ = ols_nw(s.values, np.ones((len(s), 1)))
    return b[0], t[0], len(s)


def ff_alpha(excess: pd.Series, ff: pd.DataFrame) -> dict:
    d = pd.concat([excess.rename("y"), ff[FACTORS]], axis=1, join="inner").dropna()
    if len(d) < 24:
        return {"alpha": np.nan, "t": np.nan, "n": len(d), "R2": np.nan,
                **{f: np.nan for f in FACTORS}, **{f"t_{f}": np.nan for f in FACTORS}}
    X = np.column_stack([np.ones(len(d)), d[FACTORS].values])
    b, t, r2 = ols_nw(d["y"].values, X)
    out = {"alpha": b[0] * 12, "t": t[0], "n": len(d), "R2": r2}
    out.update({f: b[i + 1] for i, f in enumerate(FACTORS)})
    out.update({f"t_{f}": t[i + 1] for i, f in enumerate(FACTORS)})
    return out


# ----------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------
def load_ff() -> pd.DataFrame:
    if not FF_CACHE.exists():
        print("  downloading Fama-French factors from Ken French's data library ...")

        def monthly(name: str) -> dict:
            raw = urllib.request.urlopen(KF_BASE + name + "_CSV.zip", timeout=60).read()
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                text = z.read(z.namelist()[0]).decode("latin-1")
            rows, started = {}, False
            for line in text.splitlines():
                c = [x.strip() for x in line.split(",")]
                if len(c[0]) == 6 and c[0].isdigit():
                    started = True
                    rows[c[0]] = c[1:]
                elif started:
                    break
            return rows

        f5, mo = monthly("F-F_Research_Data_5_Factors_2x3"), monthly("F-F_Momentum_Factor")
        lines = ["yyyymm,mktrf,smb,hml,rmw,cma,rf,umd"]
        for k in sorted(f5):
            if k >= "197901" and k in mo:
                lines.append(",".join([k] + f5[k][:6] + [mo[k][0]]))
        FF_CACHE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ff = pd.read_csv(FF_CACHE, dtype={"yyyymm": str})
    ff.index = pd.to_datetime(ff["yyyymm"], format="%Y%m") + MonthEnd(0)
    ff = ff.drop(columns="yyyymm").astype("float64") / 100
    print(f"  factors: {ff.index.min():%Y-%m} to {ff.index.max():%Y-%m} ({FF_CACHE.relative_to(REPO)})")
    return ff


def load() -> pd.DataFrame:
    p = pd.read_parquet(PANEL, columns=["permno", "date", "mthret", "prc", "me", "me_lag", "bm"])
    p["permno"] = pd.to_numeric(p["permno"]).astype("int64")
    p["date"] = pd.to_datetime(p["date"]) + MonthEnd(0)
    s = pd.read_parquet(SIGNAL, columns=["permno", "date", "filing_sim", "published_date", FLAG])
    s["permno"] = s["permno"].astype("int64")
    s["date"] = pd.to_datetime(s["date"]) + MonthEnd(0)
    df = p.merge(s, on=["permno", "date"], how="left", validate="one_to_one")
    for c in ["mthret", "prc", "me", "me_lag", "bm", "filing_sim"]:
        df[c] = df[c].astype("float64")          # plain floats (the parquet files use nullable types)
    df[FLAG] = df[FLAG].fillna(False).astype(bool)
    df = df.sort_values(["permno", "date"]).reset_index(drop=True)
    nxt = df.groupby("permno")["date"].shift(-1)
    df["ret_next"] = df.groupby("permno")["mthret"].shift(-1).where(nxt == df["date"] + MonthEnd(1))
    return df


def market_vw(df: pd.DataFrame) -> pd.Series:
    m = df[(df["me_lag"] > 0) & df["mthret"].notna()]
    return (m["mthret"] * m["me_lag"]).groupby(m["date"]).sum() / m.groupby("date")["me_lag"].sum()


def pct_rank(frame: pd.DataFrame, col: str) -> pd.Series:
    g = frame.groupby("date")[col]
    return (g.rank(method="average") - 0.5) / g.transform("count")


def bucket(pct: pd.Series, n: int) -> pd.Series:
    return (np.floor(pct * n).clip(upper=n - 1) + 1).astype("Int64")


# ----------------------------------------------------------------------------
# Portfolios
# ----------------------------------------------------------------------------
def group_returns(frame: pd.DataFrame, group: str) -> dict[str, pd.DataFrame]:
    """Monthly EW and VW returns per group; index = return month (t + 1)."""
    f = frame[frame[group].notna()]
    ew = f.groupby(["date", group])["ret_next"].mean().unstack()
    w = f["me"].where(f["ret_next"].notna())
    vw = ((f["ret_next"] * f["me"]).groupby([f["date"], f[group]]).sum(min_count=1)
          / w.groupby([f["date"], f[group]]).sum()).unstack()
    out = {}
    for name, x in (("EW", ew), ("VW", vw)):
        x = x.copy()
        x.index = x.index + MonthEnd(1)
        out[name] = x.dropna(how="all")
    return out


def turnover(frame: pd.DataFrame, member: pd.Series) -> dict[str, float]:
    """Average one-way monthly turnover (weights at formation, drift ignored)."""
    f = frame.loc[member[member].index, ["date", "permno", "me"]]
    res = {}
    for name in ("EW", "VW"):
        w = f.assign(w=1.0 if name == "EW" else f["me"])
        w["w"] = w["w"] / w.groupby("date")["w"].transform("sum")
        wide = w.pivot(index="date", columns="permno", values="w").fillna(0.0)
        res[name] = float((wide.diff().abs().sum(axis=1) / 2).iloc[1:].mean())
    return res


def fama_macbeth(frame: pd.DataFrame, xcols: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    f = frame.dropna(subset=xcols + ["ret_next"])
    rows = {}
    for d, g in f.groupby("date"):
        if len(g) < len(xcols) + 30:
            continue
        X = np.column_stack([np.ones(len(g)), g[xcols].values])
        b, *_ = np.linalg.lstsq(X, g["ret_next"].values, rcond=None)
        rows[d + MonthEnd(1)] = dict(zip(["const"] + xcols, b))
    coefs = pd.DataFrame(rows).T
    summ = []
    for c in xcols:
        m, t, n = mean_t(coefs[c])
        summ.append({"variable": c, "slope/yr": m * 12, "t": t, "months": n})
    return pd.DataFrame(summ), coefs


def add_ranks(frame: pd.DataFrame) -> pd.DataFrame:
    """Signal rank, quintile, decile and control ranks, all within the month.
    Months with fewer than MIN_STOCKS values are dropped (a 'portfolio' of a handful of stocks is noise)."""
    n = frame.groupby("date")["filing_sim"].transform("count")
    frame = frame[n >= MIN_STOCKS].copy()
    frame["pct"] = pct_rank(frame, "filing_sim")
    frame["q"] = bucket(frame["pct"], 5)
    frame["dec"] = bucket(frame["pct"], 10)
    frame["r_rev"] = pct_rank(frame, "mthret")
    frame["r_size"] = pct_rank(frame, "me")
    frame["r_bm"] = pct_rank(frame, "bm").fillna(0.5)
    frame["r_x"] = frame["pct"]
    return frame


def screen_returns(frame: pd.DataFrame, avoid: pd.Series) -> dict[str, pd.Series]:
    """Screened (universe minus avoid) and universe returns, EW and VW, by return month."""
    g = group_returns(frame.assign(keep=np.where(avoid, "avoid", "kept")), "keep")
    u = group_returns(frame.assign(all="all"), "all")
    out = {}
    for w in ("EW", "VW"):
        out[f"screened {w}"] = g[w]["kept"]
        out[f"universe {w}"] = u[w]["all"]
        out[f"avoided {w}"] = g[w]["avoid"]
        out[f"effect {w}"] = g[w]["kept"] - u[w]["all"]
    return out


def effect_row(name: str, s: pd.Series, ff: pd.DataFrame) -> dict:
    m, t, n = mean_t(s)
    fa = ff_alpha(s.dropna(), ff)
    return {"screen effect": name, "months": n, "mean/yr": m * 12, "t": t,
            "FF6 alpha/yr": fa["alpha"], "t(alpha)": fa["t"]}


# ----------------------------------------------------------------------------
# Annual (December) buy-and-hold, as in issuance_insider
# ----------------------------------------------------------------------------
def buy_and_hold(ret_wide: pd.DataFrame, picks: list, weights: np.ndarray, start: pd.Timestamp) -> pd.Series:
    end = start + MonthEnd(12)
    cols = [c for c in picks if c in ret_wide.columns]
    keep = np.isin(picks, cols)
    if not keep.all():
        raise ValueError(f"{(~keep).sum()} picked stocks have no returns loaded")
    r = ret_wide.loc[(ret_wide.index > start) & (ret_wide.index <= end), cols]
    if r.empty:
        return pd.Series(dtype="float64")
    w = np.asarray(weights, dtype=float)[keep]
    w = w / w.sum()
    value = (1 + r.fillna(0)).cumprod() * w
    start_value = value.shift(1)
    start_value.iloc[0] = w
    alive = r.notna()
    return (start_value * r).sum(axis=1) / start_value.where(alive).sum(axis=1)


# ----------------------------------------------------------------------------
def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "backtest_log.txt", "w", encoding="utf-8") as fh:
        sys.stdout = Tee(sys.__stdout__, fh)
        try:
            run()
        finally:
            sys.stdout = sys.__stdout__
    print(f"\nSaved: {(OUT / 'backtest_log.txt').relative_to(REPO)}")


def run() -> None:
    print(f"lazy_prices backtest, {pd.Timestamp.now():%Y-%m-%d %H:%M}  (plan: signals/lazy_prices/backtest.md)")
    section("0. Data")
    ff = load_ff()
    df = load()
    mkt = market_vw(df)
    rf = ff["rf"]
    inv = df[(df["prc"].abs() >= MIN_PRICE) & (df["me"] >= MIN_ME)
             & (df["date"] >= START) & (df["date"] <= LAST_FORM)]
    u = add_ranks(inv[inv["filing_sim"].notna()])
    per_month = u.groupby("date").size()
    inv_month = inv.groupby("date").size()
    print(f"  panel rows {len(df):,}; investable rows (|price| >= $5, me >= $250M, formation 1998-01 to 2025-11) {len(inv):,}")
    print(f"  with filing_sim: {len(u):,} rows = {len(u) / len(inv):.1%} of investable rows; "
          f"{per_month.mean():.0f} stocks/month (min {per_month.min()}, max {per_month.max()})")
    cov = (per_month / inv_month).groupby(per_month.index.year).mean()
    print("  share of investable stocks with a value, by year: "
          + ", ".join(f"{y}: {v:.0%}" for y, v in cov.items()))
    vwcov = (u.groupby("date")["me"].sum() / inv.groupby("date")["me"].sum()).mean()
    print(f"  share of investable market value with a value: {vwcov:.1%} (average month)")
    print(f"  rows flagged {FLAG}: {u[FLAG].sum():,} ({u[FLAG].mean():.1%}); "
          f"months with flagged rows: {u.loc[u[FLAG], 'date'].min():%Y-%m} to {u.loc[u[FLAG], 'date'].max():%Y-%m}")
    thin = per_month[per_month < 500]
    if len(thin):
        print(f"  months with fewer than 500 stocks: {', '.join(f'{d:%Y-%m} ({n})' for d, n in thin.items())}"
              " -- filings end 2024-12, so late-2025 months hold only firms with mid-2024 10-Ks")
    qn = u.groupby(["date", "q"]).size().unstack()
    print(f"  stocks per quintile (average month): " + ", ".join(f"Q{q} {qn[q].mean():.0f}" for q in qn.columns))
    print(f"  filing_sim by quintile (median): " + ", ".join(
        f"Q{q} {v:.3f}" for q, v in u.groupby("q")["filing_sim"].median().items()))

    # ------------------------------------------------------------------ portfolios
    g_q = group_returns(u, "q")
    main_s = screen_returns(u, u["q"] == 1)
    dec_s = screen_returns(u, u["dec"] == 1)
    ua = add_ranks(u[~u[FLAG]])                                 # check (a): flagged values -> missing
    gone = sorted(set(u["date"]) - set(ua["date"]))
    print(f"  check (a): {len(gone)} formation months have fewer than {MIN_STOCKS} unflagged values and are skipped "
          f"({gone[0]:%Y-%m} to {gone[-1]:%Y-%m}); every firm's latest 10-K in 2011-2014 is from 2010-2014")
    a_s = screen_returns(ua, ua["q"] == 1)
    u["months_since"] = ((u["date"].dt.year - u["published_date"].dt.year) * 12
                         + (u["date"].dt.month - u["published_date"].dt.month))
    recent = u["months_since"] < RECENT_MONTHS
    c_s = screen_returns(u, (u["q"] == 1) & recent)             # check (c): avoid recent changers only

    series, spreads = {}, {}
    for w in ("EW", "VW"):
        for q in range(1, 6):
            series[f"Q{q} {w}"] = g_q[w][q]
        series[f"Universe {w}"] = main_s[f"universe {w}"]
        series[f"Screened {w}"] = main_s[f"screened {w}"]
        spreads[f"Screen effect {w}"] = main_s[f"effect {w}"]
        spreads[f"Q5-Q1 {w}"] = g_q[w][5] - g_q[w][1]
        spreads[f"Q1-universe {w}"] = g_q[w][1] - main_s[f"universe {w}"]
        spreads[f"Q5-universe {w}"] = g_q[w][5] - main_s[f"universe {w}"]
        spreads[f"Check a effect {w}"] = a_s[f"effect {w}"]
        spreads[f"Check b effect {w}"] = dec_s[f"effect {w}"]
        spreads[f"Check c effect {w}"] = c_s[f"effect {w}"]
    series["Market VW"] = mkt
    allret = pd.DataFrame(series).join(pd.DataFrame(spreads), how="outer").loc["1998-02-28":"2025-12-31"]
    allret.to_csv(OUT / "portfolio_returns.csv", index_label="return_month")

    # weight of what is left out
    q1w = (u["me"].where(u["q"] == 1).groupby(u["date"]).sum() / u.groupby("date")["me"].sum())
    d1w = (u["me"].where(u["dec"] == 1).groupby(u["date"]).sum() / u.groupby("date")["me"].sum())
    cw = (u["me"].where((u["q"] == 1) & recent).groupby(u["date"]).sum() / u.groupby("date")["me"].sum())
    cn = ((u["q"] == 1) & recent).groupby(u["date"]).mean()
    counts = {"Screened": u[u["q"] >= 2].groupby("date").size(), "Universe": per_month,
              "Q5": u[u["q"] == 5].groupby("date").size(), "Q1": u[u["q"] == 1].groupby("date").size()}
    turns = {"Screened": turnover(u, u["q"] >= 2), "Universe": turnover(u, pd.Series(True, index=u.index)),
             "Q5": turnover(u, u["q"] == 5), "Q1": turnover(u, u["q"] == 1)}

    # ------------------------------------------------------------------ 1. screen effect (PRIMARY 2)
    section("1. The avoid screen: Screened (universe minus Q1) minus universe (PRIMARY: FF6 alpha)")
    erows = [effect_row(f"leave out Q1 (bottom fifth) {w}", allret[f"Screen effect {w}"], ff) for w in ("EW", "VW")]
    show(pd.DataFrame(erows).set_index("screen effect").round({"mean/yr": 4, "t": 2, "FF6 alpha/yr": 4, "t(alpha)": 2}))
    print(f"  share of the universe left out: EW {qn[1].mean() / per_month.mean():.1%} of stocks; "
          f"VW {q1w.mean():.1%} of market value on average (min {q1w.min():.1%}, max {q1w.max():.1%})")
    print("  mean/yr = average monthly difference x 12; FF6 = Fama-French 5 + momentum; t-stats Newey-West(6)")

    section("1b. Factor loadings of the screen effect and of Q5-Q1 (coefficient and t)")
    lrows = []
    for col in ("Screen effect EW", "Screen effect VW", "Q5-Q1 EW", "Q5-Q1 VW"):
        fa = ff_alpha(allret[col].dropna(), ff)
        lrows.append({"series": col, "alpha/yr": f"{fa['alpha']:+.4f} ({fa['t']:+.1f})",
                      **{f: f"{fa[f]:+.3f} ({fa['t_' + f]:+.1f})" for f in FACTORS}, "R2": round(fa["R2"], 2)})
    show(pd.DataFrame(lrows).set_index("series"))

    # ------------------------------------------------------------------ 2. long-only portfolios
    section("2. Long-only portfolios, rebalanced monthly (descriptive)")

    def long_row(name: str, r: pd.Series, n_avg=np.nan, turn=np.nan) -> dict:
        r = r.dropna()
        ex = (r - rf.reindex(r.index)).dropna()
        act = (r - mkt.reindex(r.index)).dropna()
        a_m, a_t, _ = mean_t(act)
        fa = ff_alpha(ex, ff)
        return {"portfolio": name, "months": len(r), "stocks": n_avg,
                "excess/yr": ex.mean() * 12, "vol/yr": ex.std() * np.sqrt(12), "Sharpe": ex.mean() / ex.std() * np.sqrt(12),
                "vs mkt/yr": a_m * 12, "t(vs mkt)": a_t, "FF6 alpha/yr": fa["alpha"], "t(alpha)": fa["t"],
                "turnover/mo": turn}

    rows = []
    for w in ("EW", "VW"):
        for k in ("Screened", "Universe", "Q5", "Q1"):
            rows.append(long_row(f"{k} {w}", allret[f"{k} {w}"], counts[k].mean(), turns[k][w]))
    rows.append(long_row("Market VW (all panel stocks)", allret["Market VW"]))
    t2 = pd.DataFrame(rows).set_index("portfolio")
    show(t2.round({"stocks": 0, "excess/yr": 4, "vol/yr": 3, "Sharpe": 2, "vs mkt/yr": 4, "t(vs mkt)": 2,
                   "FF6 alpha/yr": 4, "t(alpha)": 2, "turnover/mo": 3}))
    print("  excess = over T-bills; vs mkt = minus the market (value-weighted, all panel stocks); "
          "turnover = one-way share of the portfolio traded per month")
    for w in ("EW", "VW"):
        print(f"  extra turnover from the screen ({w}): {turns['Screened'][w] - turns['Universe'][w]:+.3f} per month")

    section("3. Average return by quintile (excess over T-bills, per year) and spreads")
    qrows = {w: {f"Q{q}": (allret[f"Q{q} {w}"] - rf).dropna().mean() * 12 for q in range(1, 6)} for w in ("EW", "VW")}
    show(pd.DataFrame(qrows).T.round(4))
    print("  Q1 = lowest similarity (biggest changers), Q5 = highest (non-changers)")
    srows = []
    for col in [c for c in spreads if c.startswith(("Q5-Q1", "Q1-universe", "Q5-universe"))]:
        s = allret[col].dropna()
        m, t, n = mean_t(s)
        fa = ff_alpha(s, ff)
        srows.append({"spread": col, "months": n, "mean/yr": m * 12, "t": t, "FF6 alpha/yr": fa["alpha"], "t(alpha)": fa["t"]})
    show(pd.DataFrame(srows).set_index("spread").round(3))

    # ------------------------------------------------------------------ 4. Fama-MacBeth (PRIMARY 1)
    section("4. Fama-MacBeth: next-month return on the percentile rank of filing_sim (PRIMARY: slope with controls)")
    ctrl = ["r_rev", "r_bm", "r_size"]
    specs = [("filing_sim alone", u, ["r_x"]), ("PRIMARY filing_sim + controls", u, ["r_x"] + ctrl)]
    fm_rows, fm_coefs = [], {}
    for name, frame, xs in specs:
        summ, coefs = fama_macbeth(frame, xs)
        fm_coefs[name] = coefs
        for r in summ.itertuples(index=False):
            fm_rows.append({"model": name, "variable": r.variable, "slope/yr": r._1, "t": r.t, "months": r.months})
    show(pd.DataFrame(fm_rows).round({"slope/yr": 4, "t": 2}), index=False)
    print("  slope/yr = annualized return difference between the lowest- and highest-similarity stock (rank 0 -> 1);"
          " controls: ranks of last month's return (reversal), bm (missing -> 0.5) and size")

    # ------------------------------------------------------------------ 5. named checks
    section("5. Named checks side by side (never swapped in for the primary)")
    chk = []
    for name, frame, eff in [("PRIMARY all values, leave out Q1", u, main_s),
                             ("(a) without flagged 2010-2014 10-Ks", ua, a_s),
                             ("(b) leave out bottom tenth instead", None, dec_s),
                             ("(c) recent 10-Ks only (last 3 months)", u[recent], c_s)]:
        row = {"check": name}
        if frame is not None:
            summ, coefs = fama_macbeth(frame, ["r_x"] + ctrl)
            fm_coefs[name] = coefs
            r = summ.iloc[0]
            row.update({"FM slope/yr": r["slope/yr"], "t(FM)": r["t"], "FM months": r["months"]})
        for w in ("EW", "VW"):
            er = effect_row("", eff[f"effect {w}"], ff)
            row.update({f"effect {w}/yr": er["mean/yr"], f"t {w}": er["t"],
                        f"alpha {w}/yr": er["FF6 alpha/yr"], f"t(a) {w}": er["t(alpha)"]})
        chk.append(row)
    show(pd.DataFrame(chk).set_index("check").round(3))
    print(f"  (b) leaves out {d1w.mean():.1%} of market value on average; "
          f"(c) leaves out {cn.mean():.1%} of stocks and {cw.mean():.1%} of market value "
          f"(Q1 stocks whose 10-K was published in the last {RECENT_MONTHS} months)")
    print("  (c) Fama-MacBeth uses only recent filers, ranked against all stocks that month")
    pd.concat({k: v for k, v in fm_coefs.items()}, names=["model", "return_month"]).to_csv(OUT / "fama_macbeth.csv")

    # ------------------------------------------------------------------ 6. sub-periods
    section("6. Sub-periods: 1998-2014 (overlaps the paper's sample) vs 2015-2025 (after it)")
    prow = []
    fm_primary = fm_coefs["PRIMARY filing_sim + controls"]["r_x"]
    for a, b in SUBPERIODS:
        fm_m, fm_t, _ = mean_t(fm_primary.loc[a:b])
        for w in ("EW", "VW"):
            e = allret[f"Screen effect {w}"].loc[a:b].dropna()
            em, et, _ = mean_t(e)
            fa = ff_alpha(e, ff)
            sp = allret[f"Q5-Q1 {w}"].loc[a:b].dropna()
            sm, st, _ = mean_t(sp)
            scr = (allret[f"Screened {w}"].loc[a:b] - rf).dropna()
            uni = (allret[f"Universe {w}"].loc[a:b] - rf).dropna()
            prow.append({"period": SUB_LABEL[a], "weights": w, "FM slope/yr": fm_m * 12, "t(FM)": fm_t,
                         "effect/yr": em * 12, "t(effect)": et, "effect alpha/yr": fa["alpha"], "t(alpha)": fa["t"],
                         "Sharpe screened": scr.mean() / scr.std() * np.sqrt(12),
                         "Sharpe universe": uni.mean() / uni.std() * np.sqrt(12),
                         "Q5-Q1/yr": sm * 12, "t(Q5-Q1)": st})
    show(pd.DataFrame(prow).set_index(["period", "weights"]).round(3))
    print("  FM slope is the same for EW and VW (one regression per month); shown on both rows")

    section("6b. By year: screen effect (VW, EW) and what Q1 holds")
    yr = pd.DataFrame({
        "effect VW": allret["Screen effect VW"].groupby(allret.index.year).sum(),
        "effect EW": allret["Screen effect EW"].groupby(allret.index.year).sum(),
        "Q5-Q1 VW": allret["Q5-Q1 VW"].groupby(allret.index.year).sum(),
    })
    form = q1w.copy()
    form.index = form.index + MonthEnd(1)                     # align formation weights with return months
    yr["Q1 share of value"] = form.groupby(form.index.year).mean()
    big = u.assign(big=pct_rank(u, "me") >= 0.8)
    q1big = big[big["q"] == 1].groupby("date")["big"].mean()
    q1big.index = q1big.index + MonthEnd(1)
    yr["Q1 share largest fifth"] = q1big.groupby(q1big.index.year).mean()
    show(yr.round(3))
    print("  effect columns: sum of monthly differences in the year; 'Q1 share largest fifth' = share of Q1 stocks"
          " that are among the largest fifth of the universe (20% = no size tilt)")

    # ------------------------------------------------------------------ 7. annual check
    section("7. Annual check: formed each December, held for the next calendar year (buy-and-hold)")
    dec = u[u["date"].dt.month == 12]
    sub = df[df["permno"].isin(set(dec["permno"])) & (df["date"] >= START)]
    ret_wide = sub.pivot(index="date", columns="permno", values="mthret").astype("float64")
    ann = {}
    for k, mem in (("Screened", dec["q"] >= 2), ("Universe", pd.Series(True, index=dec.index))):
        for w in ("EW", "VW"):
            parts = []
            for d, g in dec[mem].groupby("date"):
                wts = np.ones(len(g)) if w == "EW" else g["me"].values
                parts.append(buy_and_hold(ret_wide, g["permno"].tolist(), wts, d))
            ann[f"{k} {w}"] = pd.concat(parts).loc[:"2025-12-31"]
    for w in ("EW", "VW"):
        ann[f"Annual screen effect {w}"] = ann[f"Screened {w}"] - ann[f"Universe {w}"]
    arows = []
    for name, r in ann.items():
        r = r.dropna()
        if name.startswith("Annual screen effect"):
            m, t, _ = mean_t(r)
            fa = ff_alpha(r, ff)
            arows.append({"portfolio": name, "from": f"{r.index.min():%Y-%m}", "excess/yr": np.nan, "Sharpe": np.nan,
                          "vs mkt/yr": np.nan, "t(vs mkt)": np.nan, "effect/yr": m * 12, "t(effect)": t,
                          "FF6 alpha/yr": fa["alpha"], "t(alpha)": fa["t"]})
            continue
        ex = (r - rf.reindex(r.index)).dropna()
        act = (r - mkt.reindex(r.index)).dropna()
        m, t, _ = mean_t(act)
        fa = ff_alpha(ex, ff)
        arows.append({"portfolio": name, "from": f"{r.index.min():%Y-%m}", "excess/yr": ex.mean() * 12,
                      "Sharpe": ex.mean() / ex.std() * np.sqrt(12), "vs mkt/yr": m * 12, "t(vs mkt)": t,
                      "effect/yr": np.nan, "t(effect)": np.nan, "FF6 alpha/yr": fa["alpha"], "t(alpha)": fa["t"]})
    show(pd.DataFrame(arows).set_index("portfolio").round(3))
    for a, b in SUBPERIODS:
        bits = []
        for w in ("EW", "VW"):
            m, t, _ = mean_t(ann[f"Annual screen effect {w}"].loc[a:b])
            bits.append(f"{w} {m * 12:+.4f}/yr (t {t:+.2f})")
        print(f"  annual screen effect {SUB_LABEL[a]}: " + "; ".join(bits))
    pd.DataFrame(ann).to_csv(OUT / "annual_portfolio_returns.csv", index_label="return_month")

    # ------------------------------------------------------------------ charts
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        cols = ["Screened VW", "Universe VW", "Q1 VW", "Market VW"]
        g = (1 + allret[cols].fillna(0)).cumprod()
        ax = g.plot(logy=True, figsize=(10, 5), lw=1.4,
                    title="Avoid screen (leave out the bottom fifth of filing_sim), value-weighted, 1998-02 to 2025-12")
        ax.set_ylabel("Growth of $1 (log scale)")
        plt.tight_layout()
        plt.savefig(OUT / "growth_1998.png", dpi=120)
        plt.close()
        eff = allret[["Screen effect EW", "Screen effect VW"]].fillna(0).cumsum() * 100
        ax = eff.plot(figsize=(10, 4.5), lw=1.4, title="Cumulative screen effect: Screened minus universe (percentage points)")
        ax.axhline(0, color="grey", lw=0.8)
        fl = u.loc[u[FLAG], "date"]
        ax.axvspan(fl.min() + MonthEnd(1), fl.max() + MonthEnd(1), color="grey", alpha=0.12,
                   label="months using 2010-2014 10-Ks (flagged)")
        ax.axvline(pd.Timestamp("2014-12-31"), color="black", lw=0.8, ls="--")
        ax.set_ylabel("cumulative sum, pp")
        ax.legend(loc="upper left")
        plt.tight_layout()
        plt.savefig(OUT / "screen_effect.png", dpi=120)
        plt.close()
        print(f"\n  charts: {(OUT / 'growth_1998.png').relative_to(REPO)}, {(OUT / 'screen_effect.png').relative_to(REPO)}")
    except ImportError:
        print("\n  matplotlib not installed: charts skipped")
    print("\nDone. Reply 'done' in the chat; Claude will read data/lazy_prices/backtest/backtest_log.txt.")


if __name__ == "__main__":
    main()
