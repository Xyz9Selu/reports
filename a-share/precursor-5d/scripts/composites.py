#!/usr/bin/env python3
"""Round 3b: composites from PRE-VALIDATED signs only.

Sources allowed in a composite:
  R1 passers: 今日跌超3%, 近20日涨超10%, 今日涨超3%, 近5日已跌超5%
  R2 passers: 今日跌超5%, 今日跌超7%, 换手超5%, 振幅超5%, 今日涨超7%,
              今日涨超5%, 近60日涨超20%, 近10日涨超8%, 放量下跌,
              昨日大跌今日翻红, 低开超1%, 近10日跌超8%, 昨日大涨今日翻绿,
              高开超1%
  Candle passers: 射击之星, 光头阳, 长十字, 纺锤
Composites re-screen with a higher bar: discovery+confirmation n>=300,
lift>=1.20, edge>=3pp, halves lift>=1.10. Test opens only for passers:
n>=200, after-cost mean>0, test lift>=1.10.
"""
import os

import numpy as np
import pandas as pd

import case_control as cc
import candles as cd

OUT = cc.OUT
COST = 0.002


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

    # base signs (same definitions as rounds 1-2)
    r1 = cc.signs_of(d)
    r2 = __import__("expand_search").extra_signs(d)
    ca = cd.candle_signs(d)
    base = {}
    base.update({k: v for k, v in r1.items()})
    base.update({k: v for k, v in r2.items()})
    base.update({k: v for k, v in ca.items()})

    r1_pass = ["今日跌超3%", "近20日涨超10%", "今日涨超3%", "近5日已跌超5%"]
    r2_pass = ["今日跌超5%", "今日跌超7%", "换手超5%", "振幅超5%", "今日涨超7%",
               "今日涨超5%", "近60日涨超20%", "近10日涨超8%", "放量下跌",
               "昨日大跌今日翻红", "低开超1%", "近10日跌超8%", "昨日大涨今日翻绿", "高开超1%"]
    ca_pass = ["射击之星", "光头阳", "长十字", "纺锤"]
    validated = r1_pass + r2_pass + ca_pass
    for n in validated:
        assert n in base, n

    def A(x):
        return base[x].fillna(False)

    composites = {
        # candle x candle
        "长十字×纺锤": A("长十字") & A("纺锤"),
        "射击之星×放量": A("射击之星") & (d["vol_ratio"] > 1.2),
        "光头阳×放量": A("光头阳") & (d["vol_ratio"] > 1.2),
        # candle x drop
        "射击之星×近5日跌超5%": A("射击之星") & A("近5日已跌超5%"),
        "纺锤×近5日跌超5%": A("纺锤") & A("近5日已跌超5%"),
        "长十字×近5日跌超5%": A("长十字") & A("近5日已跌超5%"),
        # candle x position / trend
        "射击之星×贴近高点": A("射击之星") & A("贴近20日高点"),
        "长十字×跌破60日均线": A("长十字") & A("跌破60日均线"),
        "纺锤×跌破20日低点": A("纺锤") & base.get("跌破20日低点", pd.Series(False, index=d.index)),
        # big movers x volume
        "跌超5%×放量": A("今日跌超5%") & A("放量下跌"),
        "跌超5%×量比>2": A("今日跌超5%") & (d["vol_ratio"] > 2.0),
        "跌超7%×量比>2": A("今日跌超7%") & (d["vol_ratio"] > 2.0),
        "跌超5%×低开超1%": A("今日跌超5%") & A("低开超1%"),
        "跌超7%×低开超1%": A("今日跌超7%") & A("低开超1%"),
        "跌超5%×换手超5%": A("今日跌超5%") & A("换手超5%"),
        # big movers x position
        "跌超5%×跌破20日低点": A("今日跌超5%") & base.get("跌破20日低点", pd.Series(False, index=d.index)),
        "跌超5%×近10日跌超8%": A("今日跌超5%") & A("近10日跌超8%"),
        "涨超5%×贴近60日高点": A("今日涨超5%") & A("贴近60日高点"),
        "涨超7%×放量": A("今日涨超7%") & (d["vol_ratio"] > 1.2),
        "近60日涨超20%×贴近60日高点": A("近60日涨超20%") & A("贴近60日高点"),
        # reversal combos
        "昨日大跌今日翻红×放量": A("昨日大跌今日翻红") & (d["vol_ratio"] > 1.2),
        "低开超1%×长下影": A("低开超1%") & A("长下影"),
    }

    masks = {
        "discovery": cc.period_mask(d, cc.DISC, eligible),
        "confirm": cc.period_mask(d, cc.CONF, eligible),
        "h1": cc.period_mask(d, ("2019-01-01", "2020-12-31"), eligible),
        "h2": cc.period_mask(d, ("2021-01-01", "2021-12-31"), eligible),
        "test": cc.period_mask(d, cc.TEST, eligible),
    }

    rows = []
    for name, sig in composites.items():
        rec = {"sign": name, "name_n": int(sig.fillna(False).sum())}
        for k in ("discovery", "confirm", "h1", "h2"):
            m = masks[k]
            sc = cc.score_frame(d.loc[m, "fwd"].ge(0.05), d.loc[m, "fwd"], sig.loc[m])
            for fld, val in sc.items():
                rec[f"{k}_{fld}"] = val
        ok = (rec["discovery_n"] >= 300 and rec["discovery_lift"] >= 1.20 and rec["discovery_edge"] >= 0.03
              and rec["confirm_n"] >= 300 and rec["confirm_lift"] >= 1.20 and rec["confirm_edge"] >= 0.03
              and rec["h1_lift"] >= 1.10 and rec["h2_lift"] >= 1.10)
        rec["pass"] = bool(ok)
        rows.append(rec)
    tab = pd.DataFrame(rows).sort_values("confirm_lift", ascending=False)
    cols = ["sign", "name_n", "pass", "discovery_n", "discovery_lift", "discovery_edge",
            "confirm_n", "confirm_lift", "confirm_edge", "h1_lift", "h2_lift"]
    pd.set_option("display.width", 240)
    print("\n=== composites, discovery+confirmation ===")
    print(tab[cols].round(3).to_string(index=False))

    passers = tab[tab["pass"]]
    print(f"\ncomposite pass {len(passers)}/{len(tab)}")
    if not passers.empty:
        for i, rec in passers.iterrows():
            sig = composites[rec["sign"]]
            m = masks["test"]
            sc = cc.score_frame(d.loc[m, "fwd"].ge(0.05), d.loc[m, "fwd"], sig.loc[m])
            fired = m & sig.fillna(False)
            nov_n, nov_mean = None, None
            ev = d.loc[fired, ["ts_code", "trade_date", "fwd"]].sort_values(["ts_code", "trade_date"])
            keep, last = [], {}
            for x in ev.itertuples(index=False):
                prev = last.get(x.ts_code)
                if prev is None or (x.trade_date - prev).days >= 7:
                    keep.append(True); last[x.ts_code] = x.trade_date
                else:
                    keep.append(False)
            nov = ev.loc[keep, "fwd"]
            print(f"{rec['sign']}: test n={sc['n']} lift={sc['lift']:.3f} p={sc['p']:.3f} "
                  f"mean={sc['mean_ret']:+.3%} | nov n={len(nov)} after_cost={nov.mean()-COST:+.3%}")
    tab.to_csv(os.path.join(OUT, "composites.csv"), index=False)


if __name__ == "__main__":
    main()
