#!/usr/bin/env python3
"""Position-tilt variants of the PE band, using Huang Yang's own weights.

Source (2025-06-22, index PE band, applied here to each name's own band):
  below low line: 100%
  around the mean: 70%
  above high line: 50% or below
Plus the portfolio rebalance he described the same day: sell the expensive,
buy the cheap, keep ~10% cash.

No look-ahead: this week's z sets next week's weight. Cost 10bp on traded notional.
Equity is renormalized at the start of the comparison window.
"""
import json
import os

import numpy as np
import pandas as pd

DATA = os.path.expanduser("~/stock-scripts/huangyang_backtest/data")
OUT = os.path.expanduser("~/stock-scripts/huangyang_backtest/out")
COST = 0.001


def load_all():
    out = {}
    for f in sorted(os.listdir(DATA)):
        if not f.endswith(".json"):
            continue
        d = json.load(open(os.path.join(DATA, f)))
        db = pd.DataFrame(d["db"])
        adj = pd.DataFrame(d["adj"])
        if db.empty:
            continue
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
        out[d["code"]] = (d["name"], wk)
    return out


def zscore(wk, window, minp):
    pe = wk["pe_ttm"].where(wk["pe_ttm"] > 0)
    mu = pe.rolling(window, min_periods=minp).mean()
    sd = pe.rolling(window, min_periods=minp).std(ddof=0)
    z = (pe - mu) / sd
    return z


def w_step(z, high=0.50):
    """Flat bands: < -1 → 100%, [-1, 1] → 70%, > 1 → high."""
    w = pd.Series(np.nan, index=z.index)
    ok = z.notna()
    w[ok & (z < -1)] = 1.00
    w[ok & (z >= -1) & (z <= 1)] = 0.70
    w[ok & (z > 1)] = high
    return w.ffill()


def w_linear(z, high=0.50):
    """Hits his three anchors: z=-1 → 100%, z=0 → 70%, z=+1 → high. Flat outside."""
    w = pd.Series(np.nan, index=z.index)
    ok = z.notna()
    zz = z[ok]
    out = pd.Series(np.nan, index=zz.index)
    out[zz <= -1] = 1.00
    m = (zz > -1) & (zz < 0)
    out[m] = 1.00 - 0.30 * (zz[m] + 1)
    m = (zz >= 0) & (zz < 1)
    out[m] = 0.70 - (0.70 - high) * zz[m]
    out[zz >= 1] = high
    w[ok] = out
    return w.ffill()


def w_binary(z):
    """Previous mechanical rule, for the same code path."""
    pos = 0.0
    sig = []
    for v in z:
        if np.isnan(v):
            sig.append(pos)
            continue
        if pos == 0 and v < -1:
            pos = 1.0
        elif pos == 1 and v > 1:
            pos = 0.0
        sig.append(pos)
    return pd.Series(sig, index=z.index)


def apply_pos(wk, w):
    ret = wk["adj_close"].pct_change().fillna(0.0)
    pos = w.shift(1)
    # first week: use the first known weight, do not start from an artificial 0
    if pos.isna().any():
        pos = pos.fillna(w.dropna().iloc[0] if w.notna().any() else 0.0)
    trn = pos.diff().abs().fillna(0.0)
    strat = pos * ret - trn * COST
    return ret, strat, pos


def cagr_dd(eq):
    eq = eq / eq.iloc[0]
    years = max((eq.index[-1] - eq.index[0]).days / 365.25, 1e-9)
    cagr = float(eq.iloc[-1] ** (1 / years) - 1)
    dd = float((eq / eq.cummax() - 1).min())
    return cagr, dd, float(eq.iloc[-1] - 1)


def per_name(all_data, window, minp, label):
    rows = []
    schemes = {
        "binary": lambda z: w_binary(z),
        "step_50": lambda z: w_step(z, 0.50),
        "step_30": lambda z: w_step(z, 0.30),
        "linear_50": lambda z: w_linear(z, 0.50),
    }
    for code, (name, wk) in all_data.items():
        z = zscore(wk, window, minp)
        live = z.notna()
        if live.sum() < 52:
            continue
        idx = wk.index[live]
        ret_b = wk["adj_close"].pct_change().fillna(0.0)
        eq_b = (1 + ret_b).cumprod().loc[idx]
        cb, ddb, _ = cagr_dd(eq_b)
        row = dict(name=name, cagr_b=cb * 100, dd_b=ddb * 100)
        for sn, fn in schemes.items():
            w = fn(z)
            _, strat, pos = apply_pos(wk, w)
            eq = (1 + strat).cumprod().loc[idx]
            c, dd, _ = cagr_dd(eq)
            row[f"cagr_{sn}"] = c * 100
            row[f"dd_{sn}"] = dd * 100
            row[f"ex_{sn}"] = (c - cb) * 100
            row[f"avg_w_{sn}"] = float(pos.loc[idx].mean())
        rows.append(row)
    df = pd.DataFrame(rows)
    print(f"\n===== per-name {label}  n={len(df)} =====")
    for sn in ("binary", "step_50", "step_30", "linear_50"):
        print(f"{sn:10}  cagr {df[f'cagr_{sn}'].mean():5.2f}  vs bench {df['cagr_b'].mean():5.2f}  "
              f"excess {df[f'ex_{sn}'].mean():+5.2f}  med {df[f'ex_{sn}'].median():+5.2f}  "
              f"beat {(df[f'ex_{sn}']>0).sum()}/{len(df)}  "
              f"dd {df[f'dd_{sn}'].mean():5.1f} vs {df['dd_b'].mean():5.1f}  "
              f"avg weight {df[f'avg_w_{sn}'].mean():.0%}")
    return df


def portfolio(all_data, window, minp, start, label):
    """Equal-weight book vs valuation-tilt book.

    tilt: score 2 / 1 / 0.5 by zone, renormalize, optional 10% cash.
    Weights known at week open (z shifted).
    """
    rets, zs = [], []
    for code, (name, wk) in all_data.items():
        z = zscore(wk, window, minp)
        ret = wk["adj_close"].pct_change().fillna(0.0)
        rets.append(ret.rename(code))
        zs.append(z.rename(code))
    R = pd.concat(rets, axis=1).sort_index()
    Z = pd.concat(zs, axis=1).reindex(R.index)
    Z_lag = Z.shift(1)
    R = R[R.index >= start]
    Z_lag = Z_lag.loc[R.index]

    def book(weight_fn, cash=0.0):
        W = weight_fn(Z_lag)
        # names without a band this week drop out; remaining scores sum to 1-cash
        W = W.where(Z_lag.notna())
        denom = W.sum(axis=1).replace(0, np.nan)
        W = W.div(denom, axis=0) * (1 - cash)
        W = W.fillna(0.0)
        dW = W.diff().abs().fillna(0.0)
        port = (W * R.fillna(0.0)).sum(axis=1) - dW.sum(axis=1) * COST
        # weeks with nobody invested: pure cash
        return port

    def score_zones(Zlag):
        S = pd.DataFrame(np.nan, index=Zlag.index, columns=Zlag.columns)
        S = S.where(Zlag.isna(), 1.0)
        S = S.mask(Zlag < -1, 2.0)
        S = S.mask(Zlag > 1, 0.5)
        return S

    def equal(Zlag):
        return pd.DataFrame(1.0, index=Zlag.index, columns=Zlag.columns)

    series = {
        "buyhold": book(equal, cash=0.0),
        "cash10_only": book(equal, cash=0.10),
        "tilt_rebalance": book(score_zones, cash=0.0),
        "tilt_plus_cash10": book(score_zones, cash=0.10),
    }
    # binary sleeve: each name 0/1, equal-weight the resulting returns (old portfolio)
    bin_cols = []
    for code, (name, wk) in all_data.items():
        z = zscore(wk, window, minp)
        w = w_binary(z)
        ret, strat, _ = apply_pos(wk, w)
        bin_cols.append(strat.rename(code).reindex(R.index))
    series["binary_cash"] = pd.concat(bin_cols, axis=1).mean(axis=1)

    print(f"\n===== portfolio {label}  {R.index[0].date()} → {R.index[-1].date()} =====")
    for k, s in series.items():
        eq = (1 + s.fillna(0)).cumprod()
        c, dd, tot = cagr_dd(eq)
        print(f"{k:18}  total {tot:7.1%}  CAGR {c:6.2%}  MaxDD {dd:6.1%}")

    # current target weights on last week with any z
    last = Z.dropna(how="all").index[-1]
    z_now = Z.loc[last]
    names = {c: n for c, (n, _) in all_data.items()}
    snap = pd.DataFrame({"name": z_now.index.map(names), "z": z_now.values})
    snap = snap.dropna()
    sc = np.where(snap["z"] < -1, 2.0, np.where(snap["z"] > 1, 0.5, 1.0))
    snap["w_rebalance"] = sc / sc.sum()
    snap["w_cash10"] = snap["w_rebalance"] * 0.9
    snap["zone"] = np.where(snap["z"] < -1, "low", np.where(snap["z"] > 1, "high", "mid"))
    print(f"\ncurrent book as of week labeled {last.date()} (z uses that week's PE)")
    print(snap.sort_values("z").round(3).to_string(index=False))
    print(f"cash sleeve if 10% reserve: 10%   invested {snap['w_cash10'].sum():.0%}")


def main():
    data = load_all()
    print(f"loaded {len(data)} names")
    per_name(data, 260, 156, "5y window")
    per_name(data, 416, 208, "8y window")
    portfolio(data, 416, 208, pd.Timestamp("2016-10-14"), "8y band, from 2016-10")
    portfolio(data, 260, 156, pd.Timestamp("2016-10-14"), "5y band, from 2016-10")


if __name__ == "__main__":
    main()
