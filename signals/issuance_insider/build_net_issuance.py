"""
build_net_issuance.py
=====================
Step 8 (Construct) of prompts/data_acquisition.md for signals/issuance_insider,
signal 1: net_issuance. No WRDS needed; reads the Step 7 pull and the timing
measurement.

Decisions it follows (progress.md, approved 2026-11-14)
  Primary  net_issuance       12-month log change in split-adjusted shares, with a
                              4-month skip: ln(adj_{t-4} / adj_{t-16}),
                              adj = shrout x mthcumfacshr (Step 7: multiply).
  Checks   net_issuance_skip3 same, 3-month skip (t-3 vs t-15)
           net_issuance_skip6 same, 6-month skip (t-6 vs t-18)
           net_issuance_pit   same idea with exact dates: at each month-end, the
                              latest share count that was public by then (its
                              10-K/10-Q's public date where known, otherwise its
                              date + 4 months), vs the same 12 months earlier
           comp_issuance      ln(ME_{t-4} / ME_{t-16}) - sum of ln(1 + mthret) over
                              t-15..t-4 (composite issuance, 4-month skip)
           net_issuance_5y    ln(adj_{t-4} / adj_{t-64})
  Combination rules C1/C2 use net_issuance only. No winsorizing, no ranking.

Rules applied here (details beyond the approved list are marked *)
  - Month-ends: date = calendar month-end; lags are calendar months (a missing
    month gives a missing value, never a shifted one).
  - Missing values: A, skip3/6, 5y need adjusted shares > 0 at both ends; B needs
    ME > 0 at both ends and all 12 monthly returns; pit needs a public count at
    both month-ends.
  - Price rule (added in Step 9, 2026-11-14): no value unless EVERY month of the
    window, from the earlier share count to the later one, has a CRSP price. In
    months without one (security not trading on a CRSP exchange) CRSP's share count
    can be stale and splits go unrecorded (Delcath 2019-20: a 1-for-700 reverse split
    looked like a 99% buyback). B (comp_issuance) is protected already: it needs
    market value at both ends and all 12 monthly returns.
  - pit*: share counts are CRSP's share history (StkShares). Each count's
    adjusted value = shrout x the share factor on its own date (monthly factor of
    its month times any split later in that month), so counts from different dates
    compare across splits. Exact public date: the 10-K/10-Q it came from
    (measure_share_timing.py, 2003-2025-08, accepted by 4 p.m. -> that day, else
    next trading day). Otherwise ("other" source, before 2003, after 2025-08):
    month-end of its date + 4 months (date_source assumed). The latest count is
    the one with the latest date among those public by the month-end.
  - gvkey: CRSP-Compustat link (LU/LC, P/C) valid at the month-end; if none, the
    panel's gvkey*.
  - ETFs: rows whose CRSP security subtype is ETF at that date get
    applies = "n/a (ETF)" and no values (the panel currently has none).
  - Firm level across share classes (added 2026-11-16, after the backtest): a firm
    (gvkey) with 2+ classes (permnos) in the panel at month t gets ONE value, given to
    every class: x_firm = ln( sum_c W_c / sum_c W_c * exp(-x_c) ), W_c = the class's
    market value at t (panel me). That is the log change in the firm's total units,
    each class valued at its price at t (class price ratios are near-constant:
    Berkshire A = 1,500 B by conversion; Alphabet A ~ C). Classes without a value or
    a market value are left out of the sums; a firm with one class keeps its value
    exactly. Applies to every share-count column (primary and checks). Reason:
    per-class values can show a "buyback" that is a conversion between classes
    (Berkshire A -> B) or a buyback concentrated in one class (Alphabet C).
    The primary's per-class value is kept in net_issuance_class.

Outputs (data/issuance_insider/, Git ignores it)
  net_issuance_monthly.parquet  one row per panel row:
      permno, gvkey, date, net_issuance, period_end, published_date, date_source,
      source, applies, net_issuance_class, n_classes, comp_issuance, net_issuance_5y,
      net_issuance_skip3, period_end_skip3, net_issuance_skip6, period_end_skip6,
      net_issuance_pit, period_end_pit, published_date_pit, date_source_pit
  net_issuance_events.parquet   one row per share-count change (late data):
      permno, gvkey, period_end, published_date, date_source, source, version,
      shrout, prev_shrout, adj_factor, shrout_adj, count_source, form10
  build_log.txt                 everything printed

Run from the repo root, with the .venv active (about 1-3 minutes):
    python signals\\issuance_insider\\build_net_issuance.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.tseries.offsets import MonthEnd

REPO = Path(__file__).resolve().parents[2]
D = REPO / "data" / "issuance_insider"
LP = REPO / "data" / "lazy_prices"
PANEL = REPO / "data" / "crsp_monthly_ratios_clean.parquet"
LOG = D / "build_log.txt"

K_PRIMARY = 4
FALLBACK_MONTHS = 4                     # pit: assumed lag where no exact date is known
SOURCE = "crsp.msf_v2"
SOURCE_PIT = "crsp.stkshares + wrdssec.wrds_forms"
FIRM_COLS = ["net_issuance", "net_issuance_skip3", "net_issuance_skip6", "net_issuance_5y", "comp_issuance",
             "net_issuance_pit"]

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 30)


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            st.write(s)

    def flush(self):
        for st in self.streams:
            st.flush()


def show(df: pd.DataFrame, indent: int = 4) -> None:
    pad = " " * indent
    print(pad + df.to_string(index=False).replace("\n", "\n" + pad))


def section(title: str) -> None:
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


def lag(df: pd.DataFrame, cols: list[str], months: int, suffix: str) -> pd.DataFrame:
    """Values of `cols` from `months` calendar months earlier, matched on (permno, date)."""
    x = df[["permno", "date"] + cols].copy()
    x["date"] = x["date"] + MonthEnd(months)
    return x.rename(columns={c: f"{c}{suffix}" for c in cols})


def log_ratio(a: pd.Series, b: pd.Series) -> pd.Series:
    ok = (a > 0) & (b > 0)
    return pd.Series(np.where(ok, np.log(a.where(ok) / b.where(ok)), np.nan), index=a.index)


# ----------------------------------------------------------------------------
# Price rule helper: complete monthly calendar per permno, cumulative priced months
# ----------------------------------------------------------------------------
def priced_calendar(m: pd.DataFrame) -> pd.DataFrame:
    x = m[["permno", "date", "mthprc"]].copy()
    x["mi"] = x["date"].dt.year * 12 + x["date"].dt.month
    x["hp"] = (x["mthprc"].notna() & (x["mthprc"] != 0)).astype("int64")
    r = x.groupby("permno")["mi"].agg(["min", "max"])
    n = (r["max"] - r["min"] + 1).values
    cal = pd.DataFrame({"permno": np.repeat(r.index.values, n),
                        "mi": np.concatenate([np.arange(a, b + 1) for a, b in zip(r["min"], r["max"])])})
    cal = cal.merge(x[["permno", "mi", "hp"]].drop_duplicates(["permno", "mi"]), on=["permno", "mi"], how="left")
    cal["hp"] = cal["hp"].fillna(0).astype("int64")
    cal["cp"] = cal.groupby("permno")["hp"].cumsum()          # priced months up to and including mi
    return cal


def all_priced(cal: pd.DataFrame, permno: pd.Series, mi_start: pd.Series, mi_end: pd.Series) -> np.ndarray:
    """True if every calendar month from mi_start to mi_end (inclusive) has a CRSP price."""
    q = pd.DataFrame({"permno": permno.values, "s": mi_start.values, "e": mi_end.values})
    c = cal[["permno", "mi", "cp", "hp"]]
    q = q.merge(c.rename(columns={"mi": "e", "cp": "cp_e"})[["permno", "e", "cp_e"]], on=["permno", "e"], how="left")
    q = q.merge(c.rename(columns={"mi": "s", "cp": "cp_s", "hp": "hp_s"}), on=["permno", "s"], how="left")
    ok = (q["cp_e"] - q["cp_s"] + q["hp_s"]) == (q["e"] - q["s"] + 1)
    return ok.fillna(False).values


# ----------------------------------------------------------------------------
# Fixed-skip versions from CRSP monthly data
# ----------------------------------------------------------------------------
def monthly_signals(m: pd.DataFrame, cal: pd.DataFrame) -> pd.DataFrame:
    m = m.copy()
    m["adj"] = m["shrout"] * m["mthcumfacshr"]
    m["me"] = m["mthprc"].abs() * m["shrout"]
    m["lr"] = np.log1p(m["mthret"].where(m["mthret"] > -1))
    # 12-month sum of log returns ending at each month, only if all 12 months are present
    m = m.sort_values(["permno", "date"])
    m["mi"] = m["date"].dt.year * 12 + m["date"].dt.month
    g = m.groupby("permno", sort=False)
    m["lr12"] = g["lr"].transform(lambda s: s.rolling(12, min_periods=12).sum())
    span = m["mi"] - g["mi"].shift(11)
    m.loc[span != 11, "lr12"] = np.nan                   # a gap inside the 12 months -> missing

    base = m[["permno", "date"]].copy()
    out = base.copy()

    mi_t = base["date"].dt.year * 12 + base["date"].dt.month

    def change(k_end: int, k_start: int) -> np.ndarray:
        e = lag(m, ["adj"], k_end, "_e")
        s = lag(m, ["adj"], k_start, "_s")
        x = base.merge(e, on=["permno", "date"], how="left").merge(s, on=["permno", "date"], how="left")
        v = log_ratio(x["adj_e"], x["adj_s"]).values
        ok = all_priced(cal, base["permno"], mi_t - k_start, mi_t - k_end)      # price rule
        return np.where(ok, v, np.nan)

    out["net_issuance"] = change(K_PRIMARY, K_PRIMARY + 12)
    out["net_issuance_skip3"] = change(3, 15)
    out["net_issuance_skip6"] = change(6, 18)
    out["net_issuance_5y"] = change(K_PRIMARY, K_PRIMARY + 60)

    e = lag(m, ["me", "lr12"], K_PRIMARY, "_e")
    s = lag(m, ["me"], K_PRIMARY + 12, "_s")
    x = base.merge(e, on=["permno", "date"], how="left").merge(s, on=["permno", "date"], how="left")
    out["comp_issuance"] = (log_ratio(x["me_e"], x["me_s"]) - x["lr12_e"]).values
    return out


# ----------------------------------------------------------------------------
# Point-in-time version from the share history
# ----------------------------------------------------------------------------
def share_factor_on_dates(ev: pd.DataFrame, m: pd.DataFrame, dist: pd.DataFrame) -> pd.Series:
    """Share factor on each event date: monthly factor of its month times (1 + facshr) of
    any split later in the same month (so a count taken before a mid-month split is
    scaled like the months before the split)."""
    f = m[["permno", "date", "mthcumfacshr"]].rename(columns={"date": "month"})
    x = ev[["permno", "period_end"]].assign(month=ev["period_end"] + MonthEnd(0)).reset_index()
    x = x.merge(f, on=["permno", "month"], how="left")
    d = dist[dist["disfacshr"].notna() & (dist["disfacshr"] != 0)][["permno", "disexdt", "disfacshr"]]
    d = d.assign(month=d["disexdt"] + MonthEnd(0))
    y = x.merge(d, on=["permno", "month"], how="inner")
    y = y[y["disexdt"] > y["period_end"]]
    mult = y.groupby("index")["disfacshr"].apply(lambda s: float(np.prod(1 + s)))
    x = x.set_index("index")
    x["mult"] = mult.reindex(x.index).fillna(1.0)
    return (x["mthcumfacshr"] * x["mult"]).reindex(ev.index)


def build_events(sh: pd.DataFrame, matched: pd.DataFrame, m: pd.DataFrame, dist: pd.DataFrame) -> pd.DataFrame:
    sh = sh.sort_values(["permno", "shrstartdt"]).reset_index(drop=True)
    sh["prev_shrout"] = sh.groupby("permno")["shrout"].shift()
    first = sh.groupby("permno").cumcount() == 0
    ev = sh[(sh["shrsource"] == "OBS") & (sh["shrout"] > 0)
            & (first | (sh["shrout"] != sh["prev_shrout"]))].copy()
    ev = ev.rename(columns={"shrstartdt": "period_end"})
    mt = matched[["permno", "shrstartdt", "source", "form10", "public"]].rename(
        columns={"shrstartdt": "period_end", "source": "count_source"})
    ev = ev.merge(mt.drop_duplicates(["permno", "period_end"]), on=["permno", "period_end"], how="left")
    exact = ev["public"].notna() & ev["count_source"].isin(["balance sheet", "cover page"])
    assumed = ev["period_end"] + MonthEnd(0) + MonthEnd(FALLBACK_MONTHS)
    ev["published_date"] = ev["public"].where(exact, assumed)
    ev["published_date"] = ev[["published_date", "period_end"]].max(axis=1)   # never before the count's date
    ev["date_source"] = np.where(exact, "exact", "assumed")
    ev["count_source"] = ev["count_source"].fillna("before 2003 / after 2025-08 (not measured)")
    ev["source"] = SOURCE_PIT
    ev["version"] = "original"
    ev["adj_factor"] = share_factor_on_dates(ev, m, dist)
    ev["shrout_adj"] = ev["shrout"] * ev["adj_factor"]
    return ev


def pit_signal(ev: pd.DataFrame, months: pd.DataFrame, cal: pd.DataFrame) -> pd.DataFrame:
    """At each month-end: the count with the latest period_end among those published by
    then. Walk events in publication order; keep those that set a new latest period_end;
    the last such event published by the month-end is the latest public count."""
    e = ev.dropna(subset=["shrout_adj"]).sort_values(["permno", "published_date", "period_end"])
    e["run_max"] = e.groupby("permno")["period_end"].cummax()
    e = e[e["period_end"] == e["run_max"]].drop_duplicates(["permno", "published_date"], keep="last")
    e = e[["permno", "published_date", "period_end", "date_source", "shrout_adj"]]
    t = months[["permno", "date"]].drop_duplicates().sort_values("date")
    a = pd.merge_asof(t, e.sort_values("published_date"), left_on="date", right_on="published_date",
                      by="permno", direction="backward")
    prev = a[["permno", "date", "shrout_adj", "period_end"]].assign(date=a["date"] + MonthEnd(12)).rename(
        columns={"shrout_adj": "adj_12", "period_end": "pe_12"})
    a = a.merge(prev, on=["permno", "date"], how="left")
    v = log_ratio(a["shrout_adj"], a["adj_12"])
    # price rule: every month from the earlier count's month to the later count's month priced
    mi = lambda d: d.dt.year * 12 + d.dt.month
    ok = all_priced(cal, a["permno"], mi(a["pe_12"]).fillna(0).astype("int64"), mi(a["period_end"]).fillna(0).astype("int64"))
    a["net_issuance_pit"] = np.where(ok & a["pe_12"].notna(), v, np.nan)
    return a.rename(columns={"period_end": "period_end_pit", "published_date": "published_date_pit",
                             "date_source": "date_source_pit"})[
        ["permno", "date", "net_issuance_pit", "period_end_pit", "published_date_pit", "date_source_pit"]]


# ----------------------------------------------------------------------------
# Keys and flags
# ----------------------------------------------------------------------------
def firm_level(out: pd.DataFrame, me: pd.Series) -> tuple[pd.DataFrame, pd.Series]:
    """Firms with 2+ share classes in the panel at t: every class gets the firm's value
    ln( sum_c W_c / sum_c W_c * exp(-x_c) ), W_c = class market value at t. One class: unchanged."""
    out = out.copy()
    key = [out["gvkey"], out["date"]]
    has_g = out["gvkey"].notna()
    n_cls = out["permno"].where(has_g).groupby(key).transform("count")
    multi = has_g & (n_cls >= 2)
    w = me.where(me > 0)
    for c in FIRM_COLS:
        ok = multi & out[c].notna() & w.notna()
        k = ok.groupby(key).transform("sum")
        s1 = w.where(ok).groupby(key).transform("sum")
        s2 = (w * np.exp(-out[c])).where(ok).groupby(key).transform("sum")
        with np.errstate(divide="ignore", invalid="ignore"):
            firm = np.log(s1 / s2)
        out[c] = np.where(multi & (k > 0), firm, out[c])
    out["n_classes"] = n_cls
    return out, multi


def attach_gvkey(df: pd.DataFrame, ccm: pd.DataFrame, date_col: str) -> pd.Series:
    c = ccm.assign(linkenddt=ccm["linkenddt"].fillna(pd.Timestamp("2099-12-31")))
    x = df[["permno", date_col]].reset_index().merge(c[["permno", "gvkey", "linkdt", "linkenddt", "linkprim"]],
                                                      on="permno")
    x = x[(x[date_col] >= x["linkdt"]) & (x[date_col] <= x["linkenddt"])]
    x = x.sort_values(["index", "linkprim"], key=lambda s: s.map({"P": 0, "C": 1}) if s.name == "linkprim" else s)
    return x.drop_duplicates("index").set_index("index")["gvkey"].reindex(df.index)


def etf_flag(df: pd.DataFrame, si: pd.DataFrame) -> pd.Series:
    e = si[si["securitysubtype"] == "ETF"][["permno", "secinfostartdt", "secinfoenddt"]]
    if e.empty:
        return pd.Series(False, index=df.index)
    x = df[["permno", "date"]].reset_index().merge(e, on="permno")
    x = x[(x["date"] >= x["secinfostartdt"]) & (x["date"] <= x["secinfoenddt"] + MonthEnd(0))]
    return df.index.isin(set(x["index"]))


# ----------------------------------------------------------------------------
def main() -> None:
    with open(LOG, "w", encoding="utf-8") as fh:
        sys.stdout = Tee(sys.__stdout__, fh)
        try:
            run()
        finally:
            sys.stdout = sys.__stdout__
    print(f"\nSaved: {LOG.relative_to(REPO)}")


def run() -> None:
    print(f"net_issuance Step 8 build, {pd.Timestamp.now():%Y-%m-%d %H:%M}")
    panel = pd.read_parquet(PANEL, columns=["permno", "date", "gvkey", "me"])
    panel["permno"] = pd.to_numeric(panel["permno"]).astype("int64")
    panel["date"] = pd.to_datetime(panel["date"]) + MonthEnd(0)
    m = pd.read_parquet(D / "crsp_monthly.parquet")
    m["permno"] = m["permno"].astype("int64")
    sh = pd.read_parquet(D / "share_history.parquet")
    sh["permno"] = sh["permno"].astype("int64")
    dist = pd.read_parquet(D / "distributions.parquet")
    dist["permno"] = dist["permno"].astype("int64")
    matched = pd.read_parquet(D / "share_changes_matched.parquet")
    matched["permno"] = matched["permno"].astype("int64")
    ccm = pd.read_parquet(LP / "ccm_links.parquet")
    ccm["permno"] = ccm["permno"].astype("int64")
    si = pd.read_parquet(LP / "security_info.parquet")
    si["permno"] = si["permno"].astype("int64")
    print(f"  panel {len(panel):,} rows; CRSP monthly {len(m):,}; share history {len(sh):,}; "
          f"matched share changes {len(matched):,}")

    section("1. Fixed-skip versions (CRSP monthly)")
    cal = priced_calendar(m)
    print(f"  months without a CRSP price inside each security's CRSP span: {(cal['hp'] == 0).mean():.2%}")
    fx = monthly_signals(m, cal)
    print(f"  built on {len(fx):,} CRSP permno-months")

    section("2. Point-in-time version (share history + filing dates)")
    ev = build_events(sh, matched, m, dist)
    ev["gvkey"] = attach_gvkey(ev, ccm, "period_end")
    print(f"  share-count events: {len(ev):,} ({ev['permno'].nunique():,} permnos)")
    t = ev.groupby("count_source").agg(events=("permno", "size"), exact=("date_source", lambda s: (s == "exact").mean()))
    t["exact"] = t["exact"].map("{:.0%}".format)
    show(t.reset_index())
    ok_fac = ev["adj_factor"].notna().mean()
    print(f"  events with a share factor on their date: {ok_fac:.1%}")
    months = pd.concat([m[["permno", "date"]], panel[["permno", "date"]]]).drop_duplicates()
    pit = pit_signal(ev, months, cal)    # all CRSP months, so 1980 has a value 12 months back

    section("3. Monthly file on the panel's rows")
    out = panel[["permno", "date"]].merge(fx, on=["permno", "date"], how="left").merge(
        pit, on=["permno", "date"], how="left")
    out["gvkey"] = attach_gvkey(out, ccm, "date")
    pg = panel.set_index(["permno", "date"])["gvkey"]
    panel_gv = pg.reindex(pd.MultiIndex.from_frame(out[["permno", "date"]])).values
    both = out["gvkey"].notna() & pd.notna(panel_gv)
    agree = (out.loc[both, "gvkey"].astype(str).values == pd.Series(panel_gv)[both.values].astype(str).values).mean()
    out["gvkey"] = out["gvkey"].fillna(pd.Series(panel_gv, index=out.index))
    out["period_end"] = out["date"] - MonthEnd(K_PRIMARY)
    out["published_date"] = out["date"]
    out["date_source"] = "assumed"
    out["source"] = SOURCE
    out["period_end_skip3"] = out["date"] - MonthEnd(3)
    out["period_end_skip6"] = out["date"] - MonthEnd(6)
    out["net_issuance_class"] = out["net_issuance"]
    me_t = out[["permno", "date"]].merge(panel[["permno", "date", "me"]], on=["permno", "date"], how="left")["me"]
    me_t.index = out.index
    before = out[FIRM_COLS].copy()
    out, multi = firm_level(out, me_t.astype("float64"))
    chg = ~np.isclose(out[FIRM_COLS].fillna(-99).values, before.fillna(-99).values, atol=1e-12).all(axis=1)
    print(f"  share classes: {multi.sum():,} rows ({out.loc[multi, ['gvkey', 'date']].drop_duplicates().shape[0]:,} firm-months) "
          f"belong to firms with 2+ classes in the panel; values changed in {chg.sum():,} rows "
          f"({chg.mean():.2%}); every class of such a firm now carries the firm's value")
    ex = out[out["date"].eq(pd.Timestamp("2025-12-31")) & out["permno"].isin([17778, 83443, 14542, 90319])]
    if len(ex):                                     # Berkshire A / B, Alphabet C / A
        print("  examples, 2025-12 (net_issuance_class = per class, net_issuance = firm):")
        show(ex[["permno", "gvkey", "n_classes", "net_issuance_class", "net_issuance"]].round(4))
    is_etf = etf_flag(out, si)
    out["applies"] = np.where(is_etf, "n/a (ETF)", "stock")
    sig = ["net_issuance", "comp_issuance", "net_issuance_5y", "net_issuance_skip3", "net_issuance_skip6",
           "net_issuance_pit"]
    out.loc[is_etf, sig + ["net_issuance_class"]] = np.nan
    cols = ["permno", "gvkey", "date", "net_issuance", "period_end", "published_date", "date_source", "source",
            "applies", "net_issuance_class", "n_classes", "comp_issuance", "net_issuance_5y", "net_issuance_skip3",
            "period_end_skip3",
            "net_issuance_skip6", "period_end_skip6", "net_issuance_pit", "period_end_pit",
            "published_date_pit", "date_source_pit"]
    out = out[cols].sort_values(["permno", "date"]).reset_index(drop=True)
    print(f"  rows {len(out):,} (panel {len(panel):,}); duplicates (permno, date): "
          f"{out.duplicated(['permno', 'date']).sum():,}")
    print(f"  gvkey: CCM link at the month-end equals the panel's gvkey in {agree:.2%} of rows where both exist; "
          f"missing after fallback {out['gvkey'].isna().mean():.1%}")
    print(f"  ETF rows (n/a): {is_etf.sum():,}")
    cov = out[sig].notna().mean().map("{:.1%}".format)
    print("  share of panel rows with a value:")
    show(cov.rename_axis("column").reset_index(name="with value"))
    yr = out.groupby(out["date"].dt.year)[sig].apply(lambda g: g.notna().mean())
    print("\n  with a value, by year (selected):")
    show(yr.loc[[1980, 1981, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2024, 2025]]
         .map("{:.0%}".format).reset_index())
    q = out[sig].describe(percentiles=[.01, .1, .25, .5, .75, .9, .99]).T.round(3)
    print("\n  distribution (log changes; 0.10 = about +10% shares):")
    show(q.reset_index().rename(columns={"index": "column"}))
    zero = (out["net_issuance"] == 0).mean()
    neg = (out["net_issuance"] < 0).mean()
    print(f"\n  net_issuance: exactly 0 in {zero:.1%} of rows, negative (net buyback) in {neg:.1%}")
    r = out[["net_issuance", "net_issuance_skip3", "net_issuance_skip6", "net_issuance_pit",
             "comp_issuance", "net_issuance_5y"]].corr(method="spearman").round(2)
    print("\n  rank correlations between the versions:")
    show(r.reset_index().rename(columns={"index": ""}))
    print(f"\n  pit: share of rows whose newest count has an exact date: "
          f"{(out['date_source_pit'] == 'exact').mean():.1%} of all, "
          f"{(out.loc[out['date'] >= '2004-01-01', 'date_source_pit'] == 'exact').mean():.1%} from 2004; "
          f"median age of the count used (months): "
          f"{((out['date'] - out['period_end_pit']).dt.days / 30.44).median():.1f} overall, "
          f"{((out['date'] - out['period_end_pit']).dt.days / 30.44)[out['date'] >= '2004-01-01'].median():.1f} from 2004 "
          f"(primary: {K_PRIMARY} months by construction)")

    section("4. Save")
    out.to_parquet(D / "net_issuance_monthly.parquet", index=False)
    print(f"  saved data/issuance_insider/net_issuance_monthly.parquet ({len(out):,} rows)")
    evcols = ["permno", "gvkey", "period_end", "published_date", "date_source", "source", "version",
              "shrout", "prev_shrout", "adj_factor", "shrout_adj", "count_source", "form10"]
    ev[evcols].sort_values(["permno", "period_end"]).to_parquet(D / "net_issuance_events.parquet", index=False)
    print(f"  saved data/issuance_insider/net_issuance_events.parquet ({len(ev):,} rows)")


if __name__ == "__main__":
    main()
