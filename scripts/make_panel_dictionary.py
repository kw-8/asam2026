"""Generate reference/panel_dictionary.md from the panel parquet (metadata only, no data rows)."""
import sys
import pandas as pd

path = sys.argv[1] if len(sys.argv) > 1 else "data/crsp_monthly_ratios_clean.parquet"
df = pd.read_parquet(path)
lines = [
    "# Panel data dictionary",
    "",
    f"Generated from `{path.split('/')[-1]}` by `scripts/make_panel_dictionary.py`. Metadata only.",
    "",
    f"- Rows: {len(df):,} | permnos: {df.permno.nunique():,} | dates: {df.date.min():%Y-%m} to {df.date.max():%Y-%m}",
    f"- Firms per month: {df.groupby('date').permno.nunique().min():,} to {df.groupby('date').permno.nunique().max():,}",
    "- Keys: `permno` + `date` (month-end). `shrout` in thousands; `me` = prc x shrout (thousands of $).",
    "- Accounting ratios: assumed on time (change ~2 months after quarter end).",
    "",
    "| column | dtype | null % | min | median | max |",
    "|---|---|---|---|---|---|",
]
for c in df.columns:
    s = df[c]
    if pd.api.types.is_numeric_dtype(s):
        q = s.quantile([0, 0.5, 1])
        stats = [f"{v:.4g}" for v in q]
    elif pd.api.types.is_datetime64_any_dtype(s):
        stats = [f"{s.min():%Y-%m-%d}", "", f"{s.max():%Y-%m-%d}"]
    else:
        stats = ["", f"{s.nunique():,} unique", ""]
    lines.append(f"| {c} | {s.dtype} | {s.isna().mean()*100:.1f} | " + " | ".join(stats) + " |")
open("reference/panel_dictionary.md", "w").write("\n".join(lines) + "\n")
print("wrote reference/panel_dictionary.md")
