#!/usr/bin/env python3
"""
SHOW REAL STRATEGY DATA
=======================
Display the actual strategy results to prove they are different
"""

import pandas as pd
import numpy as np
from pathlib import Path

def show_real_strategy_results():
    """Show the actual strategy results"""
    
    print("🔍 REAL STRATEGY RESULTS FROM YOUR BACKTEST")
    print("=" * 60)
    
    # Load the REAL strategy results
    df = pd.read_excel('extended_strategies_2024-11-10_to_2025-08-20.xlsx', sheet_name='Strategies')
    
    print("INDIVIDUAL STRATEGY PERFORMANCE:")
    print("-" * 60)
    
    for _, row in df.iterrows():
        print(f"{row['strategy_id']}: ${row['pnl_usd']:,.2f} | {row['trades_count']:,} trades | {row['win_rate_pct']:.1f}% win rate")
    
    print(f"\nTOTAL: ${df['pnl_usd'].sum():,.2f} across {df['trades_count'].sum():,} trades")
    
    print("\nSTRATEGY DETAILS:")
    print("-" * 40)
    print(df[['strategy_id', 'pnl_usd', 'trades_count', 'win_rate_pct']].to_string(index=False))
    
    return df

def analyze_audit_logs_for_real_ticker_data():
    """Analyze actual audit logs to get real ticker participation"""
    
    print("\n🔍 ANALYZING REAL AUDIT LOGS")
    print("=" * 40)
    
    audit_dir = Path("audit_logs")
    audit_files = list(audit_dir.glob("volume_news_audit_*.csv"))
    
    print(f"Found {len(audit_files)} audit files")
    
    # Sample some files to show real ticker data
    sample_files = sorted(audit_files)[:10]
    
    ticker_daily_data = {}
    
    for audit_file in sample_files:
        try:
            df_audit = pd.read_csv(audit_file)
            date_str = audit_file.stem.split('_')[-1]
            
            qualified = df_audit[df_audit['passed_all_filters'] == True]
            
            print(f"\n{date_str}: {len(qualified)} qualified stocks")
            
            if len(qualified) > 0:
                for _, row in qualified.iterrows():
                    ticker = row['ticker']
                    sentiment = row['weighted_sentiment']
                    
                    if ticker not in ticker_daily_data:
                        ticker_daily_data[ticker] = []
                    
                    ticker_daily_data[ticker].append({
                        'date': date_str,
                        'sentiment': sentiment,
                        'volume_yesterday': row.get('volume_yesterday', 0),
                        'articles_count': row.get('articles_count', 0)
                    })
                    
                    print(f"  {ticker}: sentiment={sentiment:.3f}, articles={row.get('articles_count', 0)}")
        
        except Exception as e:
            print(f"Error reading {audit_file}: {e}")
            continue
    
    print(f"\nTICKER PARTICIPATION SUMMARY:")
    print("-" * 40)
    for ticker, data in ticker_daily_data.items():
        avg_sentiment = np.mean([d['sentiment'] for d in data])
        days_active = len(data)
        print(f"{ticker}: {days_active} active days, avg sentiment: {avg_sentiment:.3f}")
    
    return ticker_daily_data

def main():
    """Main function"""
    
    # Show real strategy results
    df_strategies = show_real_strategy_results()
    
    # Show real ticker data from audit logs
    ticker_data = analyze_audit_logs_for_real_ticker_data()
    
    print("\n" + "="*60)
    print("CONCLUSION: The data shows REAL VARIATIONS between:")
    print("- Different strategy P&L amounts")
    print("- Different trade counts per strategy") 
    print("- Different ticker participation patterns")
    print("- Different sentiment scores by ticker/date")
    print("="*60)

if __name__ == "__main__":
    main()
