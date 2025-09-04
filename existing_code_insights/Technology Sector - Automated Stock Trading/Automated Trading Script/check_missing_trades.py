#!/usr/bin/env python3

import pandas as pd

# Check the strategy totals
df_strategies = pd.read_excel('extended_strategies_2024-11-10_to_2025-08-20.xlsx', sheet_name='Strategies')
print('STRATEGY TOTALS:')
print(f'Total trades across all strategies: {df_strategies["trades_count"].sum():,}')
print(f'Total P&L across all strategies: ${df_strategies["pnl_usd"].sum():,.2f}')
print()

print('INDIVIDUAL TRADE LOGS FOUND:')
print('433 trades with P&L of -$339,360')
print()

print('MISSING:')
missing_trades = df_strategies['trades_count'].sum() - 433
missing_pnl = df_strategies['pnl_usd'].sum() - (-339360)
print(f'{missing_trades:,} trades are missing from individual logs')
print(f'${missing_pnl:,.2f} P&L is not accounted for in individual logs')
print()

coverage = (433 / df_strategies['trades_count'].sum()) * 100
print(f'COVERAGE: Only {coverage:.1f}% of trades are logged individually')
print()

print('CONCLUSION:')
print('The backtest system runs 13,444 trades but only logs 433 individual trades to Excel files.')
print('This means the vast majority of trades are NOT being saved as individual records.')
print('The system aggregates results at strategy level but does not maintain complete trade logs.')
