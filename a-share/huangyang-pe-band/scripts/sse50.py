#!/usr/bin/env python3
"""Same 12/15 sleeve test, universe = SSE 50 (000016.SH), point-in-time."""
import os

import numpy as np
import pandas as pd

import sleeve15 as s

DB = s.DB
START = s.START


def load_panel(index_code):
    mem = pd.read_csv(os.path.join(DB, "sse50_member.csv"), dtype={"ts_code": str})
    mem["trade_date"] = pd.to_datetime(mem["trade_date"])
    codes = sorted(mem.ts_code.unique())
    print(f"{index_code} unique codes {len(codes)}  snapshots {mem.trade_date.nunique()}")
    per = mem.groupby("trade_date").size()
    print(f"names per snapshot median {per.median():.0f}  min {per.min()}  max {per.max()}")

    wk = pd.read_csv(os.path.join(DB, "weekly_all.csv"), dtype={"ts_code": str}, parse_dates=["trade_date"])
    wk = wk[wk.ts_code.isin(codes)].dropna(subset=["close"]).sort_values(["ts_code", "trade_date"])
    wk["week"] = wk["trade_date"].dt.to_period("W-FRI").dt.end_time.dt.normalize()
    wk = wk.groupby(["ts_code", "week"], as_index=False).tail(1)
    wk["adj_factor"] = wk.groupby("ts_code")["adj_factor"].transform(lambda x: x.ffill().bfill())
    wk["adj"] = wk["close"] * wk["adj_factor"]
    wk["ret"] = wk.groupby("ts_code")["adj"].pct_change()
    pe = wk["pe_ttm"].where(wk["pe_ttm"] > 0)
    wk["mu"] = pe.groupby(wk["ts_code"]).transform(lambda x: x.rolling(416, min_periods=208).mean())
    wk["sd"] = pe.groupby(wk["ts_code"]).transform(lambda x: x.rolling(416, min_periods=208).std(ddof=0))
    wk["z"] = (pe - wk["mu"]) / wk["sd"]

    R = wk.pivot(index="week", columns="ts_code", values="ret").sort_index()
    Z = wk.pivot(index="week", columns="ts_code", values="z").reindex(R.index)
    snaps = {pd.Timestamp(dt): set(g.ts_code) for dt, g in mem.groupby("trade_date")}
    snap_dates = np.array(sorted(snaps))
    elig = pd.DataFrame(False, index=R.index, columns=R.columns)
    for dt in R.index:
        k = snap_dates.searchsorted(dt - pd.Timedelta(days=7), side="right") - 1
        if k < 0:
            continue
        cols = [c for c in snaps[pd.Timestamp(snap_dates[k])] if c in elig.columns]
        elig.loc[dt, cols] = True
    elig &= Z.notna()
    return R, Z, elig


def main():
    R, Z, elig = load_panel("000016.SH")
    idx = R.index[R.index >= START]
    print(f"panel {R.shape}  test {idx[0].date()} → {idx[-1].date()}  "
          f"elig mean {elig.loc[idx].sum(axis=1).mean():.1f}")
    b = s.bench_equal(R, elig, START)
    tot, c, dd = s.cagr_dd(b)
    print(f"{'SSE50 equal-weight':28} total {tot:7.1%}  CAGR {c:6.2%}  MaxDD {dd:6.1%}")
    by = (1 + b).groupby(b.index.year).prod() - 1
    print("yearly", " ".join(f"{y}:{v:+.0%}" for y, v in by.round(3).items()))

    for n in (12, 15):
        print(f"\n----- N={n}  weight={1/n:.1%} -----")
        for mode in ("semi", "signal", "both"):
            series, extra = s.simulate(R, Z, elig, n, mode, START)
            s.report(f"N={n} {mode}", series, extra)

    last = idx[-1]
    z = Z.loc[last].where(elig.loc[last]).dropna().sort_values()
    basic = pd.read_csv(os.path.join(DB, "basic.csv"), dtype={"ts_code": str})
    mp = dict(zip(basic.ts_code, basic.name))
    print(f"\nlowest z inside SSE50 at week {last.date()}")
    for i, (code, v) in enumerate(z.head(15).items(), 1):
        print(f"{i:2} {mp.get(code, code):8} {code}  z={v:+.2f}")
    print(f"eligible that week {int(elig.loc[last].sum())}")


if __name__ == "__main__":
    main()
