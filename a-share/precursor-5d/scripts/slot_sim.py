#!/usr/bin/env python3
"""Slot-simulation: can the round-3 composite edges be traded as a portfolio?

Method: N fixed slots; each signal takes 1/N of capital at entry (next open),
holds 5 trading days, exits at open; FIFO assignment, skip when full.
Daily equity marked with actual price path (open->close, close->close, close->open).
Verifies the daily-piece product equals the stored fwd for every trade.
"""
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


gidx = {ts: g.index.to_numpy() for ts, g in d.groupby("ts_code", sort=False)}
ao = d["ao"].to_numpy()
ac = d["ac"].to_numpy()
dates = d["trade_date"].to_numpy()

SIG_A = A("长十字") & A("跌破60日均线")
SIG_B = A("今日跌超5%") & A("跌破20日低点")

# breadth of each signal per day (for big-day filter)
breadth = SIG_B.groupby(d["trade_date"]).sum()


def build_trades(sig, span):
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
        out.append(dict(ts=ts, sig_dt=pd.Timestamp(d.at[i, "trade_date"]),
                        e=pd.Timestamp(ds[0]), x=pd.Timestamp(ds[5]),
                        prod=float(np.prod(1 + r) - 1), fwd=float(d.at[i, "fwd"]),
                        r=r, ds=[pd.Timestamp(x) for x in ds]))
    return out


def slot_sim(trades, span, nslots=10, cost=0.002, label=""):
    lo, hi = pd.Timestamp(span[0]), pd.Timestamp(span[1])
    cal = pd.DatetimeIndex(sorted(d.loc[(d["trade_date"] >= lo) & (d["trade_date"] <= hi), "trade_date"].unique()))
    trades = sorted([t for t in trades if lo <= t["e"] <= hi], key=lambda t: (t["e"], t["ts"]))
    init = 1.0 / nslots
    slot_cash = [init] * nslots
    free = [pd.Timestamp("1990-01-01")] * nslots
    series = {s: [(cal[0], init)] for s in range(nslots)}
    taken = skipped = 0
    nets = []
    for t in trades:
        cand = [k for k in range(nslots) if free[k] <= t["e"]]
        if not cand:
            skipped += 1
            continue
        s = cand[0]
        v = slot_cash[s]
        cv = v
        pts = []
        for k in range(6):
            cv = cv * (1 + t["r"][k])
            pts.append((t["ds"][k], cv))
        net = t["prod"] - cost
        final = v * (1 + net)
        pts[5] = (t["ds"][5], final)
        series[s].extend(pts)
        slot_cash[s] = final
        free[s] = t["x"]
        taken += 1
        nets.append(net)
    eq = None
    for s in range(nslots):
        se = pd.Series([v for _, v in series[s]], index=[dt for dt, _ in series[s]])
        se = se[~se.index.duplicated(keep="last")].sort_index()
        se = se.reindex(cal.union(se.index)).sort_index().ffill().reindex(cal).ffill().bfill()
        eq = se if eq is None else eq.add(se, fill_value=0)
    eq = eq / eq.iloc[0]
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    nets = np.array(nets)
    print(f"{label}: taken {taken} skipped {skipped} | mean {nets.mean():+.2%} median {np.median(nets):+.2%} "
          f"win {100*(nets>0).mean():.0f}% | total {eq.iloc[-1]-1:+.1%} CAGR {eq.iloc[-1] ** (1/years) - 1:+.2%} "
          f"MaxDD {(eq / eq.cummax() - 1).min():.1%}")
    return eq


print("=== verify pieces == fwd ===")
tr = build_trades(SIG_A, ("2016-01-01", "2026-10-14"))
errs = [abs(t["prod"] - t["fwd"]) for t in tr if np.isfinite(t["fwd"])]
print("trades:", len(tr), "max |prod-fwd|:", max(errs))

print("\n=== slot sim: 长十字x跌破60日均线 (all signals) ===")
for span, tag in ((cc.TEST, "test"), (("2016-01-01", "2026-10-14"), "full")):
    slot_sim(build_trades(SIG_A, span), span, 10, 0.002, f"[{tag}] cost20bp")
slot_sim(build_trades(SIG_A, ("2016-01-01", "2026-10-14")), ("2016-01-01", "2026-10-14"), 10, 0.004, "[full] cost40bp")

print("\n=== slot sim: 跌超5%x跌破20日低点 ===")
for span, tag in ((cc.TEST, "test"), (("2016-01-01", "2026-10-14"), "full")):
    slot_sim(build_trades(SIG_B, span), span, 10, 0.002, f"[{tag}] all signals")
# big-day only (breadth>=10)
big_days = set(breadth[breadth >= 10].index)
tr_b = [t for t in build_trades(SIG_B, ("2016-01-01", "2026-10-14")) if t["sig_dt"] in big_days]
slot_sim(tr_b, ("2016-01-01", "2026-10-14"), 10, 0.002, "[full] breadth>=10 only")

print("\n=== concurrency ===")
tr_all = build_trades(SIG_A, ("2016-01-01", "2026-10-14"))
cnt = pd.Series(0, index=sorted(d.loc[(d["trade_date"] >= "2016-01-01") & (d["trade_date"] <= "2026-10-14"), "trade_date"].unique()))
for t in tr_all:
    cnt.loc[(cnt.index >= t["e"]) & (cnt.index <= t["x"])] += 1
print(f"mean {cnt.mean():.1f}  max {cnt.max()}  share days >10: {(cnt > 10).mean():.1%}")

print("\n=== trade stats ===")
for lbl, trades in (("长十字x跌破60日线 full", tr_all),):
    fwds = np.array([t["fwd"] for t in trades]) - 0.002
    print(f"{lbl}: n={len(fwds)} mean {fwds.mean():+.3%} median {np.median(fwds):+.3%} win {100*(fwds>0).mean():.0f}%")

b = d.loc[d["in_idx"]].groupby("trade_date")["ret1"].mean()
for span, tag in ((cc.TEST, "test"), (("2016-01-01", "2026-10-14"), "full")):
    lo, hi = pd.Timestamp(span[0]), pd.Timestamp(span[1])
    bb = b[(b.index >= lo) & (b.index <= hi)]
    eq = (1 + bb).cumprod()
    eq = eq / eq.iloc[0]
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    print(f"index {tag}: total {eq.iloc[-1]-1:+.1%}  CAGR {eq.iloc[-1] ** (1/years) - 1:+.2%}  MaxDD {(eq / eq.cummax() - 1).min():.1%}")
