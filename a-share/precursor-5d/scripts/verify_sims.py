#!/usr/bin/env python3
"""Verify the slot-sim findings + understand take-all equal-weight discrepancy."""
import random
from collections import defaultdict

import numpy as np
import pandas as pd

import case_control as cc
import candles as cd
import expand_search as es

COST = 0.002

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


SIG = A("长十字") & A("跌破60日均线")
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
                        prod=float(np.prod(1 + r) - 1), ds=[pd.Timestamp(x) for x in ds], r=r))
    return out


FULL = ("2016-01-01", "2026-10-14")
TEST = ("2022-01-01", "2026-10-14")
fullT = build(SIG, FULL)
testT = build(SIG, TEST)
print(f"build: full {len(fullT)} test {len(testT)}")


# --- A) reproduce the two take-all methods on the full set
def take_all(trades, mode):
    day_sum = defaultdict(float)
    day_cnt = defaultdict(int)
    for t in trades:
        if mode == "pieces":
            for dd, rr in zip(t["ds"], t["r"]):
                day_sum[dd] += rr
                day_cnt[dd] += 1
        else:  # spread total/5 over first 5 days
            for dd in t["ds"][:5]:
                day_sum[dd] += t["prod"] / 5
                day_cnt[dd] += 1
    port = pd.Series({dd: day_sum[dd] / day_cnt[dd] for dd in sorted(day_sum)})
    eq = (1 + port).cumprod()
    return port, eq


for mode in ("pieces", "spread"):
    port, eq = take_all(fullT, mode)
    print(f"take-all [{mode}]: days {len(port)} sum(port) {port.sum():+.3f} total {eq.iloc[-1]-1:+.1%} "
          f"mean port {port.mean():+.4%} sd {port.std():.3%}")

# synthetic: same dates, every trade +1% (booked pieces = 0.01/6 per day)
syn = []
for t in fullT:
    r = np.full(6, 0.01 / 6)
    syn.append(dict(ts=t["ts"], e=t["e"], x=t["x"], prod=0.01, ds=t["ds"], r=r))
port, eq = take_all(syn, "pieces")
print(f"SYNTH +1%: total {eq.iloc[-1]-1:+.2%}  (expected ~ {np.exp(0.01/6*len(port))-1:+.1%})")

# --- B) slot sim, FIFO vs random-within-day
def slot_total(trades, span, seed=None, nslots=10, cost=0.002):
    lo, hi = pd.Timestamp(span[0]), pd.Timestamp(span[1])
    tr = [t for t in trades if lo <= t["e"] <= hi]
    if seed is None:
        tr = sorted(tr, key=lambda z: (z["e"], z["ts"]))
    else:
        g = defaultdict(list)
        for t in tr:
            g[t["e"]].append(t)
        rng = random.Random(seed)
        out = []
        for k in sorted(g):
            lst = g[k]
            rng.shuffle(lst)
            out += lst
        tr = out
    v = [1 / nslots] * nslots
    free = [pd.Timestamp("1990-01-01")] * nslots
    taken = skipped = 0
    tr_r = []
    sk_r = []
    for t in tr:
        cand = [k for k in range(nslots) if free[k] <= t["e"]]
        if not cand:
            skipped += 1
            sk_r.append(t["prod"] - cost)
            continue
        k = cand[0]
        v[k] *= (1 + t["prod"] - cost)
        free[k] = t["x"]
        taken += 1
        tr_r.append(t["prod"] - cost)
    return sum(v) - 1, taken, skipped, np.mean(tr_r), np.mean(sk_r)


t, tk, sk, m1, m2 = slot_total(fullT, FULL)
print(f"\nslot FIFO full: total {t:+.1%} taken {tk} skipped {sk} | taken mean {m1:+.2%} skipped mean {m2:+.2%}")
t, tk, sk, m1, m2 = slot_total(fullT, TEST)
print(f"slot FIFO test: total {t:+.1%} taken {tk} skipped {sk} | taken mean {m1:+.2%} skipped mean {m2:+.2%}")
for s in (1, 7, 42, 2026):
    tf, _, _, _, _ = slot_total(fullT, FULL, seed=s)
    tt, _, _, _, _ = slot_total(fullT, TEST, seed=s)
    print(f"slot random seed {s}: full {tf:+.1%}  test {tt:+.1%}")
