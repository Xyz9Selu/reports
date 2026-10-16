#!/usr/bin/env python3
"""Breadth/panic structure checks for the round-3 composites.

1) Verify the standalone conditioner signs used in composites.
2) Annual after-cost returns for the two headline composites.
3) Test-period breadth split: small batches vs >=10-at-once days.
4) Full-period threshold curve.
5) Excess vs same-window index on big days, clustered by 30-day gaps.
6) Sequential panic-day strategies vs always-hold.
"""
import numpy as np
import pandas as pd

import case_control as cc
import candles as cd
import expand_search as es

COST = 0.002

d = cc.fix_low(cc.load())
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


print("=== conditioner check (disc / conf / h1 / h2) ===")
for nm in ("跌破60日均线", "贴近60日高点", "贴近20日高点"):
    if nm not in base:
        print(f"{nm}: NOT in catalog")
        continue
    line = [nm]
    for k, span in (("disc", cc.DISC), ("conf", cc.CONF), ("h1", ("2019-01-01", "2020-12-31")), ("h2", ("2021-01-01", "2021-12-31"))):
        m = cc.period_mask(d, span, eligible)
        sc = cc.score_frame(d.loc[m, "fwd"].ge(0.05), d.loc[m, "fwd"], base[nm].loc[m])
        line.append(f"{k}: n={sc['n']} lift={sc['lift']:.3f} edge={sc['edge']:+.3f}")
    print(" | ".join(str(x) for x in line))

sig_c = A("今日跌超5%") & A("跌破20日低点")
sig_k = A("长十字") & A("跌破60日均线")

d["a_entry"] = d.groupby("ts_code")["ao"].shift(-1)
d["a_exit"] = d.groupby("ts_code")["ao"].shift(-6)
d["ret_ev"] = d["a_exit"] / d["a_entry"] - 1
d["e_dt"] = d.groupby("ts_code")["trade_date"].shift(-1)
d["idx5"] = d.groupby("ts_code")["ao"].shift(-5) / d["ao"] - 1
idx5 = d.loc[eligible].groupby("trade_date")["idx5"].mean()


def ev_frame(sig):
    m = eligible & sig & d["ret_ev"].notna() & d["e_dt"].notna()
    ev = d.loc[m, ["ts_code", "trade_date", "e_dt", "ret_ev"]].copy()
    ev["y"] = ev["trade_date"].dt.year
    return ev


ev_c = ev_frame(sig_c)
ev_k = ev_frame(sig_k)

print("\n=== annual after cost (all trades) ===")
for nm, ev in (("跌超5%x跌破20日低点", ev_c), ("长十字x跌破60日均线", ev_k)):
    print(nm)
    for y, ss in ev.groupby("y"):
        if len(ss) < 20:
            continue
        print(f"  {y}: n={len(ss):4d} mean={ss.ret_ev.mean():+.2%} after={ss.ret_ev.mean()-COST:+.2%}")

test = cc.period_mask(d, cc.TEST, eligible)
m = test & sig_c & d["ret_ev"].notna()
ev = d.loc[m, ["ts_code", "trade_date", "ret_ev"]].copy()
gg = ev.groupby("trade_date")["ret_ev"].agg(["count", "mean"])
print("\n=== test-period breadth split: 跌超5%x跌破20日低点 ===")
for lo, hi, tag in ((1, 2, "1-2"), (3, 9, "3-9"), (10, 10**9, "10+")):
    sc = gg[(gg["count"] >= lo) & (gg["count"] <= hi)]
    if sc.empty:
        continue
    wt = (sc["count"] * sc["mean"]).sum() / sc["count"].sum()
    print(f"{tag}: days {len(sc):3d} trades {int(sc['count'].sum()):5d} wtd mean {wt:+.2%} after_cost {wt-COST:+.2%}")

g = ev_c.groupby("e_dt")["ret_ev"].agg(["count", "mean"])
print("\n=== full-period threshold curve (跌超5%x跌破20日低点) ===")
for t in (3, 5, 8, 10, 15, 20, 30):
    sc = g[g["count"] >= t]
    wt = (sc["count"] * sc["mean"]).sum() / sc["count"].sum()
    print(f">={t:2d}: days {len(sc):3d} trades {int(sc['count'].sum()):5d} wtd {wt:+.2%}")

big = g[g["count"] >= 10].copy()
big["idx5"] = idx5.reindex(big.index)
big["excess"] = big["mean"] - big["idx5"] - COST
print(f"\n=== excess vs index, big days (>=10): {len(big)} days ===")
print(f"day mean {big['excess'].mean():+.3%} median {big['excess'].median():+.3%} share>0 {(big['excess'] > 0).mean():.0%} std {big['excess'].std():.2%}")
bd = list(big.index)
clusters, cur = [], [bd[0]]
for dt in bd[1:]:
    if (dt - cur[-1]).days <= 30:
        cur.append(dt)
    else:
        clusters.append(cur); cur = [dt]
clusters.append(cur)
clw = np.array([(big.loc[c, "count"] * big.loc[c, "excess"]).sum() / big.loc[c, "count"].sum() for c in clusters])
print(f"clusters {len(clw)}; trade-weighted mean {clw.mean():+.3%} t={clw.mean() / (clw.std(ddof=1) / np.sqrt(len(clw))):.2f}; positive {(clw > 0).sum()}/{len(clw)}")
print("per-cluster %:", np.round(clw * 100, 2).tolist())

print("\n=== per-year day-mean excess ===")
for y, ss in big.groupby(big.index.year):
    print(f"  {y}: days {len(ss):2d} mean {ss['excess'].mean():+.2%}")

cal_all = [pd.Timestamp(x) for x in sorted(d.loc[(d.trade_date >= pd.Timestamp("2016-01-01")) & (d.trade_date <= pd.Timestamp("2026-10-14")), "trade_date"].unique())]
bigset = set(g[g["count"] >= 10].index)
lk_sig = {pd.Timestamp(k): v for k, v in g["mean"].items()}
lk_idx = idx5.to_dict()


def run(dayset, lk, label):
    cash, active, nav, n = 1.0, [], [], 0
    rates = []
    for i, dt in enumerate(cal_all):
        for exit_i, cap, rate in list(active):
            if exit_i <= i:
                cash += cap * (1 + rate)
                active.remove((exit_i, cap, rate))
        if dt in dayset and cash > 1e-12:
            r = lk.get(dt)
            if r is not None and not (isinstance(r, float) and np.isnan(r)):
                active.append((i + 5, cash, float(r) - COST))
                rates.append(float(r) - COST)
                n += 1
                cash = 0.0
        nav.append(cash + sum(cap for _, cap, _ in active))
    eq = pd.Series(nav, index=pd.DatetimeIndex(cal_all))
    eq = eq / eq.iloc[0]
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    prod = float(np.prod([1 + r for r in rates]))
    print(f"{label}: trades {n} mean/trade {np.mean(rates):+.2%} prod(1+r) {prod-1:+.1%} total {eq.iloc[-1]-1:+.1%} "
          f"CAGR {eq.iloc[-1] ** (1 / years) - 1:+.2%} MaxDD {(eq / eq.cummax() - 1).min():.1%}")


print(f"\n=== panic-day strategies, 2016-2026 (bigset {len(bigset)} days, non-overlapping) ===")
run(bigset, lk_sig, "buy signal basket on panic days")
run(bigset, lk_idx, "buy index on panic days")
b = d.loc[(d.trade_date >= pd.Timestamp("2016-01-01")) & (d.trade_date <= pd.Timestamp("2026-10-14")) & d["in_idx"]].groupby("trade_date")["ret1"].mean()
beq = (1 + b).cumprod()
beq = beq / beq.iloc[0]
years = (beq.index[-1] - beq.index[0]).days / 365.25
print(f"always-hold index: total {beq.iloc[-1] - 1:+.1%} CAGR {beq.iloc[-1] ** (1 / years) - 1:+.2%} MaxDD {(beq / beq.cummax() - 1).min():.1%}")
