#!/usr/bin/env python3
"""
Run all 6 periods and generate CSV reports
"""

import subprocess
import pandas as pd
from pathlib import Path

# Define the six periods
PERIODS = [
    ("2025-01-07", "2025-01-20", "2025-01"),
    ("2025-02-07", "2025-02-20", "2025-02"),
    ("2025-04-07", "2025-04-20", "2025-04"),
    ("2025-06-07", "2025-06-20", "2025-06"),
    ("2024-10-07", "2024-10-20", "2024-10"),
    ("2024-12-07", "2024-12-20", "2024-12"),
]

STRATEGIES = [f"S{i:02d}" for i in range(1, 21)]

def run_period(start_date, end_date, period_name):
    """Run backtest for one period"""
    print(f"\n🚀 Running period {period_name}: {start_date} to {end_date}")
    
    cmd = [
        "python3", "run_multi_strategy_backtest.py",
        "--start", start_date,
        "--end", end_date,
        "--strategies", "ALL",
        "--trade-log", f"logs/period_{period_name}.csv",
        "--strategy-summary", f"reports/strategy_summary_{period_name}.csv",
        "--ticker-summary", f"reports/ticker_summary_{period_name}.csv"
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✅ Completed period {period_name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed period {period_name}: {e}")
        print(f"STDERR: {e.stderr}")
        return False

def process_period_results(period_name):
    """Process results into required format"""
    summary_file = f"reports/strategy_summary_{period_name}.csv"
    
    if not Path(summary_file).exists():
        print(f"⚠️  No results file for {period_name}")
        # Create empty results
        return pd.DataFrame([{
            'strategy_name': strategy_id,
            'pnl_usd': 0.0,
            'stop_loss_count': 0,
            'take_profit_count': 0,
            'sentiment_exit_count': 0,
            'period_end_exit_count': 0
        } for strategy_id in STRATEGIES])
    
    # Read the results
    df = pd.read_csv(summary_file)
    
    # Convert to required format
    result_data = []
    for strategy_id in STRATEGIES:
        strategy_row = df[df['strategy_id'] == strategy_id]
        
        if not strategy_row.empty:
            row = strategy_row.iloc[0]
            result_data.append({
                'strategy_name': strategy_id,
                'pnl_usd': float(row['total_pnl_usd']),
                'stop_loss_count': int(row['stop_loss_count']),
                'take_profit_count': int(row['take_profit_count']),
                'sentiment_exit_count': int(row['eod_count']),  # Using EOD as sentiment exits
                'period_end_exit_count': int(row['eod_count'])
            })
        else:
            result_data.append({
                'strategy_name': strategy_id,
                'pnl_usd': 0.0,
                'stop_loss_count': 0,
                'take_profit_count': 0,
                'sentiment_exit_count': 0,
                'period_end_exit_count': 0
            })
    
    return pd.DataFrame(result_data)

def main():
    print("🎯 Running Six-Period Backtest")
    
    # Ensure directories exist
    Path("logs").mkdir(exist_ok=True)
    Path("reports").mkdir(exist_ok=True)
    
    all_results = []
    
    # Run each period
    for start_date, end_date, period_name in PERIODS:
        success = run_period(start_date, end_date, period_name)
        
        # Process results
        period_df = process_period_results(period_name)
        
        # Save period CSV
        period_csv = f"reports/period_{period_name}.csv"
        period_df.to_csv(period_csv, index=False)
        print(f"💾 Saved: {period_csv}")
        
        # Store for aggregation
        all_results.append(period_df)
    
    # Generate overall summary
    print("\n📊 Generating overall summary...")
    overall_df = pd.concat(all_results, ignore_index=True)
    overall_summary = overall_df.groupby('strategy_name').agg({
        'pnl_usd': 'sum',
        'stop_loss_count': 'sum',
        'take_profit_count': 'sum',
        'sentiment_exit_count': 'sum',
        'period_end_exit_count': 'sum'
    }).reset_index()
    
    overall_summary.to_csv("reports/overall_summary.csv", index=False)
    print("💾 Saved: reports/overall_summary.csv")
    
    # Generate global performance
    global_performance = pd.DataFrame([{
        'total_pnl_usd': float(overall_summary['pnl_usd'].sum()),
        'total_stop_loss_count': int(overall_summary['stop_loss_count'].sum()),
        'total_take_profit_count': int(overall_summary['take_profit_count'].sum()),
        'total_sentiment_exit_count': int(overall_summary['sentiment_exit_count'].sum()),
        'total_period_end_exit_count': int(overall_summary['period_end_exit_count'].sum())
    }])
    
    global_performance.to_csv("reports/global_performance.csv", index=False)
    print("💾 Saved: reports/global_performance.csv")
    
    print("\n🎉 All periods completed!")
    print("📁 Generated files:")
    for _, _, period_name in PERIODS:
        print(f"  📄 period_{period_name}.csv")
    print("  📄 overall_summary.csv")
    print("  📄 global_performance.csv")

if __name__ == "__main__":
    main()
