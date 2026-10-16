#!/usr/bin/env python3
"""Round 3 summary charts: composite scorecard + breadth split."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.patches as mpatches

zh = fm.FontProperties(fname="/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc")
plt.rcParams["axes.unicode_minus"] = False

rows = [
    ("跌超5%x跌破20日低点", 1.24, 2003, "drop"),
    ("跌超5%x近10日跌超8%", 1.16, 2045, "drop"),
    ("跌超7%x低开超1%", 0.96, 1291, "drop"),
    ("跌超5%x低开超1%", 0.70, 2765, "drop"),
    ("长十字x跌破60日均线", 0.50, 1324, "candle"),
    ("长十字x近5日跌超5%", 0.48, 710, "candle"),
    ("跌超5%x放量", 0.34, 2351, "drop"),
    ("射击之星x近5日跌超5%", 0.22, 1419, "candle"),
    ("昨日大跌今日翻红x放量", 0.20, 2969, "other"),
    ("长十字x纺锤", 0.07, 1885, "candle"),
    ("纺锤x近5日跌超5%", 0.05, 3843, "other"),
    ("跌超7%x量比>2", -0.09, 745, "drop"),
    ("涨超7%x放量", -0.49, 3077, "other"),
    ("近60日涨超20%x贴近60日高点", -0.88, 3398, "other"),
]
colors = {"drop": "#b91c1c", "candle": "#1d4ed8", "other": "#64748b"}
labels = [r[0] for r in rows][::-1]
vals = [r[1] for r in rows][::-1]
ns = [r[2] for r in rows][::-1]
cs = [colors[r[3]] for r in rows][::-1]

fig, axes = plt.subplots(1, 2, figsize=(14.6, 6.4), dpi=120)
fig.patch.set_facecolor("#f8fafc")

ax = axes[0]
ax.set_facecolor("#f8fafc")
ypos = list(range(len(labels)))
ax.barh(ypos, vals, color=cs, zorder=3, height=0.62)
for i, (v, n) in enumerate(zip(vals, ns)):
    off = 0.035 if v >= 0 else -0.035
    ax.text(v + off, i, f"{v:+.2f}% (n={n})", va="center", ha="left" if v >= 0 else "right",
            fontproperties=zh, fontsize=8.5, color="#334155")
ax.axvline(0, color="#334155", lw=0.8)
ax.set_yticks(ypos)
ax.set_yticklabels(labels, fontproperties=zh, fontsize=9)
ax.set_xlabel("回测期扣成本每笔平均（%，5日持有）", fontproperties=zh, fontsize=10)
ax.set_title("复合因子成绩单：活下来的几乎全是「大跌之后」", fontproperties=zh, fontsize=12.5)
ax.set_xlim(-2.4, 2.1)
ax.grid(axis="x", alpha=0.25, zorder=0)
handles = [mpatches.Patch(color=colors[k], label=v) for k, v in (("drop", "含『跌超5%/7%』"), ("candle", "蜡烛形态组合"), ("other", "其他"))]
ax.legend(handles=handles, prop=zh, fontsize=8.5, loc="lower right")
for sp in ax.spines.values():
    sp.set_color("#e2e8f0")

ax = axes[1]
ax.set_facecolor("#f8fafc")
groups = [("1-2 只/天", -0.96, 329, 411), ("3-9 只/天", -0.49, 133, 599), ("10 只以上/天", 3.21, 44, 1258)]
gx = list(range(len(groups)))
gv = [g[1] for g in groups]
gc = ["#1d4ed8" if v < 0 else "#b91c1c" for v in gv]
ax.bar(gx, gv, color=gc, zorder=3, width=0.5)
for i, g in enumerate(groups):
    ax.annotate(f"{g[1]:+.2f}%\n{g[2]}天 / {g[3]}笔", (i, g[1]), textcoords="offset points",
                xytext=(0, 12 if g[1] > 0 else -42), ha="center", fontproperties=zh, fontsize=9.5)
ax.axhline(0, color="#334155", lw=0.8)
ax.set_xticks(gx)
ax.set_xticklabels([g[0] for g in groups], fontproperties=zh, fontsize=10.5)
ax.set_ylabel("回测期扣成本每笔平均（%）", fontproperties=zh, fontsize=10)
ax.set_title("「跌超5%x跌破20日低点」：单独触发是亏的，一起触发才赚", fontproperties=zh, fontsize=12.5)
ax.set_ylim(-1.8, 4.4)
ax.grid(axis="y", alpha=0.25, zorder=0)
for sp in ax.spines.values():
    sp.set_color("#e2e8f0")

fig.tight_layout()
path = "/home/xyz/reports/a-share/precursor-5d/assets/chart_composite.png"
fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
print("saved", path)
