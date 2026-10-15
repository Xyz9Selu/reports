#!/usr/bin/env python3
"""15-name / 12-name books. Rebalance every 26 weeks, or on a strong signal.

Strong signal (not a weekly rank change):
  sell: a holding's lagged z > +1 (above his high line)
  swap-in: a non-holding's lagged z < -2 (extreme cheap)
Half-year reset replaces the whole book with the N lowest z.
No leverage: 15 names = 6.7% each; 12 names = 8.3% each.
Universe: CSI 300 point-in-time, plus the original 17 names as a side check.
"""
import os

import numpy as np
import pandas as pd

BASE = os.path.expanduser("~/stock-scripts/huangyang_backtest")
DB = os.path.join(BASE, "data_db")
COST = 0.001
START = pd.Timestamp("2016-10-14")


def cagr_dd(s):
    eq = (1 + s.fillna(0.0)).cumprod()
    eq = eq / eq.iloc[0]
    years = max((eq.index[-1] - eq.index[0]).days / 365.25, 1e-9)
    return float(eq.iloc[-1] - 1), float(eq.iloc[-1] ** (1 / years) - 1), float((eq / eq.cummax() - 1).min())


def load_csi_panel():
    mem = pd.read_csv(os.path.join(DB, "index_member.csv"), dtype={"ts_code": str})
    mem = mem[mem.index_code == "000300.SH"].copy()
    mem["trade_date"] = pd.to_datetime(mem["trade_date"])
    codes = sorted(mem.ts_code.unique())
    print(f"CSI300 unique codes {len(codes)}")

    wk = pd.read_csv(
        os.path.join(DB, "weekly_all.csv"),
        dtype={"ts_code": str},
        parse_dates=["trade_date"],
    )
    wk = wk[wk.ts_code.isin(codes)].copy()
    wk = wk.dropna(subset=["close"]).sort_values(["ts_code", "trade_date"])
    wk["week"] = wk["trade_date"].dt.to_period("W-FRI").dt.end_time.dt.normalize()
    wk = wk.sort_values(["ts_code", "trade_date"]).groupby(["ts_code", "week"], as_index=False).tail(1)
    wk["adj_factor"] = wk.groupby("ts_code")["adj_factor"].transform(lambda s: s.ffill().bfill())
    wk["adj"] = wk["close"] * wk["adj_factor"]
    wk["ret"] = wk.groupby("ts_code")["adj"].pct_change()
    pe = wk["pe_ttm"].where(wk["pe_ttm"] > 0)
    wk["mu"] = pe.groupby(wk["ts_code"]).transform(lambda s: s.rolling(416, min_periods=208).mean())
    wk["sd"] = pe.groupby(wk["ts_code"]).transform(lambda s: s.rolling(416, min_periods=208).std(ddof=0))
    wk["z"] = (pe - wk["mu"]) / wk["sd"]
    print(f"weekly rows in CSI300 names {len(wk)}")

    R = wk.pivot(index="week", columns="ts_code", values="ret").sort_index()
    Z = wk.pivot(index="week", columns="ts_code", values="z").reindex(R.index)

    # membership as of the latest snapshot on or before the prior week
    snaps = {}
    for dt, g in mem.groupby("trade_date"):
        snaps[pd.Timestamp(dt)] = set(g.ts_code)
    snap_dates = np.array(sorted(snaps))
    elig = pd.DataFrame(False, index=R.index, columns=R.columns)
    for i, dt in enumerate(R.index):
        prior = dt - pd.Timedelta(days=7)
        k = snap_dates.searchsorted(prior, side="right") - 1
        if k < 0:
            continue
        members = snaps[pd.Timestamp(snap_dates[k])]
        cols = [c for c in members if c in elig.columns]
        elig.loc[dt, cols] = True
    elig &= Z.notna()
    return R, Z, elig


def simulate(R, Z, elig, n, mode, start):
    """mode: semi | signal | both."""
    idx = R.index[R.index >= start]
    Zlag = Z.shift(1)
    Elag = elig.shift(1)
    Elag = Elag.where(Elag.notna(), False).astype(bool)
    held = set()
    prev_w = None
    rets, n_reb, n_sig, n_cal = [], 0, 0, 0
    last_held = set()
    weeks_since = 26  # force an opening rebalance
    for dt in idx:
        z = Zlag.loc[dt].where(Elag.loc[dt]).dropna()
        r = R.loc[dt]
        force = weeks_since >= 26
        sig = False
        if held:
            held_z = z.reindex(list(held))
            if (held_z > 1).any() or held_z.isna().any():
                sig = True
            outsiders = z.drop(labels=list(held), errors="ignore")
            if (outsiders < -2).any():
                sig = True
        do_semi = force and mode in ("semi", "both")
        do_sig = (not do_semi) and sig and mode in ("signal", "both")
        if do_semi or not held:
            held = set(z.nsmallest(min(n, len(z))).index)
            if do_semi:
                n_cal += 1
            n_reb += 1
            weeks_since = 0
        elif do_sig:
            n_sig += 1
            n_reb += 1
            for c in list(held):
                if c not in z.index or z[c] > 1:
                    held.discard(c)
            outsiders = z.drop(labels=list(held), errors="ignore")
            for c in outsiders[outsiders < -2].index:
                held.add(c)
            if len(held) < n:
                pool = z.drop(labels=list(held), errors="ignore")
                held.update(pool.nsmallest(n - len(held)).index)
            if len(held) > n:
                rank = z.reindex(list(held)).dropna().sort_values(ascending=False)
                for c in rank.index[: len(held) - n]:
                    held.discard(c)
        else:
            weeks_since += 1

        live = [c for c in held if c in r.index and pd.notna(r[c])]
        w = pd.Series(0.0, index=R.columns)
        if live:
            w.loc[live] = 1.0 / len(live)
        if prev_w is None:
            traded = 0.0
        else:
            traded = float((w - prev_w).abs().sum())
        port = float((w * r.fillna(0.0)).sum() - traded * COST)
        rets.append(port)
        prev_w = w
        last_held = set(held)
    s = pd.Series(rets, index=idx[: len(rets)])
    return s, dict(rebalances=n_reb, signal=n_sig, calendar=n_cal, held=last_held)


def bench_equal(R, elig, start):
    idx = R.index[R.index >= start]
    out = []
    for dt in idx:
        cols = elig.columns[elig.loc[dt].to_numpy()]
        rr = R.loc[dt, cols].dropna()
        out.append(float(rr.mean()) if len(rr) else 0.0)
    return pd.Series(out, index=idx)


def report(label, s, extra):
    tot, c, dd = cagr_dd(s)
    print(f"{label:28} total {tot:7.1%}  CAGR {c:6.2%}  MaxDD {dd:6.1%}  "
          f"reb {extra['rebalances']:3} (cal {extra['calendar']}, sig {extra['signal']})  "
          f"end held {len(extra['held'])}")
    return extra["held"]


def names_of(codes):
    basic = pd.read_csv(os.path.join(DB, "basic.csv"), dtype={"ts_code": str})
    mp = dict(zip(basic.ts_code, basic.name))
    return [f"{mp.get(c, c)}" for c in codes]


def main():
    R, Z, elig = load_csi_panel()
    print(f"panel {R.shape}  {R.index.min().date()} → {R.index.max().date()}")
    b = bench_equal(R, elig, START)
    print("\n===== CSI300 equal-weight constituents, 8y z available =====")
    tot, c, dd = cagr_dd(b)
    print(f"{'buyhold equal-weight':28} total {tot:7.1%}  CAGR {c:6.2%}  MaxDD {dd:6.1%}")

    for n in (12, 15):
        print(f"\n----- N={n}  weight={1/n:.1%} -----")
        for mode in ("semi", "signal", "both"):
            s, extra = simulate(R, Z, elig, n, mode, START)
            report(f"N={n} {mode}", s, extra)

    # what a fresh ranking would hold on the last week
    last = R.index[R.index >= START][-1]
    z = Z.loc[last].where(elig.loc[last]).dropna().sort_values()
    basic = pd.read_csv(os.path.join(DB, "basic.csv"), dtype={"ts_code": str})
    mp = dict(zip(basic.ts_code, basic.name))
    print(f"\nlowest z inside CSI300 at {last.date()} (membership lagged)")
    for i, (code, v) in enumerate(z.head(15).items(), 1):
        print(f"{i:2} {mp.get(code, code):8} {code}  z={v:+.2f}")

    # side check: original 17, hold 15 or 12, both-rule, 8y z
    print("\n===== original 17 names, hold 12 or 15 =====")
    import json
    data_dir = os.path.join(BASE, "data")
    frames_r, frames_z = [], []
    code_name = {}
    for f in sorted(os.listdir(data_dir)):
        if not f.endswith(".json"):
            continue
        d = json.load(open(os.path.join(data_dir, f)))
        db = pd.DataFrame(d["db"])
        adj = pd.DataFrame(d["adj"])
        if db.empty:
            continue
        db["trade_date"] = pd.to_datetime(db["trade_date"], format="%Y%m%d")
        adj["trade_date"] = pd.to_datetime(adj["trade_date"], format="%Y%m%d")
        db["close"] = pd.to_numeric(db["close"], errors="coerce")
        db["pe_ttm"] = pd.to_numeric(db["pe_ttm"], errors="coerce")
        adj["adj_factor"] = pd.to_numeric(adj["adj_factor"], errors="coerce")
        df = db.merge(adj[["trade_date", "adj_factor"]], on="trade_date", how="left")
        df = df.sort_values("trade_date").set_index("trade_date")
        df["adj_factor"] = df["adj_factor"].ffill().bfill()
        df["adj"] = df["close"] * df["adj_factor"]
        wk = df.resample("W-FRI").last()
        wk = wk[wk["close"].notna()]
        pe = wk["pe_ttm"].where(wk["pe_ttm"] > 0)
        mu = pe.rolling(416, min_periods=208).mean()
        sd = pe.rolling(416, min_periods=208).std(ddof=0)
        frames_r.append(wk["adj"].pct_change().rename(d["code"]))
        frames_z.append(((pe - mu) / sd).rename(d["code"]))
        code_name[d["code"]] = d["name"]
    R17 = pd.concat(frames_r, axis=1).sort_index()
    Z17 = pd.concat(frames_z, axis=1).reindex(R17.index)
    elig17 = Z17.notna()
    b17 = bench_equal(R17, elig17, START)
    tot, c, dd = cagr_dd(b17)
    print(f"{'17 equal-weight':28} total {tot:7.1%}  CAGR {c:6.2%}  MaxDD {dd:6.1%}")
    for n in (12, 15):
        s, extra = simulate(R17, Z17, elig17, n, "both", START)
        held = report(f"17 N={n} both", s, extra)
        print("   end:", ", ".join(code_name.get(c, c) for c in sorted(held)))


if __name__ == "__main__":
    main()
