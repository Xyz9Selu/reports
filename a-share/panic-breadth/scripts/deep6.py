#!/usr/bin/env python3
"""Deep dive #6: trade-level stats for the washout+thrust signal.
Signal = panic (dn5>=15%) within prior 10 trading days AND today up95_share>=3%.
Entry = signal-day close, exit = close of t+k.
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
for k in (1, 5, 10, 20):
    df[f"ew_f{k}"] = df["ew"].shift(-k) / df["ew"] - 1
    df[f"vw_f{k}"] = df["vw"].shift(-k) / df["vw"] - 1

wash = (df["dn5_share"].shift(1) >= 0.15).rolling(10, min_periods=1).max().fillna(False).astype(bool)
thrust = wash & (df["up95_share"] >= 0.03)
df["sig"] = thrust
print("total signals:", int(thrust.sum()))


def fmt(x):
    return " nan " if (x is None or (isinstance(x, float) and np.isnan(x))) else f"{x*100:+.2f}%"


def show_stats(m, label, series="ew"):
    sub = df[m]
    print(f"--- {label} (n={len(sub)}) ---")
    for k in (1, 5, 10, 20):
        r = sub[f"{series}_f{k}"].dropna()
        if len(r) == 0:
            continue
        print(f"  f{k}: mean {fmt(r.mean())} med {fmt(r.median())} hit {100*(r>0).mean():.0f}% "
              f"hit_net {100*(r>0.002).mean():.0f}% | p25 {fmt(r.quantile(.25))} p75 {fmt(r.quantile(.75))} "
              f"| min {fmt(r.min())} max {fmt(r.max())}")


show_stats(thrust, "ALL signals EW")
show_stats(thrust, "ALL signals VW", series="vw")
show_stats(thrust & (df.index >= "2020-01-01"), "2020+ signals EW")
show_stats(thrust & (df.index >= "2020-01-01"), "2020+ signals VW", series="vw")
print()

# episodes: first signal after >10td gap
pos = np.where(thrust.to_numpy())[0]
epi_pos, last = [], -999
for p in pos:
    if p - last > 10:
        epi_pos.append(p)
    last = p
epi = df.iloc[epi_pos]
print(f"episodes (gap>10td): {len(epi)} | by year: {epi.index.year.value_counts().sort_index().to_dict()}")
show_stats(df.index.isin(epi.index), "episode-first EW")

# non-overlapping practical execution
def count_entries(mask, k):
    m = mask.to_numpy()
    n = len(m)
    e = 0
    end = -1
    for i in range(n):
        if i > end and m[i] and i + k < n:
            e += 1
            end = i + k
    return e


print()
print("non-overlap entries k=5:", count_entries(thrust, 5), "| k=10:", count_entries(thrust, 10),
      "| k=20:", count_entries(thrust, 20))
m20 = thrust & (df.index >= "2020-01-01")
print("2020+ non-overlap entries k=5:", count_entries(m20, 5), "| k=10:", count_entries(m20, 10),
      "| k=20:", count_entries(m20, 20))

yrs = (df.index[-1] - df.index[0]).days / 365.25
print(f"sample years {yrs:.1f} | signals/yr {len(df[thrust])/yrs:.1f} | episodes/yr {len(epi)/yrs:.1f}")

# path risk: worst drawdown within next 20d after signal
ewv = df["ew"].to_numpy()
mins = []
for p in pos:
    if p + 20 < len(ewv):
        path = ewv[p + 1:p + 21] / ewv[p] - 1
        mins.append(path.min())
mins = pd.Series(mins)
print(f"path risk (next 20d): n {len(mins)} | median worst point {fmt(mins.median())} | "
      f"25% worst {fmt(mins.quantile(.25))} | worst {fmt(mins.min())} | "
      f"share never below -5%: {100*(mins>-0.05).mean():.0f}%")
print()
print("last 12 signal dates:", ", ".join(str(d.date()) for d in df[thrust].index[-12:]))
print("2026 signals:", ", ".join(str(d.date()) for d in df[thrust].index if d.year == 2026))
