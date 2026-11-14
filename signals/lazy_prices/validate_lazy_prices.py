"""
validate_lazy_prices.py
=======================
Step 9 (Validate) of prompts/data_acquisition.md for signals/lazy_prices.
Reads only files already in data/ (no WRDS, no password).

Checks (in the prompt's order)
  1. no duplicate permno + date
  2. match rate to the panel, and why rows miss
  3. published_date >= period_end, and the share `assumed`
  4. one ticker change traced (Facebook -> Meta, 2022)
  5. one split with no jump (NVIDIA 10-for-1, June 2024)
  6. coverage vs the panel; ETFs marked n/a, not dropped
  7. outliers; spot-check 3 well-known firms (Apple, Microsoft, Boeing);
     size tilt of the bottom fifth in the format-change years (flagged 2010-2014)

Inputs
  data/lazy_prices/lazy_prices_events.parquet, lazy_prices_monthly.parquet,
  security_info.parquet; data/crsp_monthly_ratios_clean.parquet
Output
  data/lazy_prices/validate_log.txt (also printed)

Run from the repo root, with the .venv active:
    python signals\\lazy_prices\\validate_lazy_prices.py
Takes under a minute.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
LP = DATA / "lazy_prices"
LOG = LP / "validate_log.txt"
NS = "datetime64[ns]"

DATA_END = pd.Timestamp("2024-12-31")     # bow_cossim ends with 2024 filings
PHASE_IN_END = pd.Timestamp("1997-12-31")  # EDGAR phase-in + first year-on-year comparisons
TICKER_CASE = ("FB", "META")
SPLIT_CASE = ("NVDA", "2024-06")          # 10-for-1, effective June 2024
FIRMS = ("AAPL", "MSFT", "BA")

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


def verdict(check: str, ok: bool, note: str) -> None:
    status = "PASS" if ok else "CHECK"
    results.append((check, status, note))
    print(f"  -> {status}: {note}")


def permno_for(info: pd.DataFrame, ticker: str, on: str | None = None) -> int | None:
    r = info[info["ticker"] == ticker]
    if on is not None:
        d = pd.Timestamp(on)
        r = r[(r["secinfostartdt"] <= d) & (d <= r["secinfoenddt"])]
    return int(r.sort_values("secinfoenddt")["permno"].iloc[-1]) if len(r) else None


def size_tilt(ev: pd.DataFrame, panel: pd.DataFrame, col: str) -> pd.Series:
    """By published year: share of the bottom fifth (lowest `col`) that are the largest
    fifth of firms by market value at the month-end before publication (20% = no tilt)."""
    e = ev[["permno", "published_date", col]].dropna().copy()
    e["date"] = (e["published_date"] - pd.offsets.MonthEnd(1)).astype(NS)
    e = e.merge(panel[["permno", "date", "me"]], on=["permno", "date"], how="inner").dropna(subset=["me"])
    e["year"] = e["published_date"].dt.year
    e["largest"] = e.groupby("year")["me"].rank(pct=True) > 0.8
    e["bottom"] = e.groupby("year")[col].rank(pct=True, method="first") <= 0.2
    return e[e["bottom"]].groupby("year")["largest"].mean()


def info_at(rows: pd.DataFrame, info: pd.DataFrame) -> pd.DataFrame:
    """Attach the security-info record in force on each row's date."""
    cols = ["permno", "secinfostartdt", "secinfoenddt", "sharetype", "securitysubtype", "usincflg"]
    i = info[cols].dropna(subset=["secinfostartdt"]).sort_values("secinfostartdt")
    r = rows.reset_index().sort_values("date")
    m = pd.merge_asof(r, i, left_on="date", right_on="secinfostartdt", by="permno", direction="backward")
    outside = m["secinfoenddt"].notna() & (m["date"] > m["secinfoenddt"] + pd.offsets.MonthEnd(0))
    m.loc[outside, ["sharetype", "securitysubtype", "usincflg"]] = pd.NA
    return m.set_index("index").sort_index()


# ----------------------------------------------------------------------------
def main() -> None:
    ev = pd.read_parquet(LP / "lazy_prices_events.parquet")
    mo = pd.read_parquet(LP / "lazy_prices_monthly.parquet")
    info = pd.read_parquet(LP / "security_info.parquet")
    panel = pd.read_parquet(DATA / "crsp_monthly_ratios_clean.parquet",
                            columns=["permno", "date", "gvkey", "prc", "shrout", "me"])
    for df, cols in ((ev, ["period_end", "published_date", "fdate", "secadate"]),
                     (mo, ["date", "period_end", "published_date"]),
                     (info, ["secinfostartdt", "secinfoenddt"]), (panel, ["date"])):
        for c in cols:
            df[c] = df[c].astype(NS)
    panel["permno"] = panel["permno"].astype("int64")
    panel["me"] = pd.to_numeric(panel["me"], errors="coerce").astype("float64")
    mo["permno"] = mo["permno"].astype("int64")

    with open(LOG, "w", encoding="utf-8") as f:
        sys.stdout = Tee(sys.__stdout__, f)
        try:
            print(f"lazy_prices Step 9 validation, {pd.Timestamp.now():%Y-%m-%d %H:%M}")

            # 1 -------------------------------------------------------------
            section("1. No duplicate permno + date")
            d_mo = mo.duplicated(["permno", "date"]).sum()
            d_ev = ev.duplicated(["permno", "published_date"]).sum()
            print(f"  monthly file duplicates (permno, date): {d_mo}; event file duplicates (permno, published_date): {d_ev}")
            verdict("1 duplicates", d_mo == 0 and d_ev == 0, "no duplicates in either file")

            # 2 -------------------------------------------------------------
            section("2. Match rate to the panel, and why rows miss")
            keys_mo = pd.MultiIndex.from_frame(mo[["permno", "date"]])
            keys_pa = pd.MultiIndex.from_frame(panel[["permno", "date"]])
            same = len(mo) == len(panel) and keys_mo.isin(keys_pa).all()
            print(f"  monthly rows {len(mo):,} vs panel rows {len(panel):,}; every monthly row is a panel row: {same}")
            st = mo[mo["applies"] == "stock"].copy()
            has = st["filing_sim"].notna()
            core = st["date"].between(PHASE_IN_END + pd.Timedelta(days=1), DATA_END)
            print(f"  stock rows with a value, 1998-2024: {has[core].mean():.1%} "
                  f"({has.mean():.1%} of all rows; the panel starts in 1980, before EDGAR)")

            miss = st[~has].copy()
            miss = miss.join(info_at(miss[["permno", "date"]], info)[["sharetype", "securitysubtype", "usincflg"]])
            first = ev.groupby("permno")["published_date"].min()
            miss["first_pub"] = miss["permno"].map(first)
            reason = pd.Series("value older than 15 months (10-K late, missing or not comparable)", index=miss.index)
            reason[miss["first_pub"].notna() & (miss["date"] < miss["first_pub"])] = \
                "before the stock's first value (new listing: needs two comparable 10-Ks)"
            reason[miss["first_pub"].isna()] = "stock never gets a value (no 10-K link or never two comparable 10-Ks)"
            not_common = miss["sharetype"].notna() & ((miss["sharetype"] != "NS") | (miss["securitysubtype"] != "COM"))
            reason[not_common] = "not ordinary common stock (ADR, unit, trust share ...)"
            reason[miss["usincflg"] == "N"] = "foreign company (files 20-F / 40-F, not 10-K)"
            reason[miss["date"] <= PHASE_IN_END] = "before 1998: EDGAR starts 1993-96, and a 10-K a year earlier is needed"
            reason[miss["date"] > DATA_END] = "2025: data ends with 2024 filings"
            miss["reason"] = reason
            order = ["2025: data ends with 2024 filings",
                     "before 1998: EDGAR starts 1993-96, and a 10-K a year earlier is needed",
                     "foreign company (files 20-F / 40-F, not 10-K)",
                     "not ordinary common stock (ADR, unit, trust share ...)",
                     "stock never gets a value (no 10-K link or never two comparable 10-Ks)",
                     "before the stock's first value (new listing: needs two comparable 10-Ks)",
                     "value older than 15 months (10-K late, missing or not comparable)"]
            tab = (miss["reason"].value_counts().reindex(order).dropna().astype("int64")
                   .rename_axis("why the value is missing").reset_index(name="stock rows"))
            tab["share of missing"] = (tab["stock rows"] / len(miss)).map("{:.1%}".format)
            tab_core = miss.loc[miss["date"].between(PHASE_IN_END + pd.Timedelta(days=1), DATA_END), "reason"]
            tab["share, 1998-2024"] = tab["why the value is missing"].map(
                (tab_core.value_counts() / len(tab_core)).map("{:.1%}".format)).fillna("-")
            print(f"\n  {len(miss):,} stock rows have no value. Each gets the first reason that applies, in this order:")
            show(tab)
            nev = miss["reason"].str.startswith("stock never")
            pg = panel.set_index(["permno", "date"])["gvkey"]
            no_gv = pg.reindex(pd.MultiIndex.from_frame(miss.loc[nev, ["permno", "date"]])).isna().mean()
            print(f"  of the 'never gets a value' rows, {no_gv:.0%} have no gvkey in the panel either")
            verdict("2 match rate", same, "monthly file has exactly the panel's rows; every missing value has a reason")

            # 3 -------------------------------------------------------------
            section("3. published_date >= period_end, and the share assumed")
            bad = (ev["published_date"] < ev["period_end"]).sum()
            pe_na = ev["period_end"].isna().sum()
            assumed = (ev["date_source"] == "assumed").mean()
            lag = (ev["published_date"] - ev["period_end"]).dt.days
            print(f"  events: {len(ev):,}; published_date before period_end: {bad}; period_end missing: {pe_na}; "
                  f"assumed: {assumed:.0%}")
            print(f"  days from fiscal year end to published_date: min {lag.min():.0f}, 1st pct {lag.quantile(.01):.0f}, "
                  f"median {lag.median():.0f}, 99th pct {lag.quantile(.99):.0f}, max {lag.max():.0f}")
            gap = (ev["published_date"] - ev["fdate"]).dt.days
            print(f"  published_date minus EDGAR filing date: min {gap.min()}, max {gap.max()} days "
                  f"(expect about -3 to +7: after-hours filings dated the next day; weekends and holidays)")
            if "published_basis" in ev:
                print("  basis of published_date:")
                show(ev["published_basis"].value_counts().rename_axis("basis").reset_index(name="events"), indent=6)
            late = ev[lag > 365].assign(lag_days=lag)
            print(f"  events more than a year after period_end: {len(late)} (likely WRDS rdate typos; "
                  "the signal's timing uses the filing date, not rdate). Largest:")
            show(late.nlargest(5, "lag_days")[["permno", "form", "period_end", "fdate", "published_date", "lag_days"]])
            t = ev["secatime"].astype("string").str[:8]
            ex = ev[t.notna() & (t > "16:00:00") & (ev["fdate"].dt.day_of_week == 4)].tail(3)
            print("  after-close examples on a Friday (should move to the next Monday or later):")
            show(ex[["permno", "form", "secadate", "secatime", "published_date"]].assign(
                published_weekday=ex["published_date"].dt.day_name()))
            ok3 = bad == 0 and assumed == 0 and gap.between(-4, 8).all()
            verdict("3 dates", ok3, f"0 events before period_end; 0% assumed; published within -4..+8 days of the "
                    f"filing date; {pe_na} events lack a period_end, {len(late)} have a doubtful one")

            # 4 -------------------------------------------------------------
            section(f"4. One ticker change traced: {TICKER_CASE[0]} -> {TICKER_CASE[1]}")
            p = permno_for(info, TICKER_CASE[1])
            hist = info[info["permno"] == p].sort_values("secinfostartdt")
            print(f"  permno {p}, ticker history (CRSP):")
            show(hist.drop_duplicates(["ticker", "issuernm"])[["ticker", "issuernm", "secinfostartdt", "secinfoenddt"]])
            reuse = info[(info["ticker"] == TICKER_CASE[0]) & (info["permno"] != p)]
            if len(reuse):
                r = reuse.sort_values("secinfostartdt").iloc[-1]
                print(f"  note: ticker {TICKER_CASE[0]} was later reused by permno {r['permno']} "
                      f"({r['issuernm']}, from {r['secinfostartdt']:%Y-%m-%d}) -> keying on tickers would mix firms")
            win = mo[(mo["permno"] == p) & mo["date"].between("2021-11-30", "2023-03-31")]
            print("  monthly file around the change (value continues under the same permno):")
            show(win[["date", "gvkey", "filing_sim", "published_date", "period_end"]])
            ok4 = win["filing_sim"].notna().all() and win["gvkey"].nunique() == 1
            verdict("4 ticker change", ok4, f"permno {p} keeps its gvkey and values through the rename")

            # 5 -------------------------------------------------------------
            section(f"5. One split with no jump: {SPLIT_CASE[0]} {SPLIT_CASE[1]}")
            p = permno_for(info, SPLIT_CASE[0], on=SPLIT_CASE[1] + "-15")
            s = panel[(panel["permno"] == p)][["date", "prc", "shrout", "me"]].merge(
                mo[mo["permno"] == p][["date", "filing_sim", "published_date"]], on="date")
            m0 = pd.Period(SPLIT_CASE[1], "M")
            s = s[s["date"].dt.to_period("M").between(m0 - 3, m0 + 3)]
            show(s.assign(prc=s["prc"].round(2), me=(s["me"] / 1e6).round(1)).rename(columns={"me": "me_$bn"}))
            before = s[s["date"].dt.to_period("M") == m0 - 1].iloc[0]
            after = s[s["date"].dt.to_period("M") == m0].iloc[0]
            px = abs(after["prc"]) / abs(before["prc"])
            ok5 = (px < 0.2) and (after["filing_sim"] == before["filing_sim"])
            verdict("5 split", ok5, f"price per share fell to {px:.2f}x (the split), filing_sim unchanged "
                    f"({before['filing_sim']:.4f} -> {after['filing_sim']:.4f}); text-only signal needs no adjustment")

            # 6 -------------------------------------------------------------
            section("6. Coverage vs the panel; ETFs marked n/a, not dropped")
            cov = st.groupby(st["date"].dt.year)["filing_sim"].apply(lambda x: x.notna().mean())
            print("  share of the panel's stock rows with a value, by year:")
            print("    " + "  ".join(f"{y}: {v:.0%}" for y, v in cov.items() if y >= 1995))
            etf_permnos = set(info.loc[info["securitysubtype"] == "ETF", "permno"])
            in_panel = panel["permno"].isin(etf_permnos)
            na_rows = (mo["applies"] == "n/a (ETF)").sum()
            print(f"  ETF permnos in CRSP: {len(etf_permnos):,}; panel rows that are ETF permnos: {in_panel.sum():,}; "
                  f"rows marked n/a (ETF): {na_rows:,}")
            ok6 = len(mo) == len(panel) and na_rows == in_panel.sum()
            verdict("6 coverage/ETFs", ok6, "no panel rows dropped; the panel holds no ETFs, so 0 rows are n/a")

            # 7 -------------------------------------------------------------
            section("7. Outliers; spot-check 3 well-known firms")
            q = ev["filing_sim"].quantile([0, .001, .01, .05, .5, .95, 1]).round(4)
            print("  filing_sim percentiles: " + ", ".join(f"{k:g}: {v}" for k, v in q.items()))
            print(f"  outside [0, 1]: {((ev['filing_sim'] < 0) | (ev['filing_sim'] > 1)).sum()}; "
                  f"below 0.5: {(ev['filing_sim'] < 0.5).sum():,}; word count below 1,000: {(ev['wcnt'] < 1000).sum():,}")
            names = info.sort_values("secinfoenddt").drop_duplicates("permno", keep="last").set_index("permno")["issuernm"]
            low = ev.nsmallest(10, "filing_sim").assign(name=lambda d: d["permno"].map(names))
            print("  10 lowest values:")
            show(low[["permno", "name", "form", "published_date", "filing_sim", "wcnt", "form_prev", "months_apart"]])
            for tk in FIRMS:
                p = permno_for(info, tk)
                e = ev[ev["permno"] == p].sort_values("published_date").tail(8)
                lowest = ev.loc[ev["permno"] == p].nsmallest(1, "filing_sim")
                print(f"\n  {tk} (permno {p}, {names.get(p, '')}): last 8 events; lowest ever "
                      f"{lowest['filing_sim'].iloc[0]:.3f} published {lowest['published_date'].iloc[0]:%Y-%m-%d}")
                show(e[["form", "period_end", "published_date", "secatime", "filing_sim", "months_apart"]])
            measure = ev["measure"].iloc[0] if "measure" in ev else "cosine"
            cols = [c for c in ("cosine", "cosine_eng") if c in ev and ev[c].notna().any()]
            tilt = pd.DataFrame({c: size_tilt(ev, panel, c) for c in cols})
            print(f"\n  measure used for filing_sim: {measure}. Share of each published year's bottom fifth "
                  "that are the largest fifth of firms (20% = no tilt):")
            tt = tilt.loc[(tilt.index >= 2006) & (tilt.index <= 2016)]
            show(tt.apply(lambda c: c.map("{:.0%}".format)).rename_axis("year").reset_index())
            used = size_tilt(ev, panel, "filing_sim").reindex([2010, 2011, 2012])
            flag_cols = [c for c in mo.columns if c.startswith("format_change_")]
            flagged = bool(flag_cols)
            ok7 = ((ev["filing_sim"] < 0) | (ev["filing_sim"] > 1)).sum() == 0 and (used <= 0.30).all()
            verdict("7 outliers/firms/tilt", ok7,
                    f"values within [0, 1]; filing_sim = {measure}; largest-fifth share of the bottom fifth in "
                    f"2010-2012 at most {used.max():.0%}" + ("" if ok7 else
                    (f" -> handled: {flag_cols[0]} flags {int(mo[flag_cols[0]].sum()):,} monthly rows"
                     if flagged else " -> needs a decision")))

            section("Summary")
            show(pd.DataFrame(results, columns=["check", "result", "note"]), indent=2)
        finally:
            sys.stdout = sys.__stdout__
    print(f"\nSaved: {LOG.relative_to(REPO)}")


if __name__ == "__main__":
    main()
