"""
validate_shareholder_yield.py
=============================
Step 9 (Validate) of prompts/data_acquisition.md for signals/shareholder_yield.

Reads the files build_shareholder_yield.py made and runs the checks the process
asks for, plus a few specific to this signal:
  1. no duplicate permno + date (and no duplicate events)
  2. match to the panel, and why rows miss
  3. timing: published_date >= period_end, no value used before it was public,
     share assumed; Apple's FY2024 10-K time against EDGAR
  4. one ticker change traced (FB -> META)
  5. splits: one traced (NVIDIA, June 2024) and all splits checked (the yield
     divides by market value, which a split must not move)
  6. coverage vs the panel by year; ETFs marked n/a, not dropped
  7. outliers, and 3 well-known firms against their filings
  8. the named check (payout_yield) and the robustness column (net_payout_yield_xpref,
     no preferred-stock adjustment) vs the primary, and the zero-filled rows
  9. Open Source Asset Pricing NetPayoutYield / PayoutYield, if
     data/shareholder_yield/osap_payout.parquet exists (get_osap_payout.py makes it)
 10. for information only: rank correlation with divyield (panel) and
     net_issuance / comp_issuance (if data/issuance_insider/net_issuance_monthly.parquet
     exists). Not used to change the definition (Step 1: a backtest question).

Run from the repo root, with the .venv active (after build_shareholder_yield.py):
    python signals\\shareholder_yield\\validate_shareholder_yield.py
Everything printed is also saved to data/shareholder_yield/validate_log.txt.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
OUT = DATA / "shareholder_yield"
PANEL = DATA / "crsp_monthly_ratios_clean.parquet"
CRSP = DATA / "issuance_insider" / "crsp_monthly.parquet"
NETISS = DATA / "issuance_insider" / "net_issuance_monthly.parquet"
SECINFO = DATA / "lazy_prices" / "security_info.parquet"
COMPANY = DATA / "capex_intensity" / "company.parquet"
OSAP = OUT / "osap_payout.parquet"

# Values from each firm's filings, $ millions (checked in Step 7):
#   Microsoft FY2024 cash-flow statement: common stock issued 2,002, repurchased 17,254
#   ExxonMobil 2024: cash dividends to ExxonMobil shareholders 16,704, common stock acquired 19,629
#   Apple FY2024: repurchases 94,949 + taxes for net share settlement of equity awards 5,441
#                 (Compustat counts both as buybacks); no stock-issuance line (sstk blank -> 0)
TENK = {
    ("012141", "2024-06-30"): ("Microsoft", {"sstk": 2002, "prstkc": 17254}),
    ("004503", "2024-12-31"): ("ExxonMobil", {"dvc": 16704, "prstkc": 19629}),
    ("001690", "2024-09-30"): ("Apple", {"prstkc": 94949 + 5441, "sstk": np.nan}),
}
# Apple's FY2024 10-K: EDGAR accepted 2024-11-01 06:01:36 ET (before the close) -> public that day
APPLE_GVKEY, APPLE_PUBLIC = "001690", "2024-11-01"
META, NVDA = 13407, 86580
FUTURE_GVKEY = "065286"      # the one Compustat row with a fiscal year-end in the future (Step 7)
MAX_AGE = 18

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 30)
RESULTS: list[tuple[str, str, str]] = []


class Tee:
    def __init__(self, path: Path):
        self.file = open(path, "w", encoding="utf-8")
        self.screen = sys.stdout

    def write(self, text):
        self.screen.write(text)
        self.file.write(text)

    def flush(self):
        self.screen.flush()
        self.file.flush()


def ns(s):
    return pd.to_datetime(s).astype("datetime64[ns]")


def record(n: str, ok: bool, note: str) -> None:
    RESULTS.append((n, "PASS" if ok else "CHECK", note))
    print(f"  -> {'PASS' if ok else 'CHECK'}: {note}")


def head(t: str) -> None:
    print("\n" + "=" * 90 + f"\n{t}\n" + "=" * 90)


def dec_rank_corr(d: pd.DataFrame, a: str, b: str) -> pd.Series:
    d = d[(d["date"].dt.month == 12) & d[a].notna() & d[b].notna()]
    return d.groupby("date").apply(lambda x: x[a].rank().corr(x[b].rank()) if len(x) > 20 else np.nan,
                                   include_groups=False).dropna()


def main() -> None:
    sys.stdout = Tee(OUT / "validate_log.txt")
    m = pd.read_parquet(OUT / "shareholder_yield_monthly.parquet")
    ev = pd.read_parquet(OUT / "payout_events.parquet")
    for c in ("date", "period_end", "published_date"):
        m[c] = ns(m[c])
    for c in ("period_end", "published_date"):
        ev[c] = ns(ev[c])
    m["permno"] = m["permno"].astype("int64")
    co = pd.read_parquet(COMPANY)[["gvkey", "conm", "sic"]]
    co["gvkey"] = co["gvkey"].astype(str)
    sig = m[m["status"] == "ok"].copy()
    # payout dollars implied by the yield ($ millions): constant within one 10-K
    sig["payout_dollars"] = sig["net_payout_yield"] * sig["me_firm"] / 1000.0

    head("1. Duplicates")
    d1 = m.duplicated(["permno", "date"]).sum()
    d2 = ev.duplicated(["gvkey", "period_end"]).sum()
    print(f"  monthly duplicate permno+date: {d1}; event duplicate gvkey+period_end: {d2}")
    record("1 duplicates", d1 == 0 and d2 == 0, f"{d1} monthly, {d2} event duplicates")

    head("2. Match to the panel, and why rows miss")
    names = pq.read_schema(PANEL).names
    panel = pd.read_parquet(PANEL, columns=["permno", "date"] + (["divyield"] if "divyield" in names else []))
    panel["permno"] = panel["permno"].astype("int64")
    panel["date"] = ns(panel["date"])
    k_m = pd.MultiIndex.from_frame(m[["permno", "date"]])
    k_p = pd.MultiIndex.from_frame(panel[["permno", "date"]])
    extra, missing = len(k_m.difference(k_p)), len(k_p.difference(k_m))
    print(f"  panel rows {len(panel):,}; monthly rows {len(m):,}; in monthly not panel {extra}; in panel not monthly {missing}")
    print("  status of every panel row:")
    print(m["status"].value_counts().to_frame("rows").assign(share=lambda d: (d["rows"] / len(m)).map("{:.1%}".format)).to_string())
    nolink = m[m["status"] == "no CCM link"]
    print(f"  'no CCM link' rows that also have no gvkey in the panel: {nolink['gvkey_panel'].isna().mean():.0%}")
    nodvc = m[m["status"] == "no dividends figure (dvc blank)"]
    by = nodvc.groupby(nodvc["date"].dt.year // 10 * 10).size()
    print("  'dvc blank' rows by decade: " + ", ".join(f"{k}s {v:,}" for k, v in by.items()))
    record("2 match", extra == 0 and missing == 0,
           f"monthly file = panel rows exactly; yields on {len(sig) / len(m):.1%} of rows")

    head("3. Timing")
    bad_ev = (ev["published_date"] < ev["period_end"]).sum()
    early = (sig["published_date"] > sig["date"]).sum()
    old = (sig["date"] > sig["period_end"] + pd.offsets.MonthEnd(MAX_AGE)).sum()
    fut = (m["gvkey"].eq(FUTURE_GVKEY) & m["period_end"].gt("2026-11-30")).sum()
    print(f"  events published before their period end: {bad_ev}")
    print(f"  signal rows using a 10-K not yet public at the month-end: {early}")
    print(f"  signal rows older than {MAX_AGE} months: {old}")
    print(f"  rows using the future-dated Compustat record (gvkey {FUTURE_GVKEY}, FY ending 2027-05): {fut}")
    lag = (sig["published_date"] - sig["period_end"]).dt.days
    print(f"  days from fiscal year-end to publish (signal rows): median {lag.median():.0f}, "
          f"p1 {lag.quantile(.01):.0f}, p99 {lag.quantile(.99):.0f}")
    by = sig.groupby(sig["date"].dt.year // 5 * 5)["date_source"].apply(lambda s: (s == "assumed").mean())
    print("  share 'assumed' among signal rows, by 5-year period: " + ", ".join(f"{k}: {v:.0%}" for k, v in by.items()))
    print("  how the publish date was set (signal rows):")
    print(sig["timing_rule"].value_counts(normalize=True).map("{:.1%}".format).to_string())
    a = ev[(ev["gvkey"] == APPLE_GVKEY) & (ev["period_end"] == "2024-09-30")]
    a_ok = len(a) == 1 and a["published_date"].iloc[0] == pd.Timestamp(APPLE_PUBLIC)
    if len(a):
        print(f"  Apple FY2024 10-K: EDGAR acceptance 2024-11-01 06:01 ET -> ours {a['published_date'].iloc[0]:%Y-%m-%d} "
              f"({a['timing_rule'].iloc[0]})")
    record("3 timing", bad_ev == 0 and early == 0 and old == 0 and fut == 0 and a_ok,
           f"0 look-ahead; {(sig['date_source'] == 'assumed').mean():.1%} of signal rows assumed; "
           f"Apple's filing time matches EDGAR")

    head("4. Ticker change traced: FB -> META (permno 13407)")
    si = pd.read_parquet(SECINFO)
    si["permno"] = si["permno"].astype("int64")
    t = si[si["permno"] == META].drop_duplicates("ticker", keep="first")[["permno", "ticker", "issuernm", "secinfostartdt"]]
    print(t.to_string(index=False))
    x = sig[(sig["permno"] == META) & sig["date"].between("2022-03-31", "2022-09-30")]
    print(x[["permno", "gvkey", "date", "net_payout_yield", "payout_yield", "me_firm", "payout_dollars",
             "period_end", "published_date"]].to_string(index=False, float_format=lambda v: f"{v:,.4f}" if abs(v) < 10 else f"{v:,.0f}"))
    same = (x["gvkey"].nunique() == 1 and len(x) == 7
            and x.groupby("period_end")["payout_dollars"].apply(lambda s: np.ptp(s) < 1e-6).all())
    record("4 ticker change", same, "same permno and gvkey across the June 2022 rename; payout dollars change only "
                                    "with a new 10-K (the yield moves with the share price, as it should)")

    head("5. Splits (payout dollars over market value: a split must not move the yield)")
    c = pd.read_parquet(CRSP, columns=["permno", "date", "mthprc", "shrout", "mthcumfacshr", "mthretx"])
    c["permno"] = c["permno"].astype("int64")
    c["date"] = ns(c["date"])
    n = c[(c["permno"] == NVDA) & c["date"].between("2024-04-30", "2024-08-31")]
    n = n.merge(m[["permno", "date", "net_payout_yield", "me_firm", "period_end"]], on=["permno", "date"])
    print("  NVIDIA 10-for-1 split, June 2024 (price and shares jump; market value and yield don't):")
    print(n.to_string(index=False, float_format=lambda v: f"{v:,.4f}" if abs(v) < 10 else f"{v:,.0f}"))
    c = c.sort_values(["permno", "date"])
    c["fac_ratio"] = c["mthcumfacshr"] / c.groupby("permno")["mthcumfacshr"].shift()
    c["sh_ratio"] = c["shrout"] / c.groupby("permno")["shrout"].shift()
    s = sig[["permno", "gvkey", "date", "net_payout_yield", "me_firm", "n_classes", "period_end"]].sort_values(["permno", "date"]).copy()
    for col in ("net_payout_yield", "me_firm", "period_end", "gvkey", "n_classes"):
        s[f"prev_{col}"] = s.groupby("permno")[col].shift()
    s = s.merge(c[["permno", "date", "fac_ratio", "sh_ratio", "mthretx"]], on=["permno", "date"], how="left")
    split = (s["fac_ratio"] <= 0.8) | (s["fac_ratio"] >= 1.25)
    cand = (split & s["prev_me_firm"].notna() & (s["period_end"] == s["prev_period_end"])
            & (s["gvkey"] == s["prev_gvkey"]) & (s["n_classes"] == 1) & (s["prev_n_classes"] == 1))
    # with the same 10-K, the yield changes only through market value, which should follow the
    # price-only return (1 + retx) at a split, not the split factor
    rel = (s["me_firm"] / s["prev_me_firm"] / (1 + s["mthretx"]))[cand]
    within = rel.between(0.9, 1.1)
    jumps = ~rel.between(0.5, 2.0)
    # where market value did not follow the price return, did CRSP's share count move by the split factor?
    shares_off = ~(s.loc[cand, "sh_ratio"] / s.loc[cand, "fac_ratio"]).between(0.9, 1.1)
    explained = shares_off[~within].mean() if (~within).any() else 1.0
    print(f"  split months (single-class firms, same company and 10-K as the month before): {int(cand.sum()):,}")
    print(f"  market value moved with the stock's price-only return (within 10%): {within.mean():.1%}; "
          f"off by more than 2x: {int(jumps.sum())} ({jumps.mean():.1%})")
    print(f"  of the months that did not follow the price return, CRSP's shares outstanding did not move by the "
          f"split factor in {explained:.1%}")
    print("  -> those come from the panel's market value (price x CRSP shares outstanding): at some splits CRSP")
    print("     updates the share count a month late (mostly penny-stock reverse splits), or shares were also")
    print("     issued or bought back that month. Not from this build; every price-scaled signal on the panel has it.")
    by = rel[jumps].index.map(lambda i: s.loc[i, "date"].year // 10 * 10).value_counts().sort_index()
    print("  >2x months by decade: " + ", ".join(f"{k}s {v}" for k, v in by.items()))
    nv_ok = n["me_firm"].pct_change().abs().max() < 0.5
    record("5 splits", nv_ok and explained > 0.95,
           f"no jump at NVIDIA's split; market value follows the price return in {within.mean():.1%} of "
           f"{int(cand.sum()):,} split months; the rest trace to CRSP's share count ({explained:.0%}), "
           f"a known panel limitation")

    head("6. Coverage by year; ETFs")
    cov = m.groupby(m["date"].dt.year).agg(rows=("permno", "size"),
                                           yields=("status", lambda v: (v == "ok").mean()),
                                           dvc_blank=("status", lambda v: (v == "no dividends figure (dvc blank)").mean()),
                                           financial=("financial", "mean"))
    print(cov.loc[[1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025]].to_string(
        formatters={"yields": "{:.1%}".format, "dvc_blank": "{:.1%}".format, "financial": "{:.1%}".format}))
    etf = si[si["securitysubtype"].astype(str).str.upper() == "ETF"]["permno"].unique()
    in_panel = np.isin(m["permno"].unique(), etf).sum()
    print(f"  ETF permnos in CRSP security info: {len(etf):,}; in the panel: {in_panel}")
    record("6 coverage", cov["yields"].min() > 0.5 and in_panel == 0,
           f"yields on {cov['yields'].min():.0%}-{cov['yields'].max():.0%} of panel rows each year; panel has no ETFs (0 n/a)")

    head("7. Outliers and well-known firms")
    for col in ("net_payout_yield", "payout_yield"):
        print(f"  {col} percentiles (signal rows): " + ", ".join(
            f"p{q:g}: {sig[col].quantile(q / 100):.4f}" for q in (0.1, 1, 5, 50, 95, 99, 99.9))
            + f"; min {sig[col].min():.2f}, max {sig[col].max():.2f}")
    big = sig["net_payout_yield"].abs() > 1
    sx = sig.merge(ev[["gvkey", "period_end", "pref_down", "pref_up"]], on=["gvkey", "period_end"], how="left")
    sx["pref_part"] = (sx["pref_down"] - sx["pref_up"]) * 1000.0 / sx["me_firm"]
    b = big.to_numpy()
    print(f"  |net_payout_yield| > 1 (payouts or issuance larger than the firm's market value): {big.mean():.2%} of signal rows; "
          f"of these, market value under $50 million {(sx['me_firm'] < 50000).to_numpy()[b].mean():.0%}; "
          f"preferred-stock change more than half the yield {(sx['pref_part'].abs() > 0.5 * sx['net_payout_yield'].abs()).to_numpy()[b].mean():.0%}")
    inv = sx["me_firm"] >= 250000
    print(f"  firms worth $250 million or more: |net_payout_yield| > 1 in {big[inv.to_numpy()].mean():.2%}; "
          f"p1 {sig.loc[inv.to_numpy(), 'net_payout_yield'].quantile(.01):.3f}, p99 {sig.loc[inv.to_numpy(), 'net_payout_yield'].quantile(.99):.3f}")
    print(f"  preferred-stock adjustment (paper's definition): in {((sx['pref_down'] > 0) | (sx['pref_up'] > 0)).mean():.1%} "
          f"of signal rows; worth more than 10% of market value in {(sx['pref_part'].abs() > 0.1).mean():.2%}")
    e2 = ev.merge(co[["gvkey", "conm"]], on="gvkey", how="left")
    j = sig.merge(e2[["gvkey", "period_end", "conm", "dvc", "prstkc", "sstk", "net_payout"]], on=["gvkey", "period_end"])
    for lab, asc in (("highest", False), ("lowest", True)):
        top = j.sort_values("net_payout_yield", ascending=asc).drop_duplicates("gvkey").head(6)
        print(f"  {lab} net_payout_yield (one row per firm; $ millions, me_firm in $ thousands):")
        print(top[["conm", "date", "net_payout_yield", "net_payout", "dvc", "prstkc", "sstk", "me_firm"]].to_string(
            index=False, float_format=lambda v: f"{v:,.2f}"))
    rows, ok7 = [], True
    for (gv, pe), (name, items) in TENK.items():
        r = ev[(ev["gvkey"] == gv) & (ev["period_end"] == pe)]
        for k, want in items.items():
            got = float(r[k].iloc[0]) if len(r) else np.nan
            rows.append((name, pe, k, want, got))
            ok7 &= bool(np.isclose(got, want, equal_nan=True))
    tk = pd.DataFrame(rows, columns=["firm", "fiscal year-end", "item", "filing", "ours"])
    print("  three firms vs their filings ($ millions; Apple's blank sstk is filled with 0 in the yield):")
    print(tk.to_string(index=False))
    for gv, name in (("012141", "Microsoft"), ("004503", "ExxonMobil"), ("001690", "Apple")):
        r = m[(m["gvkey"] == gv) & (m["date"] == "2024-12-31")]
        if len(r):
            r = r.iloc[0]
            e = ev[(ev["gvkey"] == gv) & (ev["period_end"] == r["period_end"])].iloc[0]
            z = lambda v: 0.0 if pd.isna(v) else float(v)   # noqa: E731
            print(f"  {name}, Dec 2024: net {r['net_payout_yield']:.4f} = 1000 x ({e['dvc']:,.0f} + {z(e['prstkc']):,.0f} "
                  f"+ {abs(e['pref_down']):,.0f} - {z(e['sstk']):,.0f} + {abs(e['pref_up']):,.0f}) / {r['me_firm']:,.0f}; "
                  f"gross {r['payout_yield']:.4f}  (FY ending {r['period_end']:%Y-%m}, public {r['published_date']:%Y-%m-%d})")
    record("7 outliers + firms", ok7, "every checked filing item matches; extremes are mostly tiny firms (equity raises "
                                      "or payouts larger than market value) and preferred-stock changes; keep raw, rank or "
                                      "winsorize in the backtest")

    head("8. Named check (payout_yield) and robustness column (net_payout_yield_xpref) vs primary; zero-filled rows")
    rb = dec_rank_corr(m, "net_payout_yield", "payout_yield")
    print(f"  December rank correlation, net vs gross: median {rb.median():.2f} (min {rb.min():.2f}, max {rb.max():.2f}), {len(rb)} years")
    rx = dec_rank_corr(m, "net_payout_yield", "net_payout_yield_xpref")
    px = sig.merge(ev[["gvkey", "period_end", "pref_down", "pref_up", "dvc", "prstkc", "sstk"]],
                   on=["gvkey", "period_end"], how="left")
    no_pref = (px["pref_down"] == 0) & (px["pref_up"] == 0)
    same_x = np.isclose(px["net_payout_yield"], px["net_payout_yield_xpref"], rtol=0, atol=1e-12)
    diff_x = px["net_payout_yield"] - px["net_payout_yield_xpref"]
    want_x = (px["pref_down"] + px["pref_up"]) * 1000.0 / px["me_firm"]
    x_ok = bool(same_x[no_pref].all()) and bool(np.isclose(diff_x, want_x, rtol=1e-9, atol=1e-12).all())
    print(f"  December rank correlation, net vs net without preferred adjustment (xpref): median {rx.median():.3f} "
          f"(min {rx.min():.3f})")
    print(f"  xpref = primary where there is no preferred change: {same_x[no_pref].mean():.1%} of {int(no_pref.sum()):,} rows; "
          f"elsewhere the gap is exactly (pref_down + pref_up) / market value: {x_ok}")
    d = px[px["date"].dt.month.eq(12) & (px["me_firm"] >= 250000)].copy()
    for col in ("net_payout_yield", "net_payout_yield_xpref"):
        d[f"q_{col}"] = d.groupby("date")[col].transform(lambda v: pd.qcut(v.rank(method="first"), 5, labels=False))
    top = d[d["q_net_payout_yield"] == 4]
    print(f"  firms >= $250M, Decembers: of the primary's top quintile, {(top['q_net_payout_yield_xpref'] == 4).mean():.1%} "
          f"are also in xpref's top quintile")
    print(f"  signal rows: gross = net (no issuance) {np.isclose(sig['payout_yield'], sig['net_payout_yield']).mean():.1%}; "
          f"non-payers (gross = 0) {(sig['payout_yield'] == 0).mean():.1%}; net issuers (net < 0) {(sig['net_payout_yield'] < 0).mean():.1%}")
    zf = sig["zero_filled"].fillna("")
    print("  zero-filled items (signal rows): " + ", ".join(f"{k or 'none'} {v:.1%}" for k, v in zf.value_counts(normalize=True).items()))
    print("  share with any item zero-filled, by decade: " + ", ".join(
        f"{k}s {v:.1%}" for k, v in (zf != "").groupby(sig["date"].dt.year // 10 * 10).mean().items()))
    print("  the paper's strict sample (nothing zero-filled) = signal rows with zero_filled == ''")
    ap = sig[(sig["gvkey"] == APPLE_GVKEY) & sig["date"].dt.month.eq(12) & sig["date"].dt.year.between(2022, 2025)]
    print("  Apple, December values (sstk blank in FY2022-24 -> zero-filled):")
    print(ap[["date", "net_payout_yield", "payout_yield", "zero_filled", "period_end"]].to_string(index=False))
    record("8 net vs gross, xpref", rb.median() > 0.5 and x_ok
           and (sig["payout_yield"] >= sig["net_payout_yield"] - 1e-12).mean() > 0.97,
           f"net vs gross rank correlation {rb.median():.2f}; xpref differs only by the preferred change "
           f"(rank correlation {rx.median():.3f}); zero-filled rows flagged ({(zf != '').mean():.1%})")

    head("9. Open Source Asset Pricing NetPayoutYield / PayoutYield")
    if OSAP.exists():
        o = pd.read_parquet(OSAP)
        o["permno"] = o["permno"].astype("int64")
        o["date"] = pd.to_datetime(o["yyyymm"].astype(int).astype(str), format="%Y%m") + pd.offsets.MonthEnd(0)
        # OSAP's value at month t uses the market value of month s = t-6 and the latest fiscal year
        # ending by s. Ours at month s uses the market value of s and the latest 10-K public by s.
        # Shift OSAP back 6 months; where our fiscal year ended 0-11 months before s, both use the
        # same fiscal year and the same market-value month, so the values should agree.
        o["date"] = o["date"] - pd.offsets.MonthEnd(6)
        j = sig.merge(o[["permno", "date", "NetPayoutYield", "PayoutYield"]], on=["permno", "date"], how="inner")
        print(f"  OSAP rows {len(o):,}; our signal rows found in OSAP (OSAP date moved back 6 months): {len(j) / len(sig):.0%}")
        months = (j["date"].dt.year - j["period_end"].dt.year) * 12 + j["date"].dt.month - j["period_end"].dt.month
        same = j[months.between(0, 11) & j["NetPayoutYield"].notna()]
        rel = (same["net_payout_yield"] / same["NetPayoutYield"] - 1).abs()
        relg = (same["payout_yield"] / same["PayoutYield"] - 1).abs()
        print(f"  rows where both use the same fiscal year and the same market-value month: {len(same):,}")
        print(f"    net:   within 1% of OSAP in {(rel < 0.01).mean():.1%}; within 0.01% in {(rel < 1e-4).mean():.1%}")
        print(f"    gross: within 1% of OSAP in {(relg.dropna() < 0.01).mean():.1%}")
        rc = j.dropna(subset=["NetPayoutYield"]).groupby("date").apply(
            lambda d: d["net_payout_yield"].rank().corr(d["NetPayoutYield"].rank()) if len(d) > 20 else np.nan,
            include_groups=False).dropna()
        print(f"  median monthly rank correlation, all overlapping rows: {rc.median():.3f}")
        off = same[rel >= 0.01]
        if len(off):
            mult = off["n_classes"] > 1
            print(f"  rows more than 1% apart: {len(off):,}; of these multi-class firms {mult.mean():.0%} "
                  f"(OSAP adds every CRSP class of the firm, we add classes in the panel)")
        record("9 OSAP", (rel < 0.01).mean() > 0.9 and rc.median() > 0.9,
               f"same-year values within 1% in {(rel < 0.01).mean():.1%}; rank correlation {rc.median():.2f}")
    else:
        print("  not run: python signals\\shareholder_yield\\get_osap_payout.py downloads it (no WRDS login).")
        RESULTS.append(("9 OSAP", "SKIPPED", "run get_osap_payout.py first"))

    head("10. For information: how much it overlaps the team's related signals (December rank correlations)")
    if "divyield" in panel.columns:
        d = sig.merge(panel[["permno", "date", "divyield"]], on=["permno", "date"], how="left")
        r = dec_rank_corr(d, "payout_yield", "divyield")
        print(f"  payout_yield vs panel divyield: median {r.median():.2f}")
    if NETISS.exists():
        ni = pd.read_parquet(NETISS, columns=["permno", "date", "net_issuance", "comp_issuance"])
        ni["permno"] = ni["permno"].astype("int64")
        ni["date"] = ns(ni["date"])
        d = sig.merge(ni, on=["permno", "date"], how="left")
        d["minus_net_issuance"], d["minus_comp_issuance"] = -d["net_issuance"], -d["comp_issuance"]
        for col in ("minus_net_issuance", "minus_comp_issuance"):
            r = dec_rank_corr(d, "net_payout_yield", col)
            print(f"  net_payout_yield vs {col}: median {r.median():.2f}")
    print("  (signs flipped so that 'more paid out' is high in both; reported only, not used to choose anything)")
    RESULTS.append(("10 overlap", "INFO", "rank correlations with divyield, net_issuance, comp_issuance reported"))

    head("SUMMARY")
    for r in RESULTS:
        print(f"  {r[0]:22s} {r[1]:8s} {r[2]}")


if __name__ == "__main__":
    main()
