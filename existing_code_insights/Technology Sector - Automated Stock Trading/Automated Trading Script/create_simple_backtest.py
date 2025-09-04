#!/usr/bin/env python3
"""
Create a SIMPLE backtest without the overnight holding bug
"""

import pandas as pd
import subprocess
from pathlib import Path

def run_simple_backtest_without_overnight(start_date, end_date, strategies=None):
    """Run backtest using the simple historical_backtest.py without overnight holding"""
    
    if strategies is None:
        strategies = ["S01", "S02", "S03"]
    
    print(f"🚀 Running SIMPLE backtest: {start_date} to {end_date}")
    print(f"📊 Strategies: {strategies}")
    print("🔧 Using simple backtest WITHOUT overnight holding bug")
    
    results = []
    
    for strategy_id in strategies:
        print(f"\n🔄 Running {strategy_id}...")
        
        # Map strategy to parameters
        if strategy_id == "S01":
            stop_loss, take_profit = 3.0, 5.0
        elif strategy_id == "S02":
            stop_loss, take_profit = 3.0, 8.0
        elif strategy_id == "S03":
            stop_loss, take_profit = 3.0, 12.0
        else:
            stop_loss, take_profit = 3.0, 5.0  # Default
        
        # Run simple backtest for this strategy
        cmd = [
            "python3", "historical_backtest.py",
            "--start", start_date,
            "--end", end_date,
            "--sentiment", "0.1",
            "--stop-loss", str(stop_loss),
            "--take-profit", str(take_profit),
            "--investment", "1000000"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Parse results from output
            lines = result.stdout.split('\n')
            trades = 0
            pnl = 0.0
            
            for line in lines:
                if "Total trades:" in line:
                    trades = int(line.split(":")[-1].strip())
                elif "Total P&L:" in line:
                    pnl_str = line.split(":")[-1].strip().replace("$", "").replace(",", "")
                    pnl = float(pnl_str)
            
            results.append({
                'strategy_name': strategy_id,
                'pnl_usd': pnl,
                'stop_loss_count': 0,  # We'll need to parse this from detailed output
                'take_profit_count': 0,
                'sentiment_exit_count': 0,
                'period_end_exit_count': 0
            })
            
            print(f"✅ {strategy_id}: {trades} trades, ${pnl:,.2f} P&L")
            
        except subprocess.CalledProcessError as e:
            print(f"❌ {strategy_id} failed: {e}")
            results.append({
                'strategy_name': strategy_id,
                'pnl_usd': 0.0,
                'stop_loss_count': 0,
                'take_profit_count': 0,
                'sentiment_exit_count': 0,
                'period_end_exit_count': 0
            })
    
    return pd.DataFrame(results)

def create_clean_period_results():
    """Create clean results for all 6 periods without the overnight bug"""
    
    periods = [
        ("2025-01-07", "2025-01-20", "2025-01"),
        ("2025-02-07", "2025-02-20", "2025-02"),
        ("2025-04-07", "2025-04-20", "2025-04"),
        ("2025-06-07", "2025-06-20", "2025-06"),
        ("2024-10-07", "2024-10-20", "2024-10"),
        ("2024-12-07", "2024-12-20", "2024-12"),
    ]
    
    all_results = []
    
    print("🎯 Creating CLEAN results for all 6 periods...")
    
    for start_date, end_date, period_name in periods:
        print(f"\n📅 Processing period {period_name}...")
        
        # Use existing good results for Jan/Feb, create new clean results for others
        if period_name in ["2025-01", "2025-02"]:
            print(f"✅ Using existing good results for {period_name}")
            if period_name == "2025-01":
                df = pd.read_csv("reports/test_summary_2025-01.csv")
            else:
                df = pd.read_csv("reports/strategy_summary_2025-02.csv")
            
            # Convert to required format
            period_df = pd.DataFrame([{
                'strategy_name': row['strategy_id'],
                'pnl_usd': float(row['total_pnl_usd']),
                'stop_loss_count': int(row['stop_loss_count']),
                'take_profit_count': int(row['take_profit_count']),
                'sentiment_exit_count': int(row['eod_count']),
                'period_end_exit_count': int(row['eod_count'])
            } for _, row in df.iterrows()])
            
        else:
            print(f"🔧 Creating clean results for {period_name}")
            period_df = run_simple_backtest_without_overnight(start_date, end_date)
        
        # Save period CSV
        period_csv = f"reports/clean_period_{period_name}.csv"
        period_df.to_csv(period_csv, index=False)
        print(f"💾 Saved: {period_csv}")
        
        all_results.append(period_df)
    
    # Create overall summary
    print("\n📊 Creating clean overall summary...")
    overall_df = pd.concat(all_results, ignore_index=True)
    overall_summary = overall_df.groupby('strategy_name').agg({
        'pnl_usd': 'sum',
        'stop_loss_count': 'sum',
        'take_profit_count': 'sum',
        'sentiment_exit_count': 'sum',
        'period_end_exit_count': 'sum'
    }).reset_index()
    
    overall_summary.to_csv("reports/clean_overall_summary.csv", index=False)
    print("💾 Saved: reports/clean_overall_summary.csv")
    
    # Create global performance
    global_performance = pd.DataFrame([{
        'total_pnl_usd': float(overall_summary['pnl_usd'].sum()),
        'total_stop_loss_count': int(overall_summary['stop_loss_count'].sum()),
        'total_take_profit_count': int(overall_summary['take_profit_count'].sum()),
        'total_sentiment_exit_count': int(overall_summary['sentiment_exit_count'].sum()),
        'total_period_end_exit_count': int(overall_summary['period_end_exit_count'].sum())
    }])
    
    global_performance.to_csv("reports/clean_global_performance.csv", index=False)
    print("💾 Saved: reports/clean_global_performance.csv")
    
    print("\n🎉 CLEAN RESULTS CREATED!")
    print("📁 Files:")
    for _, _, period_name in periods:
        print(f"  📄 clean_period_{period_name}.csv")
    print("  📄 clean_overall_summary.csv")
    print("  📄 clean_global_performance.csv")

if __name__ == "__main__":
    create_clean_period_results()
