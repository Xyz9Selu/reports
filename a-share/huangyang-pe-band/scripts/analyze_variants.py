#!/usr/bin/env python3
"""Variants + charts for Huang Yang PE-band backtest.

V2: buy-and-hold after first low-band (PE < mu-sigma) touch, never sell.
    Tests the "enter zone" signal alone (Huang Yang's actual phrasing:
    low line = increase attention / watch; high line = be aware of risk).
Charts: equity comparison, event study bars, CAGR scatter.
"""
import json
import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

DATA = os.path.expanduser("~/stock-scripts/huangyang_backtest/data")
OUT = os.path.expanduser("~/stock-scripts/huangyang_backtest/out")
ASSETS = os.path.expanduser("~/stock-scripts/huangyang_backtest/assets")
os.makedirs(OUT, exist_ok=True)
os.makedirs(ASSETS, exist_ok=True)

zh = fm.FontProperties(fname="/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc")
plt.rcParams["axes.unicode_minus"] = False


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


def band_series(wk, window=260, min_periods=156, k=1.0):
    pe = wk["pe_ttm"]
    pe_valid = pe.where(pe > 0)
    mu = pe_valid.rolling(window, min_periods=min_periods).mean()
    sd = pe_valid.rolling(window, min_periods=min_periods).std(ddof=0)  # Excel STDEV.P 口径
    return pe, mu, sd, mu - k * sd, mu + k * sd


def stats(eq):
    eq = eq / eq.iloc[0]  # 窗口起点归一
    total = float(eq.iloc[-1] - 1)
    years = max((eq.index[-1] - eq.index[0]).days / 365.25, 1e-9)
    cagr = float(eq.iloc[-1] ** (1 / years) - 1)
    dd = float((eq / eq.cummax() - 1).min())
    return total, cagr, dd


def main():
    files = sorted(f for f in os.listdir(DATA) if f.endswith(".json"))
    rows = []
    curves = {}
    for f in files:
        loaded = load_one(os.path.join(DATA, f))
        if loaded is None:
            continue
        code, name, wk = loaded
        pe, mu, sd, low, high = band_series(wk)
        live = mu.notna()
        if live.sum() < 52:
            continue
        idx = wk.index[live]
        ret = wk["adj_close"].pct_change().fillna(0.0)

        # V2: once PE first goes below low -> hold forever (no sell)
        state = 0.0
        v2 = []
        for i in range(len(wk)):
            p = pe.iloc[i]
            if mu.iloc[i] is not np.nan and not np.isnan(mu.iloc[i]) and not np.isnan(p) and p > 0:
                if p < low.iloc[i]:
                    state = 1.0
            v2.append(state)
        v2 = pd.Series(v2, index=wk.index)
        pos2 = v2.shift(1).fillna(0.0)
        r2 = pos2 * ret
        eq2 = (1 + r2).cumprod().loc[idx]
        eqb = (1 + ret).cumprod().loc[idx]

        t2, c2, dd2 = stats(eq2)
        tb, cb, ddb = stats(eqb)
        # first entry date
        first_entry = None
        d2 = v2.diff().fillna(0)
        ent = v2.index[d2 > 0]
        if len(ent):
            first_entry = str(ent[0].date())
        rows.append(dict(code=code, name=name,
                         v2_start=first_entry, v2_total=round(t2 * 100, 1),
                         v2_cagr=round(c2 * 100, 2), v2_dd=round(dd2 * 100, 1),
                         b_total=round(tb * 100, 1), b_cagr=round(cb * 100, 2),
                         b_dd=round(ddb * 100, 1)))

        if code in ("000651.SZ", "600519.SH", "600036.SH", "601006.SH"):
            curves[code] = dict(name=name, idx=idx, ret=ret, low=low, high=high)

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "variant_v2_hold.csv"), index=False)
    print("=== V2: buy after first low touch, hold forever (vs buy&hold, same window) ===")
    print(df.to_string(index=False))
    d = df
    print(f"\nV2 aggregate: n={len(d)}, V2 CAGR mean={d['v2_cagr'].mean():.2f}%, "
          f"bench CAGR mean={d['b_cagr'].mean():.2f}%")
    print(f"V2 avg drawdown {d['v2_dd'].mean():.1f}% vs bench {d['b_dd'].mean():.1f}%")

    # ---- chart 1: equity curves for 4 names (V1 band strategy vs buy&hold)
    sel = [("000651.SZ", "格力电器"), ("600519.SH", "贵州茅台"), ("600036.SH", "招商银行"), ("601006.SH", "大秦铁路")]
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 7.6), dpi=120)
    fig.patch.set_facecolor("#f8fafc")
    for ax, (code, nm) in zip(axes.ravel(), sel):
        loaded = load_one(os.path.join(DATA, f"{code}.json"))
        _, _, wk = loaded
        pe, mu, sd, low, high = band_series(wk)
        live = mu.notna()
        idx = wk.index[live]
        ret = wk["adj_close"].pct_change().fillna(0.0)
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
        sig = pd.Series(sig, index=wk.index)
        pe_eff = sig.shift(1).fillna(0.0)
        trn = pe_eff.diff().abs().fillna(0.0)
        strat = pe_eff * ret - trn * 0.001
        eqs = (1 + strat).cumprod().loc[idx]
        eqb = (1 + ret).cumprod().loc[idx]
        eqs, eqb = eqs / eqs.iloc[0], eqb / eqb.iloc[0]
        ax.set_facecolor("#f8fafc")
        ax.plot(eqs.index, eqs.values, color="#b91c1c", lw=1.9, label="黄阳带策略（低线买/高线卖）")
        ax.plot(eqb.index, eqb.values, color="#1d4ed8", lw=1.9, label="买入持有")
        ax.set_title(nm, fontproperties=zh, fontsize=12, pad=6)
        ax.grid(alpha=0.25)
        for sp in ax.spines.values():
            sp.set_color("#e2e8f0")
        ax.tick_params(labelsize=8.5)
        if (code, nm) == sel[0]:
            ax.legend(prop=zh, frameon=False, fontsize=9)
    fig.suptitle("PE 均值±1σ 机械策略 vs 买入持有（净值，同一窗口）", fontproperties=zh, fontsize=13.5, y=1.0)
    fig.tight_layout()
    fig.savefig(os.path.join(ASSETS, "chart_equity.png"), bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()

    # ---- chart 2: event study bars (1y forward returns: after low vs after high)
    ev = pd.read_csv(os.path.join(OUT, "event_study.csv"))
    ev1 = ev[ev["horizon"] == "1y"].copy()
    order = ev1.sort_values("r_lo", ascending=False)
    x = np.arange(len(order))
    fig, ax = plt.subplots(figsize=(13.6, 5.4), dpi=120)
    fig.patch.set_facecolor("#f8fafc")
    ax.set_facecolor("#f8fafc")
    w = 0.38
    ax.bar(x - w / 2, order["r_lo"] * 100, w, color="#15803d", label="PE 跌破低线之后 1 年")
    ax.bar(x + w / 2, order["r_hi"] * 100, w, color="#b91c1c", label="PE 突破高线之后 1 年")
    ax.axhline(0, color="#334155", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(order["name"], fontproperties=zh, fontsize=9, rotation=28, ha="right")
    ax.set_ylabel("未来 1 年平均收益 (%)", fontproperties=zh, fontsize=11)
    ax.set_title("信号触发后的未来 1 年收益：低线信号 vs 高线信号（5 年窗口）", fontproperties=zh, fontsize=13, pad=12)
    ax.legend(prop=zh, frameon=False, fontsize=10)
    ax.grid(axis="y", alpha=0.25)
    for sp in ax.spines.values():
        sp.set_color("#e2e8f0")
    fig.tight_layout()
    fig.savefig(os.path.join(ASSETS, "chart_event.png"), bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()

    # ---- chart 3: scatter CAGR strategy vs bench + drawdown compare (horizontal)
    bt = pd.read_csv(os.path.join(OUT, "backtest_5y.csv"))
    bt = bt[bt["excess"].notna()]
    fig, axes = plt.subplots(1, 2, figsize=(13.8, 6.2), dpi=120,
                             gridspec_kw={"width_ratios": [1, 1.15]})
    fig.patch.set_facecolor("#f8fafc")
    ax = axes[0]
    ax.set_facecolor("#f8fafc")
    d = bt.sort_values("excess")
    yy = np.arange(len(d))
    cvals = ["#15803d" if v > 0 else "#b91c1c" for v in d["excess"]]
    ax.barh(yy, d["excess"], 0.62, color=cvals, zorder=3)
    ax.axvline(0, color="#334155", lw=0.9)
    ax.set_yticks(yy)
    ax.set_yticklabels(d["name"], fontproperties=zh, fontsize=9)
    ax.set_xlabel("策略 − 买入持有 年化收益差（pp）", fontproperties=zh, fontsize=10.5)
    ax.set_title("年化收益差（5 年窗口，负 = 跑输买入持有）", fontproperties=zh, fontsize=12)
    ax.grid(axis="x", alpha=0.25, zorder=0)
    for sp in ax.spines.values():
        sp.set_color("#e2e8f0")
    for yi, v in zip(yy, d["excess"]):
        ax.text(v + (0.4 if v >= 0 else -0.4), yi, f"{v:+.1f}", va="center",
                ha="left" if v >= 0 else "right", fontproperties=zh, fontsize=8, color="#334155")
    ax.margins(x=0.22)

    ax = axes[1]
    ax.set_facecolor("#f8fafc")
    order2 = bt.sort_values("dd_b", ascending=False)
    y2 = np.arange(len(order2))
    ax.barh(y2 - 0.19, order2["dd_s"], 0.36, color="#b91c1c", label="策略最大回撤", zorder=3)
    ax.barh(y2 + 0.19, order2["dd_b"], 0.36, color="#1d4ed8", label="买入持有最大回撤", zorder=3)
    ax.set_yticks(y2)
    ax.set_yticklabels(order2["name"], fontproperties=zh, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlim(-100, 5)
    ax.set_xlabel("最大回撤 (%)", fontproperties=zh, fontsize=10.5)
    ax.set_title("最大回撤对比（17 只）", fontproperties=zh, fontsize=12)
    ax.legend(prop=zh, frameon=False, fontsize=9, loc="upper center",
              bbox_to_anchor=(0.5, -0.13), ncol=2)
    ax.grid(axis="x", alpha=0.25, zorder=0)
    for sp in ax.spines.values():
        sp.set_color("#e2e8f0")
    fig.tight_layout()
    fig.savefig(os.path.join(ASSETS, "chart_summary.png"), bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print("charts saved to", ASSETS)


if __name__ == "__main__":
    main()
