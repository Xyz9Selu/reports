#!/usr/bin/env python3
"""Fetch PE + adj data for Huang Yang PE-band backtest.

Stocks: stable blue chips frequently covered by Huang Yang (banks, baijiu,
utilities, appliances, dairy, coal) + one counter-example (Daqin Railway,
his "low valuation trap" case study).
"""
import os
import sys
import json

sys.path.insert(0, os.path.expanduser("~/stock-analyse-serenity/scripts"))
from data_client import DataClient  # noqa: E402


def get_rows(resp):
    if isinstance(resp, dict) and "rows" in resp:
        return resp["rows"]
    if isinstance(resp, list):
        return resp
    return []


STOCKS = {
    "600036.SH": "招商银行",
    "601398.SH": "工商银行",
    "601288.SH": "农业银行",
    "600519.SH": "贵州茅台",
    "000858.SZ": "五粮液",
    "600900.SH": "长江电力",
    "000333.SZ": "美的集团",
    "000651.SZ": "格力电器",
    "600887.SH": "伊利股份",
    "601088.SH": "中国神华",
    "601006.SH": "大秦铁路",
}

OUT = os.path.expanduser("~/stock-scripts/huangyang_backtest/data")
os.makedirs(OUT, exist_ok=True)

client = DataClient()
for code, name in STOCKS.items():
    path = os.path.join(OUT, f"{code}.json")
    if os.path.exists(path):
        print(f"SKIP {code} {name} (exists)", flush=True)
        continue
    db = get_rows(client.tushare("daily_basic", {
        "ts_code": code, "start_date": "20090101", "end_date": "20261014",
        "fields": "trade_date,close,pe_ttm",
    }))
    adj = get_rows(client.tushare("adj_factor", {
        "ts_code": code, "start_date": "20090101", "end_date": "20261014",
    }))
    json.dump({"code": code, "name": name, "db": db, "adj": adj},
              open(path, "w"))
    first = db[0]["trade_date"] if db else "?"
    last = db[-1]["trade_date"] if db else "?"
    print(f"OK {code} {name}: db={len(db)} ({first}..{last}) adj={len(adj)}", flush=True)

print("ALL DONE", flush=True)
