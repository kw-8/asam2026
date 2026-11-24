"""
validate_net_operating_assets.py
================================
Step 9 (Validate) of prompts/data_acquisition.md for signals/net_operating_assets.

Reads the files build_net_operating_assets.py made and runs the checks the
process asks for, plus a few specific to this signal:
  1. no duplicate permno + date (and no duplicate events)
  2. match to the panel, and why rows miss
  3. timing: published_date >= period_end, no value used before it was public,
     share assumed
  4. one ticker change traced (FB -> META)
  5. splits: one traced (NVIDIA, June 2024) and all splits checked (NOA has no
     price in it, so it must not move at a split)
  6. coverage vs the panel by year; ETFs marked n/a, not dropped
  7. outliers, and 3 well-known firms against their 10-Ks
  8. Definition B (noa_at_cur) and the minority-interest version (noa_mi) vs noa
  9. optional: Open Source Asset Pricing NOA and dNoa, if
     data/net_operating_assets/osap_NOA.parquet exists (get_osap_noa.py makes it)
 10. the two accounting breaks: the 2009 minority-interest fix, and the size of
     the 2019 operating-lease shift that stays in the data (known limitation)

Run from the repo root, with the .venv active (after build_net_operating_assets.py):
    python signals\\net_operating_assets\\validate_net_operating_assets.py
Everything printed is also saved to data/net_operating_assets/validate_log.txt.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
OUT = DATA / "net_operating_assets"
PANEL = DATA / "crsp_monthly_ratios_clean.parquet"
CRSP = DATA / "issuance_insider" / "crsp_monthly.parquet"
SECINFO = DATA / "lazy_prices" / "security_info.parquet"
COMPANY = DATA / "capex_intensity" / "company.parquet"
OSAP = OUT / "osap_NOA.parquet"

# Values from each firm's 10-K, $ millions (checked in Step 7): (name, fiscal year-end) -> {item: value}
TENK = {
    ("MICROSOFT CORP", "2024-06-30"): {"at": 512163, "che": 75543, "ceq": 268477, "lt": 243686},
    ("WALMART INC", "2025-01-31"): {"at": 260823, "ceq": 91013, "mib": 271, "mibn": 6408},
    ("BOEING CO", "2024-12-31"): {"che": 26282},
}
# Boeing's 2024 10-K was accepted by EDGAR on 2025-02-03 at 14:37:45 ET (before the close) -> public that day
BOEING_PUBLIC = "2025-02-03"
META, NVDA = 13407, 86580
FUTURE_GVKEY = "065286"      # the one Compustat row with a fiscal year-end in the future (Step 5)

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
    m = pd.read_parquet(OUT / "noa_monthly.parquet")
    ev = pd.read_parquet(OUT / "noa_events.parquet")
    for c in ("date", "period_end", "published_date"):
        m[c] = ns(m[c])
    for c in ("period_end", "published_date"):
        ev[c] = ns(ev[c])
    m["permno"] = m["permno"].astype("int64")
    co = pd.read_parquet(COMPANY)[["gvkey", "conm"]]
    co["gvkey"] = co["gvkey"].astype(str)
    sig = m[m["status"] == "ok"]

    head("1. Duplicates")
    d1 = m.duplicated(["permno", "date"]).sum()
    d2 = ev.duplicated(["gvkey", "period_end"]).sum()
    print(f"  monthly duplicate permno+date: {d1}; event duplicate gvkey+period_end: {d2}")
    record("1 duplicates", d1 == 0 and d2 == 0, f"{d1} monthly, {d2} event duplicates")

    head("2. Match to the panel, and why rows miss")
    panel = pd.read_parquet(PANEL, columns=["permno", "date"])
    panel["permno"] = panel["permno"].astype("int64")
    panel["date"] = ns(panel["date"])
    k_m = pd.MultiIndex.from_frame(m[["permno", "date"]])
    k_p = pd.MultiIndex.from_frame(panel)
    extra, missing = len(k_m.difference(k_p)), len(k_p.difference(k_m))
    print(f"  panel rows {len(panel):,}; monthly rows {len(m):,}; in monthly not panel {extra}; in panel not monthly {missing}")
    print("  status of every panel row:")
    print(m["status"].value_counts().to_frame("rows").assign(share=lambda d: (d["rows"] / len(m)).map("{:.1%}".format)).to_string())
    nolink = m[m["status"] == "no CCM link"]
    print(f"  'no CCM link' rows that also have no gvkey in the panel: {nolink['gvkey_panel'].isna().mean():.0%}")
    first = m[m["status"] == "no prior-year report (first year)"]
    print(f"  'first year' rows that still have noa_at_cur (Definition B): {first['noa_at_cur'].notna().mean():.0%}")
    record("2 match", extra == 0 and missing == 0, f"monthly file = panel rows exactly; noa on {len(sig) / len(m):.1%} of rows")

    head("3. Timing")
    bad_ev = (ev["published_date"] < ev["period_end"]).sum()
    early = (sig["published_date"] > sig["date"]).sum()
    old = (sig["date"] > sig["period_end"] + pd.offsets.MonthEnd(18)).sum()
    fut = (m["gvkey"].eq(FUTURE_GVKEY) & m["period_end"].gt("2026-11-30")).sum()
    print(f"  events published before their period end: {bad_ev}")
    print(f"  signal rows using a 10-K not yet public at the month-end: {early}")
    print(f"  signal rows older than 18 months: {old}")
    print(f"  rows using the future-dated Compustat record (gvkey {FUTURE_GVKEY}, FY ending 2027-05): {fut}")
    lag = (sig["published_date"] - sig["period_end"]).dt.days
    print(f"  days from fiscal year-end to publish (signal rows): median {lag.median():.0f}, "
          f"p1 {lag.quantile(.01):.0f}, p99 {lag.quantile(.99):.0f}")
    by = sig.groupby(sig["date"].dt.year // 5 * 5)["date_source"].apply(lambda s: (s == "assumed").mean())
    print("  share 'assumed' among signal rows, by 5-year period: " + ", ".join(f"{k}: {v:.0%}" for k, v in by.items()))
    print("  how the publish date was set (signal rows):")
    print(sig["timing_rule"].value_counts(normalize=True).map("{:.1%}".format).to_string())
    bg = co.loc[co["conm"] == "BOEING CO", "gvkey"]
    b = ev[ev["gvkey"].isin(bg) & (ev["period_end"] == "2024-12-31")]
    b_ok = len(b) == 1 and b["published_date"].iloc[0] == pd.Timestamp(BOEING_PUBLIC)
    if len(b):
        print(f"  Boeing 2024 10-K: EDGAR acceptance 2025-02-03 14:37 ET -> ours {b['published_date'].iloc[0]:%Y-%m-%d} "
              f"({b['timing_rule'].iloc[0]})")
    record("3 timing", bad_ev == 0 and early == 0 and old == 0 and fut == 0 and b_ok,
           f"0 look-ahead; {(sig['date_source'] == 'assumed').mean():.1%} of signal rows assumed; Boeing's filing time matches EDGAR")

    head("4. Ticker change traced: FB -> META (permno 13407)")
    si = pd.read_parquet(SECINFO)
    si["permno"] = si["permno"].astype("int64")
    t = si[si["permno"] == META].drop_duplicates("ticker", keep="first")[["permno", "ticker", "issuernm", "secinfostartdt"]]
    print(t.to_string(index=False))
    x = m[(m["permno"] == META) & m["date"].between("2022-04-30", "2022-08-31")]
    print(x[["permno", "gvkey", "date", "noa", "status", "period_end", "published_date"]].to_string(index=False))
    same = x["gvkey"].nunique() == 1 and x["noa"].notna().all() and x["noa"].nunique() == x["period_end"].nunique()
    record("4 ticker change", same, "same permno and gvkey before/after; noa changes only with a new 10-K")

    head("5. Splits (NOA has no price or share count in it, so a split must not move it)")
    c = pd.read_parquet(CRSP, columns=["permno", "date", "mthprc", "shrout", "mthcumfacshr"])
    c["permno"] = c["permno"].astype("int64")
    c["date"] = ns(c["date"])
    n = c[(c["permno"] == NVDA) & c["date"].between("2024-04-30", "2024-07-31")]
    n = n.merge(m[["permno", "date", "noa", "period_end"]], on=["permno", "date"])
    print("  NVIDIA 10-for-1 split, June 2024:")
    print(n.to_string(index=False))
    c = c.sort_values(["permno", "date"])
    c["fac_ratio"] = c["mthcumfacshr"] / c.groupby("permno")["mthcumfacshr"].shift()
    s = sig[["permno", "gvkey", "date", "noa", "period_end"]].sort_values(["permno", "date"]).copy()
    s["prev_noa"] = s.groupby("permno")["noa"].shift()
    s["prev_pe"] = s.groupby("permno")["period_end"].shift()
    s["prev_gvkey"] = s.groupby("permno")["gvkey"].shift()
    s = s.merge(c[["permno", "date", "fac_ratio"]], on=["permno", "date"], how="left")
    split = (s["fac_ratio"] <= 0.8) | (s["fac_ratio"] >= 1.25)
    cand = split & s["prev_noa"].notna() & (s["period_end"] == s["prev_pe"])
    relink = cand & (s["gvkey"] != s["prev_gvkey"])      # the stock was re-linked to another company that month
    same_rep = cand & ~relink
    moved = (s.loc[same_rep, "noa"] != s.loc[same_rep, "prev_noa"]).sum()
    print(f"  split months with the same company and 10-K as the month before: {same_rep.sum():,}; noa changed in {moved}")
    print(f"  split months where the stock was re-linked to a different Compustat company (mergers, reverse mergers): "
          f"{relink.sum()}; noa changes there because the company changed, not because of the split")
    nv_ok = n["noa"].notna().all() and n.loc[n["period_end"] == n["period_end"].iloc[0], "noa"].nunique() == 1
    record("5 splits", nv_ok and moved == 0,
           f"no change at NVIDIA's split; {moved} of {int(same_rep.sum()):,} split months moved "
           f"({int(relink.sum())} more are company re-links, not splits)")

    head("6. Coverage by year; ETFs")
    cov = m.groupby(m["date"].dt.year).agg(rows=("permno", "size"),
                                           noa=("status", lambda v: (v == "ok").mean()),
                                           first_year=("status", lambda v: (v == "no prior-year report (first year)").mean()),
                                           financial=("financial", "mean"))
    print(cov.loc[[1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025]].to_string(
        formatters={"noa": "{:.1%}".format, "first_year": "{:.1%}".format, "financial": "{:.1%}".format}))
    etf = si[si["securitysubtype"].astype(str).str.upper() == "ETF"]["permno"].unique()
    in_panel = np.isin(m["permno"].unique(), etf).sum()
    print(f"  ETF permnos in CRSP security info: {len(etf):,}; in the panel: {in_panel}")
    record("6 coverage", cov["noa"].min() > 0.5 and in_panel == 0,
           f"noa on {cov['noa'].min():.0%}-{cov['noa'].max():.0%} of panel rows each year; panel has no ETFs (0 n/a)")

    head("7. Outliers and well-known firms")
    print("  noa percentiles (signal rows): " + ", ".join(
        f"p{q}: {sig['noa'].quantile(q / 100):.3f}" for q in (1, 5, 50, 95, 99)) + f"; min {sig['noa'].min():.1f}, max {sig['noa'].max():.1f}")
    big = sig["noa"].abs() > 5
    print(f"  |noa| > 5: {big.mean():.2%} of signal rows")
    e2 = ev.merge(co, on="gvkey", how="left")
    for lab, asc in (("largest", False), ("most negative", True)):
        top = (e2[e2["noa"].notna() & e2["permno"].notna()].sort_values("noa", ascending=asc)
                 .drop_duplicates("gvkey").head(6))
        print(f"  {lab} values (one row per firm; $ millions):")
        print(top[["conm", "period_end", "noa", "noa_dollars", "at", "at_prev", "ceq"]].to_string(
            index=False, float_format=lambda v: f"{v:,.2f}"))
    sx = sig.merge(ev[["gvkey", "period_end", "ceq", "at_prev"]], on=["gvkey", "period_end"], how="left")
    print(f"  signal rows from firms with negative common equity: {(sx['ceq'] < 0).mean():.1%}")
    tiny = sx["at_prev"] < 1
    print(f"  signal rows whose prior-year assets were under $1 million (shells, SPACs before their IPO): "
          f"{tiny.mean():.2%}; they hold {(tiny & (sx['noa'].abs() > 5)).sum() / max(1, (sx['noa'].abs() > 5).sum()):.0%} "
          f"of the |noa| > 5 rows")
    rows, ok7 = [], True
    for (name, pe), items in TENK.items():
        g = co.loc[co["conm"] == name, "gvkey"]
        r = ev[ev["gvkey"].isin(g) & (ev["period_end"] == pe)]
        for k, want in items.items():
            got = float(r[k].iloc[0]) if len(r) else np.nan
            rows.append((name, pe, k, want, got))
            ok7 &= bool(np.isclose(got, want))
    tk = pd.DataFrame(rows, columns=["firm", "fiscal year-end", "item", "10-K", "ours"])
    print("  three firms vs their 10-Ks ($ millions):")
    print(tk.to_string(index=False))
    for name in ("MICROSOFT CORP", "WALMART INC", "BOEING CO"):
        g = co.loc[co["conm"] == name, "gvkey"]
        r = m[m["gvkey"].isin(g) & (m["date"] == "2024-12-31")]
        if len(r):
            r = r.iloc[0]
            e = ev[(ev["gvkey"] == r["gvkey"]) & (ev["period_end"] == r["period_end"])].iloc[0]
            z = lambda v: 0.0 if pd.isna(v) else float(v)   # noqa: E731
            num = e["ceq"] + z(e["pstk"]) + z(e["mib"]) + z(e["dltt"]) + z(e["dlc"]) - z(e["che"])
            print(f"  {name}, Dec 2024: noa {r['noa']:.4f} = ({e['ceq']:,.0f} + {z(e['pstk']):,.0f} + {z(e['mib']):,.0f} "
                  f"+ {z(e['dltt']):,.0f} + {z(e['dlc']):,.0f} - {z(e['che']):,.0f}) / {e['at_prev']:,.0f} = {num / e['at_prev']:.4f}"
                  f"  (FY ending {r['period_end']:%Y-%m}, public {r['published_date']:%Y-%m-%d})")
    record("7 outliers + firms", ok7, "every checked 10-K item matches; extremes come from tiny prior-year assets "
                                      "(SPACs, shells) or huge one-year growth; keep raw, rank or winsorize in the backtest")

    head("8. Definition B (noa_at_cur) and the minority-interest version (noa_mi) vs noa")
    rb = dec_rank_corr(m, "noa", "noa_at_cur")
    print(f"  December rank correlation, noa vs noa_at_cur: median {rb.median():.2f} (min {rb.min():.2f}, max {rb.max():.2f}), {len(rb)} years")
    rm = dec_rank_corr(m[m["date"].dt.year >= 2010], "noa", "noa_mi")
    print(f"  December rank correlation, noa vs noa_mi, 2010+: median {rm.median():.3f} (min {rm.min():.3f})")
    record("8 definitions", rb.median() > 0.8 and rm.median() > 0.95,
           "B ranks firms much like A (differences: asset growth); noa_mi reorders few firms")

    head("9. Open Source Asset Pricing NOA and dNoa (optional)")
    if OSAP.exists():
        o = pd.read_parquet(OSAP)
        o["permno"] = o["permno"].astype("int64")
        o["date"] = pd.to_datetime(o["yyyymm"].astype(int).astype(str), format="%Y%m") + pd.offsets.MonthEnd(0)
        j = sig.merge(ev[["gvkey", "period_end", "dlc", "pstk", "at_prev"]], on=["gvkey", "period_end"], how="left")
        j = j.merge(o[["permno", "date", "NOA", "dNoa"]], on=["permno", "date"], how="inner")
        j = j[np.isfinite(j["NOA"]) | j["NOA"].isna()]          # OSAP has inf where prior-year assets are 0
        jn = j.dropna(subset=["NOA"])
        rc = jn.groupby("date").apply(lambda d: d["noa"].rank().corr(d["NOA"].rank()) if len(d) > 20 else np.nan,
                                      include_groups=False).dropna()
        # same fiscal year in both: OSAP waits 6 months after year-end; we switch at the 10-K date
        months = (j["date"].dt.year - j["period_end"].dt.year) * 12 + j["date"].dt.month - j["period_end"].dt.month
        s = j[months.between(7, 12)]
        sn, sd = s.dropna(subset=["NOA"]), s.dropna(subset=["dNoa", "dnoa"])
        d_exact = (np.abs(sd["dnoa"] - sd["dNoa"]) < 1e-6).mean()
        raw = (np.abs(sn["noa"] - sn["NOA"]) < 0.01).mean()
        # OSAP's NOA code leaves short-term debt (dlc) out of the numerator, and for some firms preferred stock;
        # HHTZ (Compustat #34) and HXZ subtract debt in current liabilities, as we do.
        no_dlc = sn["noa"] - sn["dlc"].fillna(0.0) / sn["at_prev"]
        no_dlc_pstk = no_dlc - sn["pstk"].fillna(0.0) / sn["at_prev"]
        expl_dlc = (np.abs(no_dlc - sn["NOA"]) < 0.01).mean()
        expl = ((np.abs(no_dlc - sn["NOA"]) < 0.01) | (np.abs(no_dlc_pstk - sn["NOA"]) < 0.01)).mean()
        print(f"  OSAP rows {len(o):,} ({o['date'].min():%Y-%m} to {o['date'].max():%Y-%m}); our signal rows found in OSAP "
              f"{len(jn) / len(sig):.0%}; median monthly rank correlation of noa with NOA {rc.median():.3f}")
        print(f"  Rows where both use the same fiscal year (7-12 months after year-end): {len(s):,}")
        print(f"    dnoa vs OSAP dNoa: identical (to 1e-6) in {d_exact:.1%}  -> same inputs, same prior year, same scaling")
        print(f"    noa  vs OSAP NOA: within 0.01 in {raw:.1%}")
        print(f"    ... after taking short-term debt (dlc) out of ours: {expl_dlc:.1%}; "
              f"and preferred stock where that explains it: {expl:.1%}")
        print("  OSAP's NOA leaves short-term debt out (its documentation calls the item 'deferred charges (dlc)').")
        print("  HHTZ (Compustat item 34) and Hou-Xue-Zhang subtract debt in current liabilities, as our noa does.")
        record("9 OSAP", d_exact > 0.99 and expl > 0.85,
               f"dNoa identical in {d_exact:.1%} of same-year rows; NOA differs by OSAP leaving out short-term debt "
               f"(explains {expl:.0%}); rank correlation {rc.median():.2f}")
    else:
        print("  not run: python signals\\net_operating_assets\\get_osap_noa.py downloads it (no WRDS login).")
        RESULTS.append(("9 OSAP", "SKIPPED", "optional; run get_osap_noa.py first"))

    head("10. Accounting breaks: 2009 minority interest (fixed in noa_mi), 2019 operating leases (not fixed)")
    e = ev[ev["noa"].notna()].copy()
    e["yr"] = e["period_end"].dt.year
    diff = (e["noa_mi"] - e["noa"]).abs() > 0.01
    print("  share of firm-years where noa_mi differs from noa by > 0.01: "
          + ", ".join(f"{y}: {v:.1%}" for y, v in diff.groupby(e["yr"]).mean().loc[2006:2012].items()))
    post = e[(e["yr"] >= 2010) & e["mibn"].notna()]
    fix = ((post["noa_mi"] - post["noa"]) * post["at_prev"] - post["mibn"]).abs() <= 0.01 * post["at"]
    print(f"  fiscal 2010+: noa_mi - noa equals mibn / at_prev in {fix.mean():.1%} of {len(post):,} firm-years")
    sig2 = sig.copy()
    sig2["retail"] = sig2["siccd"].between(5200, 5999)
    dm = sig2[sig2["date"].dt.month == 12].groupby([sig2["date"].dt.year, "retail"])["noa"].median().unstack()
    dm.columns = ["others", "retail & restaurants"]
    print("  median December noa (shows the 2019 lease shift that remains in the data):")
    print(dm.loc[2016:2023].to_string(float_format=lambda v: f"{v:.3f}"))
    jump = (dm.loc[2020, "retail & restaurants"] - dm.loc[2018, "retail & restaurants"]) - \
           (dm.loc[2020, "others"] - dm.loc[2018, "others"])
    print(f"  retail median rose {jump:+.3f} more than others from Dec 2018 to Dec 2020 (known limitation)")
    record("10 accounting breaks", fix.mean() > 0.99 and not diff.groupby(e["yr"]).mean().loc[:2008].gt(0.001).any(),
           f"minority-interest fix exact; lease shift measured ({jump:+.2f} for retail) and documented, not fixed")

    head("SUMMARY")
    for r in RESULTS:
        print(f"  {r[0]:22s} {r[1]:8s} {r[2]}")


if __name__ == "__main__":
    main()
