#!/usr/bin/env python3
"""Huang Yang PE-band backtest.

Method (from transcript 2025-03-07):
  - Build weekly PE(TTM) series for a stable company.
  - Rolling mean mu & std sigma of past PE.
  - Low line = mu - 1*sigma; High line = mu + 1*sigma.
  - Trade translation: PE < low -> enter (full position); PE > high -> exit.
  - No look-ahead: mu/sigma use rolling window ending at current week;
    position takes effect next week (shift(1)).

Outputs:
  - per-stock strategy vs buy&hold stats (5y and 8y windows)
  - event study: forward returns after low-band vs high-band touches
  - current snapshot (2026-10-14): PE vs bands
"""
import json
import os

import numpy as np
import pandas as pd

DATA = os.path.expanduser("~/stock-scripts/huangyang_backtest/data")
OUT = os.path.expanduser("~/stock-scripts/huangyang_backtest/out")
os.makedirs(OUT, exist_ok=True)


def load_one(path):
    d = json.load(open(path))
    code, name = d["code"], d["name"]
    db = pd.DataFrame(d["db"])
    adj = pd.DataFrame(d["adj"])
    if db.empty:
        return None
    db["trade_date"] = pd.to_datetime(db["trade_date"], format="%Y%m%d")
    adj["trade_date"] = pd.to_datetime(adj["trade_date"], format="%Y%m%d")
    db["close"] = pd.to_numeric(db["close"], errors="coerce")
    db["pe_ttm"] = pd.to_numeric(db["pe_ttm"], errors="coerce")
    adj["adj_factor"] = pd.to_numeric(adj["adj_factor"], errors="coerce")
    df = db.merge(adj[["trade_date", "adj_factor"]], on="trade_date", how="left")
    df = df.sort_values("trade_date")
    df["adj_factor"] = df["adj_factor"].ffill().bfill()
    df["adj_close"] = df["close"] * df["adj_factor"]
    df = df.set_index("trade_date")
    wk = df.resample("W-FRI").last()
    wk = wk[wk["close"].notna()]
    return code, name, wk


def run_band(wk, window, min_periods, k=1.0, cost=0.001):
    pe = wk["pe_ttm"]
    pe_valid = pe.where(pe > 0)
    mu = pe_valid.rolling(window, min_periods=min_periods).mean()
    sd = pe_valid.rolling(window, min_periods=min_periods).std(ddof=0)  # Excel STDEV.P 口径
    low, high = mu - k * sd, mu + k * sd

    pos = 0.0
    sig = []
    for i in range(len(wk)):
        p = pe.iloc[i]
        if np.isnan(mu.iloc[i]) or np.isnan(p) or p <= 0:
            sig.append(pos)
            continue
        if pos == 0 and p < low.iloc[i]:
            pos = 1.0
        elif pos == 1 and p > high.iloc[i]:
            pos = 0.0
        sig.append(pos)
    signal = pd.Series(sig, index=wk.index)
    ret = wk["adj_close"].pct_change().fillna(0.0)
    pos_eff = signal.shift(1).fillna(0.0)
    turnover = pos_eff.diff().abs().fillna(0.0)
    strat = pos_eff * ret - turnover * cost
    eq_s = (1 + strat).cumprod()
    eq_b = (1 + ret).cumprod()
    return dict(signal=signal, mu=mu, sd=sd, low=low, high=high,
                eq_s=eq_s, eq_b=eq_b, ret=ret, strat_ret=strat)


def stats(eq):
    eq = eq / eq.iloc[0]  # 窗口起点归一，避免把窗口前的涨幅算进 CAGR
    total = float(eq.iloc[-1] - 1)
    years = max((eq.index[-1] - eq.index[0]).days / 365.25, 1e-9)
    cagr = float(eq.iloc[-1] ** (1 / years) - 1)
    dd = float((eq / eq.cummax() - 1).min())
    return total, cagr, dd


def trades(signal):
    d = signal.diff().fillna(signal.iloc[0])
    n_buy = int((d > 0).sum())
    n_sell = int((d < 0).sum())
    return n_buy, n_sell


def event_study(wk, res, horizon_weeks):
    """Forward return after PE < low (enter zone) vs PE > high (exit zone)."""
    pe, mu, low, high = wk["pe_ttm"], res["mu"], res["low"], res["high"]
    fwd = wk["adj_close"].shift(-horizon_weeks) / wk["adj_close"] - 1
    valid = (pe > 0) & mu.notna() & fwd.notna()
    low_ev = valid & (pe < low)
    high_ev = valid & (pe > high)
    lo = fwd[low_ev].dropna()
    hi = fwd[high_ev].dropna()
    base = fwd[valid].dropna()
    return dict(n_lo=len(lo), r_lo=float(lo.mean()) if len(lo) else np.nan,
                win_lo=float((lo > 0).mean()) if len(lo) else np.nan,
                n_hi=len(hi), r_hi=float(hi.mean()) if len(hi) else np.nan,
                win_hi=float((hi > 0).mean()) if len(hi) else np.nan,
                n_base=len(base), r_base=float(base.mean()) if len(base) else np.nan)


def main():
    files = sorted(f for f in os.listdir(DATA) if f.endswith(".json"))
    rows5, rows8, events5, snaps = [], [], [], []

    for f in files:
        loaded = load_one(os.path.join(DATA, f))
        if loaded is None:
            continue
        code, name, wk = loaded
        for window, minp, rows, label in (
            (260, 156, rows5, "5y"),
            (416, 208, rows8, "8y"),
        ):
            res = run_band(wk, window=window, min_periods=minp)
            # restrict comparison period to first live week (mu available, i.e. strategy window)
            live = res["mu"].notna()
            if live.sum() < 52:
                rows.append(dict(code=code, name=name, live_weeks=int(live.sum()), note="too short"))
                continue
            idx = wk.index[live]
            t_s, c_s, dd_s = stats(res["eq_s"].loc[idx])
            t_b, c_b, dd_b = stats(res["eq_b"].loc[idx])
            nb, ns = trades(res["signal"])
            rows.append(dict(code=code, name=name, window=label,
                             start=str(idx[0].date()), weeks=int(live.sum()),
                             n_buy=nb, n_sell=ns,
                             total_s=round(t_s * 100, 1), cagr_s=round(c_s * 100, 2),
                             dd_s=round(dd_s * 100, 1),
                             total_b=round(t_b * 100, 1), cagr_b=round(c_b * 100, 2),
                             dd_b=round(dd_b * 100, 1),
                             excess=round((c_s - c_b) * 100, 2)))
        # event study on 5y window run
        res5 = run_band(wk, 260, 156)
        for h, hl in ((26, "0.5y"), (52, "1y")):
            ev = event_study(wk, res5, h)
            ev.update(code=code, name=name, horizon=hl)
            events5.append(ev)
        # snapshot latest
        pe_last = wk["pe_ttm"].iloc[-1]
        mu_l, sd_l, lo_l, hi_l = (res5["mu"].iloc[-1], res5["sd"].iloc[-1],
                                  res5["low"].iloc[-1], res5["high"].iloc[-1])
        dt = str(wk.index[-1].date())
        if not np.isnan(mu_l):
            if pe_last < lo_l:
                zone = "below_low"
            elif pe_last > hi_l:
                zone = "above_high"
            else:
                zone = "mid"
        else:
            zone = "n/a"
        snaps.append(dict(code=code, name=name, date=dt, pe=pe_last,
                          mu=mu_l, sd=sd_l, low=lo_l, high=hi_l, zone=zone))

    df5 = pd.DataFrame(rows5)
    df8 = pd.DataFrame(rows8)
    ev = pd.DataFrame(events5)
    sn = pd.DataFrame(snaps)
    df5.to_csv(os.path.join(OUT, "backtest_5y.csv"), index=False)
    df8.to_csv(os.path.join(OUT, "backtest_8y.csv"), index=False)
    ev.to_csv(os.path.join(OUT, "event_study.csv"), index=False)
    sn.to_csv(os.path.join(OUT, "snapshot.csv"), index=False)

    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 50)
    print("=== BACKTEST 5Y WINDOW ===")
    print(df5.to_string(index=False))
    print()
    print("=== BACKTEST 8Y WINDOW ===")
    print(df8.to_string(index=False))
    print()
    print("=== EVENT STUDY (5y window) ===")
    print(ev.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print()
    print("=== SNAPSHOT 2026-10-14 (5y window) ===")
    print(sn.to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    # aggregate
    if len(df5):
        d = df5[df5["excess"].notna()]
        print()
        print(f"5y window aggregate: n={len(d)}, strategy CAGR mean={d['cagr_s'].mean():.2f}%, "
              f"bench CAGR mean={d['cagr_b'].mean():.2f}%, excess mean={d['excess'].mean():.2f}pp, "
              f"win={(d['excess'] > 0).mean() * 100:.0f}% stocks")


if __name__ == "__main__":
    main()
