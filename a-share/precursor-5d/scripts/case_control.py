#!/usr/bin/env python3
"""Case-control: what precedes a tradable 5-day +5% move in CSI 300.

Locked before looking at results:
  Universe: CSI 300 point-in-time.
  Phenomenon: signs known at close t; buy next open; sell the open 5 trading
  days later; that round trip >= 5%. Unbuyable limit-up opens are not cases.
  Discovery 2016-2018, confirmation 2019-2021, backtest 2022-01-01 to 2026-10-14.
  A sign is kept only if BOTH discovery and confirmation have n>=500,
  lift>=1.15, and absolute edge>=2pp, same direction.
  Catalog is fixed. No threshold is changed after seeing the test period.
"""
import os

import numpy as np
import pandas as pd

BASE = os.path.expanduser("~/stock-scripts/precursor_5d")
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "out")
os.makedirs(OUT, exist_ok=True)

DISC = ("2016-01-01", "2018-12-31")
CONF = ("2019-01-01", "2021-12-31")
TEST = ("2022-01-01", "2026-10-14")
MIN_N = 500
MIN_LIFT = 1.15
MIN_EDGE = 0.02


def load():
    d = pd.read_csv(os.path.join(DATA, "daily.csv"), dtype={"ts_code": str}, parse_dates=["trade_date"])
    d = d.dropna(subset=["close", "open"]).sort_values(["ts_code", "trade_date"])
    g = d.groupby("ts_code", sort=False)
    d["adj_factor"] = g["adj_factor"].transform(lambda s: s.ffill().bfill())
    d["ac"] = d["close"] * d["adj_factor"]
    d["ao"] = d["open"] * d["adj_factor"]
    d["ah"] = d["high"] * d["adj_factor"]
    d["ret1"] = g["ac"].pct_change()
    d["ret5"] = g["ac"].pct_change(5)
    d["ret20"] = g["ac"].pct_change(20)
    d["vol_ma"] = g["vol"].transform(lambda s: s.shift(1).rolling(20, min_periods=15).mean())
    d["vol_ratio"] = d["vol"] / d["vol_ma"]
    d["hi20"] = g["ah"].transform(lambda s: s.shift(1).rolling(20, min_periods=15).max())
    d["lo20"] = g["ah"].transform(lambda s: s.shift(1).rolling(20, min_periods=15).min())
    # low of prior 20 days should use low, not high. fix below after this block if needed.
    d["ma20"] = g["ac"].transform(lambda s: s.rolling(20, min_periods=15).mean())
    d["ma20_prev"] = g["ma20"].shift(5)
    d["ma60"] = g["ac"].transform(lambda s: s.rolling(60, min_periods=40).mean())
    r = d["ret1"]
    d["up3"] = (r > 0) & (g["ret1"].shift(1) > 0) & (g["ret1"].shift(2) > 0)
    d["dn3"] = (r < 0) & (g["ret1"].shift(1) < 0) & (g["ret1"].shift(2) < 0)
    d["rvol5"] = g["ret1"].transform(lambda s: s.rolling(5, min_periods=5).std())
    d["rvol20"] = g["ret1"].transform(lambda s: s.rolling(20, min_periods=15).std())
    d["open_in"] = g["ao"].shift(-1)
    d["open_out"] = g["ao"].shift(-6)
    d["raw_open_in"] = g["open"].shift(-1)
    d["pre_in"] = g["pre_close"].shift(-1)
    d["dt_in"] = g["trade_date"].shift(-1)
    d["dt_out"] = g["trade_date"].shift(-6)
    d["fwd"] = d["open_out"] / d["open_in"] - 1
    d["gap_days"] = (d["dt_out"] - d["trade_date"]).dt.days
    return d


def fix_low(d):
    d["al"] = d["low"] * d["adj_factor"]
    d["lo20"] = d.groupby("ts_code", sort=False)["al"].transform(
        lambda s: s.shift(1).rolling(20, min_periods=15).min())
    return d


def membership_mask(d):
    mem = pd.read_csv(os.path.join(DATA, "members.csv"), dtype={"ts_code": str}, parse_dates=["trade_date"])
    snaps = {dt: set(g.ts_code) for dt, g in mem.groupby("trade_date")}
    snap_dates = np.array(sorted(snaps))
    date_members = {}
    for dt in d["trade_date"].drop_duplicates():
        k = snap_dates.searchsorted(np.datetime64(dt), side="right") - 1
        date_members[dt] = snaps[pd.Timestamp(snap_dates[k])] if k >= 0 else set()
    # vectorized via merge of (date -> frozenset) is slow in python; use categorical codes
    pairs = d[["ts_code", "trade_date"]].copy()
    # map date to an id, then check membership with a MultiIndex
    mem_idx = mem.set_index(["trade_date", "ts_code"]).index
    # expand each daily date to its snapshot date
    snap_for = {}
    for dt in date_members:
        k = snap_dates.searchsorted(np.datetime64(dt), side="right") - 1
        snap_for[dt] = pd.Timestamp(snap_dates[k]) if k >= 0 else pd.NaT
    pairs["snap"] = pairs["trade_date"].map(snap_for)
    keys = pd.MultiIndex.from_frame(pairs[["snap", "ts_code"]])
    return keys.isin(mem_idx)


def signs_of(d):
    near = d["ac"] / d["hi20"]
    return {
        "今日涨超3%": d["ret1"] > 0.03,
        "今日跌超3%": d["ret1"] < -0.03,
        "近5日已涨超5%": d["ret5"] > 0.05,
        "近5日已跌超5%": d["ret5"] < -0.05,
        "近20日涨超10%": d["ret20"] > 0.10,
        "近20日跌超10%": d["ret20"] < -0.10,
        "量比>1.5": d["vol_ratio"] > 1.5,
        "量比>2": d["vol_ratio"] > 2.0,
        "突破20日高点": d["ac"] >= d["hi20"],
        "贴近20日高点": (near >= 0.98) & (d["ac"] < d["hi20"]),
        "跌破20日低点": d["ac"] <= d["lo20"],
        "连涨3日": d["up3"],
        "连跌3日": d["dn3"],
        "站上上升的20日均线": (d["ac"] > d["ma20"]) & (d["ma20"] > d["ma20_prev"]),
        "跌破下降的20日均线": (d["ac"] < d["ma20"]) & (d["ma20"] < d["ma20_prev"]),
        "波动收缩": d["rvol5"] < 0.7 * d["rvol20"],
        "站上60日均线": d["ac"] > d["ma60"],
    }


def period_mask(d, span, eligible):
    lo, hi = pd.Timestamp(span[0]), pd.Timestamp(span[1])
    return eligible & (d["trade_date"] >= lo) & (d["trade_date"] <= hi)


def score(case, fired):
    fired = fired.fillna(False)
    n = int(fired.sum())
    base = float(case.mean())
    if n == 0:
        return dict(n=0, base=base, p=np.nan, lift=np.nan, edge=np.nan, mean_ret=np.nan)
    p = float(case[fired].mean())
    mean_ret = float(d_fwd_placeholder)
    return dict(n=n, base=base, p=p, lift=p / base if base else np.nan, edge=p - base)


def score_frame(case, fwd, fired):
    fired = fired.fillna(False).to_numpy()
    case_a = case.to_numpy()
    fwd_a = fwd.to_numpy()
    n = int(fired.sum())
    base = float(np.nanmean(case_a))
    if n == 0:
        return dict(n=0, base=base, p=np.nan, lift=np.nan, edge=np.nan, mean_ret=np.nan, base_ret=float(np.nanmean(fwd_a)))
    p = float(np.nanmean(case_a[fired]))
    return dict(
        n=n, base=base, p=p,
        lift=(p / base) if base else np.nan,
        edge=p - base,
        mean_ret=float(np.nanmean(fwd_a[fired])),
        base_ret=float(np.nanmean(fwd_a)),
    )


def main():
    print("loading...")
    d = fix_low(load())
    print(f"rows {len(d)}")
    d["in_idx"] = membership_mask(d)
    prefix = d["ts_code"].str[:3]
    lim = np.where(prefix.isin(["300", "301", "688", "689"]), 0.195, 0.095)
    d["unbuyable"] = (d["raw_open_in"] / d["pre_in"] - 1) >= lim
    d["gap_ok"] = d["gap_days"].between(5, 15)
    eligible = d["in_idx"] & d["fwd"].notna() & d["gap_ok"] & ~d["unbuyable"].fillna(True)
    d["case"] = eligible & (d["fwd"] >= 0.05)
    print(f"eligible {int(eligible.sum())}  cases {int(d['case'].sum())}  "
          f"base {d.loc[eligible, 'fwd'].ge(0.05).mean():.3f}")

    catalog = signs_of(d)
    rows = []
    spans = {"discovery": DISC, "confirm": CONF, "test": TEST}
    masks = {k: period_mask(d, v, eligible) for k, v in spans.items()}
    for name, sig in catalog.items():
        rec = {"sign": name}
        for k, m in masks.items():
            sc = score_frame(d.loc[m, "fwd"].ge(0.05), d.loc[m, "fwd"], sig.loc[m])
            for fld, val in sc.items():
                rec[f"{k}_{fld}"] = val
        disc_ok = (
            rec["discovery_n"] >= MIN_N
            and rec["discovery_lift"] >= MIN_LIFT
            and rec["discovery_edge"] >= MIN_EDGE
        )
        conf_ok = (
            rec["confirm_n"] >= MIN_N
            and rec["confirm_lift"] >= MIN_LIFT
            and rec["confirm_edge"] >= MIN_EDGE
        )
        rec["pass"] = bool(disc_ok and conf_ok)
        rows.append(rec)
    tab = pd.DataFrame(rows).sort_values("confirm_lift", ascending=False)
    tab.to_csv(os.path.join(OUT, "sign_lifts.csv"), index=False)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_rows", 40)
    show = tab[["sign", "pass",
                "discovery_n", "discovery_base", "discovery_p", "discovery_lift", "discovery_edge", "discovery_mean_ret",
                "confirm_n", "confirm_base", "confirm_p", "confirm_lift", "confirm_edge", "confirm_mean_ret",
                "test_n", "test_base", "test_p", "test_lift", "test_edge", "test_mean_ret", "test_base_ret"]]
    print("\n=== all signs, ranked by confirmation lift ===")
    print(show.round(4).to_string(index=False))
    passed = tab[tab["pass"]]
    print(f"\nPASSED {len(passed)} / {len(tab)}")
    if passed.empty:
        print("No sign survived both periods. Test-period numbers above are descriptive only, not a strategy.")
        return
    print(passed["sign"].tolist())

    # portfolio on test period for each passer: equal-weight names in a live 5-day hold
    # built only from signals in the test window
    test = d.loc[masks["test"], ["ts_code", "trade_date", "fwd"]].copy()
    print("\n=== test-period event returns (cost 20bp round trip not yet in mean_ret) ===")
    for name in passed["sign"]:
        sig = catalog[name]
        m = masks["test"] & sig.fillna(False)
        sub = d.loc[m, "fwd"]
        # non-overlapping: keep an event only if this stock's prior kept event is >5 trading rows away
        ev = d.loc[m, ["ts_code", "trade_date", "fwd"]].sort_values(["ts_code", "trade_date"])
        keep = []
        last = {}
        for rec in ev.itertuples(index=False):
            prev = last.get(rec.ts_code)
            if prev is None or (rec.trade_date - prev).days >= 7:
                keep.append(True)
                last[rec.ts_code] = rec.trade_date
            else:
                keep.append(False)
        ev["keep"] = keep
        nov = ev.loc[ev["keep"], "fwd"]
        cost = 0.002
        print(f"{name}: overlapping n={len(sub)} mean {sub.mean():.3%} after cost {sub.mean()-cost:.3%}  "
              f"| nonoverlap n={len(nov)} mean {nov.mean():.3%} after cost {nov.mean()-cost:.3%}  "
              f"| base {d.loc[masks['test'], 'fwd'].mean():.3%}")


if __name__ == "__main__":
    main()
