#!/usr/bin/env python3
"""Full-market panic-breadth event study: 2005-2026, all A-shares (incl. delisted).

Input:  data/breadth_daily.csv  (exported from stock_data.breadth_daily)
Output: threshold curves, era tables, episode stats, trajectories,
        strategy sims (EW & cap-weighted), basket-vs-market check.
"""
import numpy as np
import pandas as pd

BASE = "/home/xyz/stock-scripts/panic_breadth"
df = pd.read_csv(f"{BASE}/data/breadth_clean.csv", parse_dates=["trade_date"]).set_index("trade_date").sort_index()
df = df[df["n"] > 100].copy()

for c in ["dn5", "dn7", "dn95", "up5", "up95", "newlow", "low_dn5"]:
    df[f"{c}_share"] = df[f"c_{c}"] / df["n"]

df["ew"] = (1 + df["ew_ret"] / 100).cumprod()
df["vw"] = (1 + df["vw_ret"] / 100).cumprod()
for k in (1, 3, 5, 10, 20):
    df[f"ew_f{k}"] = df["ew"].shift(-k) / df["ew"] - 1
    df[f"vw_f{k}"] = df["vw"].shift(-k) / df["vw"] - 1


def tstat(x):
    x = np.asarray(pd.Series(x).dropna(), dtype=float)
    return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) >= 2 else np.nan


def fmt(x):
    return " nan " if (x is None or (isinstance(x, float) and np.isnan(x))) else f"{x*100:+.2f}%"


def episodes(mask, gap=30):
    days = df.index[mask.fillna(False)]
    eps = []
    if len(days) == 0:
        return eps
    start = prev = days[0]
    for d in days[1:]:
        if (d - prev).days > gap:
            eps.append((start, prev))
            start = d
        prev = d
    eps.append((start, prev))
    return eps


print(f"sample {df.index.min().date()} -> {df.index.max().date()}  days {len(df)}")
print(f"stocks/day min {df['n'].min()} median {int(df['n'].median())} max {df['n'].max()}")
print()
print("=== share quantiles (50/90/95/98/99%) ===")
for c in ["dn5_share", "dn95_share", "newlow_share", "low_dn5_share", "up95_share"]:
    qs = df[c].quantile([0.5, 0.9, 0.95, 0.98, 0.99]).map(lambda v: f"{v:.3f}")
    print(c, qs.to_dict())
print()
print("=== baseline EW forward ===")
for k in (1, 3, 5, 10, 20):
    s = df[f"ew_f{k}"].dropna()
    print(f"k={k:2d}: mean {fmt(s.mean())} med {fmt(s.median())} hit {(s>0).mean():.0%} n {len(s)}")
print()


def curve(ind, thresholds, label):
    print(f"=== curve: {label} ===")
    for t in thresholds:
        sub = df[df[ind] >= t]
        if len(sub) == 0:
            continue
        print(f"thr {t:.2f} n={len(sub):4d}  f1 {fmt(sub['ew_f1'].mean())}  f5 {fmt(sub['ew_f5'].mean())}  "
              f"f10 {fmt(sub['ew_f10'].mean())}  f20 {fmt(sub['ew_f20'].mean())}  hit5 {(sub['ew_f5'] > 0).mean():.0%}")
    print()


curve("dn5_share", [0.03, 0.05, 0.08, 0.10, 0.15, 0.20, 0.25, 0.30], "share down >5%")
curve("dn95_share", [0.02, 0.05, 0.10, 0.15, 0.20, 0.30], "share down >9.5% (near limit)")
curve("low_dn5_share", [0.02, 0.03, 0.05, 0.08, 0.10, 0.15], "share = down>5% & close below prior 20d low")
curve("up95_share", [0.05, 0.10, 0.15, 0.20, 0.30, 0.40], "EUPHORIA share up >9.5%")

eras = [("2005-2009", "2005-01-01", "2009-12-31"), ("2010-2014", "2010-01-01", "2014-12-31"),
        ("2015-2019", "2015-01-01", "2019-12-31"), ("2020-2026", "2020-01-01", "2026-12-31")]
print("=== era table (panics: dn5_share >= thr) ===")
for thr in (0.15, 0.25):
    print(f"-- thr {thr} --")
    for name, a, b in eras:
        seg = df.loc[a:b]
        sub = seg[seg["dn5_share"] >= thr]
        if len(sub) == 0:
            print(f"{name}: no days (base f5 {fmt(seg['ew_f5'].mean())})")
            continue
        print(f"{name}: days {len(sub):3d} | f5 {fmt(sub['ew_f5'].mean())} (base {fmt(seg['ew_f5'].mean())})  "
              f"f20 {fmt(sub['ew_f20'].mean())}  hit5 {(sub['ew_f5'] > 0).mean():.0%}")
    print()

print("=== episode table ===")
for thr in (0.15, 0.25):
    m = df["dn5_share"] >= thr
    eps = episodes(m)
    ep_means = [df.loc[a:b, "ew_f5"].mean() for a, b in eps]
    ep_means = [x for x in ep_means if not np.isnan(x)]
    print(f"thr {thr}: days {int(m.sum())} episodes {len(eps)} | mean-of-episode f5 {fmt(np.mean(ep_means))} "
          f"t {tstat(ep_means):.2f} | positive {(np.array(ep_means) > 0).sum()}/{len(ep_means)}")
print()

print("=== consecutive panic (2nd+ day in a run) vs first ===")
thr = 0.15
sig = (df["dn5_share"] >= thr)
run = sig.groupby((~sig).cumsum()).cumcount() + 1      # 1,2,3... within each run of sig
pos_in_run = run.where(sig)
for label, m in (("run pos 1 (first)", pos_in_run == 1), ("run pos 2", pos_in_run == 2),
                 ("run pos 3+", pos_in_run >= 3)):
    sub = df[m.fillna(False)]
    if len(sub) == 0:
        continue
    print(f"{label}: n {len(sub):3d}  f5 {fmt(sub['ew_f5'].mean())}  f20 {fmt(sub['ew_f20'].mean())}  "
          f"hit5 {(sub['ew_f5'] > 0).mean():.0%}")
print()

print("=== position within episode: first day vs later ===")
eps = episodes(sig)
first_days = [a for a, b in eps]
later_mask = sig.copy()
first_mask = pd.Series(False, index=df.index)
first_mask.loc[first_days] = True
for label, m in (("episode first day", first_mask & sig), ("episode later days", later_mask & ~first_mask)):
    sub = df[m]
    print(f"{label}: n {len(sub):3d}  f5 {fmt(sub['ew_f5'].mean())}  f20 {fmt(sub['ew_f20'].mean())}  "
          f"hit5 {(sub['ew_f5'] > 0).mean():.0%}")
print()

print("=== risk side: distribution of f5/f20 after panic days ===")
for thr in (0.15,):
    sub = df[df["dn5_share"] >= thr]
    for k in (5, 20):
        col = sub[f"ew_f{k}"].dropna()
        q = col.quantile([0.05, 0.25, 0.5, 0.75, 0.95]).map(fmt)
        print(f"thr {thr} f{k}: mean {fmt(col.mean())} | p5 {q[0.05]} p25 {q[0.25]} med {q[0.5]} p75 {q[0.75]} p95 {q[0.95]} | worst {fmt(col.min())}")
print()

print("=== path risk: after panic day, min close over next 20d relative to panic close ===")
minfwd = []
lev = df["ew"]
sig_idx = np.where((df["dn5_share"] >= 0.15).to_numpy())[0]
for i in sig_idx:
    if i + 20 < len(df):
        path = lev.iloc[i + 1:i + 21] / lev.iloc[i]
        minfwd.append(path.min() - 1)
minfwd = np.array(minfwd)
print(f"n {len(minfwd)}: median worst dd {fmt(np.median(minfwd))} | 25% worst {fmt(np.percentile(minfwd, 25))} | "
      f"worst {fmt(minfwd.min())} | share of panics that never trade below entry: {(minfwd >= -0.001).mean():.0%}")
print()

print("=== top 15 panic days (by dn5_share) ===")
for dt, r in df.nlargest(15, "dn5_share").iterrows():
    print(f"{dt.date()} n={int(r['n'])} dn5={int(r['c_dn5'])} ({r['dn5_share']:.0%})  ew {r['ew_ret']/100:+.2%}  "
          f"f5 {fmt(r['ew_f5'])}  f20 {fmt(r['ew_f20'])}")
print()

print("=== trajectory around dn5>=15% days (n shown) ===")
lev = df["ew"]
rows = []
for i in range(len(df)):
    if df["dn5_share"].iloc[i] >= 0.15 and i - 10 >= 0 and i + 40 < len(df):
        base = lev.iloc[i]
        rows.append((lev.iloc[i - 10:i + 41] / base - 1).values)
M = np.array(rows)
offs = list(range(-10, 41))
print(f"n={len(M)}")
for o in (-10, -5, -1, 1, 2, 3, 4, 5, 10, 20, 30, 40):
    col = M[:, offs.index(o)]
    print(f"t{o:+3d}: mean {fmt(np.nanmean(col))} median {fmt(np.nanmedian(col))}")
print()

print("=== basket (down>5% stocks) vs market, on panic days ===")
for thr in (0.10, 0.15, 0.25):
    m = df["dn5_share"] >= thr
    ex5 = (df.loc[m, "fw5_dn5"] - df.loc[m, "fw5_all"]).dropna()
    ex20 = (df.loc[m, "fw20_dn5"] - df.loc[m, "fw20_all"]).dropna()
    eps = episodes(m)
    epv = [(df.loc[a:b, "fw5_dn5"] - df.loc[a:b, "fw5_all"]).mean() for a, b in eps]
    epv = [x for x in epv if not np.isnan(x)]
    print(f"thr {thr}: n {len(ex5)} f5 excess {fmt(ex5.mean())} t(ep) {tstat(epv):.2f} | "
          f"f20 excess {fmt(ex20.mean())} n {len(ex20)}")
print()


def strat_curve(mask, k=5, cost=0.001, series="ew"):
    lev = df[series].to_numpy()
    n = len(lev)
    cur = 1.0
    expo_end = -1
    curve = np.empty(n)
    entries = 0
    expo_days = 0
    for i in range(n):
        if i > 0:
            if i <= expo_end:
                cur *= lev[i] / lev[i - 1]
                expo_days += 1
        if i > expo_end and bool(mask.iloc[i]) and i + k < n:
            cur *= (1 - cost)
            expo_end = i + k
            entries += 1
        curve[i] = cur
    return pd.Series(curve, index=df.index), entries, expo_days


def stats(curve):
    yrs = (curve.index[-1] - curve.index[0]).days / 365.25
    cagr = curve.iloc[-1] ** (1 / yrs) - 1
    dd = (curve / curve.cummax() - 1).min()
    return cagr, dd


print("=== strategy: cash + buy at close of panic day, hold k days (roundtrip cost 0.1%) ===")
for series, slab in (("ew", "EW"), ("vw", "cap-wt")):
    lev = df[series]
    yrs = (lev.index[-1] - lev.index[0]).days / 365.25
    cagr_bh = lev.iloc[-1] ** (1 / yrs) - 1
    dd_bh = (lev / lev.cummax() - 1).min()
    print(f"buy&hold {slab}: total {lev.iloc[-1]-1:+.1%} CAGR {fmt(cagr_bh)} MaxDD {fmt(dd_bh)}")
    for tname, mask in (("dn5>=15%", df["dn5_share"] >= 0.15), ("dn5>=25%", df["dn5_share"] >= 0.25)):
        for k in (5, 10, 20):
            c, entries, expo_days = strat_curve(mask, k=k, cost=0.001, series=series)
            cagr, dd = stats(c)
            print(f"  {tname} k={k:2d}: entries {entries:3d} expo_days {expo_days:4d} ({expo_days/len(df):.0%}) "
                  f"| total {c.iloc[-1]-1:+.1%} CAGR {fmt(cagr)} MaxDD {fmt(dd)}")
    print()
