#!/usr/bin/env python3
"""
UNIFORMITY DIAGNOSTIC REPORT
============================
Analyzes batch runner results for uniform patterns and identifies root causes
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pandas_market_calendars as mcal
from pathlib import Path
import os

def analyze_uniformity(results_file: str):
    """Analyze uniformity patterns in batch results"""
    
    print("🔍 UNIFORMITY DIAGNOSTIC REPORT")
    print("=" * 60)
    
    # Load results
    try:
        df = pd.read_excel(results_file)
        print(f"📊 Loaded {len(df)} strategies from {results_file}")
    except Exception as e:
        print(f"❌ Error loading {results_file}: {e}")
        return
    
    print()
    
    # 1. Basic uniformity analysis
    print("1️⃣ UNIFORMITY PATTERNS:")
    print("-" * 30)
    
    trades_unique = df['trades_count'].nunique()
    winrate_unique = df['win_rate_pct'].nunique()
    
    print(f"trades_count unique values: {trades_unique}")
    print(f"win_rate_pct unique values: {winrate_unique}")
    
    if trades_unique <= 3:
        print("🚨 HIGHLY UNIFORM trades_count detected!")
        trades_dist = df['trades_count'].value_counts().sort_index()
        for count, freq in trades_dist.items():
            print(f"  {count} trades: {freq} strategies")
    
    if winrate_unique <= 3:
        print("🚨 HIGHLY UNIFORM win_rate_pct detected!")
        winrate_dist = df['win_rate_pct'].round(1).value_counts().sort_index()
        for rate, freq in winrate_dist.items():
            print(f"  {rate}%: {freq} strategies")
    
    print()
    
    # 2. Trading days analysis
    print("2️⃣ TRADING DAYS ANALYSIS:")
    print("-" * 30)
    
    # Extract date range from results
    start_date_str = df['start_date'].iloc[0]
    end_date_str = df['end_date'].iloc[0]
    
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    
    # Get expected trading days
    nyse = mcal.get_calendar('NYSE')
    trading_days = nyse.schedule(start_date=start_date, end_date=end_date)
    expected_days = len(trading_days)
    
    print(f"Expected trading days ({start_date_str} to {end_date_str}): {expected_days}")
    print(f"Trading days list:")
    for i, day in enumerate(trading_days.index[:5], 1):
        print(f"  {i:2d}. {day.strftime('%Y-%m-%d (%A)')}")
    if len(trading_days) > 5:
        print(f"  ... ({len(trading_days) - 5} more)")
    
    print()
    
    # 3. Formula verification
    print("3️⃣ TRADES FORMULA VERIFICATION:")
    print("-" * 30)
    
    print("Expected: trades_count = trading_days × effective_top_k")
    print()
    
    for _, row in df.iterrows():
        strategy_id = row['strategy_id']
        top_k = int(row['top_k'])
        trades_count = int(row['trades_count'])
        
        expected_trades = expected_days * top_k
        formula_match = trades_count == expected_trades
        
        status = "✅ MATCHES" if formula_match else "❌ MISMATCH"
        
        print(f"S{strategy_id:2}: {expected_days} days × {top_k} top_k = {expected_trades} expected, {trades_count} actual {status}")
        
        if not formula_match:
            actual_days = trades_count / top_k if top_k > 0 else 0
            print(f"      → Implies {actual_days:.1f} effective trading days")
    
    print()
    
    # 4. Win rate analysis
    print("4️⃣ WIN RATE DISCRETENESS:")
    print("-" * 30)
    
    for _, row in df.iterrows():
        strategy_id = row['strategy_id']
        trades_count = int(row['trades_count'])
        win_rate = row['win_rate_pct']
        
        # Calculate wins/losses
        wins = round(trades_count * win_rate / 100)
        losses = trades_count - wins
        actual_win_rate = wins / trades_count * 100 if trades_count > 0 else 0
        
        discreteness_note = ""
        if abs(win_rate - 30.0) < 0.1:
            discreteness_note = " (3/10 pattern)"
        elif abs(win_rate - 33.333) < 0.1:
            discreteness_note = " (10/30 or 1/3 pattern)"
        
        print(f"S{strategy_id:2}: {wins}W/{losses}L = {actual_win_rate:.1f}%{discreteness_note}")
    
    print()
    
    # 5. Root cause analysis
    print("5️⃣ ROOT CAUSE ANALYSIS:")
    print("-" * 30)
    
    # Check for perfect formula matches
    perfect_matches = 0
    for _, row in df.iterrows():
        top_k = int(row['top_k'])
        trades_count = int(row['trades_count'])
        expected_trades = expected_days * top_k
        if trades_count == expected_trades:
            perfect_matches += 1
    
    if perfect_matches == len(df):
        print("🚨 ALL STRATEGIES show perfect days×top_k formula!")
        print("   This indicates the system ALWAYS selects exactly top_k stocks per day")
        print("   Likely cause: sentiment analyzer returns exactly top_k stocks regardless of qualification")
        print()
        print("   Expected behavior: Return ≤ top_k stocks (only those that qualify)")
        print("   Actual behavior: Return exactly top_k stocks (forced selection)")
    
    # Check win rate patterns
    win_rates = df['win_rate_pct'].round(1).unique()
    if len(win_rates) <= 2 and all(rate in [30.0, 33.3] for rate in win_rates):
        print("🚨 WIN RATES show extreme discreteness!")
        print("   30.0% = 3 wins out of 10 trades")
        print("   33.3% = 10 wins out of 30 trades") 
        print("   This suggests deterministic win/loss patterns")
    
    print()
    
    # 6. Recommendations
    print("6️⃣ RECOMMENDATIONS:")
    print("-" * 30)
    
    if perfect_matches == len(df):
        print("🔧 FIX REQUIRED in real_sentiment_analyzer.py:")
        print("   Line ~297: qualified_stocks = stock_sentiments[:top_k]")
        print("   Should be: qualified_stocks = [s for s in stock_sentiments if s['qualifies']][:top_k]")
        print()
    
    print("🔍 FURTHER INVESTIGATION:")
    print("   1. Check audit logs for actual qualification counts per day")
    print("   2. Verify sentiment/trend filters are working correctly")
    print("   3. Examine why win/loss patterns are so deterministic")
    
    return df

def create_per_day_breakdown(results_file: str, audit_dir: str = "audit_logs"):
    """Create per-day breakdown from audit logs"""
    
    print("\n📋 PER-DAY BREAKDOWN ANALYSIS:")
    print("-" * 40)
    
    audit_path = Path(audit_dir)
    if not audit_path.exists():
        print(f"❌ Audit directory {audit_dir} not found")
        return
    
    # Get audit files
    audit_files = list(audit_path.glob("sentiment_audit_*.csv"))
    if not audit_files:
        print(f"❌ No audit files found in {audit_dir}")
        return
    
    print(f"📁 Found {len(audit_files)} audit files")
    
    # Analyze first few days
    for audit_file in sorted(audit_files)[:3]:
        date = audit_file.stem.replace("sentiment_audit_", "")
        print(f"\n📅 {date}:")
        
        try:
            audit_df = pd.read_csv(audit_file)
            total_analyzed = len(audit_df)
            qualified = len(audit_df[audit_df['qualifies'] == True])
            with_news = len(audit_df[audit_df['meets_min_news'] == True])
            
            print(f"   Total analyzed: {total_analyzed}")
            print(f"   With ≥2 news: {with_news}")
            print(f"   Qualified: {qualified}")
            
            if qualified > 0:
                top_qualified = audit_df[audit_df['qualifies'] == True].nlargest(5, 'weighted_sentiment')
                print("   Top qualified:")
                for _, row in top_qualified.iterrows():
                    print(f"     {row['ticker']}: {row['weighted_sentiment']:.3f} ({row['articles_count']} articles)")
        
        except Exception as e:
            print(f"   ❌ Error reading {audit_file}: {e}")

def main():
    """Main diagnostic function"""
    
    # Find the most recent results file
    results_files = [
        "results_REAL_FULL_test_dec09-20.xlsx",
        "results_REAL_test_dec16-17.xlsx", 
        "results_strategies_march_2025.xlsx"
    ]
    
    results_file = None
    for file in results_files:
        if os.path.exists(file):
            results_file = file
            break
    
    if not results_file:
        print("❌ No results file found")
        return
    
    # Run analysis
    df = analyze_uniformity(results_file)
    
    # Create per-day breakdown
    create_per_day_breakdown(results_file)
    
    print("\n" + "=" * 60)
    print("📋 DIAGNOSTIC COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
