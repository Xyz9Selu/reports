#!/usr/bin/env python3
"""Large-sample validation of Huang Yang's PE mean±sigma band method.

Data source: local Postgres stock_data (ALL A-shares 2005-2026, incl. 340 delisted)
exported by data_db export (weekly_all.csv: ts_code, trade_date, close, pe_ttm,
total_mv, adj_factor; basic.csv).

Tests:
  1) Forward 26w/52w returns by z bucket, z = (PE - rolling mean) / rolling std,
     windows: 8y (416w) and 5y (260w). Also top-30% market cap subset.
  2) Episode starts: first weekly crossing below -1 / above +1 (and ±2).
  3) Mean reversion: P(z_t+52 below current | z>1) etc.
Outputs: out_db/*.csv, assets/chart_dblarge.png
"""
import os

import numpy as np
import pandas as pd

BASE = os.path.expanduser("~/stock-scripts/huangyang_backtest")
DATA = os.path.join(BASE, "data_db")
OUT = os.path.join(BASE, "out_db")
ASSETS = os.path.join(BASE, "assets")
os.makedirs(OUT, exist_ok=True)

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 60)

LBL = ["z<-2", "-2~-1", "-1~1", "1~2", "z>2"]


def rolling_z(pe, window, minp):
    mu = pe.rolling(window, min_periods=minp).mean()
    sd = pe.rolling(window, min_periods=minp).std(ddof=0)
    return (pe - mu) / sd


def main():
    wk = pd.read_csv(
        os.path.join(DATA, "weekly_all.csv"),
        dtype={"ts_code": str, "close": float, "pe_ttm": float,
               "total_mv": float, "adj_factor": float},
        parse_dates=["trade_date"],
    )
    n0 = len(wk)
    wk = wk.dropna(subset=["close"]).sort_values(["ts_code", "trade_date"], kind="mergesort")
    print(f"weekly rows: {n0} -> {len(wk)}; stocks: {wk['ts_code'].nunique()}")

    wk["adj_factor"] = wk.groupby("ts_code")["adj_factor"].transform(lambda s: s.ffill().bfill())
    wk["adj_close"] = wk["close"] * wk["adj_factor"]
    g = wk.groupby("ts_code", sort=False)
    wk["fwd26"] = g["adj_close"].shift(-26) / wk["adj_close"] - 1
    wk["fwd52"] = g["adj_close"].shift(-52) / wk["adj_close"] - 1

    # cross-sectional market cap percentile (per week) for large-cap subset
    wk["mv_pct"] = wk.groupby("trade_date")["total_mv"].rank(pct=True)

    # delisted flag
    basic = pd.read_csv(os.path.join(DATA, "basic.csv"), dtype={"ts_code": str})
    delisted = set(basic.loc[basic["list_status"] == "D", "ts_code"])
    wk["is_delisted"] = wk["ts_code"].isin(delisted)
    print("delisted stocks in basic:", len(delisted),
          "| obs on delisted:", int(wk["is_delisted"].sum()))

    # ---- rolling z for both windows (single pass per stock)
    z8, z5 = [], []
    for _, sub in wk.groupby("ts_code", sort=False):
        pe = sub["pe_ttm"].where(sub["pe_ttm"] > 0)
        z8.append(rolling_z(pe, 416, 208))
        z5.append(rolling_z(pe, 260, 156))
    wk["z_8y"] = pd.concat(z8).sort_index()
    wk["z_5y"] = pd.concat(z5).sort_index()

    summary_plot = None
    base_win = base_mean = None

    for tag in ("8y", "5y"):
        zcol = f"z_{tag}"
        valid = wk[zcol].notna()
        first_yr = wk.loc[valid, "trade_date"].dt.year.min()
        print(f"\n########## window = {tag} (valid from {first_yr}) ##########")

        for h in ("fwd26", "fwd52"):
            sub = wk.loc[valid & wk[h].notna()].copy()
            sub["b"] = pd.cut(sub[zcol], [-np.inf, -2, -1, 1, 2, np.inf], labels=LBL)
            st = sub.groupby("b", observed=True)[h].agg(
                n="count", mean="mean", median="median",
                win=lambda s: (s > 0).mean(),
                q10=lambda s: s.quantile(0.10), q90=lambda s: s.quantile(0.90))
            print(f"\n-- {h} | all stocks --")
            print(st.round(4).to_string())
            st.to_csv(os.path.join(OUT, f"bucket_{tag}_{h}.csv"))
            subcap = sub[sub["mv_pct"] >= 0.7]
            stc = subcap.groupby("b", observed=True)[h].agg(
                n="count", mean="mean", median="median", win=lambda s: (s > 0).mean())
            print(f"-- {h} | top 30% mktcap --")
            print(stc.round(4).to_string())
            stc.to_csv(os.path.join(OUT, f"bucket_{tag}_{h}_largecap.csv"))

            if tag == "8y" and h == "fwd52":
                summary_plot = st
                base_win = (sub[h] > 0).mean()
                base_mean = sub[h].mean()
                print(f"\nbaseline fwd52: n={len(sub)}, win={base_win:.4f}, "
                      f"mean={base_mean:.4f}, median={sub[h].median():.4f}")

        # ---- episode starts
        prev = wk.groupby("ts_code", sort=False)[zcol].shift(1)
        eps = {
            "low1(z<-1)": (wk[zcol] < -1) & (prev >= -1),
            "high1(z>1)": (wk[zcol] > 1) & (prev <= 1),
            "low2(z<-2)": (wk[zcol] < -2) & (prev >= -2),
            "high2(z>2)": (wk[zcol] > 2) & (prev <= 2),
        }
        rows = []
        for name, m in eps.items():
            s = wk.loc[m & wk["fwd52"].notna()]
            rows.append(dict(episode=name, n=len(s),
                             fwd26_mean=s["fwd26"].mean(), fwd26_win=(s["fwd26"] > 0).mean(),
                             fwd52_mean=s["fwd52"].mean(), fwd52_win=(s["fwd52"] > 0).mean(),
                             fwd52_med=s["fwd52"].median()))
        epdf = pd.DataFrame(rows).set_index("episode")
        print(f"\n-- episode starts | {tag} --")
        print(epdf.round(4).to_string())
        epdf.to_csv(os.path.join(OUT, f"episode_{tag}.csv"))

        # ---- reversion probabilities
        zf = wk.groupby("ts_code", sort=False)[zcol].shift(-52)
        zt = wk[zcol]
        hi = zt > 1
        lo = zt < -1
        rev = dict(
            high_n=int((hi & zf.notna()).sum()),
            high_P_z52_lt_z=float((zf[hi & zf.notna()] < zt[hi & zf.notna()]).mean()),
            high_P_z52_le_1=float((zf[hi & zf.notna()] <= 1).mean()),
            high_P_z52_le_0=float((zf[hi & zf.notna()] <= 0).mean()),
            low_n=int((lo & zf.notna()).sum()),
            low_P_z52_gt_z=float((zf[lo & zf.notna()] > zt[lo & zf.notna()]).mean()),
            low_P_z52_ge_m1=float((zf[lo & zf.notna()] >= -1).mean()),
            low_P_z52_ge_0=float((zf[lo & zf.notna()] >= 0).mean()),
        )
        print(f"\n-- reversion | {tag} --")
        print(rev)
        pd.Series(rev).to_csv(os.path.join(OUT, f"reversion_{tag}.csv"))

        # spearman corr z vs fwd52 (sample every 5th row)
        smp = wk.loc[valid & wk["fwd52"].notna(), [zcol, "fwd52"]].iloc[::5]
        print(f"spearman corr({zcol}, fwd52) = {smp.corr(method='spearman').iloc[0,1]:.4f} (n={len(smp)})")

    # ---- chart for report (8y, fwd52, all stocks)
    if summary_plot is not None:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.font_manager as fm
        zh = fm.FontProperties(fname="/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc")
        plt.rcParams["axes.unicode_minus"] = False

        st = summary_plot
        labels = list(st.index)
        x = np.arange(len(labels))
        colors = ["#15803d", "#4ade80", "#94a3b8", "#fb923c", "#b91c1c"]
        fig, axes = plt.subplots(1, 2, figsize=(12.8, 4.9), dpi=120)
        fig.patch.set_facecolor("#f8fafc")
        for ax, col, title, base in (
            (axes[0], "win", "未来 52 周正收益概率", base_win),
            (axes[1], "mean", "未来 52 周平均收益", base_mean),
        ):
            ax.set_facecolor("#f8fafc")
            vals = st[col] * 100
            ax.bar(x, vals, 0.6, color=colors, zorder=3)
            ax.axhline(base * 100, color="#334155", ls="--", lw=1.1, zorder=2)
            ax.text(len(labels) - 0.55, base * 100 + 1.2, f"全样本基线 {base*100:.1f}%",
                    ha="right", fontproperties=zh, fontsize=9, color="#334155")
            ax.set_xticks(x)
            ax.set_xticklabels([f"{l}\n(n={int(nn):,})" for l, nn in zip(labels, st["n"])],
                               fontproperties=zh, fontsize=9)
            ax.set_title(title + "（全A样本，8 年窗口）", fontproperties=zh, fontsize=12)
            ax.grid(axis="y", alpha=0.25, zorder=0)
            for sp in ax.spines.values():
                sp.set_color("#e2e8f0")
            for xi, v in zip(x, vals):
                if v >= 0:
                    ax.text(xi, v + 0.6, f"{v:+.1f}%", ha="center", va="bottom",
                            fontproperties=zh, fontsize=8.5, color="#334155")
                else:
                    ax.text(xi, v - 0.8, f"{v:+.1f}%", ha="center", va="top",
                            fontproperties=zh, fontsize=8.5, color="#334155")
            ax.margins(y=0.14)
        fig.supxlabel("z = (PE - 8年均值) / 8年标准差   |   <-2 极低估 | -2~-1 低估 | -1~1 中枢 | "
                      "1~2 高估 | >2 极高估   （全部 A 股，含退市，周频，前复权）",
                      fontproperties=zh, fontsize=9)
        fig.tight_layout()
        fig.savefig(os.path.join(ASSETS, "chart_dblarge.png"), bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close()
        print("\nchart saved: assets/chart_dblarge.png")


if __name__ == "__main__":
    main()
