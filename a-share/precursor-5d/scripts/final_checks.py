#!/usr/bin/env python3
"""Final checks: take-all variants decomposition + full-period breadth buckets."""
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

import case_control as cc
import candles as cd
import expand_search as es

d = cc.fix_low(cc.load()).sort_values(["ts_code", "trade_date"]).reset_index(drop=True)
d["in_idx"] = cc.membership_mask(d)
prefix = d["ts_code"].str[:3]
lim = np.where(prefix.isin(["300", "301", "688", "689"]), 0.195, 0.095)
d["unbuyable"] = (d["raw_open_in"] / d["pre_in"] - 1) >= lim
d["gap_ok"] = d["gap_days"].between(5, 15)
eligible = d["in_idx"] & d["fwd"].notna() & d["gap_ok"] & ~d["unbuyable"].fillna(True)
d = cd.body_stats(d)
base = cc.signs_of(d)
base.update(es.extra_signs(d))
base.update(cd.candle_signs(d))


def A(x):
    return base[x].fillna(False)


SIG_A = A("长十字") & A("跌破60日均线")
SIG_B = A("今日跌超5%") & A("跌破20日低点")
gidx = {ts: g.index.to_numpy() for ts, g in d.groupby("ts_code", sort=False)}
ao = d["ao"].to_numpy()
ac = d["ac"].to_numpy()
dates = d["trade_date"].to_numpy()


def build(sig, span):
    lo, hi = pd.Timestamp(span[0]), pd.Timestamp(span[1])
    m = (eligible & sig & d["trade_date"].between(lo, hi)).to_numpy()
    out = []
    for i in np.where(m)[0]:
        ts = d.at[i, "ts_code"]
        idxs = gidx[ts]
        p = np.searchsorted(idxs, i)
        if p >= len(idxs) or idxs[p] != i or p + 6 >= len(idxs):
            continue
        rows = idxs[p + 1:p + 7]
        ds = dates[rows]
        r = np.empty(6)
        r[0] = ac[rows[0]] / ao[rows[0]] - 1
        for k in range(1, 5):
            r[k] = ac[rows[k]] / ac[rows[k - 1]] - 1
        r[5] = ao[rows[5]] / ac[rows[4]] - 1
        out.append(dict(ts=ts, e=pd.Timestamp(ds[0]), x=pd.Timestamp(ds[5]),
                        prod=float(np.prod(1 + r) - 1), ds=[pd.Timestamp(z) for z in ds], r=r))
    return out


FULL = ("2016-01-01", "2026-10-14")
fullA = build(SIG_A, FULL)
fullB = build(SIG_B, FULL)


def take_all(trades, cost_mode=None):
    day_sum = defaultdict(float)
    day_cnt = defaultdict(int)
    for t in trades:
        for k, (dd, rr) in enumerate(zip(t["ds"], t["r"])):
            r = rr
            if cost_mode == "first" and k == 0:
                r -= 0.002
            if cost_mode == "sixth":
                r -= 0.002 / 6
            day_sum[dd] += r
            day_cnt[dd] += 1
    port = pd.Series({dd: day_sum[dd] / day_cnt[dd] for dd in sorted(day_sum)})
    return port, (1 + port).cumprod()


print("=== take-all 长十字x破60 (full) ===")
for mode in (None, "first", "sixth"):
    port, eq = take_all(fullA, mode)
    print(f"  cost={mode}: sum(port) {port.sum():+.3f}  total {eq.iloc[-1]-1:+.1%}")

cnt = Counter()
for t in fullA:
    for dd in t["ds"]:
        cnt[dd] += 1
s = sum(1 / cnt[t["e"]] for t in fullA)
print(f"  Σ1/N_entry {s:.1f}  => cost drag ≈ {-0.002 * s:+.3f}")

print("\n=== full-period breadth buckets ===")
for name, trades in (("A 长十字x破60日线", fullA), ("B 跌超5%x破20日低点", fullB)):
    df = pd.DataFrame([{"d": t["e"], "r": t["prod"]} for t in trades])
    g = df.groupby("d")["r"].agg(["count", "mean"])
    for lo, hi, lab in ((1, 2, "1-2"), (3, 9, "3-9"), (10, 10**9, "10+")):
        sub = g[(g["count"] >= lo) & (g["count"] <= hi)]
        if len(sub) == 0:
            continue
        wt = (sub["count"] * sub["mean"]).sum() / sub["count"].sum()
        print(f"  {name} [{lab}]: days {len(sub)} trades {int(sub['count'].sum())} wtd {wt:+.2%} after_cost {wt - 0.002:+.2%}")

print("\n=== test-period buckets (already reported, reprint) ===")
TEST = ("2022-01-01", "2026-10-14")
testB = build(SIG_B, TEST)
df = pd.DataFrame([{"d": t["e"], "r": t["prod"]} for t in testB])
g = df.groupby("d")["r"].agg(["count", "mean"])
for lo, hi, lab in ((1, 2, "1-2"), (3, 9, "3-9"), (10, 10**9, "10+")):
    sub = g[(g["count"] >= lo) & (g["count"] <= hi)]
    wt = (sub["count"] * sub["mean"]).sum() / sub["count"].sum()
    print(f"  B [{lab}]: days {len(sub)} trades {int(sub['count'].sum())} wtd {wt:+.2%} after_cost {wt - 0.002:+.2%}")
