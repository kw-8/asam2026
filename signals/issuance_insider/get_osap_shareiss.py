"""
get_osap_shareiss.py
====================
Optional helper for Step 9, check 10 (signals/issuance_insider, net_issuance).
Downloads Open Source Asset Pricing's firm-level ShareIss1Y (Pontiff & Woodgate
share issuance, Chen & Zimmermann) so validate_net_issuance.py can compare it
with our net_issuance_skip6. No WRDS login needed for this signal.

One-time install (inside the .venv):
    pip install openassetpricing
Run from the repo root:
    python signals\\issuance_insider\\get_osap_shareiss.py

Saves data/issuance_insider/osap_ShareIss1Y.parquet (permno, yyyymm, ShareIss1Y).
Firm-level OSAP data stays in data/ and on the shared drive, not on GitHub
(reference/wrds_guide.md section 8). Cite: Chen & Zimmermann (2022), Open Source
Cross-Sectional Asset Pricing, Critical Finance Review.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "issuance_insider" / "osap_ShareIss1Y.parquet"


def main() -> None:
    try:
        import openassetpricing as oap
    except ImportError:
        raise SystemExit("openassetpricing is not installed: run  pip install openassetpricing  (inside the .venv).")
    print("Downloading ShareIss1Y from Open Source Asset Pricing ...")
    openap = oap.OpenAP()
    df = openap.dl_signal("pandas", ["ShareIss1Y"])
    df = pd.DataFrame(df)
    df.columns = [str(c) for c in df.columns]
    need = {"permno", "yyyymm", "ShareIss1Y"}
    if not need <= set(df.columns):
        raise SystemExit(f"Unexpected columns {list(df.columns)}; show this message to Claude.")
    df = df[["permno", "yyyymm", "ShareIss1Y"]].dropna()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    print(f"Saved {OUT.relative_to(REPO)}: {len(df):,} rows, {df['permno'].nunique():,} permnos, "
          f"{int(df['yyyymm'].min())} to {int(df['yyyymm'].max())}")
    print("Next: python signals\\issuance_insider\\validate_net_issuance.py")


if __name__ == "__main__":
    main()
