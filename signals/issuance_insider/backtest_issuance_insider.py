"""
backtest_issuance_insider.py
============================
Backtest of net_issuance, insider_cluster and their combinations C1 and C2 for ASAM.
The plan was fixed before any return was computed: signals/issuance_insider/backtest.md
(2026-11-16). This script follows it; it does not try variations.

Inputs (all local, no WRDS):
  data/crsp_monthly_ratios_clean.parquet                 panel: returns, price, me, bm
  data/issuance_insider/net_issuance_monthly.parquet     signal 1 + named checks
  data/issuance_insider/insider_cluster_monthly.parquet  signal 2 + named checks
  data/ff_monthly_kf.csv   Fama-French 5 factors + momentum + T-bill (Ken French, percent).
                           Downloaded from Ken French's data library on the first run and
                           kept there; delete it to download again.

Outputs: data/issuance_insider/backtest/
  backtest_log.txt            everything printed
  portfolio_returns.csv       monthly returns of every portfolio and spread (by return month)
  fama_macbeth.csv            monthly Fama-MacBeth slopes
  growth_2006.png, growth_1980.png   growth of $1

Run from the repo root, with the .venv active (about 3-6 minutes):
    python signals\\issuance_insider\\backtest_issuance_insider.py
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
D = REPO / "data" / "issuance_insider"
OUT = D / "backtest"
PANEL = REPO / "data" / "crsp_monthly_ratios_clean.parquet"
FF_CACHE = REPO / "data" / "ff_monthly_kf.csv"
KF_BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"

MIN_PRICE, MIN_ME = 5.0, 250_000          # me is in $ thousands -> $250 million
START = pd.Timestamp("1980-01-31")         # first formation month for net_issuance
INS_START = pd.Timestamp("2006-03-31")     # first formation month for insider_cluster (3-month window)
NW_LAGS = 6
FACTORS = ["mktrf", "smb", "hml", "rmw", "cma", "umd"]
NI_CHECKS = ["net_issuance_skip3", "net_issuance_skip6", "net_issuance_pit", "comp_issuance", "net_issuance_5y"]
IC_CHECKS = ["insider_buyers_1m", "insider_buy_value_3m", "insider_npr_6m"]
SUBPERIODS = {
    "net_issuance": [("1980-02", "2007-12"), ("2008-01", "2025-12"), ("2006-04", "2025-12")],
    "other": [("2006-04", "2016-12"), ("2017-01", "2025-12")],
}

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
        return {"alpha": np.nan, "t": np.nan, "n": len(d)}
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

        def monthly(name: str) -> pd.DataFrame:
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
    ni = pd.read_parquet(D / "net_issuance_monthly.parquet", columns=["permno", "date", "net_issuance"] + NI_CHECKS)
    ic = pd.read_parquet(D / "insider_cluster_monthly.parquet", columns=["permno", "date", "insider_cluster"] + IC_CHECKS)
    for x in (ni, ic):
        x["permno"] = x["permno"].astype("int64")
        x["date"] = pd.to_datetime(x["date"]) + MonthEnd(0)
    df = p.merge(ni, on=["permno", "date"], how="left").merge(ic, on=["permno", "date"], how="left")
    num = [c for c in df.columns if c not in ("permno", "date")]
    df[num] = df[num].astype("float64")          # plain floats (the parquet files use nullable types)
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


def quintile(pct: pd.Series) -> pd.Series:
    return (np.floor(pct * 5).clip(upper=4) + 1).astype("Int64")


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
    """Average one-way monthly turnover of the long-only portfolio (weights at formation, drift ignored)."""
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


# ----------------------------------------------------------------------------
# Annual (December) buy-and-hold, as in the gpa notebook
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
    print(f"issuance_insider backtest, {pd.Timestamp.now():%Y-%m-%d %H:%M}  (plan: signals/issuance_insider/backtest.md)")
    section("0. Data")
    ff = load_ff()
    df = load()
    mkt = market_vw(df)
    rf = ff["rf"]
    u = df[(df["prc"].abs() >= MIN_PRICE) & (df["me"] >= MIN_ME) & (df["date"] >= START)].copy()
    u = u[u["date"] < u["date"].max()]          # the last month has no next-month return
    print(f"  panel rows {len(df):,}; investable rows (|price| >= $5, me >= $250M, from 1980-01) {len(u):,}")

    # signal directions: high = what the hypothesis buys
    u["s_ni"] = -u["net_issuance"]
    u["s_ic"] = u["insider_cluster"]
    for c in NI_CHECKS:
        u[f"s_{c}"] = -u[c]
    for c in IC_CHECKS:
        u[f"s_{c}"] = u[c]

    ni = u[u["s_ni"].notna()].copy()
    ni["pct"] = pct_rank(ni, "s_ni")
    ni["q"] = quintile(ni["pct"])
    both = u[(u["date"] >= INS_START) & u["s_ni"].notna() & u["s_ic"].notna()].copy()
    both["pct_ni"] = pct_rank(both, "s_ni")
    both["pct_ic"] = pct_rank(both, "s_ic")
    both["c2"] = (both["pct_ni"] + both["pct_ic"]) / 2
    both["pct_c2"] = pct_rank(both, "c2")
    both["q_c2"] = quintile(both["pct_c2"])
    both["cluster"] = np.where(both["s_ic"] >= 1, "cluster", "none")
    both["c1"] = np.where((both["net_issuance"] < 0) & (both["s_ic"] >= 1), "C1", "other")
    ic = u[(u["date"] >= INS_START) & u["s_ic"].notna()].copy()
    ic["cluster"] = np.where(ic["s_ic"] >= 1, "cluster", "none")
    print(f"  net_issuance: {ni['date'].min():%Y-%m} to {ni['date'].max():%Y-%m}, "
          f"{ni.groupby('date').size().mean():.0f} stocks/month (min {ni.groupby('date').size().min()})")
    print(f"  insider_cluster: {ic['date'].min():%Y-%m} to {ic['date'].max():%Y-%m}, "
          f"{ic.groupby('date').size().mean():.0f} stocks/month; with both signals {both.groupby('date').size().mean():.0f}")
    rc = both.groupby("date")[["pct_ni", "pct_ic"]].corr().xs("pct_ni", level=1)["pct_ic"]
    print(f"  average monthly rank correlation of -net_issuance and insider_cluster: {rc.mean():+.3f}")

    # ------------------------------------------------------------------ portfolios
    g_ni = group_returns(ni, "q")
    g_ni_all = group_returns(ni.assign(all="all"), "all")
    g_ic = group_returns(ic, "cluster")
    g_ic_all = group_returns(ic.assign(all="all"), "all")
    g_c1 = group_returns(both, "c1")
    g_both = group_returns(both.assign(all="all"), "all")
    g_c2 = group_returns(both, "q_c2")
    series, spreads = {}, {}
    for w in ("EW", "VW"):
        for q in range(1, 6):
            series[f"NI Q{q} {w}"] = g_ni[w][q]
        series[f"NI universe {w}"] = g_ni_all[w]["all"]
        series[f"IC cluster {w}"] = g_ic[w]["cluster"]
        series[f"IC no cluster {w}"] = g_ic[w]["none"]
        series[f"IC universe {w}"] = g_ic_all[w]["all"]
        series[f"C1 {w}"] = g_c1[w]["C1"]
        series[f"Both-signal universe {w}"] = g_both[w]["all"]
        for q in range(1, 6):
            series[f"C2 Q{q} {w}"] = g_c2[w][q]
        spreads[f"NI Q5-Q1 {w}"] = g_ni[w][5] - g_ni[w][1]
        spreads[f"NI Q5-universe {w}"] = g_ni[w][5] - g_ni_all[w]["all"]
        spreads[f"IC cluster-none {w}"] = g_ic[w]["cluster"] - g_ic[w]["none"]
        spreads[f"IC cluster-universe {w}"] = g_ic[w]["cluster"] - g_ic_all[w]["all"]
        spreads[f"C1-both universe {w}"] = g_c1[w]["C1"] - g_both[w]["all"]
        spreads[f"C2 Q5-Q1 {w}"] = g_c2[w][5] - g_c2[w][1]
        spreads[f"C2 Q5-universe {w}"] = g_c2[w][5] - g_both[w]["all"]
    series["Market VW"] = mkt
    allret = pd.DataFrame(series).join(pd.DataFrame(spreads), how="outer").loc["1980-02-29":"2025-12-31"]
    allret.to_csv(OUT / "portfolio_returns.csv", index_label="return_month")

    members = {"NI Q5": ni["q"] == 5, "IC cluster": ic["cluster"] == "cluster",
               "C1": both["c1"] == "C1", "C2 Q5": both["q_c2"] == 5}
    frames = {"NI Q5": ni, "IC cluster": ic, "C1": both, "C2 Q5": both}
    counts = {k: frames[k][v].groupby("date").size() for k, v in members.items()}
    turns = {k: turnover(frames[k], v) for k, v in members.items()}

    # ------------------------------------------------------------------ 1. long-only
    section("1. Long-only portfolios, rebalanced monthly (PRIMARY: FF5+UMD alpha)")

    def long_row(name: str, r: pd.Series, n_avg=np.nan, turn=np.nan) -> dict:
        r = r.dropna()
        ex = (r - rf.reindex(r.index)).dropna()
        act = (r - mkt.reindex(r.index)).dropna()
        a_m, a_t, _ = mean_t(act)
        fa = ff_alpha(ex, ff)
        return {"portfolio": name, "months": len(r), "from": f"{r.index.min():%Y-%m}", "stocks": n_avg,
                "excess/yr": ex.mean() * 12, "vol/yr": ex.std() * np.sqrt(12), "Sharpe": ex.mean() / ex.std() * np.sqrt(12),
                "vs mkt/yr": a_m * 12, "t(vs mkt)": a_t, "FF6 alpha/yr": fa["alpha"], "t(alpha)": fa["t"],
                "turnover/mo": turn}

    rows = []
    for w in ("EW", "VW"):
        for k, col in (("NI Q5", f"NI Q5 {w}"), ("IC cluster", f"IC cluster {w}"), ("C1", f"C1 {w}"), ("C2 Q5", f"C2 Q5 {w}")):
            rows.append(long_row(f"{k} {w}", allret[col], counts[k].mean(), turns[k][w]))
        rows.append(long_row(f"NI universe {w}", allret[f"NI universe {w}"]))
        rows.append(long_row(f"Both-signal universe {w} (2006+)", allret[f"Both-signal universe {w}"]))
    rows.append(long_row("Market VW (1980+)", allret["Market VW"]))
    rows.append(long_row("Market VW (2006-04+)", allret["Market VW"].loc["2006-04-30":]))
    t1 = pd.DataFrame(rows).set_index("portfolio")
    show(t1.round({"stocks": 0, "excess/yr": 4, "vol/yr": 3, "Sharpe": 2, "vs mkt/yr": 4, "t(vs mkt)": 2,
                   "FF6 alpha/yr": 4, "t(alpha)": 2, "turnover/mo": 3}))
    print("  excess = over T-bills; vs mkt = minus the market (value-weighted, all panel stocks); FF6 = Fama-French 5 + momentum;"
          " t-stats Newey-West(6); turnover = one-way share of the portfolio traded per month")

    section("1b. Factor loadings of the long-only portfolios (FF5 + momentum, coefficient and t)")
    lrows = []
    for w in ("EW", "VW"):
        for k, col in (("NI Q5", f"NI Q5 {w}"), ("IC cluster", f"IC cluster {w}"), ("C1", f"C1 {w}"), ("C2 Q5", f"C2 Q5 {w}")):
            r = allret[col].dropna()
            fa = ff_alpha((r - rf.reindex(r.index)).dropna(), ff)
            lrows.append({"portfolio": f"{k} {w}", **{f: f"{fa[f]:+.2f} ({fa['t_' + f]:+.1f})" for f in FACTORS},
                          "R2": round(fa["R2"], 2)})
    show(pd.DataFrame(lrows).set_index("portfolio"))

    # ------------------------------------------------------------------ 2. spreads
    section("2. Spreads (zero-investment), rebalanced monthly")
    srows = []
    for col in spreads:
        s = allret[col].dropna()
        m, t, n = mean_t(s)
        fa = ff_alpha(s, ff)
        srows.append({"spread": col, "months": n, "mean/yr": m * 12, "t": t, "FF6 alpha/yr": fa["alpha"], "t(alpha)": fa["t"]})
    show(pd.DataFrame(srows).set_index("spread").round(3))

    section("3. Average return by quintile (excess over T-bills, per year)")
    qrows = {}
    for lab, pre in (("net_issuance (1980+)", "NI"), ("C2 (2006+)", "C2")):
        for w in ("EW", "VW"):
            qrows[f"{lab} {w}"] = {f"Q{q}": (allret[f"{pre} Q{q} {w}"] - rf).dropna().mean() * 12 for q in range(1, 6)}
    show(pd.DataFrame(qrows).T.round(4))
    print("  Q1 = most net issuance / lowest combined rank; Q5 = most net buyback / highest combined rank")

    # ------------------------------------------------------------------ 4. Fama-MacBeth
    section("4. Fama-MacBeth: next-month return on percentile ranks (PRIMARY: slope with controls)")
    for frame in (ni, ic, both):
        frame["r_rev"] = pct_rank(frame, "mthret")
        frame["r_size"] = pct_rank(frame, "me")
        frame["r_bm"] = pct_rank(frame, "bm").fillna(0.5)
    ni["r_ni"] = ni["pct"]
    ic["r_ic"] = pct_rank(ic, "s_ic")
    both["r_ni"], both["r_ic"], both["r_c2"] = both["pct_ni"], both["pct_ic"], both["pct_c2"]
    ctrl = ["r_rev", "r_bm", "r_size"]
    specs = [("net_issuance, 1980+", ni, ["r_ni"]), ("net_issuance + controls, 1980+", ni, ["r_ni"] + ctrl),
             ("net_issuance + controls, 2006+", ni[ni["date"] >= INS_START], ["r_ni"] + ctrl),
             ("insider_cluster, 2006+", ic, ["r_ic"]), ("insider_cluster + controls, 2006+", ic, ["r_ic"] + ctrl),
             ("both + controls, 2006+", both, ["r_ni", "r_ic"] + ctrl), ("C2 rank + controls, 2006+", both, ["r_c2"] + ctrl)]
    fm_rows, fm_coefs = [], {}
    for name, frame, xs in specs:
        summ, coefs = fama_macbeth(frame, xs)
        fm_coefs[name] = coefs
        for r in summ.itertuples(index=False):
            fm_rows.append({"model": name, "variable": r.variable, "slope/yr": r._1, "t": r.t, "months": r.months})
    show(pd.DataFrame(fm_rows).round({"slope/yr": 4, "t": 2}), index=False)
    print("  slope/yr = annualized return difference between the lowest- and highest-ranked stock (rank 0 -> 1);"
          " controls: ranks of last month's return (reversal), bm (missing -> 0.5) and size")
    pd.concat({k: v for k, v in fm_coefs.items()}, names=["model", "return_month"]).to_csv(OUT / "fama_macbeth.csv")

    section("5. Named checks side by side (Fama-MacBeth with the same controls; never swapped in for the primary)")
    crow = []
    for c in ["net_issuance"] + NI_CHECKS:
        s = "s_ni" if c == "net_issuance" else f"s_{c}"
        f = u[u[s].notna()].copy()
        f["r_x"] = pct_rank(f, s)
        f["r_rev"], f["r_size"] = pct_rank(f, "mthret"), pct_rank(f, "me")
        f["r_bm"] = pct_rank(f, "bm").fillna(0.5)
        summ, _ = fama_macbeth(f, ["r_x"] + ctrl)
        r = summ.iloc[0]
        crow.append({"signal": ("PRIMARY " if c == "net_issuance" else "check ") + c + " (sign flipped)",
                     "from": f"{f['date'].min():%Y-%m}", "slope/yr": r["slope/yr"], "t": r["t"], "months": r["months"]})
    for c in ["insider_cluster"] + IC_CHECKS:
        s = "s_ic" if c == "insider_cluster" else f"s_{c}"
        f = u[(u["date"] >= INS_START) & u[s].notna()].copy()
        f["r_x"] = pct_rank(f, s)
        f["r_rev"], f["r_size"] = pct_rank(f, "mthret"), pct_rank(f, "me")
        f["r_bm"] = pct_rank(f, "bm").fillna(0.5)
        summ, _ = fama_macbeth(f, ["r_x"] + ctrl)
        r = summ.iloc[0]
        crow.append({"signal": ("PRIMARY " if c == "insider_cluster" else "check ") + c,
                     "from": f"{f['date'].min():%Y-%m}", "slope/yr": r["slope/yr"], "t": r["t"], "months": r["months"]})
    show(pd.DataFrame(crow).round({"slope/yr": 4, "t": 2}), index=False)

    # ------------------------------------------------------------------ 6. sub-periods
    section("6. Sub-periods (long-only: excess return, Sharpe, FF6 alpha; spread: mean)")
    prow = []
    plan = [("NI Q5", "net_issuance", "NI Q5-Q1"), ("IC cluster", "other", "IC cluster-none"),
            ("C1", "other", "C1-both universe"), ("C2 Q5", "other", "C2 Q5-Q1")]
    for k, key, sp in plan:
        for a, b in SUBPERIODS[key]:
            for w in ("EW", "VW"):
                r = allret[f"{k} {w}"].loc[a:b].dropna()
                ex = (r - rf.reindex(r.index)).dropna()
                fa = ff_alpha(ex, ff)
                s = allret[f"{sp} {w}"].loc[a:b].dropna()
                m, t, _ = mean_t(s)
                mk = (allret["Market VW"].loc[a:b] - rf).dropna()
                prow.append({"portfolio": f"{k} {w}", "period": f"{a} to {b}", "excess/yr": ex.mean() * 12,
                             "Sharpe": ex.mean() / ex.std() * np.sqrt(12), "mkt Sharpe": mk.mean() / mk.std() * np.sqrt(12),
                             "FF6 alpha/yr": fa["alpha"], "t(alpha)": fa["t"], f"spread/yr": m * 12, "t(spread)": t})
    show(pd.DataFrame(prow).set_index(["portfolio", "period"]).round(3))

    # ------------------------------------------------------------------ 7. annual check
    section("7. Annual check: formed each December, held for the next calendar year (buy-and-hold)")
    need = set()
    for frame in (ni, ic, both):                      # every stock that can be bought in a December
        need |= set(frame.loc[frame["date"].dt.month == 12, "permno"])
    sub = df[df["permno"].isin(need) & (df["date"] >= START)]
    ret_wide = sub.pivot(index="date", columns="permno", values="mthret").astype("float64")
    ann = {}
    for k, frame, mem in (("NI Q5", ni, ni["q"] == 5), ("IC cluster", ic, ic["cluster"] == "cluster"),
                          ("C1", both, both["c1"] == "C1"), ("C2 Q5", both, both["q_c2"] == 5)):
        dec = frame[mem & (frame["date"].dt.month == 12)]
        for w in ("EW", "VW"):
            parts = []
            for d, g in dec.groupby("date"):
                wts = np.ones(len(g)) if w == "EW" else g["me"].values
                parts.append(buy_and_hold(ret_wide, g["permno"].tolist(), wts, d))
            ann[f"{k} {w}"] = pd.concat(parts).loc[:"2025-12-31"]
    arows = []
    for name, r in ann.items():
        r = r.dropna()
        ex = (r - rf.reindex(r.index)).dropna()
        act = (r - mkt.reindex(r.index)).dropna()
        m, t, _ = mean_t(act)
        fa = ff_alpha(ex, ff)
        mk = (mkt.reindex(r.index) - rf.reindex(r.index)).dropna()
        arows.append({"portfolio": name, "from": f"{r.index.min():%Y-%m}", "excess/yr": ex.mean() * 12,
                      "Sharpe": ex.mean() / ex.std() * np.sqrt(12), "mkt Sharpe": mk.mean() / mk.std() * np.sqrt(12),
                      "vs mkt/yr": m * 12, "t(vs mkt)": t, "FF6 alpha/yr": fa["alpha"], "t(alpha)": fa["t"]})
    show(pd.DataFrame(arows).set_index("portfolio").round(3))
    pd.DataFrame(ann).to_csv(OUT / "annual_portfolio_returns.csv", index_label="return_month")

    # ------------------------------------------------------------------ charts
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        for start, cols, fname, title in [
            ("2006-04-30", ["NI Q5 VW", "IC cluster VW", "C1 VW", "C2 Q5 VW", "Market VW"], "growth_2006.png",
             "Long-only, value-weighted, monthly rebalancing, 2006-04 to 2025-12"),
            ("1980-02-29", ["NI Q5 VW", "NI Q1 VW", "NI universe VW", "Market VW"], "growth_1980.png",
             "net_issuance quintiles, value-weighted, monthly rebalancing, 1980-02 to 2025-12")]:
            g = (1 + allret.loc[start:, cols].fillna(0)).cumprod()
            ax = g.plot(logy=True, figsize=(10, 5), lw=1.4, title=title)
            ax.set_ylabel("Growth of $1 (log scale)")
            plt.tight_layout()
            plt.savefig(OUT / fname, dpi=120)
            plt.close()
        print(f"\n  charts: {(OUT / 'growth_2006.png').relative_to(REPO)}, {(OUT / 'growth_1980.png').relative_to(REPO)}")
    except ImportError:
        print("\n  matplotlib not installed: charts skipped")
    print("\nDone. Reply 'done' in the chat; Claude will read data/issuance_insider/backtest/backtest_log.txt.")


if __name__ == "__main__":
    main()
