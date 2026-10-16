#!/usr/bin/env python3
"""Round 3c: classic multi-bar candle patterns, same locked screens as round 3a.

Definitions are mechanical and lenient (standard textbook shapes, no tuning).
Screen bar identical to candles.py: discovery+confirmation n>=500, lift>=1.15,
edge>=2pp, both confirmation halves >=1.10. Test opened only afterwards.
"""
import os

import numpy as np
import pandas as pd

import case_control as cc
import candles as cd

OUT = cc.OUT
COST = 0.002


def more_signs(d):
    g = d.groupby("ts_code", sort=False)
    a1 = {k: g[col].shift(1) for k, col in (("o", "ao"), ("c", "ac"), ("h", "ah"), ("l", "al"))}
    a2 = {k: g[col].shift(2) for k, col in (("o", "ao"), ("c", "ac"), ("h", "ah"), ("l", "al"))}
    ao, ac, ah, al = d["ao"], d["ac"], d["ah"], d["al"]
    b0 = ac - ao
    f0 = b0 / ao
    f1 = (a1["c"] - a1["o"]) / a1["o"]
    f2 = (a2["c"] - a2["o"]) / a2["o"]
    up = b0 > 0
    dn = b0 < 0
    return {
        "早晨之星": (f2 <= -0.015) & (f1.abs() <= 0.012) & (np.minimum(a1["o"], a1["c"]) <= np.minimum(a2["o"], a2["c"])) & up & (ac > (a2["o"] + a2["c"]) / 2) & (f0 >= 0.015),
        "黄昏之星": (f2 >= 0.015) & (f1.abs() <= 0.012) & (np.maximum(a1["o"], a1["c"]) >= np.maximum(a2["o"], a2["c"])) & dn & (ac < (a2["o"] + a2["c"]) / 2) & (f0 <= -0.015),
        "红三兵": (f0 >= 0.01) & (f1 >= 0.01) & (f2 >= 0.01) & (ac > a1["c"]) & (a1["c"] > a2["c"]),
        "三只乌鸦": (f0 <= -0.01) & (f1 <= -0.01) & (f2 <= -0.01) & (ac < a1["c"]) & (a1["c"] < a2["c"]),
        "平底": (a1["c"] < a1["o"]) & up & (al / a1["l"] <= 1.003) & (al / a1["l"] >= 0.997),
        "平顶": (a1["c"] > a1["o"]) & dn & (ah / a1["h"] >= 0.997) & (ah / a1["h"] <= 1.003),
        "向上跳空缺口": (al > a1["h"]) & (al / a1["h"] - 1 >= 0.005),
        "向下跳空缺口": (ah < a1["l"]) & (1 - ah / a1["l"] >= 0.005),
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
    d = cd.body_stats(d)

    masks = {
        "discovery": cc.period_mask(d, cc.DISC, eligible),
        "confirm": cc.period_mask(d, cc.CONF, eligible),
        "h1": cc.period_mask(d, ("2019-01-01", "2020-12-31"), eligible),
        "h2": cc.period_mask(d, ("2021-01-01", "2021-12-31"), eligible),
    }
    signs = more_signs(d)

    rows = []
    for name, sig in signs.items():
        rec = {"sign": name, "n_all": int(sig.fillna(False).sum())}
        for k, m in masks.items():
            sc = cc.score_frame(d.loc[m, "fwd"].ge(0.05), d.loc[m, "fwd"], sig.loc[m])
            for fld, val in sc.items():
                rec[f"{k}_{fld}"] = val
        ok = (rec["discovery_n"] >= 500 and rec["discovery_lift"] >= 1.15 and rec["discovery_edge"] >= 2e-2
              and rec["confirm_n"] >= 500 and rec["confirm_lift"] >= 1.15 and rec["confirm_edge"] >= 2e-2
              and rec["h1_lift"] >= 1.10 and rec["h2_lift"] >= 1.10)
        rec["pass"] = bool(ok)
        rows.append(rec)
    tab = pd.DataFrame(rows)
    pd.set_option("display.width", 240)
    cols = ["sign", "n_all", "pass", "discovery_n", "discovery_lift", "discovery_edge", "confirm_n", "confirm_lift", "confirm_edge", "h1_lift", "h2_lift"]
    print(tab[cols].round(3).to_string(index=False))
    print(f"\npass {int(tab['pass'].sum())}/{len(tab)}")

    # test-period detail for every pattern (descriptive only)
    test = cc.period_mask(d, cc.TEST, eligible)
    print("\n=== test-period detail (non-overlap, after 20bp cost) ===")
    for name, sig in signs.items():
        rec = tab[tab["sign"] == name].iloc[0]
        fired = test & sig.fillna(False)
        ev = d.loc[fired, ["ts_code", "trade_date", "fwd"]].sort_values(["ts_code", "trade_date"])
        keep, last = [], {}
        for x in ev.itertuples(index=False):
            prev = last.get(x.ts_code)
            if prev is None or (x.trade_date - prev).days >= 7:
                keep.append(True); last[x.ts_code] = x.trade_date
            else:
                keep.append(False)
        nov = ev.loc[keep, "fwd"]
        print(f"{name}: pass={rec['pass']} test n={len(ev)} nov n={len(nov)} "
              f"nov_mean={nov.mean():+.2%} after_cost={nov.mean()-COST:+.2%}")
    tab.to_csv(os.path.join(OUT, "candles_more.csv"), index=False)


if __name__ == "__main__":
    main()
