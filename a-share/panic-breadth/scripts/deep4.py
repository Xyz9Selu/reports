#!/usr/bin/env python3
"""Deep dive #4: current-state precision check + analog sensitivity."""
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


def fmt(x):
    return " nan " if (x is None or (isinstance(x, float) and np.isnan(x))) else f"{x*100:+.2f}%"


print("=== [T1] today (2026-10-15) readings vs 2020+ history ===")
p = df[df.index >= "2020-01-01"]
last = df.iloc[-1]
for col in ("dn5_share", "dn95_share", "newlow_share", "low_dn5_share", "up95_share"):
    pct = (p[col] <= last[col]).mean()
    print(f"{col}: today {last[col]:.3f} | 2020+ percentile {pct*100:.0f}%")
print(f"ew_ret today {fmt(last['ew_ret']/100)} vw_ret {fmt(last['vw_ret']/100)}")
print()

print("=== [T2] recent 12 days (clean) ===")
cols = ["n", "c_dn5", "dn5_share", "c_dn95", "dn95_share", "newlow_share", "c_low_dn5", "ew_ret", "vw_ret"]
t = df[cols].tail(12).copy()
t["dn5_share"] = t["dn5_share"].map(lambda v: f"{v:.1%}")
t["dn95_share"] = t["dn95_share"].map(lambda v: f"{v:.1%}")
t["newlow_share"] = t["newlow_share"].map(lambda v: f"{v:.1%}")
t["ew_ret"] = t["ew_ret"].map(lambda v: f"{v:+.2f}%")
t["vw_ret"] = t["vw_ret"].map(lambda v: f"{v:+.2f}%")
print(t.to_string())
print()

base = (df["dn5_share"] >= 0.12) & (df["newlow_share"] >= 0.30)
cur = base & (df.index >= "2020-01-01")
print("=== [T3] analog split by dn95 among 2020+ analogs ===")
for label, m in (("dn95>=2%", cur & (df["dn95_share"] >= 0.02)), ("dn95<2%", cur & (df["dn95_share"] < 0.02))):
    sub = df[m]
    f5, f20 = sub["ew_f5"].dropna(), sub["ew_f20"].dropna()
    print(f"{label}: n {len(sub)} | f5 mean {fmt(f5.mean())} med {fmt(f5.median())} hit {(f5>0).mean():.0%} | "
          f"f20 mean {fmt(f20.mean())} med {fmt(f20.median())}")
    print("   days:", ", ".join(f"{d.date()}({fmt(r['ew_f5'])})" for d, r in sub.iterrows()))
print()

print("=== [T4] analog quantiles (2020+, C1=dn5>=12% & newlow>=30%) ===")
f5 = df[cur]["ew_f5"].dropna()
f20 = df[cur]["ew_f20"].dropna()
for nm, s in (("f5", f5), ("f20", f20)):
    q = s.quantile([0.1, 0.25, 0.5, 0.75, 0.9])
    print(f"{nm}: n {len(s)} mean {fmt(s.mean())} | p10 {fmt(q[0.1])} p25 {fmt(q[0.25])} med {fmt(q[0.5])} "
          f"p75 {fmt(q[0.75])} p90 {fmt(q[0.9])} | min {fmt(s.min())} max {fmt(s.max())}")
print()

print("=== [T5] condition sensitivity (stats over 2020+ subset) ===")
conds = (("C1 dn5>=12% & newlow>=30%", (df["dn5_share"] >= 0.12) & (df["newlow_share"] >= 0.30)),
         ("C2 dn5>=15% & newlow>=30%", (df["dn5_share"] >= 0.15) & (df["newlow_share"] >= 0.30)),
         ("C3 dn5>=12% & newlow>=30% & dn95>=2%", (df["dn5_share"] >= 0.12) & (df["newlow_share"] >= 0.30) & (df["dn95_share"] >= 0.02)))
for label, cm in conds:
    m = cm & (df.index >= "2020-01-01")
    sub = df[m]
    if len(sub) == 0:
        print(f"{label}: n 0")
        continue
    f5, f20 = sub["ew_f5"].dropna(), sub["ew_f20"].dropna()
    print(f"{label}: n {len(sub)} | f5 {fmt(f5.mean())} med {fmt(f5.median())} hit {(f5>0).mean():.0%} | "
          f"f20 {fmt(f20.mean())} med {fmt(f20.median())} hit {(f20>0).mean():.0%}")
print()

print("=== [T6] checklist of 2026-10-15 against condition C1 components ===")
for col, thr in (("dn5_share", 0.12), ("newlow_share", 0.30)):
    v = last[col]
    print(f"{col}: {v:.3f} {'>=' if v >= thr else '<'} {thr}")
print()

print("=== [T7] dn5>=15% full list 2024+ with forward returns ===")
m = (df["dn5_share"] >= 0.15) & (df.index >= "2024-01-01")
sub = df[m]
for d, r in sub.iterrows():
    print(f"{d.date()} dn5 {r['dn5_share']:.1%} newlow {r['newlow_share']:.0%} dn95 {r['dn95_share']:.1%} "
          f"| f5 {fmt(r['ew_f5'])} f20 {fmt(r['ew_f20'])}")
