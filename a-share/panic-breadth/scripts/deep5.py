#!/usr/bin/env python3
"""Deep dive #5: final numbers for the report."""
import numpy as np
import pandas as pd

BASE = "/home/xyz/stock-scripts/panic_breadth"
df = pd.read_csv(f"{BASE}/data/breadth_clean.csv", parse_dates=["trade_date"]).set_index("trade_date").sort_index()
df = df[df["n"] > 100].copy()
for c in ["dn5", "dn7", "dn95", "up5", "up95", "newlow", "low_dn5"]:
    df[f"{c}_share"] = df[f"c_{c}"] / df["n"]
df["ew"] = (1 + df["ew_ret"] / 100).cumprod()
df["vw"] = (1 + df["vw_ret"] / 100).cumprod()
for k in (1, 5, 20):
    df[f"ew_f{k}"] = df["ew"].shift(-k) / df["ew"] - 1
    df[f"vw_f{k}"] = df["vw"].shift(-k) / df["vw"] - 1


def fmt(x):
    return " nan " if (x is None or (isinstance(x, float) and np.isnan(x))) else f"{x*100:+.2f}%"


print("=== [U1] 2026-10-15 readings: all-sample & 2020+ percentiles ===")
last = df.iloc[-1]
for col in ("dn5_share", "newlow_share", "dn95_share", "low_dn5_share"):
    pct_all = (df[col] <= last[col]).mean()
    p = df[df.index >= "2020-01-01"]
    pct_20 = (p[col] <= last[col]).mean()
    print(f"{col}: {last[col]:.4f} | all-sample pct {pct_all*100:.0f}% | 2020+ pct {pct_20*100:.0f}%")
print()

print("=== [U2] repeat vs isolated panic (prior 10 trading days) ===")
sig = df["dn5_share"] >= 0.15
prev10 = sig.shift(1).rolling(10, min_periods=1).max().astype(bool)
for era_label, era_mask in (("ALL", pd.Series(True, index=df.index)),
                            ("2020+", df.index >= "2020-01-01"),
                            ("2024+", df.index >= "2024-01-01")):
    print(f"-- {era_label} --")
    for label, m in (("isolated", sig & ~prev10 & era_mask), ("repeat(<=10td)", sig & prev10 & era_mask)):
        sub = df[m]
        f5, f20 = sub["ew_f5"].dropna(), sub["ew_f20"].dropna()
        if len(sub) == 0:
            print(f"  {label}: n 0")
            continue
        print(f"  {label}: n {len(sub):3d} | f5 {fmt(f5.mean())} med {fmt(f5.median())} hit {(f5>0).mean():.0%} | "
              f"f20 {fmt(f20.mean())} med {fmt(f20.median())} hit {(f20>0).mean():.0%}")
print()

print("=== [U3] drawdowns from recent highs (as of 2026-10-15) ===")
for series in ("ew", "vw"):
    lev = df[series]
    for win in (60, 120, 250):
        hi = lev.iloc[-win:].max()
        print(f"{series} dd_from_{win}d_high: {lev.iloc[-1]/hi-1:+.2%} (high {lev.iloc[-win:].idxmax().date()})")
print()

print("=== [U4] 2026 dn5>=15% days (14) with forward returns ===")
sub = df[(df["dn5_share"] >= 0.15) & (df.index >= "2026-01-01")]
for d, r in sub.iterrows():
    print(f"{d.date()} dn5 {r['dn5_share']:.1%} dn95 {r['dn95_share']:.1%} newlow {r['newlow_share']:.0%} "
          f"f5 {fmt(r['ew_f5'])} f20 {fmt(r['ew_f20'])}")
print()

print("=== [U5] analogs (2020+: dn5>=12% & newlow>=30%) dn95 trivision ===")
base = (df["dn5_share"] >= 0.12) & (df["newlow_share"] >= 0.30) & (df.index >= "2020-01-01")
for label, m in (("dn95 < 0.5%", base & (df["dn95_share"] < 0.005)),
                 ("0.5% <= dn95 < 2%", base & (df["dn95_share"] >= 0.005) & (df["dn95_share"] < 0.02)),
                 ("dn95 >= 2%", base & (df["dn95_share"] >= 0.02))):
    sub = df[m]
    f5, f20 = sub["ew_f5"].dropna(), sub["ew_f20"].dropna()
    print(f"{label}: n {len(sub)} | f5 mean {fmt(f5.mean())} med {fmt(f5.median())} hit {(f5>0).mean():.0%} | "
          f"f20 mean {fmt(f20.mean())} med {fmt(f20.median())}")
    print("   ", ", ".join(f"{d.date()}({fmt(r['ew_f5'])})" for d, r in sub.iterrows() if not np.isnan(r["ew_f5"])))
print()

print("=== [U6] if panic is followed by a thrust within next 10d, what then? ===")
up = df["up95_share"] >= 0.03
fwd_up10 = up.iloc[::-1].rolling(10, min_periods=1).max().iloc[::-1]          # any thrust in t+1..t+10
fwd_up10 = fwd_up10.shift(-1).fillna(0).astype(bool)
for label, m in (("panic: thrust within 10d", sig & fwd_up10),
                 ("panic: no thrust within 10d", sig & ~fwd_up10)):
    sub = df[m & (df.index >= "2020-01-01")]
    if len(sub) == 0:
        print(f"{label}: n 0")
        continue
    f5, f20 = sub["ew_f5"].dropna(), sub["ew_f20"].dropna()
    print(f"{label} (2020+): n {len(sub)} | f5 {fmt(f5.mean())} med {fmt(f5.median())} | f20 {fmt(f20.mean())} med {fmt(f20.median())}")

print()
print("=== [U7] trading days since prior panic for recent 2026 panics ===")
panic_dates = list(df.index[df["dn5_share"] >= 0.15])
for d in panic_dates[-8:]:
    pos = df.index.get_loc(d)
    prevs = [x for x in panic_dates if x < d]
    if prevs:
        gap = pos - df.index.get_loc(prevs[-1])
        print(f"{d.date()}: {gap} trading days since prior panic ({prevs[-1].date()})")
    else:
        print(f"{d.date()}: first panic in sample")
