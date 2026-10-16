#!/usr/bin/env python3
"""bt1b.py — 回测诊断：最大回撤区间、关键变体最差交易、cap2 两种口径、止损成交口径对比。"""
import numpy as np
import pandas as pd

BASE = "/home/xyz/stock-scripts/panic_breadth"
df = pd.read_csv(f"{BASE}/data/breadth_clean.csv", parse_dates=["trade_date"]).set_index("trade_date").sort_index()
df = df[df["n"] > 100].copy()
df["dn5_share"] = df["c_dn5"] / df["n"]
df["up95_share"] = df["c_up95"] / df["n"]
df["ew"] = (1 + df["ew_ret"] / 100).cumprod()
df["vw"] = (1 + df["vw_ret"] / 100).cumprod()
dates = df.index
N = len(df)

wash = (df["dn5_share"].shift(1) >= 0.15).rolling(10, min_periods=1).max().fillna(False).astype(bool).to_numpy()
thrust = wash & (df["up95_share"].to_numpy() >= 0.03)
EW = df["ew"].to_numpy()

# streak id（连续 wash 段）
streak = np.full(N, -1, dtype=int)
sid = -1
for i in range(N):
    if wash[i]:
        if i == 0 or not wash[i - 1]:
            sid += 1
        streak[i] = sid

# 30日聚簇 id（恐慌日间隔>30交易日分簇；信号日归属"最近一次恐慌"所在簇）
panic_days = np.where(df["dn5_share"].to_numpy() >= 0.15)[0]
cl = {}
cid = -1
prev = None
for p in panic_days:
    if prev is None or p - prev > 30:
        cid += 1
    cl[p] = cid
    prev = p
cluster = np.full(N, -1, dtype=int)
lastp = -1
for i in range(N):
    if lastp >= 0 and i - lastp <= 10:
        cluster[i] = cl[lastp]
    if df["dn5_share"].to_numpy()[i] >= 0.15:
        lastp = i

print(f"panic clusters: {cid+1}")


def make_rec(entry_i, exit_i, entry_px, exit_px, cost, stopped=False):
    gross = exit_px / entry_px
    net = (1 - cost) * gross * (1 - cost) - 1
    return dict(entry_i=entry_i, exit_i=exit_i,
                entry_date=dates[entry_i].strftime("%Y-%m-%d"), exit_date=dates[exit_i].strftime("%Y-%m-%d"),
                gross=gross, net=net, stopped=stopped)


def simulate(close, entry_delay=0, hold_k=5, stop=None, stop_delay=1, stop_fill="close", cap=None, cost=0.001, group=None):
    value = 1.0
    eq = np.empty(N)
    pos = None
    last_exit = -1
    pending = None
    pending_streak = -1
    trades = []
    counts = {}
    if group is None:
        group = streak
    for i in range(N):
        if pos is not None and i == pos["exit_day"]:
            trades.append(make_rec(pos["entry_i"], i, pos["entry_px"], close[i], cost, pos.get("stopped", False)))
            value *= (close[i] / pos["entry_px"]) * (1 - cost)
            last_exit = i
            pos = None
        if pos is None and pending is not None and i == pending:
            if i > last_exit:
                value *= (1 - cost)
                pos = dict(entry_i=i, entry_px=close[i], exit_day=min(i + hold_k, N - 1), stopped=False)
                if cap is not None:
                    counts[pending_streak] = counts.get(pending_streak, 0) + 1
            pending = None
        if pos is not None and stop is not None and not pos.get("stopped") and i < pos["exit_day"]:
            if close[i] <= pos["entry_px"] * (1 - stop):
                if stop_delay == 0:
                    exit_px = pos["entry_px"] * (1 - stop) if stop_fill == "level" else close[i]
                    trades.append(make_rec(pos["entry_i"], i, pos["entry_px"], exit_px, cost, True))
                    value *= (exit_px / pos["entry_px"]) * (1 - cost)
                    last_exit = i
                    pos = None
                else:
                    pos["exit_day"] = min(i + 1, pos["exit_day"])
                    pos["stopped"] = True
        if pos is None and pending is None and thrust[i]:
            allowed = cap is None or counts.get(group[i], 0) < cap
            if allowed:
                if entry_delay == 0:
                    if i > last_exit:
                        value *= (1 - cost)
                        pos = dict(entry_i=i, entry_px=close[i], exit_day=min(i + hold_k, N - 1), stopped=False)
                        if cap is not None:
                            counts[group[i]] = counts.get(group[i], 0) + 1
                else:
                    pending = i + 1
                    pending_streak = group[i]
                    if pending > N - 1:
                        pending = None
        eq[i] = value * (close[i] / pos["entry_px"]) if pos is not None else value
    if pos is not None:
        trades.append(make_rec(pos["entry_i"], N - 1, pos["entry_px"], close[N - 1], cost, pos.get("stopped", False)))
        value *= (close[N - 1] / pos["entry_px"]) * (1 - cost)
        eq[N - 1] = value
    return value, eq, pd.DataFrame(trades)


def dd_span(eq):
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1
    i = int(np.argmin(dd))
    k = int(np.where(eq[:i + 1] == peak[i])[0][-1])
    return f"{dates[k].strftime('%Y-%m-%d')} -> {dates[i].strftime('%Y-%m-%d')}  {dd[i]*100:.1f}%"


def max_dd(eq):
    peak = np.maximum.accumulate(eq)
    return float((eq / peak - 1).min())


# diagnostics
cases = {
    "V1 base": dict(entry_delay=0, hold_k=5),
    "V3 stop same-close": dict(entry_delay=0, hold_k=5, stop=0.05, stop_delay=0),
    "V6 entry t+1": dict(entry_delay=1, hold_k=5),
    "V9 20d": dict(entry_delay=0, hold_k=20),
    "CAP2b (30d cluster)": dict(entry_delay=0, hold_k=5, cap=2, group=cluster),
}
for name, kw in cases.items():
    v, eq, tr = simulate(EW, cost=0.001, **kw)
    print(f"\n== {name} ==  trades={len(tr)} final={v:.2f}x maxDD={max_dd(eq)*100:.1f}%")
    print(f"   maxDD span: {dd_span(eq)}")
    print("   worst 4: ", [(r['entry_date'], f"{r['net']*100:+.1f}%") for _, r in tr.nsmallest(4, "net").iterrows()])
    if "stop" in name:
        print(f"   stop triggers: {int(tr['stopped'].sum())}")

# cap2 对比（两种口径 + base）
print("\n== cap comparison ==")
for name, kw in {"base": dict(entry_delay=0, hold_k=5),
                 "cap2/streak": dict(entry_delay=0, hold_k=5, cap=2),
                 "cap2/cluster": dict(entry_delay=0, hold_k=5, cap=2, group=cluster),
                 "cap3/cluster": dict(entry_delay=0, hold_k=5, cap=3, group=cluster)}.items():
    v, eq, tr = simulate(EW, cost=0.001, **kw)
    print(f"  {name:<14} trades={len(tr):>3} final={v:.2f}x maxDD={max_dd(eq)*100:.1f}%")

# 止损成交口径对比
print("\n== stop fill comparison ==")
for name, kw in {"no stop": dict(entry_delay=0, hold_k=5),
                 "stop next close": dict(entry_delay=0, hold_k=5, stop=0.05, stop_delay=1),
                 "stop same close": dict(entry_delay=0, hold_k=5, stop=0.05, stop_delay=0),
                 "stop fill -5%": dict(entry_delay=0, hold_k=5, stop=0.05, stop_delay=0, stop_fill="level")}.items():
    v, eq, tr = simulate(EW, cost=0.001, **kw)
    print(f"  {name:<16} trades={len(tr):>3} final={v:.2f}x maxDD={max_dd(eq)*100:.1f}% worst={tr['net'].min()*100:+.1f}%")

# save equity csv (with v3)
v1 = simulate(EW, entry_delay=0, hold_k=5, cost=0.001)
v2 = simulate(EW, entry_delay=0, hold_k=5, stop=0.05, stop_delay=1, cost=0.001)
v3 = simulate(EW, entry_delay=0, hold_k=5, stop=0.05, stop_delay=0, cost=0.001)
v4 = simulate(EW, entry_delay=0, hold_k=5, cap=2, cost=0.001)
v9 = simulate(EW, entry_delay=0, hold_k=20, cost=0.001)
eq_df = pd.DataFrame({
    "date": [d.strftime("%Y-%m-%d") for d in dates],
    "ew_bh": EW, "vw_bh": df["vw"].to_numpy(),
    "v1_base": v1[1], "v2_stop_next": v2[1], "v3_stop_same": v3[1],
    "v4_cap2": v4[1], "v9_20d": v9[1],
})
eq_df.to_csv(f"{BASE}/out/bt1_equity.csv", index=False)
print("\nsaved out/bt1_equity.csv (with v3)")
