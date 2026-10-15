#!/usr/bin/env python3
"""Supplement tests for Huang Yang PE-band backtest.

A. k sensitivity (k = 0.5 / 1.0 / 1.5) on 5y window
B. Risk-adjusted: Calmar (CAGR / |MaxDD|) strategy vs bench
C. Year-by-year decomposition (k=1.0)
D. Portfolio version: equal-weight 17 names, band-signal positions, 2016-10 onward
"""
import json
import os

import numpy as np
import pandas as pd

DATA = os.path.expanduser("~/stock-scripts/huangyang_backtest/data")
OUT = os.path.expanduser("~/stock-scripts/huangyang_backtest/out")


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


def bands(wk, window=260, min_periods=156, k=1.0):
    pe = wk["pe_ttm"]
    pe_valid = pe.where(pe > 0)
    mu = pe_valid.rolling(window, min_periods=min_periods).mean()
    sd = pe_valid.rolling(window, min_periods=min_periods).std(ddof=0)  # Excel STDEV.P 口径
    return pe, mu, sd, mu - k * sd, mu + k * sd


def signal_series(pe, mu, low, high):
    pos = 0.0
    sig = []
    for i in range(len(pe)):
        p = pe.iloc[i]
        if np.isnan(mu.iloc[i]) or np.isnan(p) or p <= 0:
            sig.append(pos)
            continue
        if pos == 0 and p < low.iloc[i]:
            pos = 1.0
        elif pos == 1 and p > high.iloc[i]:
            pos = 0.0
        sig.append(pos)
    return pd.Series(sig, index=pe.index)


def cagr_dd(eq):
    eq = eq / eq.iloc[0]  # 窗口起点归一
    years = max((eq.index[-1] - eq.index[0]).days / 365.25, 1e-9)
    c = float(eq.iloc[-1] ** (1 / years) - 1)
    dd = float((eq / eq.cummax() - 1).min())
    return c, dd


def main():
    files = sorted(f for f in os.listdir(DATA) if f.endswith(".json"))
    all_data = {}
    for f in files:
        loaded = load_one(os.path.join(DATA, f))
        if loaded is None:
            continue
        code, name, wk = loaded
        all_data[code] = (name, wk)

    # ---- A. k sensitivity
    rows = []
    for k in (0.5, 1.0, 1.5):
        for code, (name, wk) in all_data.items():
            pe, mu, sd, low, high = bands(wk, k=k)
            live = mu.notna()
            if live.sum() < 52:
                continue
            idx = wk.index[live]
            ret = wk["adj_close"].pct_change().fillna(0.0)
            sig = signal_series(pe, mu, low, high)
            pos = sig.shift(1).fillna(0.0)
            trn = pos.diff().abs().fillna(0.0)
            strat = pos * ret - trn * 0.001
            eqs = (1 + strat).cumprod().loc[idx]
            eqb = (1 + ret).cumprod().loc[idx]
            cs, _ = cagr_dd(eqs)
            cb, _ = cagr_dd(eqb)
            rows.append(dict(k=k, code=code, name=name, cagr_s=cs * 100, cagr_b=cb * 100,
                             excess=(cs - cb) * 100))
    ks = pd.DataFrame(rows)
    piv = ks.pivot_table(index="name", columns="k", values="excess", aggfunc="mean")
    print("=== A. k sensitivity: excess CAGR (pp), 5y window ===")
    print(piv.round(2).to_string())
    print("\nMean excess by k:")
    print(ks.groupby("k")["excess"].agg(["mean", "median", "count"]).round(2).to_string())
    ks.to_csv(os.path.join(OUT, "k_sensitivity.csv"), index=False)

    # ---- B. Calmar comparison (k=1.0)
    rows = []
    for code, (name, wk) in all_data.items():
        pe, mu, sd, low, high = bands(wk, k=1.0)
        live = mu.notna()
        if live.sum() < 52:
            continue
        idx = wk.index[live]
        ret = wk["adj_close"].pct_change().fillna(0.0)
        sig = signal_series(pe, mu, low, high)
        pos = sig.shift(1).fillna(0.0)
        trn = pos.diff().abs().fillna(0.0)
        strat = pos * ret - trn * 0.001
        eqs = (1 + strat).cumprod().loc[idx]
        eqb = (1 + ret).cumprod().loc[idx]
        cs, dds = cagr_dd(eqs)
        cb, ddb = cagr_dd(eqb)
        rows.append(dict(name=name, calmar_s=cs / max(abs(dds), 1e-9),
                         calmar_b=cb / max(abs(ddb), 1e-9),
                         dd_s=dds * 100, dd_b=ddb * 100))
    cal = pd.DataFrame(rows)
    cal["calmar_diff"] = cal["calmar_s"] - cal["calmar_b"]
    print("\n=== B. Calmar ratio (CAGR/|MaxDD|), k=1.0, 5y ===")
    print(cal.round(2).to_string(index=False))
    print(f"\nMean Calmar: strategy {cal['calmar_s'].mean():.2f} vs bench {cal['calmar_b'].mean():.2f}")
    cal.to_csv(os.path.join(OUT, "calmar.csv"), index=False)

    # ---- C. Year-by-year (k=1.0): average across names
    yr = {}
    for code, (name, wk) in all_data.items():
        pe, mu, sd, low, high = bands(wk, k=1.0)
        live = mu.notna()
        if live.sum() < 52:
            continue
        ret = wk["adj_close"].pct_change().fillna(0.0)
        sig = signal_series(pe, mu, low, high)
        pos = sig.shift(1).fillna(0.0)
        trn = pos.diff().abs().fillna(0.0)
        strat = (pos * ret - trn * 0.001)
        for y in range(2012, 2027):
            m = (strat.index.year == y) & live.values
            if m.sum() < 10:
                continue
            s_y = float((1 + strat[m]).prod() - 1)
            b_y = float((1 + ret[m]).prod() - 1)
            yr.setdefault(y, []).append((s_y, b_y))
    print("\n=== C. Yearly avg returns: strategy vs bench (names with data that year) ===")
    yrows = []
    for y in sorted(yr):
        arr = np.array(yr[y])
        yrows.append(dict(year=y, strat=arr[:, 0].mean() * 100, bench=arr[:, 1].mean() * 100,
                          n=len(arr)))
    yd = pd.DataFrame(yrows)
    print(yd.round(2).to_string(index=False))
    yd.to_csv(os.path.join(OUT, "yearly.csv"), index=False)

    # ---- D. Portfolio: equal weight, signal-based positions, from 2016-10
    start = pd.Timestamp("2016-10-14")
    frames_s, frames_b = [], []
    for code, (name, wk) in all_data.items():
        pe, mu, sd, low, high = bands(wk, k=1.0)
        ret = wk["adj_close"].pct_change().fillna(0.0)
        sig = signal_series(pe, mu, low, high)
        pos = sig.shift(1).fillna(0.0)
        trn = pos.diff().abs().fillna(0.0)
        strat = pos * ret - trn * 0.001
        s = pd.Series(strat.values, index=wk.index, name=code)
        b = pd.Series(ret.values, index=wk.index, name=code)
        s = s[s.index >= start]
        b = b[b.index >= start]
        frames_s.append(s)
        frames_b.append(b)
    S = pd.concat(frames_s, axis=1)
    B = pd.concat(frames_b, axis=1)
    # equal weight: mean across available names each week
    port_s = S.mean(axis=1)
    port_b = B.mean(axis=1)
    eqs = (1 + port_s).cumprod()
    eqb = (1 + port_b).cumprod()
    cs = float(eqs.iloc[-1] ** (1 / ((eqs.index[-1] - eqs.index[0]).days / 365.25)) - 1)
    cb = float(eqb.iloc[-1] ** (1 / ((eqb.index[-1] - eqb.index[0]).days / 365.25)) - 1)
    dds = float((eqs / eqs.cummax() - 1).min())
    ddb = float((eqb / eqb.cummax() - 1).min())
    print("\n=== D. Portfolio (equal weight 17 names), 2016-10 → 2026-10 ===")
    print(f"Strategy: total {eqs.iloc[-1] - 1:.1%}, CAGR {cs:.2%}, MaxDD {dds:.1%}")
    print(f"Bench   : total {eqb.iloc[-1] - 1:.1%}, CAGR {cb:.2%}, MaxDD {ddb:.1%}")
    pd.DataFrame({"s": eqs, "b": eqb}).to_csv(os.path.join(OUT, "portfolio_curves.csv"))


if __name__ == "__main__":
    main()
