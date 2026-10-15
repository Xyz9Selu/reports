#!/usr/bin/env python3
"""Second pass: a larger fixed catalog. Thresholds unchanged.

Because more signs are tried, a sign must also clear both halves of the
confirmation window (2019-2020 and 2021) at lift>=1.10 and edge>=1pp.
Test period is scored only after that filter. A tradable factor additionally
needs non-overlapping test mean return after 20bp round-trip cost > 0.
"""
import os

import numpy as np
import pandas as pd

import case_control as cc

OUT = cc.OUT
COST = 0.002


def extra_signs(d):
    g = d.groupby("ts_code", sort=False)
    d["ret10"] = g["ac"].pct_change(10)
    d["ret60"] = g["ac"].pct_change(60)
    d["hi60"] = g["ah"].transform(lambda s: s.shift(1).rolling(60, min_periods=40).max())
    d["gap"] = d["open"] / d["pre_close"] - 1
    rng = (d["high"] - d["low"]).replace(0, np.nan)
    d["close_pos"] = (d["close"] - d["low"]) / rng
    d["lower_shadow"] = (np.minimum(d["open"], d["close"]) - d["low"]) / rng
    d["day_range"] = (d["high"] - d["low"]) / d["pre_close"]
    prev_ret = g["ret1"].shift(1)
    wd = d["trade_date"].dt.dayofweek
    return {
        "今日跌超5%": d["ret1"] < -0.05,
        "今日跌超7%": d["ret1"] < -0.07,
        "今日涨超5%": d["ret1"] > 0.05,
        "今日涨超7%": d["ret1"] > 0.07,
        "低开超1%": d["gap"] < -0.01,
        "高开超1%": d["gap"] > 0.01,
        "收在日内下沿": d["close_pos"] < 0.2,
        "收在日内上沿": d["close_pos"] > 0.8,
        "长下影": (d["lower_shadow"] > 0.6) & (d["day_range"] > 0.02),
        "振幅超5%": d["day_range"] > 0.05,
        "近10日跌超8%": d["ret10"] < -0.08,
        "近10日涨超8%": d["ret10"] > 0.08,
        "近60日跌超15%": d["ret60"] < -0.15,
        "近60日涨超20%": d["ret60"] > 0.20,
        "距60日高点回撤超15%": d["ac"] / d["hi60"] - 1 < -0.15,
        "贴近60日高点": d["ac"] / d["hi60"] >= 0.97,
        "跌破60日均线": d["ac"] < d["ma60"],
        "缩量上涨": (d["ret1"] > 0.01) & (d["vol_ratio"] < 0.8),
        "放量下跌": (d["ret1"] < -0.01) & (d["vol_ratio"] > 1.5),
        "昨日大跌今日翻红": (prev_ret < -0.03) & (d["ret1"] > 0),
        "昨日大涨今日翻绿": (prev_ret > 0.03) & (d["ret1"] < 0),
        "换手超5%": d["turnover_rate"] > 5,
        "换手低于0.3%": d["turnover_rate"] < 0.3,
        "量比低于0.6": d["vol_ratio"] < 0.6,
        "周一": wd == 0,
        "周五": wd == 4,
    }


def halves(d, eligible):
    return {
        "h1": cc.period_mask(d, ("2019-01-01", "2020-12-31"), eligible),
        "h2": cc.period_mask(d, ("2021-01-01", "2021-12-31"), eligible),
    }


def nonoverlap_mean(frame):
    ev = frame.sort_values(["ts_code", "trade_date"])
    keep = []
    last = {}
    for rec in ev.itertuples(index=False):
        prev = last.get(rec.ts_code)
        if prev is None or (rec.trade_date - prev).days >= 7:
            keep.append(True)
            last[rec.ts_code] = rec.trade_date
        else:
            keep.append(False)
    nov = ev.loc[keep, "fwd"]
    return len(nov), float(nov.mean()) if len(nov) else np.nan


def main():
    print("loading...")
    d = cc.fix_low(cc.load())
    d["in_idx"] = cc.membership_mask(d)
    prefix = d["ts_code"].str[:3]
    lim = np.where(prefix.isin(["300", "301", "688", "689"]), 0.195, 0.095)
    d["unbuyable"] = (d["raw_open_in"] / d["pre_in"] - 1) >= lim
    d["gap_ok"] = d["gap_days"].between(5, 15)
    eligible = d["in_idx"] & d["fwd"].notna() & d["gap_ok"] & ~d["unbuyable"].fillna(True)
    catalog = extra_signs(d)
    print(f"new signs {len(catalog)}")
    masks = {
        "discovery": cc.period_mask(d, cc.DISC, eligible),
        "confirm": cc.period_mask(d, cc.CONF, eligible),
        "test": cc.period_mask(d, cc.TEST, eligible),
    }
    masks.update(halves(d, eligible))
    rows = []
    for name, sig in catalog.items():
        rec = {"sign": name}
        for k, m in masks.items():
            if k == "test":
                continue
            sc = cc.score_frame(d.loc[m, "fwd"].ge(0.05), d.loc[m, "fwd"], sig.loc[m])
            for fld, val in sc.items():
                rec[f"{k}_{fld}"] = val
        disc_ok = rec["discovery_n"] >= cc.MIN_N and rec["discovery_lift"] >= cc.MIN_LIFT and rec["discovery_edge"] >= cc.MIN_EDGE
        conf_ok = rec["confirm_n"] >= cc.MIN_N and rec["confirm_lift"] >= cc.MIN_LIFT and rec["confirm_edge"] >= cc.MIN_EDGE
        half_ok = (
            rec["h1_n"] >= 200 and rec["h2_n"] >= 200
            and rec["h1_lift"] >= 1.10 and rec["h2_lift"] >= 1.10
            and rec["h1_edge"] >= 0.01 and rec["h2_edge"] >= 0.01
        )
        rec["pass"] = bool(disc_ok and conf_ok and half_ok)
        rows.append(rec)
    tab = pd.DataFrame(rows).sort_values("confirm_lift", ascending=False)
    # open test only for passers
    for i, rec in tab.iterrows():
        if not rec["pass"]:
            continue
        sig = catalog[rec["sign"]]
        m = masks["test"]
        sc = cc.score_frame(d.loc[m, "fwd"].ge(0.05), d.loc[m, "fwd"], sig.loc[m])
        for fld, val in sc.items():
            tab.loc[i, f"test_{fld}"] = val
        fired = masks["test"] & sig.fillna(False)
        n_nov, mean_nov = nonoverlap_mean(d.loc[fired, ["ts_code", "trade_date", "fwd"]])
        tab.loc[i, "test_nov_n"] = n_nov
        tab.loc[i, "test_nov_mean"] = mean_nov
        tab.loc[i, "test_nov_after_cost"] = mean_nov - COST
        tab.loc[i, "tradable"] = bool(n_nov >= 200 and (mean_nov - COST) > 0 and sc["lift"] >= 1.10)
    tab.to_csv(os.path.join(OUT, "sign_lifts_round2.csv"), index=False)
    pd.set_option("display.width", 240)
    pd.set_option("display.max_rows", 40)
    cols = ["sign", "pass", "discovery_n", "discovery_lift", "discovery_edge",
            "confirm_lift", "confirm_edge", "h1_lift", "h2_lift"]
    print(tab[cols].round(3).to_string(index=False))
    passed = tab[tab["pass"]]
    print(f"\nprobability pass {len(passed)} / {len(tab)}")
    if not passed.empty:
        show = ["sign", "test_n", "test_lift", "test_edge", "test_mean_ret", "test_nov_n", "test_nov_after_cost", "tradable"]
        print(passed[show].round(4).to_string(index=False))
        print("tradable", int(passed["tradable"].fillna(False).sum()))
    else:
        print("none passed. test period not used.")


if __name__ == "__main__":
    main()
