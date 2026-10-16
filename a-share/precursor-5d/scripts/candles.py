#!/usr/bin/env python3
"""Round 3: Japanese candle patterns + composites.

Same discipline. Phase A screens single patterns on discovery + confirmation
(+ both confirmation halves). Phase B builds composites ONLY from signs that
already passed in round 1 or round 2 or phase A single screens, then re-screens
the composites on discovery + confirmation with a HIGHER bar (lift>=1.20,
edge>=3pp, halves>=1.10, n>=300; test n>=200, after-cost>0, test lift>=1.10).

Definitions are mechanical, computed from open/high/low/close with adj factor.
No new thresholds after seeing the test period.
"""
import os

import numpy as np
import pandas as pd

import case_control as cc

OUT = cc.OUT
COST = 0.002


def body_stats(d):
    g = d.groupby("ts_code", sort=False)
    o, c, h, l = d["open"], d["close"], d["high"], d["low"]
    rng = (h - l).replace(0, np.nan)
    d["rng"] = rng
    d["body"] = (c - o) / rng
    d["up_sh"] = (h - np.maximum(o, c)) / rng
    d["dn_sh"] = (np.minimum(o, c) - l) / rng
    d["body_frac"] = np.abs(c - o) / d["pre_close"]
    d["prev_open"] = g["open"].shift(1)
    d["prev_close"] = g["close"].shift(1)
    d["prev_high"] = g["high"].shift(1)
    d["prev_low"] = g["low"].shift(1)
    d["prev_body"] = d["prev_close"] - d["prev_open"]
    d["ret_prev"] = g["ret1"].shift(1)
    return d


def candle_signs(d):
    o, c, h, l = d["open"], d["close"], d["high"], d["low"]
    po, pc = d["prev_open"], d["prev_close"]
    prev_up = d["ret_prev"] > 0
    prev_dn = d["ret_prev"] < 0
    return {
        "锤子": (d["dn_sh"] >= 0.55) & (d["up_sh"] <= 0.2) & (d["body_frac"].abs() <= 0.01) & (d["rng"] / d["pre_close"] > 0.02),
        "倒锤": (d["up_sh"] >= 0.55) & (d["dn_sh"] <= 0.2) & (d["body_frac"].abs() <= 0.01) & (d["rng"] / d["pre_close"] > 0.02),
        "射击之星": (d["up_sh"] >= 0.55) & (d["dn_sh"] <= 0.2) & (d["body"] < 0) & (d["rng"] / d["pre_close"] > 0.02),
        "光头阳": (d["body"] > 0) & (d["up_sh"] <= 0.05) & (d["body_frac"] > 0.02),
        "光头阴": (d["body"] < 0) & (d["up_sh"] <= 0.05) & (-d["body_frac"] > 0.02),
        "十字星": (d["body"].abs() <= 0.1) & (d["rng"] / d["pre_close"] > 0.015),
        "长十字": (d["body"].abs() <= 0.1) & (d["rng"] / d["pre_close"] > 0.04),
        "纺锤": (d["body"].abs() <= 0.35) & (d["up_sh"] > 0.25) & (d["dn_sh"] > 0.25) & (d["rng"] / d["pre_close"] > 0.02),
        "看涨吞没": prev_dn & (d["body"] > 0) & (c > po) & (o <= pc) & (d["body_frac"] > 0.015),
        "看跌吞没": prev_up & (d["body"] < 0) & (c < po) & (o >= pc) & (-d["body_frac"] > 0.015),
        "孕线": (np.maximum(o, c) < np.maximum(po, pc)) & (np.minimum(o, c) > np.minimum(po, pc)) & (np.abs(d["body_frac"]) < np.abs(d["ret_prev"])),
        "刺透": (d["ret_prev"] < -0.005) & (d["body"] > 0) & (o < pc) & (c > (po + pc) / 2) & (c < po),
        "乌云盖顶": (d["ret_prev"] > 0.005) & (d["body"] < 0) & (o > pc) & (c < (po + pc) / 2) & (c > po),
    }


def main():
    print("loading...")
    d = cc.fix_low(cc.load())
    d["in_idx"] = cc.membership_mask(d)
    prefix = d["ts_code"].str[:3]
    lim = np.where(prefix.isin(["300", "301", "688", "689"]), 0.195, 0.095)
    d["unbuyable"] = (d["raw_open_in"] / d["pre_in"] - 1) >= lim
    d["gap_ok"] = d["gap_days"].between(5, 15)
    eligible = d["in_idx"] & d["fwd"].notna() & d["gap_ok"] & ~d["unbuyable"].fillna(True)
    d = body_stats(d)

    masks = {
        "discovery": cc.period_mask(d, cc.DISC, eligible),
        "confirm": cc.period_mask(d, cc.CONF, eligible),
        "h1": cc.period_mask(d, ("2019-01-01", "2020-12-31"), eligible),
        "h2": cc.period_mask(d, ("2021-01-01", "2021-12-31"), eligible),
    }
    patterns = candle_signs(d)

    def screen(name, sig, disc_n=500, lift=1.15, edge=2e-2, half=1.10):
        rec = {"sign": name}
        for k, m in masks.items():
            sc = cc.score_frame(d.loc[m, "fwd"].ge(0.05), d.loc[m, "fwd"], sig.loc[m])
            for fld, val in sc.items():
                rec[f"{k}_{fld}"] = val
        ok = (rec["discovery_n"] >= disc_n and rec["discovery_lift"] >= lift and rec["discovery_edge"] >= edge
              and rec["confirm_n"] >= disc_n and rec["confirm_lift"] >= lift and rec["confirm_edge"] >= edge
              and rec["h1_lift"] >= half and rec["h2_lift"] >= half)
        rec["pass"] = bool(ok)
        return rec

    rows = [screen(n, s) for n, s in patterns.items()]
    pat = pd.DataFrame(rows)
    pat.to_csv(os.path.join(OUT, "candle_singles.csv"), index=False)
    pd.set_option("display.width", 240)
    cols = ["sign", "pass", "discovery_n", "discovery_lift", "discovery_edge", "confirm_n", "confirm_lift", "confirm_edge", "h1_lift", "h2_lift"]
    print("\n=== candle singles ===")
    print(pat[cols].round(3).to_string(index=False))
    passed = pat[pat["pass"]]["sign"].tolist()
    print(f"\nsingle pass {len(passed)}/{len(pat)}: {passed}")
    return d, eligible, masks, patterns, passed


if __name__ == "__main__":
    main()
