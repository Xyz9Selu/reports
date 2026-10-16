#!/usr/bin/env python3
"""Clip-sensitivity check: raw vs winsorized daily mean returns."""
import numpy as np
import pandas as pd

BASE = "/home/xyz/stock-scripts/panic_breadth"
raw = pd.read_csv(f"{BASE}/data/breadth_daily.csv", parse_dates=["trade_date"]).set_index("trade_date").sort_index()
clip = pd.read_csv(f"{BASE}/out/ew_clip.csv", parse_dates=["trade_date"]).set_index("trade_date").sort_index()
d = raw.join(clip[["raw", "c30", "c21"]], how="inner")
d = d[d["n"] > 100]

for col in ("raw", "c30", "c21"):
    lev = (1 + d[col] / 100).cumprod()
    yrs = (lev.index[-1] - lev.index[0]).days / 365.25
    cagr = lev.iloc[-1] ** (1 / yrs) - 1
    dd = (lev / lev.cummax() - 1).min()
    print(f"{col}: total {lev.iloc[-1]-1:+.0%} CAGR {cagr:+.2%} MaxDD {dd:.1%}")

print()
# where does the clipping matter most? top 10 days by |raw - c21| difference
d["diff"] = d["raw"] - d["c21"]
print("top 12 days by raw-c21 difference:")
print(d[["raw", "c30", "c21", "diff"]].reindex(d["diff"].abs().sort_values(ascending=False).head(12).index).to_string(float_format=lambda v: f"{v:.4f}"))

print()
# check: does clipping change the panic-day stats?
for thr in (0.15, 0.25):
    sub = d[d["c_dn5"] / d["n"] >= thr]
    for col in ("raw", "c21"):
        lv = (1 + d[col] / 100).cumprod()
        f5 = (lv.shift(-5) / lv - 1).loc[sub.index].dropna()
        f20 = (lv.shift(-20) / lv - 1).loc[sub.index].dropna()
        print(f"thr {thr} {col}: f5 {f5.mean()*100:+.2f}% f20 {f20.mean()*100:+.2f}% n={len(f5)}")
    print()
