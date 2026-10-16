#!/usr/bin/env python3
"""Deep dive #6b: extremes check, VW baselines, entries by year, worst paths."""
import numpy as np
import pandas as pd

BASE = "/home/xyz/stock-scripts/panic_breadth"
df = pd.read_csv(f"{BASE}/data/breadth_clean.csv", parse_dates=["trade_date"]).set_index("trade_date").sort_index()
df = df[df["n"] > 100].copy()
for c in ["dn5", "dn7", "dn95", "up5", "up95", "newlow", "low_dn5"]:
    df[f"{c}_share"] = df[f"c_{c}"] / df["n"]
df["ew"] = (1 + df["ew_ret"] / 100).cumprod()
df["vw"] = (1 + df["vw_ret"] / 100).cumprod()
for k in (5, 20):
    df[f"ew_f{k}"] = df["ew"].shift(-k) / df["ew"] - 1
    df[f"vw_f{k}"] = df["vw"].shift(-k) / df["vw"] - 1

wash = (df["dn5_share"].shift(1) >= 0.15).rolling(10, min_periods=1).max().fillna(False).astype(bool)
thrust = wash & (df["up95_share"] >= 0.03)
sub = df[thrust]

print("== extremes of signal returns ==")
for col, name in (("ew_f5", "f5"), ("ew_f20", "f20")):
    print(f"{name}: min {sub[col].min()*100:+.1f}% at {sub[col].idxmin().date()} | max {sub[col].max()*100:+.1f}% at {sub[col].idxmax().date()}")
print("worst 8 signals by f20:")
for d, r in sub.nsmallest(8, "ew_f20").iterrows():
    print(f"  {d.date()} f20 {r['ew_f20']*100:+.1f}% (f5 {r['ew_f5']*100:+.1f}%)")
print("best 5 signals by f20:")
for d, r in sub.nlargest(5, "ew_f20").iterrows():
    print(f"  {d.date()} f20 {r['ew_f20']*100:+.1f}%")
print()

print("== baselines (all-days mean) ==")
for lab, m in (("ALL", df.index == df.index), ("2020+", df.index >= "2020-01-01")):
    s = df[m]
    print(f"{lab}: EW f5 {s['ew_f5'].mean()*100:+.2f}% f20 {s['ew_f20'].mean()*100:+.2f}% | "
          f"VW f5 {s['vw_f5'].mean()*100:+.2f}% f20 {s['vw_f20'].mean()*100:+.2f}%")
print()

print("== non-overlap entries by year ==")


def entries_by_year(mask, k):
    m = mask.to_numpy()
    n = len(m)
    end = -1
    out = {}
    for i in range(n):
        if i > end and m[i] and i + k < n:
            y = df.index[i].year
            out[y] = out.get(y, 0) + 1
            end = i + k
    return out


print("k=5 :", entries_by_year(thrust, 5))
print("k=20:", entries_by_year(thrust, 20))
print()

print("== worst path mins (next 20td) ==")
ewv = df["ew"].to_numpy()
worst = []
for p in np.where(thrust.to_numpy())[0]:
    if p + 20 < len(ewv):
        path = ewv[p + 1:p + 21] / ewv[p] - 1
        worst.append((df.index[p], path.min()))
w = pd.Series(dict(worst)).sort_values()
print("worst 5:", [(str(k.date()), round(v * 100, 1)) for k, v in w.head(5).items()])
print()

print("== sanity: ew path around f5 min ==")
d = sub["ew_f5"].idxmin()
i = df.index.get_loc(d)
print(df.iloc[i - 1:i + 7][["ew_ret", "ew"]].to_string())
