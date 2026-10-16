#!/usr/bin/env python3
"""bt1.py — 「恐慌→反击」策略独立回测：多执行变体 + 基准对比。
信号: 恐慌日(dn5>=15%)后10个交易日内出现反击日(up95>=3%) → 反击日收盘买入(或次日)。
退出: 固定持有 k 日 / 止损 / 检查点延伸。非重叠: 上一笔结束后才能接下一笔。
成本: 单边 0.1%(来回 0.2%)，另做 0.2% 敏感性。
"""
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

# wash 连续段 id（用于「同一波恐慌最多 N 次」）
streak = np.full(N, -1, dtype=int)
sid = -1
for i in range(N):
    if wash[i]:
        if i == 0 or not wash[i - 1]:
            sid += 1
        streak[i] = sid
n_streaks = sid + 1

EW = df["ew"].to_numpy()
VW = df["vw"].to_numpy()
years = (dates[-1] - dates[0]).days / 365.25

print(f"days={N}  range={dates[0].date()}..{dates[-1].date()}  years={years:.1f}")
print(f"wash streaks={n_streaks}  thrust-signals={int(thrust.sum())}")
print()


def make_rec(entry_i, exit_i, entry_px, exit_px, cost, stopped=False):
    gross = exit_px / entry_px
    net = (1 - cost) * gross * (1 - cost) - 1
    return dict(entry_i=entry_i, exit_i=exit_i,
                entry_date=dates[entry_i].strftime("%Y-%m-%d"), exit_date=dates[exit_i].strftime("%Y-%m-%d"),
                gross=gross, net=net, stopped=stopped)


def simulate(close, entry_delay=0, hold_k=5, stop=None, stop_delay=1, cap=None, cost=0.001, checkpoint=False):
    value = 1.0
    eq = np.empty(N)
    pos = None
    last_exit = -1
    pending = None
    pending_streak = -1
    trades = []
    counts = {}
    for i in range(N):
        # 0) checkpoint: 第 k 日收盘不亏 → 延到 20 日
        if (pos is not None and checkpoint and not pos.get("extended")
                and i == pos["exit_day"] and close[i] >= pos["entry_px"]
                and pos["entry_i"] + 20 <= N - 1):
            pos["exit_day"] = pos["entry_i"] + 20
            pos["extended"] = True
        # 1) scheduled exit
        if pos is not None and i == pos["exit_day"]:
            trades.append(make_rec(pos["entry_i"], i, pos["entry_px"], close[i], cost, pos.get("stopped", False)))
            value *= (close[i] / pos["entry_px"]) * (1 - cost)
            last_exit = i
            pos = None
        # 2) pending delayed entry
        if pos is None and pending is not None and i == pending:
            if i > last_exit:
                value *= (1 - cost)
                pos = dict(entry_i=i, entry_px=close[i], exit_day=min(i + hold_k, N - 1), stopped=False)
                if cap is not None:
                    counts[pending_streak] = counts.get(pending_streak, 0) + 1
            pending = None
        # 3) stop check
        if pos is not None and stop is not None and not pos.get("stopped") and i < pos["exit_day"]:
            if close[i] <= pos["entry_px"] * (1 - stop):
                if stop_delay == 0:
                    trades.append(make_rec(pos["entry_i"], i, pos["entry_px"], close[i], cost, True))
                    value *= (close[i] / pos["entry_px"]) * (1 - cost)
                    last_exit = i
                    pos = None
                else:
                    pos["exit_day"] = min(i + 1, pos["exit_day"])
                    pos["stopped"] = True
        # 4) signal / entry
        if pos is None and pending is None and thrust[i]:
            allowed = cap is None or counts.get(streak[i], 0) < cap
            if allowed:
                if entry_delay == 0:
                    if i > last_exit:
                        value *= (1 - cost)
                        pos = dict(entry_i=i, entry_px=close[i], exit_day=min(i + hold_k, N - 1), stopped=False)
                        if cap is not None:
                            counts[streak[i]] = counts.get(streak[i], 0) + 1
                else:
                    pending = i + 1
                    pending_streak = streak[i]
                    if pending > N - 1:
                        pending = None
        # 5) daily equity
        eq[i] = value * (close[i] / pos["entry_px"]) if pos is not None else value
    if pos is not None:  # data end close-out
        trades.append(make_rec(pos["entry_i"], N - 1, pos["entry_px"], close[N - 1], cost, pos.get("stopped", False)))
        value *= (close[N - 1] / pos["entry_px"]) * (1 - cost)
        eq[N - 1] = value
    return value, eq, pd.DataFrame(trades)


def max_dd(eq):
    peak = np.maximum.accumulate(eq)
    return float((eq / peak - 1).min())


def row_stats(name, value, eq, tr):
    rets = np.diff(eq) / eq[:-1]
    vol = rets.std() * np.sqrt(252)
    sharpe = rets.mean() * 252 / vol if vol > 0 else np.nan
    expos = tr.apply(lambda r: r["exit_i"] - r["entry_i"], axis=1).sum() / (N - 1) if len(tr) else 0
    return dict(name=name, trades=len(tr), win=(tr["net"] > 0).mean() if len(tr) else np.nan,
                mean=tr["net"].mean() if len(tr) else np.nan, med=tr["net"].median() if len(tr) else np.nan,
                worst=tr["net"].min() if len(tr) else np.nan, best=tr["net"].max() if len(tr) else np.nan,
                final=value, cagr=value ** (1 / years) - 1, mdd=max_dd(eq), vol=vol, sharpe=sharpe,
                expos=expos, avg_hold=(tr["exit_i"] - tr["entry_i"]).mean() if len(tr) else np.nan)


def show(rows, title):
    print(f"== {title} ==")
    hdr = f"{'variant':<26} {'trades':>6} {'win%':>5} {'mean':>7} {'med':>7} {'worst':>7} {'final':>8} {'CAGR':>7} {'maxDD':>7} {'vol':>6} {'Sharpe':>6} {'expo%':>6} {'hold':>4}"
    print(hdr)
    for r in rows:
        print(f"{r['name']:<26} {r['trades']:>6} {r['win']*100:>4.0f}% {r['mean']*100:>6.2f}% {r['med']*100:>6.2f}% "
              f"{r['worst']*100:>6.1f}% {r['final']:>7.2f}x {r['cagr']*100:>6.1f}% {r['mdd']*100:>6.1f}% "
              f"{r['vol']*100:>5.1f}% {r['sharpe']:>6.2f} {r['expos']*100:>5.1f}% {r['avg_hold']:>4.1f}")
    print()


# ---- benchmarks ----
show([dict(name="EW buy&hold", trades=0, win=np.nan, mean=np.nan, med=np.nan, worst=np.nan, best=np.nan,
           final=EW[-1] / EW[0], cagr=(EW[-1] / EW[0]) ** (1 / years) - 1, mdd=max_dd(EW),
           vol=np.diff(EW).std() / EW[:-1].std() * 0 , sharpe=np.nan, expos=1.0, avg_hold=np.nan),
      dict(name="VW buy&hold", trades=0, win=np.nan, mean=np.nan, med=np.nan, worst=np.nan, best=np.nan,
           final=VW[-1] / VW[0], cagr=(VW[-1] / VW[0]) ** (1 / years) - 1, mdd=max_dd(VW),
           vol=0, sharpe=np.nan, expos=1.0, avg_hold=np.nan)],
     "benchmarks (buy & hold)")

# recompute bench vol/sharpe properly
for nm, arr in (("EW buy&hold", EW), ("VW buy&hold", VW)):
    rets = np.diff(arr) / arr[:-1]
    print(f"{nm}: vol={rets.std()*np.sqrt(252)*100:.1f}%  sharpe={rets.mean()*252/(rets.std()*np.sqrt(252)):.2f}")
print()

# ---- variants on EW ----
variants = []
r = simulate(EW, entry_delay=0, hold_k=5, cost=0.001)
variants.append(("V1 5d base", r))
base_value, base_eq, base_tr = r
r = simulate(EW, entry_delay=0, hold_k=5, stop=0.05, stop_delay=1, cost=0.001)
variants.append(("V2 5d stop(next close)", r))
r = simulate(EW, entry_delay=0, hold_k=5, stop=0.05, stop_delay=0, cost=0.001)
variants.append(("V3 5d stop(same close)", r))
r = simulate(EW, entry_delay=0, hold_k=5, cap=2, cost=0.001)
variants.append(("V4 5d cap2/wave", r))
r = simulate(EW, entry_delay=0, hold_k=5, stop=0.05, stop_delay=1, cap=2, cost=0.001)
variants.append(("V5 5d cap2+stop", r))
r = simulate(EW, entry_delay=1, hold_k=5, cost=0.001)
variants.append(("V6 5d entry t+1", r))
r = simulate(EW, entry_delay=0, hold_k=5, cost=0.002)
variants.append(("V7 5d cost 0.2%/side", r))
r = simulate(EW, entry_delay=0, hold_k=5, cost=0.001, checkpoint=True)
variants.append(("V8 checkpoint 5->20", r))
r = simulate(EW, entry_delay=0, hold_k=20, cost=0.001)
variants.append(("V9 20d base", r))
r = simulate(EW, entry_delay=0, hold_k=20, stop=0.05, stop_delay=1, cost=0.001)
variants.append(("V10 20d stop", r))
r = simulate(VW, entry_delay=0, hold_k=5, cost=0.001)
variants.append(("V11 5d base on VW", r))
r = simulate(VW, entry_delay=0, hold_k=20, cost=0.001)
variants.append(("V12 20d base on VW", r))

show([row_stats(n, v, e, t) for n, (v, e, t) in variants], "variants (EW unless noted)")

# ---- era split for base & stop ----
def era_table(eq, tr, label):
    print(f"== era split: {label} ==")
    bounds = [("2005-2009", "2005-01-01", "2009-12-31"),
              ("2010-2014", "2010-01-01", "2014-12-31"),
              ("2015-2019", "2015-01-01", "2019-12-31"),
              ("2020-2026", "2020-01-01", "2026-12-31")]
    prev_end_eq = 1.0
    for name, a, b in bounds:
        m = (dates >= a) & (dates <= b)
        iend = np.where(m)[0][-1]
        v = eq[iend] / prev_end_eq
        sub = tr[(tr["entry_date"] >= a) & (tr["entry_date"] <= b)]
        win = (sub["net"] > 0).mean() * 100 if len(sub) else np.nan
        mdd = max_dd(eq[m])
        print(f"  {name}: trades={len(sub):>3}  win={win:>4.0f}%  era_mult={v:.2f}x  era_maxDD={mdd*100:.1f}%")
        prev_end_eq = eq[iend]
    print()


era_table(base_eq, base_tr, "V1 5d base")
_, stop_eq, stop_tr = variants[1][1]
era_table(stop_eq, stop_tr, "V2 5d stop")

# ---- yearly for base ----
print("== yearly: V1 5d base ==")
base_tr["year"] = base_tr["entry_date"].str[:4]
for y, g in base_tr.groupby("year"):
    mult = float(np.prod(1 + g["net"]))
    print(f"  {y}: trades={len(g):>2} win={(g['net']>0).mean()*100:>3.0f}% year_mult={mult:.3f}")
print()

# ---- details ----
print("== V1 base: worst 6 / best 4 trades ==")
for _, row in base_tr.nsmallest(6, "net").iterrows():
    print(f"  {row['entry_date']} -> {row['exit_date']}  net {row['net']*100:+.1f}%")
for _, row in base_tr.nlargest(4, "net").iterrows():
    print(f"  {row['entry_date']} -> {row['exit_date']}  net {row['net']*100:+.1f}%")
print()
print("== V1 base: last 10 trades ==")
for _, row in base_tr.tail(10).iterrows():
    print(f"  {row['entry_date']} -> {row['exit_date']}  net {row['net']*100:+.2f}%")
print()

# stops info
_, _, stop_tr = variants[1][1]
print(f"stop triggers: {int(stop_tr['stopped'].sum())} / {len(stop_tr)} trades")
_, _, cap_tr = variants[3][1]
print(f"cap2 trades: {len(cap_tr)} vs base {len(base_tr)}")

# ---- save ----
eq_df = pd.DataFrame({
    "date": [d.strftime("%Y-%m-%d") for d in dates],
    "ew_bh": EW, "vw_bh": VW,
    "v1_base": base_eq,
    "v2_stop": variants[1][1][1],
    "v4_cap2": variants[3][1][1],
    "v5_cap2stop": variants[4][1][1],
    "v9_20d": variants[8][1][1],
})
eq_df.to_csv(f"{BASE}/out/bt1_equity.csv", index=False)
base_tr.to_csv(f"{BASE}/out/bt1_trades_base.csv", index=False)
print("saved: out/bt1_equity.csv  out/bt1_trades_base.csv")
