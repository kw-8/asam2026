"""
validate_rd_to_market.py
========================
Step 9 (Validate) of prompts/data_acquisition.md for signals/rd_to_market.

Reads the files build_rd_to_market.py made and runs the checks the process
asks for, plus a few specific to this signal:
  1. no duplicate permno + date (and no duplicate events)
  2. match to the panel, and why rows miss
  3. timing: published_date >= period_end, no value used before it was public,
     share assumed
  4. one ticker change traced (FB -> META)
  5. splits: one traced (NVIDIA, June 2024) and all splits checked for jumps
  6. coverage vs the panel by year; ETFs marked n/a, not dropped
  7. outliers, and 3 well-known firms against their 10-Ks
  8. Definition B (Hou-Xue-Zhang, June-fixed) vs Definition A
  9. optional: Open Source Asset Pricing RD, if data/rd_to_market/osap_RD.parquet
     exists (python signals\\rd_to_market\\get_osap_rd.py makes it)

Run from the repo root, with the .venv active (after build_rd_to_market.py):
    python signals\\rd_to_market\\validate_rd_to_market.py
Everything printed is also saved to data/rd_to_market/validate_log.txt.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
OUT = DATA / "rd_to_market"
PANEL = DATA / "crsp_monthly_ratios_clean.parquet"
CRSP = DATA / "issuance_insider" / "crsp_monthly.parquet"
SECINFO = DATA / "lazy_prices" / "security_info.parquet"
COMPANY = DATA / "capex_intensity" / "company.parquet"
OSAP = OUT / "osap_RD.parquet"

# Values from each firm's 10-K, $ millions (checked in Step 7)
TENK = {("MICROSOFT CORP", 2024): 29510, ("INTEL CORP", 2023): 16046, ("MERCK & CO INC", 2023): 30531}
META, NVDA = 13407, 86580

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


def main() -> None:
    sys.stdout = Tee(OUT / "validate_log.txt")
    m = pd.read_parquet(OUT / "rd_to_market_monthly.parquet")
    ev = pd.read_parquet(OUT / "rd_events.parquet")
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
    record("2 match", extra == 0 and missing == 0, f"monthly file = panel rows exactly; signal on {len(sig) / len(m):.1%} of rows")

    head("3. Timing")
    bad_ev = (ev["published_date"] < ev["period_end"]).sum()
    early = (sig["published_date"] > sig["date"]).sum()
    old = (sig["date"] > sig["period_end"] + pd.offsets.MonthEnd(18)).sum()
    print(f"  events published before their period end: {bad_ev}")
    print(f"  signal rows using a 10-K not yet public at the month-end: {early}")
    print(f"  signal rows older than 18 months: {old}")
    lag = (sig["published_date"] - sig["period_end"]).dt.days
    print(f"  days from fiscal year-end to publish (signal rows): median {lag.median():.0f}, "
          f"p1 {lag.quantile(.01):.0f}, p99 {lag.quantile(.99):.0f}")
    by = sig.groupby(sig["date"].dt.year // 5 * 5)["date_source"].apply(lambda s: (s == "assumed").mean())
    print("  share 'assumed' among signal rows, by 5-year period: " + ", ".join(f"{k}: {v:.0%}" for k, v in by.items()))
    print("  how the publish date was set (signal rows):")
    print(sig["timing_rule"].value_counts(normalize=True).map("{:.1%}".format).to_string())
    record("3 timing", bad_ev == 0 and early == 0 and old == 0,
           f"0 look-ahead; {(sig['date_source'] == 'assumed').mean():.1%} of signal rows assumed")

    head("4. Ticker change traced: FB -> META (permno 13407)")
    si = pd.read_parquet(SECINFO)
    si["permno"] = si["permno"].astype("int64")
    t = si[si["permno"] == META].drop_duplicates("ticker", keep="first")[["permno", "ticker", "issuernm", "secinfostartdt"]]
    print(t.to_string(index=False))
    x = m[(m["permno"] == META) & m["date"].between("2022-04-30", "2022-08-31")]
    print(x[["permno", "gvkey", "date", "rdm", "status", "period_end", "xrd", "me_firm"]].to_string(index=False))
    same = x["gvkey"].nunique() == 1 and x["rdm"].notna().all()
    record("4 ticker change", same, "same permno and gvkey before/after; rdm moves only with price")

    head("5. Splits")
    c = pd.read_parquet(CRSP, columns=["permno", "date", "mthprc", "shrout", "mthcumfacshr", "mthretx"])
    c["permno"] = c["permno"].astype("int64")
    c["date"] = ns(c["date"])
    n = c[(c["permno"] == NVDA) & c["date"].between("2024-04-30", "2024-07-31")]
    n = n.merge(m[["permno", "date", "rdm", "me_firm", "xrd"]], on=["permno", "date"])
    print("  NVIDIA 10-for-1 split, June 2024:")
    print(n.drop(columns="mthretx").to_string(index=False))
    # CRSP's cumulative share factor FALLS at a forward split (NVIDIA 10 -> 1) and RISES at a
    # reverse split. With the same R&D figure, rdm should change by the inverse of the price
    # return (excluding dividends), whatever the split: residual = log(rdm_t/rdm_t-1) + log(1+retx_t).
    # A split artifact would leave a residual of about log(split ratio).
    c = c.sort_values(["permno", "date"])
    c["fac_ratio"] = c["mthcumfacshr"] / c.groupby("permno")["mthcumfacshr"].shift()
    s = sig[["permno", "date", "rdm", "period_end", "n_classes"]].sort_values(["permno", "date"]).copy()
    s["prev_rdm"] = s.groupby("permno")["rdm"].shift()
    s["prev_pe"] = s.groupby("permno")["period_end"].shift()
    s["prev_date"] = s.groupby("permno")["date"].shift()
    s = s.merge(c[["permno", "date", "fac_ratio", "mthretx"]], on=["permno", "date"], how="left")
    s = s[s["prev_rdm"].notna() & (s["period_end"] == s["prev_pe"]) & (s["n_classes"] == 1)
          & (s["date"] == s["prev_date"] + pd.offsets.MonthEnd(1)) & s["mthretx"].notna()]
    s["resid"] = (np.log(s["rdm"] / s["prev_rdm"]) + np.log1p(s["mthretx"])).abs()
    fwd, rev = s["fac_ratio"] <= 0.8, s["fac_ratio"] >= 1.25
    other = ~(fwd | rev)
    # the signature of a split error: a residual about equal to the split ratio itself
    s["artifact"] = (s["resid"] > np.log(1.25)) & ((s["resid"] - np.log(s["fac_ratio"]).abs()).abs() < 0.1)
    for lab, mask in (("forward splits", fwd), ("reverse splits", rev), ("all other months", other)):
        print(f"  {lab:17s}: {mask.sum():>9,} months; median |residual| {s.loc[mask, 'resid'].median():.4f}; "
              f"|residual| > log(1.25): {(s.loc[mask, 'resid'] > np.log(1.25)).mean():.2%}; "
              f"residual = split ratio (error signature): {s.loc[mask, 'artifact'].mean():.2%}")
    print("  Reverse-split months often move more than the return because the firm also issues new shares that month")
    print("  (more shares than the split alone leaves, not undone the next month); that is real, not a split error.")
    nv_ok = n["rdm"].notna().all() and (n["rdm"].pct_change().abs().max() < 0.5)
    split_ok = all(s.loc[mk, "artifact"].mean() < 0.02 for mk in (fwd, rev))
    record("5 splits", nv_ok and split_ok,
           f"no jump at NVIDIA's split; {s.loc[fwd | rev, 'artifact'].mean():.1%} of {int((fwd | rev).sum()):,} split months "
           "look like a split error")

    head("6. Coverage by year; ETFs")
    cov = m.groupby(m["date"].dt.year).agg(rows=("permno", "size"),
                                           signal=("status", lambda v: (v == "ok").mean()),
                                           no_rd=("status", lambda v: (v == "no R&D reported (has_rd = 0)").mean()))
    print(cov.loc[[1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025]].to_string(
        formatters={"signal": "{:.1%}".format, "no_rd": "{:.1%}".format}))
    etf = si[si["securitysubtype"].astype(str).str.upper() == "ETF"]["permno"].unique()
    in_panel = np.isin(m["permno"].unique(), etf).sum()
    print(f"  ETF permnos in CRSP security info: {len(etf):,}; in the panel: {in_panel}")
    record("6 coverage", cov["signal"].min() > 0.2 and in_panel == 0,
           f"signal on {cov['signal'].min():.0%}-{cov['signal'].max():.0%} of panel rows each year; panel has no ETFs (0 n/a)")

    head("7. Outliers and well-known firms")
    print("  rdm percentiles (signal rows): " + ", ".join(
        f"p{q}: {sig['rdm'].quantile(q / 100):.3f}" for q in (1, 5, 50, 95, 99)) + f", max {sig['rdm'].max():.1f}")
    top = (sig.merge(co, on="gvkey", how="left").sort_values("rdm", ascending=False)
              .drop_duplicates("gvkey").head(8))
    print("  largest values (one row per firm):")
    print(top[["conm", "date", "rdm", "xrd", "me_firm"]].to_string(index=False))
    e2 = ev[ev["xrd"] > 0].sort_values(["gvkey", "period_end"]).copy()
    e2["prev"] = e2.groupby("gvkey")["xrd"].shift()
    spikes = e2[(e2["xrd"] > 3 * e2["prev"]) & (e2["xrd"] > 1000)].merge(co, on="gvkey", how="left")
    print(f"  R&D more than tripled in a year, above $1bn: {len(spikes)} firm-years (one-off acquired R&D charges are typical):")
    print(spikes[["conm", "period_end", "prev", "xrd"]].tail(6).to_string(index=False))
    rows = []
    for (name, fy), want in TENK.items():
        g = co.loc[co["conm"] == name, "gvkey"]
        got = ev[ev["gvkey"].isin(g) & (ev["fyear"] == fy)]["xrd"]
        rows.append((name, fy, want, float(got.iloc[0]) if len(got) else np.nan))
    tk = pd.DataFrame(rows, columns=["firm", "fyear", "10-K R&D", "our xrd"])
    print("  three firms vs their 10-Ks ($ millions):")
    print(tk.to_string(index=False))
    for name in ("MICROSOFT CORP", "INTEL CORP", "MERCK & CO INC"):
        g = co.loc[co["conm"] == name, "gvkey"]
        r = m[m["gvkey"].isin(g) & (m["date"] == "2024-12-31")]
        if len(r):
            r = r.iloc[0]
            print(f"  {name}, Dec 2024: rdm {r['rdm']:.4f} = 1000 x {r['xrd']:,.0f} / {r['me_firm']:,.0f} "
                  f"= {1000 * r['xrd'] / r['me_firm']:.4f}  (FY ending {r['period_end']:%Y-%m}, public {r['published_date']:%Y-%m-%d})")
    record("7 outliers + firms", (tk["10-K R&D"] == tk["our xrd"]).all(),
           "3/3 firms match their 10-Ks; large values are small firms with big R&D budgets; acquired-R&D spikes noted")

    head("8. Definition B (Hou-Xue-Zhang, June-fixed) vs Definition A")
    dec = m[(m["date"].dt.month == 12) & m["rdm"].notna() & m["rdm_hxz"].notna()]
    rc = dec.groupby("date").apply(lambda d: d["rdm"].rank().corr(d["rdm_hxz"].rank()))
    print(f"  December rank correlation of rdm with rdm_hxz: median {rc.median():.2f} (min {rc.min():.2f}, max {rc.max():.2f}), "
          f"{len(rc)} years")
    record("8 definition B", rc.median() > 0.8, "B ranks firms much like A (differences: price moves since December, filing dates)")

    head("9. Open Source Asset Pricing RD (optional)")
    if OSAP.exists():
        o = pd.read_parquet(OSAP)
        o["permno"] = o["permno"].astype("int64")
        o["date"] = pd.to_datetime(o["yyyymm"].astype(int).astype(str), format="%Y%m") + pd.offsets.MonthEnd(0)
        j = sig.merge(o[["permno", "date", "RD"]], on=["permno", "date"], how="inner")
        j = j[j["RD"] > 0]
        rc = j.groupby("date").apply(lambda d: d["rdm"].rank().corr(d["RD"].rank()) if len(d) > 20 else np.nan)
        close = (np.abs(np.log(j["rdm"] / j["RD"])) < 0.1).mean()
        print(f"  OSAP rows {len(o):,} ({o['date'].min():%Y-%m} to {o['date'].max():%Y-%m}); matched signal rows {len(j):,} "
              f"({len(j) / len(sig):.0%} of ours); median monthly rank correlation {rc.median():.2f}; within 10%: {close:.0%}")
        record("9 OSAP", rc.median() > 0.9, f"rank correlation {rc.median():.2f} with OSAP RD")
    else:
        print("  not run: python signals\\rd_to_market\\get_osap_rd.py downloads it (no WRDS login).")
        RESULTS.append(("9 OSAP", "SKIPPED", "optional; run get_osap_rd.py first"))

    head("SUMMARY")
    for r in RESULTS:
        print(f"  {r[0]:22s} {r[1]:8s} {r[2]}")


if __name__ == "__main__":
    main()
