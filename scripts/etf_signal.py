#!/usr/bin/env python3
"""
ETF Technical Signal Generator
================================
Calculates Bollinger Bands, MACD, RSI, MA system, and generates composite signals.

Usage:
    python etf_signal.py --code 510300
    python etf_signal.py --codes 510300 159570 512480
    python etf_signal.py --code 000300 --window 20 --output signals.json
"""

import argparse
import json
import sys
from datetime import datetime, timedelta

import baostock as bs
import numpy as np
import pandas as pd


def parse_args():
    p = argparse.ArgumentParser(description="ETF technical signal generator")
    p.add_argument("--codes", nargs="+", default=["sh.000300"],
                   help="baostock codes (default: sh.000300)")
    p.add_argument("--days", type=int, default=120,
                   help="lookback days for data (default: 120)")
    p.add_argument("--window", type=int, default=20,
                   help="Bollinger MA window (default: 20)")
    p.add_argument("--std", type=float, default=2.0,
                   help="Bollinger std multiplier (default: 2.0)")
    p.add_argument("--output", "-o", help="save to JSON file")
    return p.parse_args()


def fetch_recent(code: str, days: int) -> pd.DataFrame:
    """Fetch recent N days of daily data from baostock."""
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=days * 2)).strftime("%Y-%m-%d")
    rs = bs.query_history_k_data_plus(
        code, "date,open,high,low,close,volume",
        start_date=start, end_date=end,
        frequency="d", adjustflag="2",
    )
    rows = []
    while rs.error_code == "0" and rs.next():
        rows.append(rs.get_row_data())
    if not rows:
        raise ValueError(f"No data for {code}")
    df = pd.DataFrame(rows, columns=rs.fields)
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])
    df = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
    return df.tail(days).reset_index(drop=True)


def calc_indicators(df: pd.DataFrame, window: int, num_std: float) -> pd.DataFrame:
    """Calculate Bollinger Bands, MACD, RSI, MA system."""
    df = df.copy()
    close = df["close"]

    # --- Bollinger Bands ---
    df["bb_ma"] = close.rolling(window).mean()
    df["bb_std"] = close.rolling(window).std()
    df["bb_upper"] = df["bb_ma"] + num_std * df["bb_std"]
    df["bb_lower"] = df["bb_ma"] - num_std * df["bb_std"]
    df["bb_pct"] = (close - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])

    # --- Moving Averages ---
    for p in [5, 10, 20, 60]:
        df[f"ma{p}"] = close.rolling(p).mean()

    # --- MACD (12, 26, 9) ---
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    df["macd_dif"] = ema12 - ema26
    df["macd_dea"] = df["macd_dif"].ewm(span=9).mean()
    df["macd_hist"] = 2 * (df["macd_dif"] - df["macd_dea"])

    # --- RSI (14) ---
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi14"] = 100 - (100 / (1 + rs))

    # --- Volume ratio ---
    df["vol_ma20"] = df["volume"].rolling(20).mean()
    df["vol_ratio"] = df["volume"] / df["vol_ma20"]

    return df


def generate_signal(df: pd.DataFrame, window: int) -> dict:
    """Generate composite trading signal from latest data."""
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest

    signals = {}
    score = 50  # neutral baseline

    # --- Bollinger signal ---
    bb_pct = latest.get("bb_pct", 0.5)
    if bb_pct > 1.0:
        signals["bollinger"] = "ABOVE_UPPER"
        score += 15
    elif bb_pct > 0.8:
        signals["bollinger"] = "NEAR_UPPER"
        score += 8
    elif bb_pct < 0.0:
        signals["bollinger"] = "BELOW_LOWER"
        score -= 15
    elif bb_pct < 0.2:
        signals["bollinger"] = "NEAR_LOWER"
        score -= 8
    else:
        signals["bollinger"] = "MID_RANGE"

    # --- MA alignment ---
    ma5, ma10, ma20 = latest.get("ma5"), latest.get("ma10"), latest.get("ma20")
    if pd.notna(ma5) and pd.notna(ma10) and pd.notna(ma20):
        if ma5 > ma10 > ma20:
            signals["ma_system"] = "BULLISH_ALIGN"
            score += 10
        elif ma5 < ma10 < ma20:
            signals["ma_system"] = "BEARISH_ALIGN"
            score -= 10
        else:
            signals["ma_system"] = "MIXED"

    # --- MACD ---
    if pd.notna(latest.get("macd_hist")):
        if latest["macd_hist"] > 0 and prev.get("macd_hist", 0) <= 0:
            signals["macd"] = "GOLDEN_CROSS"
            score += 10
        elif latest["macd_hist"] < 0 and prev.get("macd_hist", 0) >= 0:
            signals["macd"] = "DEATH_CROSS"
            score -= 10
        elif latest["macd_hist"] > 0:
            signals["macd"] = "POSITIVE"
            score += 3
        else:
            signals["macd"] = "NEGATIVE"
            score -= 3

    # --- RSI ---
    rsi = latest.get("rsi14")
    if pd.notna(rsi):
        if rsi > 70:
            signals["rsi"] = "OVERBOUGHT"
            score -= 5
        elif rsi < 30:
            signals["rsi"] = "OVERSOLD"
            score += 5
        else:
            signals["rsi"] = "NEUTRAL"

    # --- Volume ---
    vr = latest.get("vol_ratio")
    if pd.notna(vr):
        if vr > 2.0:
            signals["volume"] = "HEAVY"
        elif vr > 1.5:
            signals["volume"] = "ABOVE_AVG"
        elif vr < 0.5:
            signals["volume"] = "LIGHT"
        else:
            signals["volume"] = "NORMAL"

    # --- Composite ---
    score = max(0, min(100, score))
    if score >= 70:
        verdict = "BULLISH"
    elif score >= 55:
        verdict = "LEAN_BULLISH"
    elif score <= 30:
        verdict = "BEARISH"
    elif score <= 45:
        verdict = "LEAN_BEARISH"
    else:
        verdict = "NEUTRAL"

    return {
        "date": latest["date"].strftime("%Y-%m-%d"),
        "close": round(float(latest["close"]), 4),
        "score": score,
        "verdict": verdict,
        "signals": signals,
        "details": {
            "bb_ma": round(float(latest.get("bb_ma", 0)), 4) if pd.notna(latest.get("bb_ma")) else None,
            "bb_upper": round(float(latest.get("bb_upper", 0)), 4) if pd.notna(latest.get("bb_upper")) else None,
            "bb_lower": round(float(latest.get("bb_lower", 0)), 4) if pd.notna(latest.get("bb_lower")) else None,
            "rsi14": round(float(rsi), 1) if pd.notna(rsi) else None,
            "macd_hist": round(float(latest.get("macd_hist", 0)), 4) if pd.notna(latest.get("macd_hist")) else None,
            "vol_ratio": round(float(vr), 2) if pd.notna(vr) else None,
        },
    }


def print_signal(code: str, sig: dict):
    """Pretty-print a signal."""
    verdict_icon = {
        "BULLISH": "🟢", "LEAN_BULLISH": "🟡",
        "BEARISH": "🔴", "LEAN_BEARISH": "🟠",
        "NEUTRAL": "⚪",
    }
    print(f"\n{'─' * 48}")
    print(f"  {code}  |  {sig['date']}  |  Close: {sig['close']}")
    print(f"{'─' * 48}")
    print(f"  Score: {sig['score']}/100  "
          f"{verdict_icon.get(sig['verdict'], '?')} {sig['verdict']}")
    print()
    for k, v in sig["signals"].items():
        print(f"  {k:<12} {v}")
    print()
    d = sig["details"]
    parts = []
    if d["bb_upper"]:
        parts.append(f"BB[{d['bb_lower']:.2f} | {d['bb_ma']:.2f} | {d['bb_upper']:.2f}]")
    if d["rsi14"]:
        parts.append(f"RSI={d['rsi14']:.1f}")
    if d["vol_ratio"]:
        parts.append(f"Vol={d['vol_ratio']:.2f}x")
    if parts:
        print(f"  {'  '.join(parts)}")


# ── Main ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = parse_args()

    lg = bs.login()
    if lg.error_code != "0":
        print(f"baostock login failed: {lg.error_msg}", file=sys.stderr)
        sys.exit(1)

    all_signals = {}
    for code in args.codes:
        try:
            df = fetch_recent(code, args.days)
            df = calc_indicators(df, args.window, args.std)
            sig = generate_signal(df, args.window)
            all_signals[code] = sig
            print_signal(code, sig)
        except Exception as e:
            print(f"  {code}: FAILED - {e}")
            all_signals[code] = {"error": str(e)}

    bs.logout()

    if args.output:
        Path(args.output).write_text(
            json.dumps(all_signals, ensure_ascii=False, indent=2, default=str)
        )
        print(f"\nSaved to {args.output}")
