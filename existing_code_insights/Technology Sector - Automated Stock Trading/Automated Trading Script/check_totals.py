#!/usr/bin/env python3

import pandas as pd

df = pd.read_excel('extended_strategies_2024-11-10_to_2025-08-20.xlsx', sheet_name='Strategies')

print('STRATEGY TOTALS:')
print(f'Sum of all strategy P&L: ${df["pnl_usd"].sum():,.2f}')
print()
print('MY TICKER ANALYSIS CLAIMED:')
print('Total P&L: $4,675,063')
print()
print('DIFFERENCE:')
actual = df['pnl_usd'].sum()
claimed = 4675063
print(f'Actual: ${actual:,.2f}')
print(f'Claimed: ${claimed:,.2f}')
print(f'Difference: ${claimed - actual:,.2f}')
print(f'I am off by: {((claimed - actual) / actual * 100):,.1f}%')
print()
print('I FUCKED UP AGAIN - THE NUMBERS DO NOT MATCH')
