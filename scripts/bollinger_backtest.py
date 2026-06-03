#!/usr/bin/env python3
"""
Bollinger Band Breakout Strategy Backtester
============================================
Strategy: MA(N) ± K*σ, N-day confirmation for entry, exit on return + MA flattening.

Usage:
    python bollinger_backtest.py
    python bollinger_backtest.py --codes sh.600519 sh.000300 sz.000001
    python bollinger_backtest.py --codes sh.000300 --start 2020-01-01 --end 2026-06-01
    python bollinger_backtest.py --window 30 --std 2.5 --confirm 3
"""

import argparse
import json
import sys
from pathlib import Path

import baostock as bs
import numpy as np
import pandas as pd


def parse_args():
    p = argparse.ArgumentParser(description="Bollinger Band breakout backtest")
    p.add_argument("--codes", nargs="+", default=["sh.000300"],
                   help="baostock codes (default: sh.000300 CSI 300 Index)")
    p.add_argument("--start", default="2023-01-01", help="start date YYYY-MM-DD")
    p.add_argument("--end", default="2026-06-01", help="end date YYYY-MM-DD")
    p.add_argument("--window", type=int, default=20, help="MA window (default: 20)")
    p.add_argument("--std", type=float, default=2.0, help="std dev multiplier (default: 2.0)")
    p.add_argument("--confirm", type=int, default=2,
                   help="consecutive days above upper band to confirm entry (default: 2)")
    p.add_argument("--flat-threshold", type=float, default=0.003,
                   help="MA slope threshold for 'flat' (default: 0.003)")
    p.add_argument("--output", "-o", help="save results to JSON file")
    return p.parse_args()


def fetch_data(code: str, start: str, end: str) -> pd.DataFrame:
    """Fetch daily OHLCV from baostock (前复权)."""
    rs = bs.query_history_k_data_plus(
        code, "date,open,high,low,close,volume",
        start_date=start, end_date=end,
        frequency="d", adjustflag="2",
    )
    rows = []
    while rs.error_code == "0" and rs.next():
        rows.append(rs.get_row_data())
    if not rows:
        raise ValueError(f"No data returned for {code}")
    df = pd.DataFrame(rows, columns=rs.fields)
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])
    df = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
    return df


def calc_bollinger(df: pd.DataFrame, window: int, num_std: float) -> pd.DataFrame:
    """Add Bollinger Band columns."""
    df = df.copy()
    df["ma"] = df["close"].rolling(window).mean()
    df["std"] = df["close"].rolling(window).std()
    df["upper"] = df["ma"] + num_std * df["std"]
    df["lower"] = df["ma"] - num_std * df["std"]
    df["ma_slope"] = df["ma"].pct_change(5).abs()
    return df


def backtest(df: pd.DataFrame, name: str, confirm_days: int,
             flat_threshold: float) -> dict:
    """Run Bollinger breakout backtest on a single series."""
    df = calc_bollinger(df, args.window, args.std)
    df = df.dropna().reset_index(drop=True)

    trades = []
    position = None

    for i in range(confirm_days, len(df)):
        row = df.iloc[i]

        # --- Entry: N consecutive closes above upper band ---
        if position is None:
            if all(df.iloc[i - j]["close"] > df.iloc[i - j]["upper"]
                   for j in range(confirm_days)):
                position = {
                    "entry_date": row["date"],
                    "entry_price": row["close"],
                    "peak": row["close"],
                }
                continue

        # --- In position: track peak, check exit ---
        if position is not None:
            position["peak"] = max(position["peak"], row["close"])

            if row["close"] < row["upper"] and row["ma_slope"] < flat_threshold:
                pnl = (row["close"] - position["entry_price"]) / position["entry_price"]
                max_gain = (position["peak"] - position["entry_price"]) / position["entry_price"]
                holding = (row["date"] - position["entry_date"]).days

                trades.append({
                    "entry_date": position["entry_date"].strftime("%Y-%m-%d"),
                    "exit_date": row["date"].strftime("%Y-%m-%d"),
                    "entry_price": round(position["entry_price"], 4),
                    "exit_price": round(row["close"], 4),
                    "pnl_pct": round(pnl * 100, 2),
                    "max_gain_pct": round(max_gain * 100, 2),
                    "holding_days": holding,
                    "win": pnl > 0,
                })
                position = None

    if not trades:
        return {"name": name, "total_trades": 0, "note": "No trade signals generated"}

    tdf = pd.DataFrame(trades)
    wins = tdf[tdf["win"]]

    # Cumulative return
    cum = 1.0
    for t in trades:
        cum *= (1 + t["pnl_pct"] / 100)

    total_days = (pd.to_datetime(trades[-1]["exit_date"])
                  - pd.to_datetime(trades[0]["entry_date"])).days
    annual = (cum ** (365 / max(total_days, 1)) - 1) * 100

    # Buy-and-hold benchmark
    bh_ret = (df.iloc[-1]["close"] - df.iloc[0]["close"]) / df.iloc[0]["close"] * 100
    bh_annual = ((1 + bh_ret / 100) ** (365 / max(len(df), 1)) - 1) * 100

    false_bo = len(tdf[tdf["max_gain_pct"] < 2]) / len(trades) * 100

    return {
        "name": name,
        "data_range": f"{df.iloc[0]['date'].strftime('%Y-%m-%d')} ~ "
                      f"{df.iloc[-1]['date'].strftime('%Y-%m-%d')}",
        "total_trades": len(trades),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 1),
        "avg_pnl_pct": round(tdf["pnl_pct"].mean(), 2),
        "avg_holding_days": round(tdf["holding_days"].mean(), 1),
        "max_gain_pct": round(tdf["pnl_pct"].max(), 2),
        "max_loss_pct": round(tdf["pnl_pct"].min(), 2),
        "false_breakout_pct": round(false_bo, 1),
        "cum_return_pct": round((cum - 1) * 100, 2),
        "annual_return_pct": round(annual, 2),
        "bh_annual_pct": round(bh_annual, 2),
        "outperform_pct": round(annual - bh_annual, 2),
        "trades": trades,
    }


def print_report(result: dict):
    """Pretty-print a single backtest result."""
    print(f"\n{'=' * 56}")
    print(f"  {result['name']}")
    print(f"{'=' * 56}")

    if result.get("note"):
        print(f"  ⚠️  {result['note']}")
        return

    kv = [
        ("Data range",        result["data_range"]),
        ("Total trades",      result["total_trades"]),
        ("Win rate",          f"{result['win_rate_pct']}%"),
        ("Avg return/trade",  f"{result['avg_pnl_pct']}%"),
        ("Avg holding",       f"{result['avg_holding_days']} days"),
        ("Max single gain",   f"+{result['max_gain_pct']}%"),
        ("Max single loss",   f"{result['max_loss_pct']}%"),
        ("False breakout",    f"{result['false_breakout_pct']}%"),
        ("Cumulative return", f"{result['cum_return_pct']}%"),
        ("Annualized return", f"{result['annual_return_pct']}%"),
        ("Buy&Hold annual",   f"{result['bh_annual_pct']}%"),
        ("Alpha (annual)",    f"{result['outperform_pct']:+.2f}%"),
    ]
    for label, val in kv:
        print(f"  {label:<20} {val}")

    print(f"\n  {'#':<4} {'Entry':>10} {'Exit':>10} {'P&L':>8} {'Peak':>8} {'Days':>5}")
    print(f"  {'-'*4} {'-'*10} {'-'*10} {'-'*8} {'-'*8} {'-'*5}")
    for j, t in enumerate(result["trades"], 1):
        icon = "+" if t["win"] else "-"
        print(f"  {j:<4} {t['entry_date']:>10} {t['exit_date']:>10} "
              f"{t['pnl_pct']:>+7.2f}% {t['max_gain_pct']:>+7.1f}% {t['holding_days']:>4}d")


# ── Main ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = parse_args()

    print("Bollinger Band Breakout Strategy Backtest")
    print(f"Parameters: MA{args.window}, ±{args.std}σ, "
          f"confirm={args.confirm}d, flat_threshold={args.flat_threshold}")
    print(f"Period: {args.start} → {args.end}")

    lg = bs.login()
    if lg.error_code != "0":
        print(f"baostock login failed: {lg.error_msg}", file=sys.stderr)
        sys.exit(1)

    results = []
    for code in args.codes:
        print(f"\nFetching {code}...", end=" ", flush=True)
        try:
            df = fetch_data(code, args.start, args.end)
            print(f"{len(df)} rows")
            name = f"{code}"
            result = backtest(df, name, args.confirm, args.flat_threshold)
            results.append(result)
            print_report(result)
        except Exception as e:
            print(f"FAILED: {e}")
            results.append({"name": code, "error": str(e)})

    bs.logout()

    # Summary table
    valid = [r for r in results if "error" not in r and r.get("total_trades", 0) > 0]
    if len(valid) > 1:
        print(f"\n{'=' * 56}")
        print("  SUMMARY")
        print(f"{'=' * 56}")
        print(f"  {'Code':<16} {'Trades':>6} {'Win%':>6} {'Annual':>8} "
              f"{'B&H':>8} {'Alpha':>8} {'FBO%':>6}")
        print(f"  {'-'*16} {'-'*6} {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*6}")
        for r in valid:
            print(f"  {r['name']:<16} {r['total_trades']:>5}  "
                  f"{r['win_rate_pct']:>5.1f}% {r['annual_return_pct']:>7.2f}% "
                  f"{r['bh_annual_pct']:>7.2f}% {r['outperform_pct']:>+7.2f}% "
                  f"{r['false_breakout_pct']:>5.1f}%")

    # Save JSON
    out = args.output or "backtest_result.json"
    Path(out).write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    print(f"\nResults saved to {out}")
