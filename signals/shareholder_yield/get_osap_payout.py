"""
get_osap_payout.py
==================
Helper for Step 9 (validate) of signals/shareholder_yield. Same pattern as
signals/net_operating_assets/get_osap_noa.py.

Downloads Open Source Asset Pricing's firm-level NetPayoutYield and PayoutYield
(Boudoukh, Michaely, Richardson & Roberts 2007; Chen & Zimmermann) so the
validation can compare them with our net_payout_yield and payout_yield.
No WRDS login needed.

How OSAP differs from ours (Step 2): market cap from 6 months earlier, every
annual report used 6 months after fiscal year-end, non-payers dropped from
PayoutYield and exact zeros from NetPayoutYield, financials and ceq <= 0 dropped.
So expect a high rank correlation where both exist, not identical values.

One-time install (inside the .venv; already there if you ran get_osap_noa.py):
    pip install openassetpricing
Run from the repo root:
    python signals\\shareholder_yield\\get_osap_payout.py

Saves data/shareholder_yield/osap_payout.parquet (permno, yyyymm, NetPayoutYield,
PayoutYield). Firm-level OSAP data stays in data/ and on the shared drive, not on
GitHub (reference/wrds_guide.md). Cite: Chen & Zimmermann (2022), Open Source
Cross-Sectional Asset Pricing, Critical Finance Review.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "shareholder_yield" / "osap_payout.parquet"
SIGNALS = ["NetPayoutYield", "PayoutYield"]


def main() -> None:
    try:
        import openassetpricing as oap
    except ImportError:
        raise SystemExit("openassetpricing is not installed: run  pip install openassetpricing  (inside the .venv).")
    print(f"Downloading {', '.join(SIGNALS)} from Open Source Asset Pricing ...")
    df = pd.DataFrame(oap.OpenAP().dl_signal("pandas", SIGNALS))
    df.columns = [str(c) for c in df.columns]
    need = {"permno", "yyyymm", *SIGNALS}
    if not need <= set(df.columns):
        raise SystemExit(f"Unexpected columns {list(df.columns)}; show this message to Claude.")
    df = df[["permno", "yyyymm"] + SIGNALS].dropna(how="all", subset=SIGNALS)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    print(f"Saved {OUT.relative_to(REPO)}: {len(df):,} rows, {df['permno'].nunique():,} permnos, "
          f"{int(df['yyyymm'].min())} to {int(df['yyyymm'].max())}")
    for s in SIGNALS:
        x = df[s].dropna()
        print(f"  {s}: {len(x):,} values; share < 0: {(x < 0).mean():.1%}; "
              f"median {x.median():.4f}; p1 {x.quantile(0.01):.4f}; p99 {x.quantile(0.99):.4f}")


if __name__ == "__main__":
    main()
