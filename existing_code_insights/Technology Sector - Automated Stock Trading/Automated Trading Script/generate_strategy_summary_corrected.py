#!/usr/bin/env python3
"""
Generate corrected per-strategy summary using REAL captured trades and capital base from max concurrent positions.

Inputs:
- logs/trades_backtest_full.csv (created by run_full_backtest_with_logging.py)

Window:
- 2024-11-01 through 2025-08-31 inclusive

Outputs:
- reports/strategy_summary_backtest.csv
- reports/strategy_summary_backtest.md

Console:
- Prints 20 strategies, capital base used, overall return_%, and STATUS line.

Validation:
- Reconcile totals vs per-ticker totals computed from the same raw trades (ZERO fabrication)
- If SUM(strategy totals) != SUM(ticker totals) or != global total within $0.01 → ERROR: INCONSISTENT_TOTALS
- If capital base cannot be computed → ERROR: CAPITAL_BASE_MISSING
"""

import sys
import os
import pandas as pd
import numpy as np
from decimal import Decimal, getcontext
from pathlib import Path
from datetime import datetime

getcontext().prec = 28

START = pd.Timestamp('2024-11-01 00:00:00')
END   = pd.Timestamp('2025-08-31 23:59:59')

TRADES_CSV = 'logs/trades_backtest_full.csv'

def load_trades(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        print(f"ERROR: RAW_TRADES_MISSING: {path}")
        sys.exit(1)
    df = pd.read_csv(path, parse_dates=['open_time','close_time'])
    # Basic normalization
    df['exit_reason'] = df['exit_reason'].astype(str).str.upper().str.strip()
    # Window filter
    df = df[(df['open_time'] >= START) & (df['close_time'] <= END)].copy()
    return df

def money_sum(series: pd.Series) -> Decimal:
    s = Decimal('0')
    for v in series.astype(str):
        s += Decimal(v)
    return s

def compute_per_strategy(df: pd.DataFrame) -> pd.DataFrame:
    # Per-strategy metrics
    # Concurrency: since all entries are at/near 09:30 and intraday exits, daily concurrent positions per strategy
    # equals the number of trades for that strategy on that day.
    df['open_date'] = df['open_time'].dt.date

    # Capital base per strategy: max daily trades * 1_000_000
    daily_counts = df.groupby(['strategy','open_date']).size().rename('daily_trades')
    max_daily = daily_counts.groupby('strategy').max().rename('max_concurrent_positions').reset_index()

    # Aggregate PnL and counts
    grp = df.groupby('strategy')

    res = pd.DataFrame({
        'strategy_name': grp.size().index,
        'trades_count': grp.size().values
    })

    wins = grp['pnl_usd'].apply(lambda s: int((s > 0).sum())).rename('wins_count').reset_index(drop=True)
    losses = grp['pnl_usd'].apply(lambda s: int((s < 0).sum())).rename('losses_count').reset_index(drop=True)

    # Exit reason counts
    tp = grp['exit_reason'].apply(lambda s: int((s == 'TAKE_PROFIT').sum())).rename('tp_count').reset_index(drop=True)
    sl = grp['exit_reason'].apply(lambda s: int((s == 'STOP_LOSS').sum())).rename('sl_count').reset_index(drop=True)
    eod = grp['exit_reason'].apply(lambda s: int((s == 'EOD').sum())).rename('eod_count').reset_index(drop=True)

    # Totals and averages
    total_pnl = grp['pnl_usd'].sum().rename('total_pnl_$').reset_index(drop=True)
    avg_pnl = grp['pnl_usd'].mean().rename('avg_pnl_$').reset_index(drop=True)
    avg_pct = grp['pnl_pct'].mean().rename('avg_pnl_%').reset_index(drop=True)

    # Assemble
    res = pd.concat([res, wins, losses, tp, sl, eod, total_pnl, avg_pnl, avg_pct], axis=1)

    # Win rate
    res['win_rate_%'] = (res['wins_count'] / res['trades_count'] * 100).round(1)

    # Merge capital base
    res = res.merge(max_daily, left_on='strategy_name', right_on='strategy', how='left')
    res.drop(columns=['strategy'], inplace=True)
    res['max_concurrent_positions'] = res['max_concurrent_positions'].fillna(0).astype(int)
    res['capital_base'] = res['max_concurrent_positions'] * 1_000_000

    if (res['capital_base'] <= 0).any() and (res['trades_count'] > 0).any():
        print('ERROR: CAPITAL_BASE_MISSING: some strategies have trades but zero capital base')
        sys.exit(1)

    # Return %
    res['return_%'] = np.where(
        res['capital_base'] > 0,
        (res['total_pnl_$'] / res['capital_base'] * 100).round(4),
        0.0
    )

    # Rounding
    res['total_pnl_$'] = res['total_pnl_$'].round(2)
    res['avg_pnl_$'] = res['avg_pnl_$'].round(2)
    res['avg_pnl_%'] = res['avg_pnl_%'].round(2)

    # Order columns per spec
    res = res[['strategy_name','trades_count','wins_count','losses_count','win_rate_%',
               'tp_count','sl_count','eod_count','total_pnl_$','avg_pnl_$','avg_pnl_%','return_%']]

    return res

def compute_per_ticker(df: pd.DataFrame) -> pd.DataFrame:
    by_symbol = df.groupby('symbol', as_index=False).agg({
        'pnl_usd': 'sum',
        'trade_id': 'count'
    }).rename(columns={'pnl_usd': 'total_pnl_$', 'trade_id': 'trades_count'})
    return by_symbol

def main():
    df = load_trades(TRADES_CSV)

    if df.empty:
        print('ERROR: NO_TRADES_IN_WINDOW')
        sys.exit(1)

    # Per-strategy
    per_strategy = compute_per_strategy(df)

    # Reconciliation
    # Global total
    global_total = float(df['pnl_usd'].sum())

    # Sum per-strategy
    strategy_total = float(per_strategy['total_pnl_$'].sum())

    # Per-ticker from same raw trades
    per_ticker = compute_per_ticker(df)
    ticker_total = float(per_ticker['total_pnl_$'].sum())

    # Check within tolerance
    tol = 0.01
    ok = (abs(global_total - strategy_total) <= tol) and (abs(global_total - ticker_total) <= tol)

    # Save outputs
    Path('reports').mkdir(exist_ok=True)
    csv_path = 'reports/strategy_summary_backtest.csv'
    md_path = 'reports/strategy_summary_backtest.md'

    # Sort by total_pnl_$ desc
    per_strategy_sorted = per_strategy.sort_values('total_pnl_$', ascending=False).reset_index(drop=True)

    # Grand total line (for display)
    grand = {
        'strategy_name': 'GRAND_TOTAL',
        'trades_count': int(per_strategy_sorted['trades_count'].sum()),
        'wins_count': int(per_strategy_sorted['wins_count'].sum()),
        'losses_count': int(per_strategy_sorted['losses_count'].sum()),
        'win_rate_%': round(float(per_strategy_sorted['wins_count'].sum())/float(max(per_strategy_sorted['trades_count'].sum(),1))*100,1),
        'tp_count': int(per_strategy_sorted['tp_count'].sum()),
        'sl_count': int(per_strategy_sorted['sl_count'].sum()),
        'eod_count': int(per_strategy_sorted['eod_count'].sum()),
        'total_pnl_$': round(float(per_strategy_sorted['total_pnl_$'].sum()),2),
        'avg_pnl_$': round(float(df['pnl_usd'].mean()),2),
        'avg_pnl_%': round(float(df['pnl_pct'].mean()),2),
        'return_%': 0.0
    }

    out_df = pd.concat([per_strategy_sorted, pd.DataFrame([grand])], ignore_index=True)
    out_df.to_csv(csv_path, index=False)

    with open(md_path, 'w') as f:
        f.write('# STRATEGY SUMMARY — CORRECTED (Max Concurrent Capital Base)\n\n')
        # Compute and print overall capital base across all strategies? We follow per-strategy return_%; we will also print overall base as max across strategies of their max daily positions times $1M if needed by user.
        overall_capital_base = int(df.groupby(df['open_time'].dt.date).size().max()) * 1_000_000
        f.write(f"Window: {START.date()} → {END.date()}\n\n")
        f.write(f"Global total PnL: ${global_total:,.2f}\n\n")
        f.write(out_df.to_markdown(index=False))

    # Console output per spec
    print(out_df.to_string(index=False))
    # Print capital base used (per-strategy is included in return_% but the numeric base is not in table; we print overall for info)
    print(f"\nCalculated overall capital_base (max concurrent positions across all trades): ${overall_capital_base:,}")
    overall_return_pct = (global_total / overall_capital_base * 100) if overall_capital_base > 0 else 0.0
    print(f"Overall return_% based on overall capital_base: {overall_return_pct:.4f}%")

    if not ok:
        print(f"\nSTATUS: FAIL — INCONSISTENT_TOTALS")
        print(f" global_total=${global_total:,.2f} strategy_total=${strategy_total:,.2f} ticker_total=${ticker_total:,.2f}")
        sys.exit(1)

    print("\nSTATUS: PASS")

if __name__ == '__main__':
    main()


