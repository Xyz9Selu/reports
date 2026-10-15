#!/usr/bin/env python3
"""Probability study for Huang Yang PE-band method (8y window, weekly PE-TTM).

Claims tested (verbatim from transcripts):
 1) "估值高于红线(均值+1σ)时，上涨概率与下跌概率大约是3:7" (2022-10-21 茅台数学文)
 2) "低估(均值-1σ以下)时建仓，上涨概率明显大于继续下跌" (2024-12-27 农行文)

Outputs: bucket table (z<-2 / -2..-1 / -1..1 / 1..2 / z>2) with forward
26w & 52w mean returns and win rates; episode-start variant; chart_probability.png.
Note: weekly obs overlap - treat n as upper bound; episode view is the cleaner one.
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

W, MINP = 416, 208  # 8y window, 4y min


def load_wk(path):
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


def main():
    frames = []
    for f in sorted(os.listdir(DATA)):
        if not f.endswith(".json"):
            continue
        got = load_wk(os.path.join(DATA, f))
        if got is None:
            continue
        code, name, wk = got
        pe = wk["pe_ttm"].where(wk["pe_ttm"] > 0)
        mu = pe.rolling(W, min_periods=MINP).mean()
        sd = pe.rolling(W, min_periods=MINP).std(ddof=0)
        z = (pe - mu) / sd
        fwd26 = wk["adj_close"].shift(-26) / wk["adj_close"] - 1
        fwd52 = wk["adj_close"].shift(-52) / wk["adj_close"] - 1
        t = pd.DataFrame({"code": code, "name": name, "date": wk.index,
                          "z": z, "fwd26": fwd26, "fwd52": fwd52})
        frames.append(t)

    allf = pd.concat(frames)
    allf = allf[allf["z"].notna() & allf["fwd52"].notna()].copy()
    allf["bucket"] = pd.cut(allf["z"], bins=[-np.inf, -2, -1, 1, 2, np.inf],
                            labels=["z<-2", "-2~-1", "-1~1", "1~2", "z>2"])

    def agg(g):
        return pd.Series({
            "n": len(g),
            "fwd26_mean": g["fwd26"].mean(),
            "fwd26_win": (g["fwd26"] > 0).mean(),
            "fwd52_mean": g["fwd52"].mean(),
            "fwd52_win": (g["fwd52"] > 0).mean(),
        })

    summ = allf.groupby("bucket", observed=True).apply(agg)
    print("=== pooled weekly observations (upper-bound n, overlapping) ===")
    print(summ.round(3).to_string())
    summ.to_csv(os.path.join(OUT, "probability_buckets.csv"))
    base52 = (allf["fwd52"] > 0).mean()
    print(f"\nbaseline fwd52 win rate: {base52:.3f}   n={len(allf)}")

    # ---- episode starts: first week crossing below -1 / above +1
    eps = []
    for code, g in allf.groupby("code"):
        g = g.sort_values("date")
        for side, cond in (("low(z<-1)", g["z"] < -1), ("high(z>1)", g["z"] > 1)):
            cond = cond.astype(int)
            d = cond.diff().fillna(0)
            starts = g[d == 1]
            for _, r in starts.iterrows():
                eps.append(dict(code=code, name=r["name"], side=side, date=r["date"],
                                z=round(float(r["z"]), 2),
                                fwd26=r["fwd26"], fwd52=r["fwd52"]))
    ep = pd.DataFrame(eps)

    def agg_ep(g):
        return pd.Series({
            "n": len(g),
            "z_mean": g["z"].mean(),
            "fwd26_mean": g["fwd26"].mean(),
            "fwd26_win": (g["fwd26"] > 0).mean(),
            "fwd52_mean": g["fwd52"].mean(),
            "fwd52_win": (g["fwd52"] > 0).mean(),
        })

    epsumm = ep.groupby("side").apply(agg_ep)
    print("\n=== episode starts (first week crossing the line) ===")
    print(epsumm.round(3).to_string())
    ep.to_csv(os.path.join(OUT, "probability_episodes.csv"), index=False)

    # episode detail for report
    print("\n--- episode list ---")
    print(ep.sort_values(["side", "date"]).to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    # ---- chart
    colors = ["#15803d", "#4ade80", "#94a3b8", "#fb923c", "#b91c1c"]
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 4.9), dpi=120)
    fig.patch.set_facecolor("#f8fafc")
    x = np.arange(len(summ))
    for ax, col, title, base, fmt in (
        (axes[0], "fwd52_win", "未来 52 周正收益概率", base52, "%"),
        (axes[1], "fwd52_mean", "未来 52 周平均收益", allf["fwd52"].mean(), "%"),
    ):
        ax.set_facecolor("#f8fafc")
        vals = summ[col] * 100 if fmt == "%" else summ[col]
        ax.bar(x, vals, 0.58, color=colors, zorder=3)
        base_v = base * 100
        ax.axhline(base_v, color="#334155", ls="--", lw=1.1, zorder=2)
        ax.text(len(summ) - 0.52, base_v + 1.3, f"全样本基线 {base_v:.1f}%", ha="right",
                fontproperties=zh, fontsize=9, color="#334155")
        ax.set_xticks(x)
        ax.set_xticklabels(summ.index, fontproperties=zh, fontsize=9.5)
        ax.set_title(title + "（按 z 分档）", fontproperties=zh, fontsize=12)
        ax.grid(axis="y", alpha=0.25, zorder=0)
        for sp in ax.spines.values():
            sp.set_color("#e2e8f0")
        for xi, v in zip(x, vals):
            if v >= 0:
                ax.text(xi, v + 0.6, f"{v:+.1f}%", ha="center", va="bottom",
                        fontproperties=zh, fontsize=8.5, color="#334155",
                        bbox=dict(facecolor="#f8fafc", edgecolor="none", pad=1.0))
            else:
                ax.text(xi, v - 0.8, f"{v:+.1f}%", ha="center", va="top",
                        fontproperties=zh, fontsize=8.5, color="#334155",
                        bbox=dict(facecolor="#f8fafc", edgecolor="none", pad=1.0))
        ax.margins(y=0.14)
    fig.supxlabel("z = (PE - 8年均值) / 8年标准差   |   <-2 极低估 | -2~-1 低估 | -1~1 中枢 | 1~2 高估 | >2 极高估",
                  fontproperties=zh, fontsize=9.5)
    fig.tight_layout()
    fig.savefig(os.path.join(ASSETS, "chart_probability.png"), bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()
    print("\nchart saved:", os.path.join(ASSETS, "chart_probability.png"))


if __name__ == "__main__":
    main()
