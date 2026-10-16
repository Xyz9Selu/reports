#!/usr/bin/env python3
"""Deep dive #7: strategy diagnostics for the washout+thrust signal (fixed).
- path risk (5d / 20d) for k=5 non-overlap entries (stop calibration)
- recovery conditional on path dips; extension value; delayed entry; cumulative products
"""
import numpy as np
import pandas as pd

BASE = "/home/xyz/stock-scripts/panic_breadth"
df = pd.read_csv(f"{BASE}/data/breadth_clean.csv", parse_dates=["trade_date"]).set_index("trade_date").sort_index()
df = df[df["n"] > 100].copy()
for c in ["dn5", "dn7", "dn95", "up5", "up95", "newlow", "low_dn5"]:
    df[f"{c}_share"] = df[f"c_{c}"] / df["n"]
df["ew"] = (1 + df["ew_ret"] / 100).cumprod()
ewv = df["ew"].to_numpy()
dates = df.index

wash = (df["dn5_share"].shift(1) >= 0.15).rolling(10, min_periods=1).max().fillna(False).astype(bool)
thrust = wash & (df["up95_share"] >= 0.03)


def nonoverlap_pos(mask, k):
    m = mask.to_numpy()
    n = len(m)
    sel, end = [], -1
    for i in range(n):
        if i > end and m[i] and i + k < n:
            sel.append(i)
            end = i + k
    return sel


def stats(r, label=""):
    r = pd.Series([x for x in r if x is not None and not np.isnan(x)])
    print(f"  {label}: n {len(r)} | mean {r.mean()*100:+.2f}% med {r.median()*100:+.2f}% hit {(r>0).mean():.0%} "
          f"| p10 {r.quantile(.10)*100:+.2f}% p25 {r.quantile(.25)*100:+.2f}% min {r.min()*100:+.1f}%")


pos = nonoverlap_pos(thrust, 5)
print(f"k=5 non-overlap entries: {len(pos)} | last: {dates[pos[-1]].date()}")
print(f"EW index growth over sample: {ewv[-1]/ewv[0]:.2f}x\n")

for lab, start in (("ALL", None), ("2020+", "2020-01-01")):
    p2 = [p for p in pos if (start is None or dates[p] >= pd.Timestamp(start))]
    print(f"== {lab} (n {len(p2)}) ==")
    r5 = [ewv[p+5]/ewv[p]-1 for p in p2]
    r20 = [ewv[p+20]/ewv[p]-1 for p in p2 if p+20 < len(ewv)]
    stats(r5, "f5 ")
    stats(r20, "f20")
    pm5 = pd.Series([np.min(ewv[p+1:p+6]/ewv[p]-1) for p in p2])
    pm20 = pd.Series([np.min(ewv[p+1:p+21]/ewv[p]-1) for p in p2 if p+20 < len(ewv)])
    print(f"  path5 : med {pm5.median()*100:+.2f}% p10 {pm5.quantile(.1)*100:+.2f}% min {pm5.min()*100:+.1f}%"
          f" | < -3% {(pm5<-0.03).mean():.0%} < -5% {(pm5<-0.05).mean():.0%} < -8% {(pm5<-0.08).mean():.0%} < -10% {(pm5<-0.10).mean():.0%}")
    print(f"  path20: med {pm20.median()*100:+.2f}% p10 {pm20.quantile(.1)*100:+.2f}% min {pm20.min()*100:+.1f}%"
          f" | < -5% {(pm20<-0.05).mean():.0%} < -8% {(pm20<-0.08).mean():.0%} < -10% {(pm20<-0.10).mean():.0%} < -15% {(pm20<-0.15).mean():.0%}")
    sub5 = [p for p in p2 if np.min(ewv[p+1:p+6]/ewv[p]-1) < -0.05]
    stats([ewv[p+5]/ewv[p]-1 for p in sub5], "f5 | path5 dipped <-5%")
    sub20 = [p for p in p2 if p+20 < len(ewv) and np.min(ewv[p+1:p+21]/ewv[p]-1) < -0.10]
    stats([ewv[p+20]/ewv[p]-1 for p in sub20], "f20 | path20 dipped <-10%")
    ext = [ewv[p+20]/ewv[p+5]-1 for p in p2 if p+20 < len(ewv)]
    stats(ext, "day5->day20 extra")
    d5 = [ewv[p+6]/ewv[p+1]-1 for p in p2 if p+6 < len(ewv)]
    stats(d5, "delayed entry t+1 close, 5d")
    prod = float(np.prod([ewv[p+5]/ewv[p]-0.002 for p in p2]))
    print(f"  cumulative net product (k=5, 0.2% cost): {prod:.2f}x")
    print()

s = pd.Series([ewv[p+5]/ewv[p]-1 for p in pos], index=[dates[p] for p in pos])
runs, cur = [], []
for d, v in s.items():
    if v < 0:
        cur.append((d, v))
    elif cur:
        runs.append(cur)
        cur = []
if cur:
    runs.append(cur)
runs.sort(key=lambda r: sum(x[1] for x in r))
print("worst losing runs (consecutive f5<0):")
for r in runs[:3]:
    print(f"  {r[0][0].date()}..{r[-1][0].date()} n={len(r)} cum {sum(x[1] for x in r)*100:+.1f}%")

p2 = [p for p in pos if dates[p] >= pd.Timestamp("2020-01-01")]
w = sorted(p2, key=lambda p: ewv[p+5]/ewv[p]-1)[:5]
print("\n2020+ worst 5 by f5:", [(str(dates[p].date()), f"{(ewv[p+5]/ewv[p]-1)*100:+.1f}%") for p in w])
w2 = sorted([p for p in p2 if p+20 < len(ewv)], key=lambda p: ewv[p+20]/ewv[p]-1)[:5]
print("2020+ worst 5 by f20:", [(str(dates[p].date()), f"{(ewv[p+20]/ewv[p]-1)*100:+.1f}%") for p in w2])
