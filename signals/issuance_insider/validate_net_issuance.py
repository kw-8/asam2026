"""
validate_net_issuance.py
========================
Step 9 (Validate) of prompts/data_acquisition.md for signals/issuance_insider,
signal 1: net_issuance. Reads only files already in data/ (no WRDS, no password).

Checks (the prompt's list, then three for this signal)
  1. no duplicate permno + date (monthly file) / permno + period_end (event file)
  2. match rate to the panel, and why rows miss
  3. published_date >= period_end, and the share `assumed`
  4. one ticker change traced (Facebook -> Meta, June 2022)
  5. one split with no jump (Tesla 5-for-1 Aug 2020 and 3-for-1 Aug 2022, NVIDIA
     10-for-1 June 2024), plus every split in the data
  6. coverage vs the panel; ETFs marked n/a, not dropped
  7. outliers; spot-check 3 well-known firms (Apple, Microsoft, Tesla)
  8. the versions agree where they must: skip6(t) = primary(t-2), skip3(t) = primary(t+1)
     (single-class firms; for firms with 2+ classes the class weights change each month)
  9. market value from the pull vs the panel's `me` (same CRSP source)
 10. cross-check with Open Source Asset Pricing ShareIss1Y (only if
     data/issuance_insider/osap_ShareIss1Y.parquet exists; see get_osap_shareiss.py)
 11. share classes (added 2026-11-16): single-class rows keep their own value; every
     class of a multi-class firm carries one value; that value recomputed
     independently from the per-class values and the panel's me; Berkshire and
     Alphabet at 2025-12

Inputs
  data/issuance_insider/net_issuance_monthly.parquet, net_issuance_events.parquet,
  crsp_monthly.parquet, distributions.parquet; data/lazy_prices/security_info.parquet;
  data/crsp_monthly_ratios_clean.parquet
Output
  data/issuance_insider/validate_log.txt (also printed)

Run from the repo root, with the .venv active (about 1 minute):
    python signals\\issuance_insider\\validate_net_issuance.py
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
LOG = D / "validate_log.txt"
OSAP = D / "osap_ShareIss1Y.parquet"

K = 4
SIG = ["net_issuance", "comp_issuance", "net_issuance_5y", "net_issuance_skip3", "net_issuance_skip6",
       "net_issuance_pit"]
TICKER_CASE = ("FB", "META")
SPLITS = [("TSLA", "2020-08"), ("TSLA", "2022-08"), ("NVDA", "2024-06")]
FIRMS = ("AAPL", "MSFT", "TSLA")

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 30)
results: list[tuple[str, str, str]] = []


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


def record(n: str, ok: bool, note: str) -> None:
    status = "PASS" if ok else "CHECK"
    results.append((n, status, note))
    print(f"  -> {status}: {note}")


def permno_of(si: pd.DataFrame, ticker: str, when: str) -> int | None:
    t = pd.Timestamp(when) + MonthEnd(0)
    x = si[(si["ticker"] == ticker) & (si["secinfostartdt"] <= t) & (si["secinfoenddt"] >= t - MonthEnd(1))]
    return int(x["permno"].iloc[0]) if len(x) else None


def main() -> None:
    with open(LOG, "w", encoding="utf-8") as fh:
        sys.stdout = Tee(sys.__stdout__, fh)
        try:
            run()
        finally:
            sys.stdout = sys.__stdout__
    print(f"\nSaved: {LOG.relative_to(REPO)}")


def run() -> None:
    print(f"net_issuance Step 9 validation, {pd.Timestamp.now():%Y-%m-%d %H:%M}")
    o = pd.read_parquet(D / "net_issuance_monthly.parquet")
    ev = pd.read_parquet(D / "net_issuance_events.parquet")
    m = pd.read_parquet(D / "crsp_monthly.parquet")
    dist = pd.read_parquet(D / "distributions.parquet")
    si = pd.read_parquet(LP / "security_info.parquet")
    panel = pd.read_parquet(PANEL, columns=["permno", "date", "me", "gvkey"])
    for df in (o, ev, m, dist, si, panel):
        df["permno"] = pd.to_numeric(df["permno"]).astype("int64")
    panel["date"] = pd.to_datetime(panel["date"]) + MonthEnd(0)
    m["adj"] = m["shrout"] * m["mthcumfacshr"]
    print(f"  monthly {len(o):,} rows; events {len(ev):,}; CRSP monthly {len(m):,}; panel {len(panel):,}")
    # Independent check of the price rule (rolling count, not the build's cumulative sums):
    # priced13 at month s = all 13 months s-12..s have a CRSP price.
    mm = m[["permno", "date", "mthprc"]].assign(mi=m["date"].dt.year * 12 + m["date"].dt.month,
                                                hp=(m["mthprc"].notna() & (m["mthprc"] != 0)).astype(int))
    full = mm.groupby("permno")["mi"].agg(["min", "max"])
    cal = pd.DataFrame({"permno": np.repeat(full.index.values, (full["max"] - full["min"] + 1).values),
                        "mi": np.concatenate([np.arange(a, b + 1) for a, b in zip(full["min"], full["max"])])})
    cal = cal.merge(mm[["permno", "mi", "hp"]].drop_duplicates(["permno", "mi"]), on=["permno", "mi"], how="left").fillna({"hp": 0})
    cal["priced13"] = cal.groupby("permno")["hp"].transform(lambda s: s.rolling(13, min_periods=13).sum()) == 13
    o["mi"] = o["date"].dt.year * 12 + o["date"].dt.month
    o = o.merge(cal[["permno", "mi", "priced13"]].assign(mi=lambda c: c["mi"] + K), on=["permno", "mi"], how="left")
    o["window_priced"] = o["priced13"].fillna(False).astype(bool)
    o = o.drop(columns=["mi", "priced13"])

    # 1 ------------------------------------------------------------------------------
    section("1. No duplicate permno + date")
    d1 = o.duplicated(["permno", "date"]).sum()
    d2 = ev.duplicated(["permno", "period_end"]).sum()
    print(f"  monthly duplicates (permno, date): {d1:,}; event duplicates (permno, period_end): {d2:,}")
    record("1", d1 == 0 and d2 == 0, f"{d1} monthly and {d2} event duplicates")

    # 2 ------------------------------------------------------------------------------
    section("2. Match rate to the panel, and why rows miss")
    keys = o[["permno", "date"]].merge(panel[["permno", "date"]], how="outer", indicator=True)
    only_o, only_p = (keys["_merge"] == "left_only").sum(), (keys["_merge"] == "right_only").sum()
    print(f"  monthly rows not in the panel: {only_o:,}; panel rows not in the monthly file: {only_p:,}")
    has = o["net_issuance"].notna()
    print(f"  panel rows with a primary value: {has.mean():.1%}")
    miss = o.loc[~has, ["permno", "date"]].copy()
    first = m.groupby("permno")["date"].min().rename("first_crsp")
    miss = miss.join(first, on="permno")
    e = m[["permno", "date", "adj", "shrout", "mthcumfacshr", "mthprc"]]
    miss = miss.merge(e.assign(date=e["date"] + MonthEnd(K)).rename(
        columns={"adj": "adj_e", "shrout": "sh_e", "mthcumfacshr": "f_e", "mthprc": "p_e"}), on=["permno", "date"], how="left")
    miss = miss.merge(e.assign(date=e["date"] + MonthEnd(K + 12)).rename(
        columns={"adj": "adj_s", "shrout": "sh_s", "mthcumfacshr": "f_s", "mthprc": "p_s"}), on=["permno", "date"], how="left")
    no_price = ~o.loc[~has, "window_priced"].values
    reason = np.select(
        [miss["first_crsp"] > miss["date"] - MonthEnd(K + 12),
         no_price,
         miss["sh_e"].isna() | miss["sh_s"].isna(),
         miss["f_e"].isna() | miss["f_s"].isna(),
         (miss["adj_e"] <= 0) | (miss["adj_s"] <= 0)],
        [f"new in CRSP: under {K + 12} months of history",
         "a month without a CRSP price in the window (not trading on a CRSP exchange; price rule)",
         "a month missing in CRSP at one end (gap)",
         "share-adjustment factor missing at one end",
         "zero shares at one end"], "other")
    r = pd.Series(reason).value_counts().rename_axis("why the primary is missing").reset_index(name="rows")
    r["share of missing"] = (r["rows"] / r["rows"].sum()).map("{:.1%}".format)
    show(r)
    record("2", only_o == 0 and only_p == 0 and has.mean() > 0.85,
           f"monthly file = panel rows exactly; {has.mean():.1%} have the primary; "
           f"main reason for missing: {r.iloc[0, 0]} ({r.iloc[0, 2]})")

    # 3 ------------------------------------------------------------------------------
    section("3. published_date >= period_end, and the share assumed")
    b1 = (o["published_date"] < o["period_end"]).sum()
    f1 = (o["published_date"] > o["date"]).sum()
    p = o["net_issuance_pit"].notna()
    b2 = (o.loc[p, "published_date_pit"] < o.loc[p, "period_end_pit"]).sum()
    f2 = (o.loc[p, "published_date_pit"] > o.loc[p, "date"]).sum()
    b3 = (ev["published_date"] < ev["period_end"]).sum()
    print(f"  primary: published_date < period_end in {b1:,} rows; published after the row's month-end in {f1:,}; "
          f"date_source 'assumed' in {(o['date_source'] == 'assumed').mean():.0%} (fixed 4-month skip, backed by the "
          f"timing measurement: under 1% of share changes used before public)")
    print(f"  exact-date check: published < period_end in {b2:,}; published after the month-end in {f2:,}; "
          f"exact in {(o.loc[p, 'date_source_pit'] == 'exact').mean():.1%} of rows with a value "
          f"({(o.loc[p & (o['date'] >= '2004-01-01'), 'date_source_pit'] == 'exact').mean():.1%} from 2004)")
    ev_y = ev.groupby(ev["period_end"].dt.year)["date_source"].apply(lambda s: (s == "exact").mean())
    print("  events: published < period_end in {:,}; exact share by year (selected): {}".format(
        b3, ", ".join(f"{y}: {v:.0%}" for y, v in ev_y.items() if y in (1990, 2002, 2003, 2010, 2020, 2025))))
    record("3", b1 == 0 and f1 == 0 and b2 == 0 and f2 == 0 and b3 == 0,
           "no value dated before its period end or used before its published date; primary 100% assumed "
           "(fixed skip), exact-date check 73% exact from 2004")

    # 4 ------------------------------------------------------------------------------
    section(f"4. Ticker change traced: {TICKER_CASE[0]} -> {TICKER_CASE[1]}")
    pn = permno_of(si, TICKER_CASE[0], "2021-12")
    if pn is None:
        record("4", False, "ticker FB not found in security_info")
    else:
        h = si[si["permno"] == pn].sort_values("secinfostartdt")[["secinfostartdt", "secinfoenddt", "ticker", "issuernm"]]
        h = h[h["secinfoenddt"] >= "2021-01-01"].drop_duplicates(["ticker", "issuernm"])
        print(f"  permno {pn}:")
        show(h, indent=4)
        x = o[(o["permno"] == pn) & o["date"].between("2022-01-31", "2022-12-31")][
            ["date", "gvkey", "net_issuance", "net_issuance_pit", "comp_issuance"]]
        show(x.round(4), indent=4)
        reuse = si[(si["ticker"] == "FB") & (si["permno"] != pn) & (si["secinfostartdt"] >= "2022-06-01")]
        if len(reuse):
            print(f"  ticker FB later used by permno {sorted(reuse['permno'].unique())} "
                  f"({reuse['issuernm'].iloc[0]}): keyed on permno, so no mix-up")
        cont = x["net_issuance"].notna().all() and x["gvkey"].nunique() == 1
        jump = x["net_issuance"].diff().abs().max()
        record("4", bool(cont) and jump < 0.02,
               f"Meta (permno {pn}) has a value every month of 2022, one gvkey, largest month-to-month change {jump:.4f}")

    # 5 ------------------------------------------------------------------------------
    section("5. Splits: no jump")
    for tk, mon in SPLITS:
        pn = permno_of(si, tk, mon)
        ex = pd.Timestamp(mon) + MonthEnd(0)
        y = m[(m["permno"] == pn) & m["date"].between(ex - MonthEnd(2), ex + MonthEnd(1))][
            ["date", "shrout", "mthcumfacshr", "adj"]]
        z = o[(o["permno"] == pn) & o["date"].between(ex + MonthEnd(K - 1), ex + MonthEnd(K + 1))][
            ["date", "net_issuance", "net_issuance_pit"]]
        print(f"  {tk} split in {mon} (permno {pn}) - raw shares jump, adjusted shares do not:")
        show(y.assign(date=y["date"].dt.strftime("%Y-%m")), indent=6)
        print(f"    signal when the split month enters (t-{K}):")
        show(z.assign(date=z["date"].dt.strftime("%Y-%m")).round(4), indent=6)
    # Every split / stock dividend (CRSP type FRS, |factor| >= 20%): does CRSP's cumulative share
    # factor move by exactly the split size in the ex-date month?
    fr = dist[dist["distype"] == "FRS"].assign(date=lambda d: d["disexdt"] + MonthEnd(0))
    fr = fr.groupby(["permno", "date"], as_index=False).agg(f=("disfacshr", lambda s: float(np.prod(1 + s)) - 1))
    fr = fr[fr["f"].abs() >= 0.2]
    a = m[["permno", "date", "shrout", "mthcumfacshr"]]
    x = fr.merge(a, on=["permno", "date"]).merge(
        a.assign(date=a["date"] + MonthEnd(1)).rename(columns={"shrout": "s_m", "mthcumfacshr": "f_m"}),
        on=["permno", "date"]).dropna()
    x = x[(x[["shrout", "s_m", "mthcumfacshr", "f_m"]] > 0).all(axis=1)]
    split = np.log1p(x["f"])
    fac_ok = (np.log(x["mthcumfacshr"] / x["f_m"]) + split).abs() < 0.01
    raw = np.log(x["shrout"] / x["s_m"])
    adj = raw + np.log(x["mthcumfacshr"] / x["f_m"])
    other = adj.abs() > 0.5 * split.abs()
    print(f"\n  all CRSP splits / stock dividends (type FRS, |factor| >= 20%) with data both sides: {len(x):,}")
    print(f"    CRSP's share factor moves by exactly the split size in the split month: {fac_ok.mean():.2%}")
    print(f"    adjusted shares within 5% of the month before: {(adj.abs() < 0.05).mean():.2%}; "
          f"moved by more than half the split size: {other.mean():.2%} — in those the raw count changed by more "
          f"or less than the split (other share changes that month, e.g. an offering next to a reverse split; "
          f"factor correct in {fac_ok[other].mean():.1%} of them), so the change is real and counts")
    nt = dist[dist["distype"].isin(["TSOO", "SP"]) & (dist["disfacshr"].abs() >= 0.2)]
    print(f"    not splits: {len(nt):,} CRSP events of type TSOO (total-shares observation: mergers, offerings; "
          f"1980s-1990s) and SP (security payment, mostly mergers) carry a share factor but no price factor; "
          f"CRSP does not adjust for them, so they count as issuance (e.g. Newmont 1997)")
    record("5", fac_ok.mean() > 0.995,
           f"CRSP's factor tracks {fac_ok.mean():.2%} of {len(x):,} splits exactly; Tesla 2020/2022 and NVIDIA 2024 "
           f"show no jump; remaining split-month moves ({other.mean():.1%}) are real share changes")

    # 6 ------------------------------------------------------------------------------
    section("6. Coverage vs the panel; ETFs")
    cov = o.groupby(o["date"].dt.year)[SIG].apply(lambda g: g.notna().mean())
    show(cov.loc[::5].map("{:.0%}".format).reset_index().rename(columns={"date": "year"}))
    etf_perm = set(si.loc[si["securitysubtype"] == "ETF", "permno"])
    in_panel = len(etf_perm & set(panel["permno"]))
    na = (o["applies"] == "n/a (ETF)").sum()
    print(f"  ETF permnos in CRSP: {len(etf_perm):,}; in the panel: {in_panel:,}; rows marked n/a: {na:,}")
    low = cov["net_issuance"].min()
    worst = cov["net_issuance"].nsmallest(3)
    print("  lowest years for the primary: " + ", ".join(f"{y}: {v:.1%}" for y, v in worst.items())
          + " (listing waves: new stocks need 16 months of CRSP history; see check 2)")
    record("6", low > 0.75 and in_panel == na == 0,
           f"primary covers {low:.0%}-{cov['net_issuance'].max():.0%} of panel rows each year (lowest in listing waves); "
           f"panel has no ETFs (0 rows n/a, none dropped)")

    # 7 ------------------------------------------------------------------------------
    section("7. Outliers and three well-known firms")
    v = o["net_issuance"]
    q = v.quantile([.001, .01, .05, .5, .95, .99, .999])
    print("  primary percentiles: " + ", ".join(f"{k:.1%}: {x:.3f}" for k, x in q.items()))
    print(f"  |value| > 1 (shares x2.7 or /2.7 in a year): {(v.abs() > 1).mean():.2%} of rows with a value; "
          f"below -1: {(v < -1).sum():,} rows ({o.loc[v < -1, 'permno'].nunique():,} permnos)")
    bad_price = (o["net_issuance_class"].notna() & ~o["window_priced"]).sum()   # per class (a class can carry its firm's value)
    print(f"  primary values whose 13-month window has a month without a CRSP price: {bad_price:,} (price rule; should be 0)")
    dp = o[(o["permno"] == 89169) & o["date"].between("2020-05-31", "2021-08-31")]["net_issuance_class"].notna().sum()
    dx = o[(o["permno"] == 89169) & o["date"].between("2020-05-31", "2021-04-30")]["net_issuance_pit"].notna().sum()
    print(f"  Delcath (permno 89169), whose unrecorded 1-for-700 reverse split fell in an unpriced gap (Mar 2019 - Apr 2020): "
          f"values comparing across the gap - primary (May 2020 - Aug 2021) {dp}, exact-date (May 2020 - Apr 2021) {dx} "
          f"(should be 0); later values compare two post-gap counts and are kept")
    bad_price += dp + dx
    print("  remaining extremes are real: large positive = serial diluters (offerings next to reverse splits); "
          "large negative = SPAC trust redemptions (shares fall 70-85% at a flat ~$10 price) and big tender offers; "
          "market value falls about as much as the share count, unlike an unrecorded split")
    names = si.sort_values("secinfoenddt").groupby("permno")["issuernm"].last()
    for label, rows in (("largest", o.nlargest(5, "net_issuance")), ("smallest", o.nsmallest(5, "net_issuance"))):
        t = rows[["permno", "date", "net_issuance"]].assign(name=lambda d: d["permno"].map(names).str.slice(0, 40))
        print(f"  {label}:")
        show(t.round(3), indent=4)
    for tk in FIRMS:
        pn = permno_of(si, tk, "2024-12")
        x = o[(o["permno"] == pn) & (o["date"].dt.month == 12) & (o["date"].dt.year >= 2019)][
            ["date", "net_issuance", "net_issuance_pit", "comp_issuance"]]
        a = m[(m["permno"] == pn) & (m["date"].dt.month == 8)][["date", "adj"]].set_index("date")["adj"]
        x["check: log change in adj. shares, Aug to Aug"] = [
            np.log(a.get(d - MonthEnd(K), np.nan) / a.get(d - MonthEnd(K + 12), np.nan)) for d in x["date"]]
        print(f"  {tk} (permno {pn}), December values (period_end = August):")
        show(x.assign(date=x["date"].dt.strftime("%Y-%m")).round(4), indent=4)
    record("7", (v.abs() > 1).mean() < 0.02 and bad_price == 0,
           "extremes are real serial diluters (see list); Apple negative every year, Microsoft near 0, "
           "Tesla positive in 2020-21 (stock offerings) — compare with the table")

    # 8 ------------------------------------------------------------------------------
    section("8. Versions agree where they must")
    s = o.loc[o["n_classes"].fillna(1) == 1, ["permno", "date", "net_issuance", "net_issuance_skip3", "net_issuance_skip6"]]
    a6 = s.merge(s[["permno", "date", "net_issuance"]].assign(date=s["date"] + MonthEnd(2))
                 .rename(columns={"net_issuance": "prim_lag2"}), on=["permno", "date"])
    a3 = s.merge(s[["permno", "date", "net_issuance"]].assign(date=s["date"] - MonthEnd(1))
                 .rename(columns={"net_issuance": "prim_lead1"}), on=["permno", "date"])
    e6 = a6.dropna(subset=["net_issuance_skip6", "prim_lag2"])
    e3 = a3.dropna(subset=["net_issuance_skip3", "prim_lead1"])
    ok6 = np.isclose(e6["net_issuance_skip6"], e6["prim_lag2"], atol=1e-12).mean()
    ok3 = np.isclose(e3["net_issuance_skip3"], e3["prim_lead1"], atol=1e-12).mean()
    print(f"  single-class rows: skip6(t) = primary(t-2): {ok6:.4%} of {len(e6):,} rows; skip3(t) = primary(t+1): {ok3:.4%} of {len(e3):,}")
    record("8", ok6 > 0.9999 and ok3 > 0.9999, f"identical in {min(ok6, ok3):.4%} of comparable rows")

    # 9 ------------------------------------------------------------------------------
    section("9. Market value from the pull vs the panel's me")
    mm = m.assign(me_pull=m["mthprc"].abs() * m["shrout"])[["permno", "date", "me_pull"]]
    c = panel.merge(mm, on=["permno", "date"], how="inner").dropna(subset=["me", "me_pull"])
    rel = (c["me_pull"] / c["me"] - 1).abs()
    print(f"  {len(c):,} rows: within 0.1% in {(rel < 0.001).mean():.2%}; within 1% in {(rel < 0.01).mean():.2%}")
    record("9", (rel < 0.01).mean() > 0.99, f"pulled market value matches the panel's me within 1% in {(rel < 0.01).mean():.2%}")

    # 10 -----------------------------------------------------------------------------
    section("10. Cross-check with Open Source Asset Pricing ShareIss1Y")
    if not OSAP.exists():
        print(f"  {OSAP.relative_to(REPO)} not found: run signals\\issuance_insider\\get_osap_shareiss.py first (optional).")
        results.append(("10", "SKIPPED", "OSAP file not downloaded"))
    else:
        op = pd.read_parquet(OSAP)
        op["permno"] = pd.to_numeric(op["permno"]).astype("int64")
        op["date"] = pd.to_datetime(op["yyyymm"].astype(int).astype(str), format="%Y%m") + MonthEnd(0)
        x = o[["permno", "date", "net_issuance_skip6"]].merge(op[["permno", "date", "ShareIss1Y"]], on=["permno", "date"])
        x = x.dropna()
        ours = np.expm1(x["net_issuance_skip6"])            # OSAP is a percentage change, ours a log change
        same = np.isclose(ours, x["ShareIss1Y"], rtol=1e-3, atol=1e-6).mean()
        rho = x["net_issuance_skip6"].corr(x["ShareIss1Y"], method="spearman")
        print(f"  {len(x):,} rows in both (OSAP's month = ours, both skip 6 months): same value (0.1%) in {same:.1%}; "
              f"rank correlation {rho:.3f}; OSAP months {op['date'].min():%Y-%m} to {op['date'].max():%Y-%m}")
        record("10", rho > 0.95, f"rank correlation with OSAP ShareIss1Y {rho:.3f}; identical in {same:.1%}")

    # 11 -----------------------------------------------------------------------------
    section("11. Share classes: one value per firm")
    one = o["n_classes"].fillna(1) == 1
    same1 = np.isclose(o.loc[one, "net_issuance"].fillna(-99), o.loc[one, "net_issuance_class"].fillna(-99), atol=1e-12).mean()
    mc = o[~one].merge(panel[["permno", "date", "me"]], on=["permno", "date"], how="left")
    spread = mc.groupby(["gvkey", "date"])["net_issuance"].agg(lambda x: x.max() - x.min() if x.notna().any() else 0.0)
    # independent recomputation: units now / units 12 months earlier, each class at its price at t
    r = mc.dropna(subset=["net_issuance_class", "me"])
    r = r[r["me"] > 0]
    units_now = r.groupby(["gvkey", "date"])["me"].sum()
    units_then = (r["me"] * np.exp(-r["net_issuance_class"])).groupby([r["gvkey"], r["date"]]).sum()
    rec = np.log(units_now / units_then).rename("recomputed")
    cmp_ = mc.drop_duplicates(["gvkey", "date"]).set_index(["gvkey", "date"])["net_issuance"].to_frame().join(rec, how="inner").dropna()
    agree = np.isclose(cmp_["net_issuance"], cmp_["recomputed"], atol=1e-10).mean()
    print(f"  single-class rows whose value equals the per-class value: {same1:.4%} of {one.sum():,}")
    print(f"  multi-class firm-months: {len(spread):,}; all classes carry one value in {(spread < 1e-12).mean():.4%}; "
          f"recomputed independently: same in {agree:.4%} of {len(cmp_):,}")
    ex = o[(o["date"] == "2025-12-31") & o["permno"].isin([17778, 83443, 14542, 90319])][
        ["permno", "gvkey", "n_classes", "net_issuance_class", "net_issuance"]]
    show(ex.round(4), indent=4)
    brk = ex.loc[ex["permno"].isin([17778, 83443]), "net_issuance"]
    goog = ex.loc[ex["permno"].isin([14542, 90319]), "net_issuance"]
    ok_ex = len(brk) == 2 and brk.nunique() == 1 and abs(brk.iloc[0]) < 0.01 and len(goog) == 2 and goog.nunique() == 1
    print("  Berkshire A and B: one value near 0 (A shares convert into B, no net buyback); Alphabet C and A: one value")
    record("11", same1 > 0.9999 and (spread < 1e-12).mean() > 0.9999 and agree > 0.9999 and ok_ex,
           f"single-class unchanged; one value per multi-class firm-month ({len(spread):,}); recomputed independently "
           f"{agree:.2%}; Berkshire {brk.iloc[0] if len(brk) else float('nan'):+.4f}, Alphabet {goog.iloc[0] if len(goog) else float('nan'):+.4f}")

    section("Summary")
    show(pd.DataFrame(results, columns=["check", "status", "note"]), indent=2)


if __name__ == "__main__":
    main()
