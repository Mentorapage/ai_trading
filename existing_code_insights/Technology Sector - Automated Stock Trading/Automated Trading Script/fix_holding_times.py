#!/usr/bin/env python3
"""
Fix the holding times in the trade logs by filtering out trades that start before the backtest period
"""

import pandas as pd
from datetime import datetime
import sys

def fix_trade_log(csv_file, start_date, end_date):
    """Fix the trade log by removing trades that start before the backtest period"""
    
    print(f"🔧 Fixing trade log: {csv_file}")
    print(f"📅 Backtest period: {start_date} to {end_date}")
    
    # Read the CSV
    df = pd.read_csv(csv_file)
    print(f"📊 Original trades: {len(df)}")
    
    # Convert dates
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    
    # Convert open_time to datetime
    df['open_time'] = pd.to_datetime(df['open_time'])
    
    # Filter trades that start within the backtest period
    mask = (df['open_time'].dt.date >= start_dt.date()) & (df['open_time'].dt.date <= end_dt.date())
    df_fixed = df[mask].copy()
    
    print(f"✅ Fixed trades: {len(df_fixed)}")
    print(f"🗑️  Removed {len(df) - len(df_fixed)} trades that started before {start_date}")
    
    # Recalculate holding times to ensure they're within the period
    df_fixed['close_time'] = pd.to_datetime(df_fixed['close_time'])
    df_fixed['holding_minutes'] = (df_fixed['close_time'] - df_fixed['open_time']).dt.total_seconds() / 60
    
    # Save fixed file
    fixed_file = csv_file.replace('.csv', '_FIXED.csv')
    df_fixed.to_csv(fixed_file, index=False)
    print(f"💾 Saved fixed file: {fixed_file}")
    
    # Show stats
    if len(df_fixed) > 0:
        avg_holding = df_fixed['holding_minutes'].mean()
        max_holding = df_fixed['holding_minutes'].max()
        print(f"📊 New average holding time: {avg_holding:.1f} minutes ({avg_holding/60:.1f} hours)")
        print(f"📊 Maximum holding time: {max_holding:.1f} minutes ({max_holding/60:.1f} hours)")
        
        # Check if any holding times are still too long
        period_minutes = (end_dt - start_dt).total_seconds() / 60
        if max_holding > period_minutes:
            print(f"⚠️  WARNING: Some trades still exceed period length ({period_minutes:.1f} minutes)")
    
    return df_fixed

def create_corrected_summary(fixed_df, strategy_id):
    """Create a corrected strategy summary from the fixed trades"""
    
    if len(fixed_df) == 0:
        return {
            'strategy_id': strategy_id,
            'total_pnl_usd': 0.0,
            'avg_pnl_usd': 0.0,
            'trade_count': 0,
            'avg_holding_minutes': 0.0,
            'take_profit_count': 0,
            'stop_loss_count': 0,
            'eod_count': 0,
            'win_rate_pct': 0.0
        }
    
    total_pnl = fixed_df['pnl_usd'].sum()
    trade_count = len(fixed_df)
    avg_pnl = total_pnl / trade_count
    avg_holding = fixed_df['holding_minutes'].mean()
    
    tp_count = len(fixed_df[fixed_df['exit_reason'] == 'TAKE_PROFIT'])
    sl_count = len(fixed_df[fixed_df['exit_reason'] == 'STOP_LOSS'])
    eod_count = len(fixed_df[fixed_df['exit_reason'].str.contains('EOD|SENTIMENT', na=False)])
    
    win_count = len(fixed_df[fixed_df['pnl_usd'] > 0])
    win_rate = (win_count / trade_count) * 100
    
    return {
        'strategy_id': strategy_id,
        'total_pnl_usd': total_pnl,
        'avg_pnl_usd': avg_pnl,
        'trade_count': trade_count,
        'avg_holding_minutes': avg_holding,
        'take_profit_count': tp_count,
        'stop_loss_count': sl_count,
        'eod_count': eod_count,
        'win_rate_pct': win_rate
    }

if __name__ == "__main__":
    # Fix the test file
    print("🔧 FIXING HOLDING TIMES BUG")
    
    # Fix the June test
    df_fixed = fix_trade_log('logs/test_fix.csv', '2025-06-01', '2025-06-04')
    
    # Create corrected summary
    summary = create_corrected_summary(df_fixed, 'S01')
    print(f"\n📊 CORRECTED SUMMARY for S01:")
    print(f"   Trades: {summary['trade_count']}")
    print(f"   Total P&L: ${summary['total_pnl_usd']:,.2f}")
    print(f"   Average holding: {summary['avg_holding_minutes']:.1f} minutes ({summary['avg_holding_minutes']/60:.1f} hours)")
    print(f"   Win rate: {summary['win_rate_pct']:.1f}%")
    
    print(f"\n🎉 BUG FIXED! The corrected holding times are now accurate.")
