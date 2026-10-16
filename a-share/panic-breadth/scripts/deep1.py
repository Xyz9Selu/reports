#!/usr/bin/env python3
"""Deep dive #1: regime dependence, euphoria side, drawdown splits."""
import numpy as np
import pandas as pd

BASE = "/home/xyz/stock-scripts/panic_breadth"
df = pd.read_csv(f"{BASE}/data/breadth_clean.csv", parse_dates=["trade_date"]).set_index("trade_date").sort_index()
df = df[df["n"] > 100].copy()
for c in ["dn5", "dn7", "dn95", "up5", "up95", "newlow", "low_dn5"]:
    df[f"{c}_share"] = df[f"c_{c}"] / df["n"]
df["ew"] = (1 + df["ew_ret"] / 100).cumprod()
df["vw"] = (1 + df["vw_ret"] / 100).cumprod()
for k in (1, 3, 5, 10, 20):
    df[f"ew_f{k}"] = df["ew"].shift(-k) / df["ew"] - 1
    df[f"vw_f{k}"] = df["vw"].shift(-k) / df["vw"] - 1

df["ma200"] = df["ew"].rolling(200).mean()
df["above200"] = df["ew"] >= df["ma200"]
df["dd250"] = df["ew"] / df["ew"].rolling(250, min_periods=100).max() - 1

eras = [("2005-2009", "2005-01-01", "2009-12-31"), ("2010-2014", "2010-01-01", "2014-12-31"),
        ("2015-2019", "2015-01-01", "2019-12-31"), ("2020-2026", "2020-01-01", "2026-12-31")]


def fmt(x):
    return " nan " if (x is None or (isinstance(x, float) and np.isnan(x))) else f"{x*100:+.2f}%"


def tstat(x):
    x = np.asarray(pd.Series(x).dropna(), dtype=float)
    return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) >= 2 else np.nan


print("=== [1] euphoria up95>=0.05 by era (EW f5/f20; base = era baseline) ===")
for name, a, b in eras:
    seg = df.loc[a:b]
    sub = seg[seg["up95_share"] >= 0.05]
    if len(sub) == 0:
        print(f"{name}: no days")
        continue
    print(f"{name}: n {len(sub):3d} | EW f5 {fmt(sub['ew_f5'].mean())} (base {fmt(seg['ew_f5'].mean())})  "
          f"f20 {fmt(sub['ew_f20'].mean())} (base {fmt(seg['ew_f20'].mean())})  hit5 {(sub['ew_f5']>0).mean():.0%}")
print()

print("=== [1b] euphoria up95>=0.05 by era (cap-wt f5/f20) ===")
for name, a, b in eras:
    seg = df.loc[a:b]
    sub = seg[seg["up95_share"] >= 0.05]
    if len(sub) == 0:
        continue
    print(f"{name}: n {len(sub):3d} | VW f5 {fmt(sub['vw_f5'].mean())} (base {fmt(seg['vw_f5'].mean())})  "
          f"f20 {fmt(sub['vw_f20'].mean())} (base {fmt(seg['vw_f20'].mean())})")
print()

print("=== [2] panic bands by era (EW f5/f20) ===")
bands = [(0.10, 0.15), (0.15, 0.25), (0.25, 0.50), (0.50, 1.01)]
for name, a, b in eras:
    seg = df.loc[a:b]
    print(f"-- {name} (base f5 {fmt(seg['ew_f5'].mean())}) --")
    for lo, hi in bands:
        sub = seg[(seg["dn5_share"] >= lo) & (seg["dn5_share"] < hi)]
        if len(sub) == 0:
            continue
        print(f"  dn5 [{lo:.2f},{hi:.2f}): n {len(sub):3d} f5 {fmt(sub['ew_f5'].mean())} f20 {fmt(sub['ew_f20'].mean())} "
              f"hit5 {(sub['ew_f5']>0).mean():.0%}")
print()

print("=== [3] dn5_share deciles -> EW f5/f20 (full sample) ===")
q = pd.qcut(df["dn5_share"], 10, labels=False, duplicates="drop")
g = df.groupby(q).agg(lo=("dn5_share", "min"), hi=("dn5_share", "max"), n=("ew_f5", "size"),
                      f5=("ew_f5", "mean"), f20=("ew_f20", "mean"), hit5=("ew_f5", lambda s: (s > 0).mean()))
for idx, r in g.iterrows():
    print(f"D{idx+1}: share {r['lo']:.3f}-{r['hi']:.3f} n={int(r['n']):4d}  f5 {fmt(r['f5'])}  f20 {fmt(r['f20'])}  hit5 {r['hit5']:.0%}")
print()

print("=== [4] panic (dn5>=0.15) split by market state (MA200) ===")
for label, m in (("above MA200", df["above200"]), ("below MA200", ~df["above200"])):
    sub = df[(df["dn5_share"] >= 0.15) & m & df["ma200"].notna()]
    print(f"{label}: n {len(sub):3d} | f5 {fmt(sub['ew_f5'].mean())} f20 {fmt(sub['ew_f20'].mean())} hit5 {(sub['ew_f5']>0).mean():.0%}")
print()

print("=== [5] panic (dn5>=0.15) split by drawdown from 250d high ===")
for label, m in (("dd > -10% (shallow)", df["dd250"] > -0.10),
                 ("dd -10~-20%", (df["dd250"] <= -0.10) & (df["dd250"] > -0.20)),
                 ("dd <= -20% (deep)", df["dd250"] <= -0.20)):
    sub = df[(df["dn5_share"] >= 0.15) & m]
    print(f"{label}: n {len(sub):3d} | f5 {fmt(sub['ew_f5'].mean())} f20 {fmt(sub['ew_f20'].mean())} hit5 {(sub['ew_f5']>0).mean():.0%}")
print()

print("=== [6] thrust after washout: panic within last 10d AND up95>=0.03 today ===")
recent = (df["dn5_share"] >= 0.15).rolling(10, min_periods=1).max().astype(bool)
mask = recent & (df["up95_share"] >= 0.03)
sub = df[mask]
print(f"n {len(sub)} | f1 {fmt(sub['ew_f1'].mean())} f5 {fmt(sub['ew_f5'].mean())} f20 {fmt(sub['ew_f20'].mean())} "
      f"hit5 {(sub['ew_f5']>0).mean():.0%} | baseline f5 {fmt(df['ew_f5'].mean())}")
print()

print("=== [7] strategy per era: buy close of dn5>=0.15 day, hold 5 (cost 0.1%) vs BH ===")


def strat_curve(d2, mask, k=5, cost=0.001, series="ew"):
    lev = d2[series].to_numpy()
    n = len(lev)
    cur = 1.0
    expo_end = -1
    curve = np.empty(n)
    entries = 0
    for i in range(n):
        if i > 0 and i <= expo_end:
            cur *= lev[i] / lev[i - 1]
        if i > expo_end and bool(mask.iloc[i]) and i + k < n:
            cur *= (1 - cost)
            expo_end = i + k
            entries += 1
        curve[i] = cur
    return pd.Series(curve, index=d2.index), entries


for name, a, b in eras:
    seg = df.loc[a:b]
    yrs = (seg.index[-1] - seg.index[0]).days / 365.25
    for series in ("ew", "vw"):
        c, e = strat_curve(seg, seg["dn5_share"] >= 0.15, k=5, series=series)
        cagr_s = c.iloc[-1] ** (1 / yrs) - 1
        dd_s = (c / c.cummax() - 1).min()
        bh = seg[series] / seg[series].iloc[0]          # normalize to era start
        cagr_b = bh.iloc[-1] ** (1 / yrs) - 1
        dd_b = (bh / bh.cummax() - 1).min()
        if series == "ew":
            print(f"{name}: strat5 EW total {c.iloc[-1]-1:+.0%} CAGR {fmt(cagr_s)} DD {fmt(dd_s)} | "
                  f"BH {bh.iloc[-1]-1:+.0%} CAGR {fmt(cagr_b)} DD {fmt(dd_b)} | entries {e}")
        else:
            print(f"{name}: strat5 VW total {c.iloc[-1]-1:+.0%} CAGR {fmt(cagr_s)} DD {fmt(dd_s)} | "
                  f"BH {bh.iloc[-1]-1:+.0%} CAGR {fmt(cagr_b)} DD {fmt(dd_b)}")
print()

print("=== [8] same-day up95 distribution check (are euphoria days clustered?) ===")
e = df[df["up95_share"] >= 0.05]
print(f"total euphoria days {len(e)}, by year:")
print(e.groupby(e.index.year).size().to_dict())
