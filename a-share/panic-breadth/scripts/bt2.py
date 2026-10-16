#!/usr/bin/env python3
"""bt2.py — 回测图表：资金曲线 / 回撤 / 分年代对比。输出 assets/chart_bt_*.png"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = "/home/xyz/stock-scripts/panic_breadth"
plt.rcParams["font.sans-serif"] = ["WenQuanYi Zen Hei", "Noto Sans CJK SC", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

eq = pd.read_csv(f"{BASE}/out/bt1_equity.csv", parse_dates=["date"]).set_index("date")
print("range:", eq.index[0].date(), "->", eq.index[-1].date(), "rows:", len(eq))

eras = [("2005–2009", "2005-02-01", "2009-12-31"), ("2010–2014", "2010-01-01", "2014-12-31"),
        ("2015–2019", "2015-01-01", "2019-12-31"), ("2020–2026", "2020-01-01", "2026-12-31")]
print("== era multiples ==")
rows = []
prev_s, prev_b = 1.0, 1.0
for name, a, b in eras:
    m = (eq.index >= a) & (eq.index <= b)
    s = eq.loc[m]
    sv, bv = s["v1_base"].iloc[-1] / prev_s, s["ew_bh"].iloc[-1] / prev_b
    rows.append((name, sv, bv))
    print(f"  {name}: strategy {sv:.2f}x   EW-BH {bv:.2f}x")
    prev_s, prev_b = s["v1_base"].iloc[-1], s["ew_bh"].iloc[-1]

# fig 1: equity curves
fig, ax = plt.subplots(figsize=(11, 6.2))
ax.plot(eq.index, eq["ew_bh"], color="#999999", lw=2.2, label="等权买入持有　23.1x")
ax.plot(eq.index, eq["vw_bh"], color="#c9c9c9", lw=1.6, label="市值加权买入持有　4.9x")
ax.plot(eq.index, eq["v1_base"], color="#2563eb", lw=1.9, label="策略·5日基础　6.3x")
ax.plot(eq.index, eq["v3_stop_same"], color="#16a34a", lw=1.9, label="策略·5日+破位止损　8.5x")
ax.set_yscale("log")
ax.set_yticks([1, 2, 4, 8, 16, 32])
ax.set_yticklabels(["1x", "2x", "4x", "8x", "16x", "32x"])
ax.set_title("「恐慌→反击」策略 vs 买入持有（全A等权，2005-02 — 2026-10-15，对数轴）", fontsize=13)
ax.legend(loc="upper left", fontsize=10)
ax.grid(True, which="major", alpha=0.3)
ax.set_ylabel("净值（起点=1）")
fig.tight_layout()
fig.savefig(f"{BASE}/assets/chart_bt_equity.png", dpi=150)
plt.close(fig)

# fig 2: drawdowns
fig, ax = plt.subplots(figsize=(11, 5))
for col, color, label in [("ew_bh", "#999999", "等权买入持有"), ("v1_base", "#2563eb", "策略·5日基础"), ("v3_stop_same", "#16a34a", "策略·5日+止损")]:
    s = eq[col]
    dd = s / s.cummax() - 1
    ax.plot(eq.index, dd * 100, color=color, lw=1.6, label=f"{label}（最深 {dd.min()*100:.0f}%）")
ax.set_title("回撤对比（自高点，%）", fontsize=13)
ax.legend(loc="lower left", fontsize=10)
ax.grid(True, alpha=0.3)
ax.set_ylabel("回撤 %")
fig.tight_layout()
fig.savefig(f"{BASE}/assets/chart_bt_dd.png", dpi=150)
plt.close(fig)

# fig 3: era bars
fig, ax = plt.subplots(figsize=(8.6, 4.8))
xpos = np.arange(len(rows))
w = 0.36
b1 = ax.bar(xpos - w / 2, [r[1] for r in rows], width=w, color="#2563eb", label="策略·5日基础")
b2 = ax.bar(xpos + w / 2, [r[2] for r in rows], width=w, color="#999999", label="等权买入持有")
for rects in (b1, b2):
    for r in rects:
        ax.annotate(f"{r.get_height():.2f}x", (r.get_x() + r.get_width() / 2, r.get_height()), ha="center", va="bottom", fontsize=9)
ax.set_xticks(xpos)
ax.set_xticklabels([r[0] for r in rows])
ax.axhline(1.0, color="k", lw=0.8, ls="--", alpha=0.5)
ax.set_title("分年代倍数（区间起点归一）", fontsize=13)
ax.legend(fontsize=10)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(f"{BASE}/assets/chart_bt_era.png", dpi=150)
plt.close(fig)

print("saved: assets/chart_bt_equity.png chart_bt_dd.png chart_bt_era.png")
