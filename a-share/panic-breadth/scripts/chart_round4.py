#!/usr/bin/env python3
"""Round 4 charts: panic intensity, era/cascade, current analogs."""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["WenQuanYi Zen Hei", "DejaVu Sans", "sans-serif"]
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["axes.unicode_minus"] = False

BASE = "/home/xyz/stock-scripts/panic_breadth"
OUT = f"{BASE}/assets"
os.makedirs(OUT, exist_ok=True)

df = pd.read_csv(f"{BASE}/data/breadth_clean.csv", parse_dates=["trade_date"]).set_index("trade_date").sort_index()
df = df[df["n"] > 100].copy()
for c in ["dn5", "dn7", "dn95", "up5", "up95", "newlow", "low_dn5"]:
    df[f"{c}_share"] = df[f"c_{c}"] / df["n"]
df["ew"] = (1 + df["ew_ret"] / 100).cumprod()
df["vw"] = (1 + df["vw_ret"] / 100).cumprod()
for k in (1, 5, 10, 20):
    df[f"ew_f{k}"] = df["ew"].shift(-k) / df["ew"] - 1
    df[f"vw_f{k}"] = df["vw"].shift(-k) / df["vw"] - 1

C_POS, C_NEG, C_GRAY, C_BLUE, C_ORANGE = "#2E7D32", "#D32F2F", "#8b95a1", "#1565C0", "#f39c12"
sig = df["dn5_share"] >= 0.15

# ---------------- Chart 1: intensity curves ----------------
fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2))
ax = axes[0]
thrs = [0.02, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.60]
rec = [(t, len(df[df["dn5_share"] >= t]), df[df["dn5_share"] >= t]["ew_f5"].mean(),
        df[df["dn5_share"] >= t]["ew_f20"].mean()) for t in thrs]
rec = pd.DataFrame(rec, columns=["t", "n", "f5", "f20"])
x = np.arange(len(rec))
ax.plot(x, rec["f5"] * 100, "o-", color=C_BLUE, lw=2, ms=5, label="之后 5 日")
ax.plot(x, rec["f20"] * 100, "s-", color=C_ORANGE, lw=2, ms=5, label="之后 20 日")
ax.axhline(df["ew_f5"].mean() * 100, color=C_GRAY, ls="--", lw=1)
ax.axhline(df["ew_f20"].mean() * 100, color=C_GRAY, ls=":", lw=1)
ax.text(len(rec) - 0.3, df["ew_f5"].mean() * 100 - 0.45, "全样本基准 5日 +0.41%", color=C_GRAY, fontsize=8.5, ha="right")
ax.axvline(5.05, color=C_NEG, ls="--", lw=1.2)
ax.annotate("2026-10-15（15.1%）", xy=(5.05, 2.6), xytext=(5.8, 3.4), color=C_NEG, fontsize=9,
            arrowprops=dict(arrowstyle="->", color=C_NEG, lw=1))
ax.set_xticks(x)
ax.set_xticklabels([f"{t*100:.0f}%" for t in rec["t"]], fontsize=9)
ax.set_xlabel("当日跌超 5% 的股票占比 ≥ X", fontsize=10)
ax.set_ylabel("恐慌日之后平均收益（%）", fontsize=10)
ax.set_title("下跌广度 → 之后收益（全A等权，2005–2026）", fontsize=11.5)
ax.legend(fontsize=9, loc="upper left")
ax.grid(alpha=0.25, axis="y")

ax = axes[1]
thrs95 = [0.02, 0.05, 0.10, 0.15, 0.20, 0.30]
rec2 = [(t, len(df[df["dn95_share"] >= t]), df[df["dn95_share"] >= t]["ew_f1"].mean(),
         df[df["dn95_share"] >= t]["ew_f5"].mean(), df[df["dn95_share"] >= t]["ew_f20"].mean()) for t in thrs95]
rec2 = pd.DataFrame(rec2, columns=["t", "n", "f1", "f5", "f20"])
x2 = np.arange(len(rec2))
ax.plot(x2, rec2["f1"] * 100, "^-", color=C_GRAY, lw=1.6, ms=5, label="之后 1 日")
ax.plot(x2, rec2["f5"] * 100, "o-", color=C_BLUE, lw=2, ms=5, label="之后 5 日")
ax.plot(x2, rec2["f20"] * 100, "s-", color=C_ORANGE, lw=2, ms=5, label="之后 20 日")
ax.axhline(0, color="#333", lw=0.8)
ax.set_xticks(x2)
ax.set_xticklabels([f"{t*100:.0f}%" for t in rec2["t"]], fontsize=9)
ax.set_xlabel("当日跌超 9.5%（准跌停）的股票占比 ≥ X", fontsize=10)
ax.set_title("跌停潮广度 → 之后收益（同上）", fontsize=11.5)
ax.legend(fontsize=9, loc="upper left")
ax.grid(alpha=0.25, axis="y")
ax.text(0.02, 0.02, "极端跌停潮：第 1–2 天仍多下跌，10–20 日修复", transform=ax.transAxes,
        fontsize=8.5, color="#555")
fig.tight_layout()
fig.savefig(f"{OUT}/chart_round4_intensity.png", dpi=120, bbox_inches="tight")
plt.close(fig)

# ---------------- Chart 2: era & cascade ----------------
eras = [("2005–2009", "2005-01-01", "2009-12-31"), ("2010–2014", "2010-01-01", "2014-12-31"),
        ("2015–2019", "2015-01-01", "2019-12-31"), ("2020–2026", "2020-01-01", "2026-12-31")]
rows = []
for label, a, b in eras:
    seg = df.loc[a:b]
    s = seg[sig.loc[a:b]]
    rows.append((label, seg["ew_f5"].mean() * 100, s["ew_f5"].mean() * 100))
rows = pd.DataFrame(rows, columns=["era", "base", "panic"])

cas = (df.index >= "2015-06-01") & (df.index <= "2016-02-29")
e15 = (df.index >= "2015-01-01") & (df.index <= "2019-12-31")
items = [
    ("2015-06→2016-02\n级联中（股灾）", df[sig & cas]["ew_f5"].mean() * 100, int((sig & cas).sum())),
    ("2015–2019 其余恐慌日", df[sig & e15 & ~cas]["ew_f5"].mean() * 100, int((sig & e15 & ~cas).sum())),
    ("全样本恐慌日（去级联段）", df[sig & ~cas]["ew_f5"].mean() * 100, int((sig & ~cas).sum())),
    ("全样本恐慌日（含级联段）", df[sig]["ew_f5"].mean() * 100, int(sig.sum())),
]

fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.4))
ax = axes[0]
x = np.arange(len(rows))
w = 0.36
ax.bar(x - w / 2, rows["base"], w, color=C_GRAY, alpha=0.75, label="全样本基准 5 日")
ax.bar(x + w / 2, rows["panic"], w, color=C_BLUE, label="恐慌日（跌超5%占比≥15%）5 日")
for xi, v in zip(x + w / 2, rows["panic"]):
    ax.text(xi, v + (0.08 if v >= 0 else -0.22), f"{v:+.2f}%", ha="center", fontsize=9,
            color=C_POS if v > 0 else C_NEG, fontweight="bold")
ax.axhline(0, color="#333", lw=0.8)
ax.set_xticks(x)
ax.set_xticklabels(rows["era"], fontsize=10)
ax.set_ylabel("之后 5 日平均收益（%）", fontsize=10)
ax.set_title("恐慌日的效果随年代变化（等权）", fontsize=11.5)
ax.legend(fontsize=9)
ax.grid(alpha=0.25, axis="y")

ax = axes[1]
labels = [it[0] for it in items][::-1]
vals = [it[1] for it in items][::-1]
ns = [it[2] for it in items][::-1]
colors = [C_POS if v > 0 else C_NEG for v in vals]
bars = ax.barh(np.arange(len(items)), vals, color=colors, alpha=0.85, height=0.55)
for yi, (v, n) in enumerate(zip(vals, ns)):
    ax.text(v + (0.06 if v >= 0 else -0.06), yi, f"{v:+.2f}%（n={n}）", va="center",
            ha="left" if v >= 0 else "right", fontsize=9)
ax.set_yticks(np.arange(len(items)))
ax.set_yticklabels(labels, fontsize=9)
ax.axvline(0, color="#333", lw=0.8)
ax.set_xlabel("之后 5 日平均收益（%）", fontsize=10)
ax.set_title("股灾级联是最大的失败模式（等权）", fontsize=11.5)
ax.grid(alpha=0.25, axis="x")
fig.tight_layout()
fig.savefig(f"{OUT}/chart_round4_era.png", dpi=120, bbox_inches="tight")
plt.close(fig)

# ---------------- Chart 3: 2020+ analogs ----------------
cur = (df["dn5_share"] >= 0.12) & (df["newlow_share"] >= 0.30) & (df.index >= "2020-01-01")
sub = df[cur].copy()
sub["x"] = np.arange(len(sub))
f5 = sub["ew_f5"] * 100
f20 = sub["ew_f20"] * 100
weak = (sub["dn95_share"] < 0.02).to_numpy()

fig, axes = plt.subplots(2, 1, figsize=(13, 7.2), sharex=True)
for ax, series, name in ((axes[0], f5, "之后 5 日"), (axes[1], f20, "之后 20 日")):
    vals = series.to_numpy()
    for xi, v in zip(sub["x"].to_numpy(), vals):
        if np.isnan(v):
            continue
        ax.scatter(xi, v, color=C_POS if v > 0 else C_NEG, s=30, zorder=3)
    ax.scatter(sub["x"].to_numpy()[weak], vals[weak], facecolors="none", edgecolors="#333",
               marker="s", s=64, zorder=4, linewidths=1.0, label="跌停占比 < 2%（偏弱子样本）")
    ax.axhline(0, color="#333", lw=0.8)
    med = np.nanmedian(vals)
    ax.axhline(med, color=C_BLUE, ls="--", lw=1.1)
    ax.text(0.2, med + (0.35 if med >= 0 else -0.9), f"中位数 {med:+.2f}%", color=C_BLUE, fontsize=9)
    ax.set_ylabel(f"{name}收益（%）", fontsize=10)
    ax.grid(alpha=0.22, axis="y")
    ax.legend(fontsize=8.5, loc="upper left")
    # mark today
    last_x = sub["x"].iloc[-1]
    ax.axvline(last_x, color=C_NEG, ls=":", lw=1.2)
    ax.text(last_x - 0.3, ax.get_ylim()[1] * 0.78, "10-15 本次\n（待验证）", color=C_NEG,
            fontsize=8.5, ha="right")

# annotations
axes[0].annotate("2024-01-30 小微盘踩踏 -15.4%", xy=(sub.index.get_loc("2024-01-30"), -15.44),
                 xytext=(sub.index.get_loc("2024-01-30") + 2.0, -12.0), fontsize=8.5, color=C_NEG,
                 arrowprops=dict(arrowstyle="->", color=C_NEG, lw=1))
axes[0].annotate("2024-02-05 +13.1%", xy=(sub.index.get_loc("2024-02-05"), 13.11),
                 xytext=(sub.index.get_loc("2024-02-05") - 9.5, 11.0), fontsize=8.5, color=C_POS,
                 arrowprops=dict(arrowstyle="->", color=C_POS, lw=1))
axes[0].annotate("2025-04-07/08 关税急跌后 +8%", xy=(sub.index.get_loc("2025-04-08"), 8.16),
                 xytext=(sub.index.get_loc("2025-04-08") - 1.0, 10.5), fontsize=8.5, color=C_POS,
                 arrowprops=dict(arrowstyle="->", color=C_POS, lw=1))

tick_idx = list(range(0, len(sub), 3))
axes[1].set_xticks(tick_idx)
axes[1].set_xticklabels([sub.index[i].strftime("%y-%m-%d") for i in tick_idx], rotation=45, fontsize=8)
axes[0].set_title("2020 年以来「跌超5%占比≥12% 且 新低占比≥30%」的同类恐慌日（共 42 次，含 10/15）", fontsize=11.5)
fig.tight_layout()
fig.savefig(f"{OUT}/chart_round4_analog.png", dpi=120, bbox_inches="tight")
plt.close(fig)

print("charts done")
for f in ("chart_round4_intensity.png", "chart_round4_era.png", "chart_round4_analog.png"):
    p = f"{OUT}/{f}"
    print(f, os.path.getsize(p))
