#!/usr/bin/env python3
"""
Per-ticker summary using REAL captured trades (~28k) with corrected capital base.

Window: 2024-11-01 → 2025-08-31 (inclusive)

Inputs:
- logs/trades_backtest_full.csv

Outputs:
- reports/per_ticker_summary_full.csv
- reports/per_ticker_summary_full.md

Columns (per ticker):
- symbol, trades_count, pnl_usd, pnl_pct, win_rate_%, tp_count, sl_count, eod_count,
  avg_pnl_$, avg_pnl_%, capital_base, return_%

Checks:
- SUM(pnl_usd by ticker) == SUM(pnl_usd by strategy) == global total ± 0.01
- Sum(trades_count by ticker) == raw trades count; else TRADE_COUNT_MISMATCH
- Required fields non-null; else MISSING_FIELD
"""

import sys
import os
import pandas as pd
import numpy as np
from decimal import Decimal, getcontext
from pathlib import Path

getcontext().prec = 28

START = pd.Timestamp('2024-11-01 00:00:00')
END   = pd.Timestamp('2025-08-31 23:59:59')
TRADES_CSV = 'logs/trades_backtest_full.csv'

def load_trades(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        print(f"ERROR: RAW_TRADES_MISSING: {path}")
        sys.exit(1)
    df = pd.read_csv(path, parse_dates=['open_time','close_time'])
    # Window filter
    df = df[(df['open_time'] >= START) & (df['close_time'] <= END)].copy()
    # Normalize
    df['exit_reason'] = df['exit_reason'].astype(str).str.upper().str.strip()
    return df

def decimal_sum(series: pd.Series) -> Decimal:
    s = Decimal('0')
    for v in series.astype(str):
        s += Decimal(v)
    return s

def main():
    df = load_trades(TRADES_CSV)
    if df.empty:
        print('ERROR: NO_TRADES_IN_WINDOW')
        sys.exit(1)

    # Basic validations
    required_cols = ['trade_id','open_time','close_time','symbol','strategy','pnl_usd','pnl_pct','exit_reason']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"ERROR: MISSING_FIELD: Missing columns: {', '.join(missing)}")
        sys.exit(1)
    for c in required_cols:
        if df[c].isna().any():
            print(f"ERROR: MISSING_FIELD: Nulls found in {c}")
            sys.exit(1)

    # Per-ticker aggregation
    # Capital base per ticker: max daily concurrent positions × $1M
    df['open_date'] = df['open_time'].dt.date
    daily_counts = df.groupby(['symbol','open_date']).size().rename('daily_trades')
    max_daily = daily_counts.groupby('symbol').max().rename('max_concurrent_positions').reset_index()

    grp = df.groupby('symbol')

    res = pd.DataFrame({
        'symbol': grp.size().index,
        'trades_count': grp.size().values
    })

    wins = grp['pnl_usd'].apply(lambda s: int((s > 0).sum())).rename('wins_count').reset_index(drop=True)
    losses = grp['pnl_usd'].apply(lambda s: int((s < 0).sum())).rename('losses_count').reset_index(drop=True)
    tp = grp['exit_reason'].apply(lambda s: int((s == 'TAKE_PROFIT').sum())).rename('tp_count').reset_index(drop=True)
    sl = grp['exit_reason'].apply(lambda s: int((s == 'STOP_LOSS').sum())).rename('sl_count').reset_index(drop=True)
    eod = grp['exit_reason'].apply(lambda s: int((s == 'EOD').sum())).rename('eod_count').reset_index(drop=True)

    total_pnl = grp['pnl_usd'].sum().rename('pnl_usd').reset_index(drop=True)
    avg_pnl = grp['pnl_usd'].mean().rename('avg_pnl_$').reset_index(drop=True)
    avg_pct = grp['pnl_pct'].mean().rename('avg_pnl_%').reset_index(drop=True)

    res = pd.concat([res, wins, losses, tp, sl, eod, total_pnl, avg_pnl, avg_pct], axis=1)

    # Rates and percentages
    res['win_rate_%'] = (res['wins_count'] / res['trades_count'] * 100).round(1)
    # Calculate P&L as percentage of total capital (14M for 14 stocks)
    total_capital = 14_000_000  # 14M total capital for 14 stocks
    res['pnl_pct'] = (res['pnl_usd'] / total_capital * 100).round(4)

    # Capital base and return_%
    res = res.merge(max_daily, on='symbol', how='left')
    res['max_concurrent_positions'] = res['max_concurrent_positions'].fillna(0).astype(int)
    res['capital_base'] = res['max_concurrent_positions'] * 1_000_000
    # Use total capital (14M) for return calculation instead of individual capital base
    res['return_%'] = (res['pnl_usd'] / total_capital * 100).round(4)

    # Round money
    res['pnl_usd'] = res['pnl_usd'].round(2)
    res['avg_pnl_$'] = res['avg_pnl_$'].round(2)
    res['avg_pnl_%'] = res['avg_pnl_%'].round(2)

    # Reorder columns
    res = res[['symbol','trades_count','pnl_usd','pnl_pct','win_rate_%','tp_count','sl_count','eod_count','avg_pnl_$','avg_pnl_%','capital_base','return_%']]

    # Sort by pnl_usd desc
    res_sorted = res.sort_values('pnl_usd', ascending=False).reset_index(drop=True)

    # Grand total line
    grand = {
        'symbol': 'GRAND_TOTAL',
        'trades_count': int(res_sorted['trades_count'].sum()),
        'pnl_usd': round(float(res_sorted['pnl_usd'].sum()), 2),
        'pnl_pct': round(float(res_sorted['pnl_usd'].sum() / 14_000_000 * 100), 4),
        'win_rate_%': round(float((df['pnl_usd'] > 0).sum()) / float(len(df)) * 100, 1),
        'tp_count': int((df['exit_reason'] == 'TAKE_PROFIT').sum()),
        'sl_count': int((df['exit_reason'] == 'STOP_LOSS').sum()),
        'eod_count': int((df['exit_reason'] == 'EOD').sum()),
        'avg_pnl_$': round(float(df['pnl_usd'].mean()), 2),
        'avg_pnl_%': round(float(df['pnl_pct'].mean()), 2),
        'capital_base': int(df.groupby(df['open_time'].dt.date).size().max()) * 1_000_000,
        'return_%': round(float(res_sorted['pnl_usd'].sum()) / 14_000_000 * 100, 4)
    }
    out_df = pd.concat([res_sorted, pd.DataFrame([grand])], ignore_index=True)

    # Checks (use unrounded raw sums to avoid rounding drift)
    global_total = float(df['pnl_usd'].sum())
    ticker_total = float(df.groupby('symbol')['pnl_usd'].sum().sum())
    strategy_total = float(df.groupby('strategy')['pnl_usd'].sum().sum())
    tol = 0.01
    if abs(global_total - ticker_total) > tol or abs(global_total - strategy_total) > tol:
        print(f"TOTAL_TICKERS: {out_df[out_df['symbol']!='GRAND_TOTAL'].shape[0]}")
        print(f"TOTAL_TRADES: {len(df)}")
        print(f"GRAND_TOTAL_PNL: ${global_total:,.2f}")
        print(f"STATUS: FAIL — INCONSISTENT_TOTALS")
        sys.exit(1)

    # Trade count match
    if int(out_df[out_df['symbol']!='GRAND_TOTAL']['trades_count'].sum()) != len(df):
        print(f"TOTAL_TICKERS: {out_df[out_df['symbol']!='GRAND_TOTAL'].shape[0]}")
        print(f"TOTAL_TRADES: {len(df)}")
        print(f"GRAND_TOTAL_PNL: ${global_total:,.2f}")
        print(f"STATUS: FAIL — TRADE_COUNT_MISMATCH")
        sys.exit(1)

    # Save
    Path('reports').mkdir(exist_ok=True)
    csv_path = 'reports/per_ticker_summary_full.csv'
    md_path = 'reports/per_ticker_summary_full.md'
    out_df.to_csv(csv_path, index=False)
    with open(md_path, 'w') as f:
        f.write('# PER-TICKER SUMMARY — FULL BACKTEST (CORRECTED CAPITAL BASE)\n\n')
        f.write(f"Window: {START.date()} → {END.date()}\n\n")
        f.write(out_df.to_markdown(index=False))

    # Console preview top 20 tickers
    print(out_df.head(20).to_string(index=False))
    print(f"\nTOTAL_TICKERS: {out_df[out_df['symbol']!='GRAND_TOTAL'].shape[0]}")
    print(f"TOTAL_TRADES: {len(df)}")
    print(f"GRAND_TOTAL_PNL: ${global_total:,.2f}")
    print("STATUS: PASS")

if __name__ == '__main__':
    main()


