#!/usr/bin/env python3
"""Deep dive #2: current-state analogs, regime-controlled stats, execution delay, VW side."""
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
# execution-delay versions: buy at close t+1, sell at close t+1+k
df["ewd_f5"] = df["ew"].shift(-6) / df["ew"].shift(-1) - 1
df["ewd_f20"] = df["ew"].shift(-21) / df["ew"].shift(-1) - 1
df["vwd_f5"] = df["vw"].shift(-6) / df["vw"].shift(-1) - 1
df["vwd_f20"] = df["vw"].shift(-21) / df["vw"].shift(-1) - 1
df["ma200"] = df["ew"].rolling(200).mean()
df["above200"] = df["ew"] >= df["ma200"]
df["dd250"] = df["ew"] / df["ew"].rolling(250, min_periods=100).max() - 1


def fmt(x):
    return " nan " if (x is None or (isinstance(x, float) and np.isnan(x))) else f"{x*100:+.2f}%"


print("=== [A] recent 12 days: full-market state (panic watch) ===")
cols = ["n", "c_dn5", "dn5_share", "c_dn95", "newlow_share", "c_low_dn5", "ew_ret", "vw_ret"]
print(df[cols].tail(12).to_string(float_format=lambda v: f"{v:.4f}"))
print()

print("=== [B] current-state analogs: dn5_share in [0.12,0.25) & newlow_share >= 0.30 ===")


def conditional_table(mask, label, cols=("ew_f5", "ew_f20", "ewd_f5", "ewd_f20", "vw_f5", "vw_f20")):
    sub = df[mask]
    if len(sub) == 0:
        print(f"{label}: none")
        return
    out = [f"{label}: n {len(sub)}"]
    for c in cols:
        s = sub[c].dropna()
        out.append(f"{c} {fmt(s.mean())} | hit5 {(s>0).mean():.0%}")
    print("  " + " | ".join(out))


analog = (df["dn5_share"].between(0.12, 0.25)) & (df["newlow_share"] >= 0.30)
conditional_table(analog, "ALL")
conditional_table(analog & (df.index >= "2016-01-01"), "2016+")
conditional_table(analog & (df.index >= "2020-01-01"), "2020+")
conditional_table(analog & (df.index < "2016-01-01"), "2005-2015")
print()
sub = df[analog & (df.index >= "2019-01-01")]
print("recent analog days (2019+) — date, dn5%, newlow%, f5, f20:")
for dt, r in sub.iterrows():
    print(f"  {dt.date()}  dn5 {r['dn5_share']:.1%}  newlow {r['newlow_share']:.0%}  f5 {fmt(r['ew_f5'])}  f20 {fmt(r['ew_f20'])}")
print()

print("=== [B2] slightly softer condition: dn5_share >= 0.12 & newlow >= 0.25, era detail ===")
analog2 = (df["dn5_share"] >= 0.12) & (df["newlow_share"] >= 0.25)
conditional_table(analog2, "ALL")
conditional_table(analog2 & (df.index >= "2016-01-01"), "2016+")
conditional_table(analog2 & (df.index >= "2020-01-01"), "2020+")
print()

print("=== [C] within-year demeaned deciles (regime-controlled) ===")
for col in ("ew_f5", "ew_f20"):
    df[col + "_adj"] = df[col] - df.groupby(df.index.year)[col].transform("mean")
q = pd.qcut(df["dn5_share"], 10, labels=False, duplicates="drop")
g = df.groupby(q).agg(lo=("dn5_share", "min"), hi=("dn5_share", "max"), n=("ew_f5", "size"),
                      f5a=("ew_f5_adj", "mean"), f20a=("ew_f20_adj", "mean"),
                      f5=("ew_f5", "mean"), f20=("ew_f20", "mean"))
print("decile | share range | n | f5 raw | f5 adj | f20 raw | f20 adj")
for idx, r in g.iterrows():
    print(f"D{idx+1:2d} {r['lo']:.3f}-{r['hi']:.3f} n={int(r['n']):4d}  f5 {fmt(r['f5'])}  f5adj {fmt(r['f5a'])}  f20 {fmt(r['f20'])}  f20adj {fmt(r['f20a'])}")
print()

print("=== [D] VW-side conditional curve ===")
for t in (0.05, 0.10, 0.15, 0.25):
    sub = df[df["dn5_share"] >= t]
    print(f"dn5>={t:.2f}: n {len(sub):4d}  VW f5 {fmt(sub['vw_f5'].mean())}  VW f20 {fmt(sub['vw_f20'].mean())}  "
          f"EW f5 {fmt(sub['ew_f5'].mean())} | VWd f5 {fmt(sub['vwd_f5'].mean())}")
print()

print("=== [E] execution delay on EW: close-t vs close-t+1 entry ===")
for t in (0.15, 0.25):
    sub = df[df["dn5_share"] >= t]
    print(f"dn5>={t}: f5 {fmt(sub['ew_f5'].mean())} -> delayed {fmt(sub['ewd_f5'].mean())} | "
          f"f20 {fmt(sub['ew_f20'].mean())} -> delayed {fmt(sub['ewd_f20'].mean())}")
print()

print("=== [F] strategy sims (VW): A=panic close entry, B=panic+aboveMA200, C=thrust after washout ===")


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


recent = (df["dn5_share"] >= 0.15).rolling(10, min_periods=1).max().astype(bool)
thrust = recent & (df["up95_share"] >= 0.03)
panic = df["dn5_share"] >= 0.15
panic_above = panic & df["above200"]

for name, mask in (("A panic", panic), ("B panic&aboveMA200", panic_above), ("C thrust", thrust)):
    for k in (5, 20):
        c, e = strat_curve(df, mask, k=k)
        yrs = (df.index[-1] - df.index[0]).days / 365.25
        cagr = c.iloc[-1] ** (1 / yrs) - 1
        dd = (c / c.cummax() - 1).min()
        print(f"{name} k={k:2d}: entries {e:3d} total {c.iloc[-1]-1:+.0%} CAGR {fmt(cagr)} DD {fmt(dd)}")
bh = df["vw"] / df["vw"].iloc[0]
yrs = (df.index[-1] - df.index[0]).days / 365.25
print(f"BH VW: total {bh.iloc[-1]-1:+.0%} CAGR {fmt(bh.iloc[-1]**(1/yrs)-1)} DD {fmt((bh/bh.cummax()-1).min())}")
# era subtotals for B
print()
print("era check for B (panic & above 200MA), k=5:")
for a, b in (("2005-01-01", "2009-12-31"), ("2010-01-01", "2014-12-31"), ("2015-01-01", "2019-12-31"), ("2020-01-01", "2026-12-31")):
    seg = df.loc[a:b]
    mask_seg = (seg["dn5_share"] >= 0.15) & seg["above200"].fillna(False)
    c, e = strat_curve(seg, mask_seg, k=5)
    sub = df.loc[a:b]
    print(f"  {a[:4]}-{b[:4]}: entries {e:3d}  strat total {c.iloc[-1]-1:+.0%}  "
          f"| panic-days f5 {fmt(sub.loc[mask_seg, 'ew_f5'].mean())} n={int(mask_seg.sum())}")
print()

print("=== [G] euphoria by-year forward returns (EW f5) — mania clustering check ===")
e = df[df["up95_share"] >= 0.05]
by_year = e.groupby(e.index.year).agg(n=("ew_f5", "size"), f5=("ew_f5", "mean"), f20=("ew_f20", "mean"))
print(by_year.to_string(float_format=lambda v: f"{v:.4f}"))
print(f"\nall: n {len(e)} f5 {fmt(e['ew_f5'].mean())} f20 {fmt(e['ew_f20'].mean())}")
e_ex = e[e.index.year != 2015]
print(f"ex-2015: n {len(e_ex)} f5 {fmt(e_ex['ew_f5'].mean())} f20 {fmt(e_ex['ew_f20'].mean())}")
e_ex2 = e[~e.index.year.isin([2007, 2008, 2015])]
print(f"ex-2007/08/15: n {len(e_ex2)} f5 {fmt(e_ex2['ew_f5'].mean())} f20 {fmt(e_ex2['ew_f20'].mean())}")
