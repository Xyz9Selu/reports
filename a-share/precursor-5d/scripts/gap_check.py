#!/usr/bin/env python3
"""Deep check on 向下跳空缺口 (the only new candle pattern with after-cost > 0).

Also reprints conditioner lines used by composites (standalone strength).
"""
import numpy as np
import pandas as pd

import case_control as cc
import candles as cd
import candles_more as cm
import expand_search as es

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
base.update(cm.more_signs(d))


def A(x):
    return base[x].fillna(False)


print("=== conditioner standalone (disc / conf / h1 / h2) ===")
for nm in ("跌破60日均线", "贴近60日高点", "贴近20日高点"):
    line = []
    for k, span in (("disc", cc.DISC), ("conf", cc.CONF), ("h1", ("2019-01-01", "2020-12-31")), ("h2", ("2021-01-01", "2021-12-31"))):
        m = cc.period_mask(d, span, eligible)
        sc = cc.score_frame(d.loc[m, "fwd"].ge(0.05), d.loc[m, "fwd"], base[nm].loc[m])
        line.append(f"{k}: n={sc['n']} lift={sc['lift']:.3f} edge={sc['edge']:+.3f}")
    print(nm, "|", " | ".join(line))

d["a_entry"] = d.groupby("ts_code")["ao"].shift(-1)
d["a_exit"] = d.groupby("ts_code")["ao"].shift(-6)
d["ret_ev"] = d["a_exit"] / d["a_entry"] - 1
d["e_dt"] = d.groupby("ts_code")["trade_date"].shift(-1)

sig = A("向下跳空缺口")
m = sig & eligible & d["ret_ev"].notna() & d["trade_date"].between(pd.Timestamp("2016-01-01"), pd.Timestamp("2026-10-14"))
ev = d.loc[m, ["ts_code", "trade_date", "ret_ev"]].copy()
ev["y"] = ev.trade_date.dt.year

print("\n=== 向下跳空缺口 yearly (all trades, after 0.2% cost) ===")
for y, ss in ev.groupby("y"):
    if len(ss) < 50:
        continue
    print(f"  {y}: n={len(ss):4d} mean={ss.ret_ev.mean():+.2%} after={ss.ret_ev.mean()-0.002:+.2%}")

for tag, sub in (("full 2016-2026", ev), ("test 2022-2026", ev[ev.trade_date >= pd.Timestamp("2022-01-01")])):
    g = sub.groupby("trade_date")["ret_ev"].agg(["count", "mean"])
    print(f"\nbreadth split {tag}:")
    for lo, hi, lbl in ((1, 2, "1-2"), (3, 9, "3-9"), (10, 10**9, "10+")):
        s2 = g[(g["count"] >= lo) & (g["count"] <= hi)]
        if len(s2) == 0:
            continue
        wt = (s2["count"] * s2["mean"]).sum() / s2["count"].sum()
        print(f"   {lbl}: days {len(s2):4d} trades {int(s2['count'].sum()):5d} wtd {wt:+.2%}")

te = d.loc[m & (d.trade_date >= pd.Timestamp("2022-01-01")) & ~A("今日跌超5%"), "ret_ev"]
tw = d.loc[m & (d.trade_date >= pd.Timestamp("2022-01-01")) & A("今日跌超5%"), "ret_ev"]
print(f"\ntest: gap-only n={len(te)} mean {te.mean():+.3%} | gap+跌超5% n={len(tw)} mean {tw.mean():+.3%}")
both = (A("今日跌超5%")[m]).mean()
print(f"share of gap-down events that also fell >5%: {both:.1%}")
