#!/usr/bin/env python3
"""Deep dive #3: thrust robustness, confirmation rules, cascade split, current analogs."""
import numpy as np
import pandas as pd

BASE = "/home/xyz/stock-scripts/panic_breadth"
df = pd.read_csv(f"{BASE}/data/breadth_clean.csv", parse_dates=["trade_date"]).set_index("trade_date").sort_index()
df = df[df["n"] > 100].copy()
for c in ["dn5", "dn7", "dn95", "up5", "up95", "newlow", "low_dn5"]:
    df[f"{c}_share"] = df[f"c_{c}"] / df["n"]
df["ew"] = (1 + df["ew_ret"] / 100).cumprod()
df["vw"] = (1 + df["vw_ret"] / 100).cumprod()
for k in (1, 2, 3, 5, 10, 20):
    df[f"ew_f{k}"] = df["ew"].shift(-k) / df["ew"] - 1
    df[f"vw_f{k}"] = df["vw"].shift(-k) / df["vw"] - 1


def fmt(x):
    return " nan " if (x is None or (isinstance(x, float) and np.isnan(x))) else f"{x*100:+.2f}%"


def tstat(x):
    x = np.asarray(pd.Series(x).dropna(), dtype=float)
    return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) >= 2 else np.nan


print("=== [S0] baseline EW & VW f5/f20 ===")
print(f"EW f1 {fmt(df['ew_f1'].mean())} f5 {fmt(df['ew_f5'].mean())} f20 {fmt(df['ew_f20'].mean())}")
print(f"VW f1 {fmt(df['vw_f1'].mean())} f5 {fmt(df['vw_f5'].mean())} f20 {fmt(df['vw_f20'].mean())}")
print()

sig = df["dn5_share"] >= 0.15
print("=== [S1] year table: panic(dn5>=15%) vs baseline ===")
for y, g in df.groupby(df.index.year):
    s = g[sig.reindex(g.index)]
    tag = f"n {len(s):3d} f5 {fmt(s['ew_f5'].mean())} f20 {fmt(s['ew_f20'].mean())} hit {(s['ew_f5']>0).mean():.0%}" if len(s) else "n   0"
    print(f"{y}: panic {tag} | base f5 {fmt(g['ew_f5'].mean())} f20 {fmt(g['ew_f20'].mean())}")
print()

print("=== [S2] cascade split: 2015-06..2016-02 vs rest of 2015-2019 ===")
cas = (df.index >= "2015-06-01") & (df.index <= "2016-02-29")
e15 = (df.index >= "2015-01-01") & (df.index <= "2019-12-31")
for label, m in (("2015-06..2016-02 cascade", e15 & cas), ("2015-2019 ex-cascade", e15 & ~cas),
                 ("all-sample ex cascade", ~cas)):
    sub = df[m & sig]
    if len(sub):
        print(f"{label}: n {len(sub):3d} f5 {fmt(sub['ew_f5'].mean())} f20 {fmt(sub['ew_f20'].mean())} hit5 {(sub['ew_f5']>0).mean():.0%}")
    else:
        print(f"{label}: n 0")
print()

print("=== [S3] thrust robustness ===")
for wthr in (0.10, 0.15):
    wash = (df["dn5_share"].shift(1) >= wthr).rolling(10, min_periods=1).max().fillna(False).astype(bool)
    thrust = wash & (df["up95_share"] >= 0.03)
    no_wash_th = (~wash) & (df["up95_share"] >= 0.03)
    print(f"-- washout thr {wthr} --")
    for label, m in (("wash&thrust", thrust), ("thrust w/o wash", no_wash_th)):
        sub = df[m]
        if len(sub):
            print(f"  {label}: n {len(sub):3d} f1 {fmt(sub['ew_f1'].mean())} f5 {fmt(sub['ew_f5'].mean())} "
                  f"f20 {fmt(sub['ew_f20'].mean())} hit5 {(sub['ew_f5']>0).mean():.0%}")
    # era split for wash(0.15)&thrust
    if wthr == 0.15:
        for label, a, b in (("2005-2009", "2005-01-01", "2009-12-31"), ("2010-2014", "2010-01-01", "2014-12-31"),
                            ("2015-2019", "2015-01-01", "2019-12-31"), ("2020-2026", "2020-01-01", "2026-12-31")):
            s = df.loc[a:b][thrust.loc[a:b]]
            if len(s):
                print(f"  era {a[:4]}-{b[:4]}: n {len(s):3d} f5 {fmt(s['ew_f5'].mean())} f20 {fmt(s['ew_f20'].mean())} hit5 {(s['ew_f5']>0).mean():.0%}")
        print("  year distribution:", df[thrust].groupby(df[thrust].index.year).size().to_dict())
print()

print("=== [S3b] strategy sims on VW: thrust & confirmed-panic ===")


def strat_curve(d2, mask, k=5, cost=0.001, series="vw"):
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


yrs = (df.index[-1] - df.index[0]).days / 365.25
bh = df["vw"]
print(f"BH VW: total {bh.iloc[-1]-1:+.0%} CAGR {fmt(bh.iloc[-1]**(1/yrs)-1)} DD {fmt((bh/bh.cummax()-1).min())}")
for label, mask in (("thrust5", thrust), ("thrust10", thrust), ("thrust20", thrust)):
    k = {"thrust5": 5, "thrust10": 10, "thrust20": 20}[label]
    c, e = strat_curve(df, mask, k=k)
    print(f"{label}: entries {e:3d} total {c.iloc[-1]-1:+.0%} CAGR {fmt(c.iloc[-1]**(1/yrs)-1)} DD {fmt((c/c.cummax()-1).min())}")
print()

print("=== [S4] confirmation rules after panic (dn5>=15%) ===")
t1 = df["ew"].shift(-1) / df["ew"] - 1          # next-day return
pan = sig
for label, m in (("A: all panic days", pan),
                 ("B: t+1 up >0%", pan & (t1 > 0)),
                 ("C: t+1 up >1%", pan & (t1 > 0.01)),
                 ("D: t+1 down", pan & (t1 <= 0))):
    f5_from_t = df["ew_f5"][m].dropna()
    f5_from_t1 = df["ew_f5"].shift(-1)[m & t1.notna()].dropna()
    f20_from_t1 = df["ew_f20"].shift(-1)[m & t1.notna()].dropna()
    print(f"{label}: n {len(f5_from_t)} | from-t f5 {fmt(f5_from_t.mean())} | from-t+1close f5 {fmt(f5_from_t1.mean())} "
          f"f20 {fmt(f20_from_t1.mean())} hit5 {(f5_from_t1>0).mean():.0%}")
print()

print("=== [S5] trajectory after near-limit waves dn95>=10%: 2015-16 vs others ===")
d95 = df["dn95_share"] >= 0.10
for label, m in (("2015-06..2016-02", d95 & cas), ("others", d95 & ~cas)):
    idx = np.where(m.to_numpy())[0]
    idx = [i for i in idx if i + 20 < len(df)]
    if not idx:
        continue
    path = np.array([df["ew"].iloc[i + 1:i + 21].to_numpy() / df["ew"].iloc[i] - 1 for i in idx])
    print(f"{label}: n {len(idx)} | t+1 {fmt(np.median(path[:, 0]))} t+2 {fmt(np.median(path[:, 1]))} "
          f"t+3 {fmt(np.median(path[:, 2]))} t+5 {fmt(np.median(path[:, 4]))} t+10 {fmt(np.median(path[:, 9]))} "
          f"t+20 {fmt(np.median(path[:, 19]))} | t+5 mean {fmt(path[:, 4].mean())} t+20 mean {fmt(path[:, 19].mean())}")
print()

print("=== [S6] current-state analogs (2020+, dn5>=12% & newlow>=30%) ===")
base = (df["dn5_share"] >= 0.12) & (df["newlow_share"] >= 0.30)
for label, m in (("2020+ all", base & (df.index >= "2020-01-01")),
                 ("2020+ & dn95<2%", base & (df.index >= "2020-01-01") & (df["dn95_share"] < 0.02)),
                 ("2024+ all", base & (df.index >= "2024-01-01"))):
    sub = df[m]
    f5 = sub["ew_f5"].dropna()
    f20 = sub["ew_f20"].dropna()
    if len(sub) == 0:
        print(f"{label}: n 0")
        continue
    print(f"{label}: n {len(sub)} | f5 mean {fmt(f5.mean())} med {fmt(f5.median())} hit {(f5>0).mean():.0%} "
          f"min {fmt(f5.min())} | f20 mean {fmt(f20.mean())} med {fmt(f20.median())} min {fmt(f20.min())}")
print()
sub = df[base & (df.index >= "2020-01-01")]
print("days:", ", ".join(str(d.date()) for d in sub.index))
print()

print("=== [S7] post-panic next-day 'wait' detail: f1 by panic intensity ===")
for t in (0.10, 0.15, 0.25, 0.40):
    sub = df[df["dn5_share"] >= t]
    print(f"dn5>={t:.2f}: n {len(sub):3d} f1 {fmt(sub['ew_f1'].mean())} f2r {fmt((df['ew'].shift(-2)/df['ew']-1)[df['dn5_share']>=t].mean())} f5 {fmt(sub['ew_f5'].mean())}")
for t in (0.02, 0.10, 0.20):
    sub = df[df["dn95_share"] >= t]
    print(f"dn95>={t:.2f}: n {len(sub):3d} f1 {fmt(sub['ew_f1'].mean())} f2r {fmt((df['ew'].shift(-2)/df['ew']-1)[df['dn95_share']>=t].mean())} f5 {fmt(sub['ew_f5'].mean())}")
