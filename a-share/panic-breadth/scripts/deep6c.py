#!/usr/bin/env python3
"""Deep dive #6c: non-overlap trade-level stats + no-wash thrust era check."""
import numpy as np
import pandas as pd

BASE = "/home/xyz/stock-scripts/panic_breadth"
df = pd.read_csv(f"{BASE}/data/breadth_clean.csv", parse_dates=["trade_date"]).set_index("trade_date").sort_index()
df = df[df["n"] > 100].copy()
for c in ["dn5", "dn7", "dn95", "up5", "up95", "newlow", "low_dn5"]:
    df[f"{c}_share"] = df[f"c_{c}"] / df["n"]
df["ew"] = (1 + df["ew_ret"] / 100).cumprod()
for k in (5, 20):
    df[f"ew_f{k}"] = df["ew"].shift(-k) / df["ew"] - 1

wash = (df["dn5_share"].shift(1) >= 0.15).rolling(10, min_periods=1).max().fillna(False).astype(bool)
thrust = wash & (df["up95_share"] >= 0.03)
no_wash = (~wash) & (df["up95_share"] >= 0.03)


def nonoverlap(mask, k, start=None):
    m = mask.copy()
    if start is not None:
        m = m & (df.index >= start)
    idx = np.where(m.to_numpy())[0]
    sel = []
    end = -1
    for i in idx:
        if i > end and i + k < len(df):
            sel.append(i)
            end = i + k
    return df.iloc[sel]


print("== non-overlap trades, k=5 (entry close, exit close t+5) ==")
for lab, start in (("ALL", None), ("2020+", "2020-01-01")):
    sub = nonoverlap(thrust, 5, start)
    r5, r20 = sub["ew_f5"].dropna(), sub["ew_f20"].dropna()
    print(f"{lab}: n {len(sub)} | f5 mean {r5.mean()*100:+.2f}% med {r5.median()*100:+.2f}% hit {(r5>0).mean():.0%} | "
          f"f20 mean {r20.mean()*100:+.2f}% med {r20.median()*100:+.2f}% hit {(r20>0).mean():.0%}")
    print("   f5 quartiles:", f"p25 {r5.quantile(.25)*100:+.2f}% p75 {r5.quantile(.75)*100:+.2f}% min {r5.min()*100:+.1f}% max {r5.max()*100:+.1f}%")
print()

print("== non-overlap trades, k=20 ==")
for lab, start in (("ALL", None), ("2020+", "2020-01-01")):
    sub = nonoverlap(thrust, 20, start)
    r20 = sub["ew_f20"].dropna()
    print(f"{lab}: n {len(sub)} | f20 mean {r20.mean()*100:+.2f}% med {r20.median()*100:+.2f}% hit {(r20>0).mean():.0%}")
print()

print("== no-wash thrust by era (robustness of 'not panic-specific') ==")
for a, b in (("2005", "2009"), ("2010", "2014"), ("2015", "2019"), ("2020", "2026")):
    s = df.loc[f"{a}-01-01":f"{b}-12-31"]
    sub = s[no_wash.reindex(s.index).fillna(False)]
    if len(sub) == 0:
        print(f"{a}-{b}: n 0")
        continue
    f5 = sub["ew_f5"].dropna()
    print(f"{a}-{b}: n {len(sub):3d} f5 {f5.mean()*100:+.2f}% hit {(f5>0).mean():.0%}")
print()

print("== consistency: wash&thrust by era, f5 (for reference) ==")
for a, b in (("2005", "2009"), ("2010", "2014"), ("2015", "2019"), ("2020", "2026")):
    s = df.loc[f"{a}-01-01":f"{b}-12-31"]
    sub = s[thrust.reindex(s.index).fillna(False)]
    f5 = sub["ew_f5"].dropna()
    print(f"{a}-{b}: n {len(sub):3d} f5 {f5.mean()*100:+.2f}% hit {(f5>0).mean():.0%}")
