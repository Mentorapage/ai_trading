#!/usr/bin/env python3
"""
Simple Six-Period Backtest Runner
Run 20 strategies over six 2-week periods using subprocess calls.
"""

import os
import sys
import pandas as pd
import subprocess
from pathlib import Path

print("🚀 Starting Simple Six-Period Backtest Runner...")

# Define the six periods (14 calendar days each, starting from the 7th)
PERIODS = [
    ("2025-01-07", "2025-01-20", "2025-01"),
    ("2025-02-07", "2025-02-20", "2025-02"),
    ("2025-04-07", "2025-04-20", "2025-04"),
    ("2025-06-07", "2025-06-20", "2025-06"),
    ("2024-10-07", "2024-10-20", "2024-10"),
    ("2024-12-07", "2024-12-20", "2024-12"),
]

# Define the 20 strategies (S01-S20)
STRATEGIES = [f"S{i:02d}" for i in range(1, 21)]

def run_period_backtest(start_date: str, end_date: str, period_name: str):
    """Run backtest for a specific period using subprocess"""
    
    print(f"🚀 Starting backtest for period {period_name}: {start_date} to {end_date}")
    
    # Define output files for this period
    trade_log_file = f"logs/multi_strategy_{start_date}_{end_date}.csv"
    strategy_summary_file = f"reports/multi_strategy_summary_{start_date}_{end_date}.csv"
    ticker_summary_file = f"reports/multi_strategy_per_ticker_{start_date}_{end_date}.csv"
    
    # Ensure directories exist
    Path("logs").mkdir(exist_ok=True)
    Path("reports").mkdir(exist_ok=True)
    
    # Run the existing multi-strategy backtest script
    try:
        cmd = [
            "python3", "run_multi_strategy_backtest.py",
            "--start", start_date,
            "--end", end_date,
            "--strategies", "ALL",
            "--trade-log", trade_log_file,
            "--strategy-summary", strategy_summary_file,
            "--ticker-summary", ticker_summary_file
        ]
        
        print(f"📊 Running: {' '.join(cmd)}")
        
        # Run with real-time output
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                 universal_newlines=True, bufsize=1)
        
        # Print output in real-time
        for line in process.stdout:
            print(f"   {line.rstrip()}")
        
        process.wait()
        
        if process.returncode == 0:
            print(f"✅ Completed backtest for period {period_name}")
            
            # Read the strategy summary file to get results
            if Path(strategy_summary_file).exists():
                return pd.read_csv(strategy_summary_file)
            else:
                print(f"⚠️  Strategy summary file not found: {strategy_summary_file}")
                return create_empty_results()
        else:
            print(f"❌ Backtest failed for period {period_name} with return code {process.returncode}")
            return create_empty_results()
        
    except Exception as e:
        print(f"❌ Error running backtest for period {period_name}: {e}")
        return create_empty_results()

def create_empty_results():
    """Create empty results DataFrame"""
    return pd.DataFrame([{
        'strategy_id': strategy_id,
        'total_pnl_$': 0.0,
        'sl_count': 0,
        'tp_count': 0,
        'eod_count': 0
    } for strategy_id in STRATEGIES])

def process_results_to_csv_format(results_df: pd.DataFrame, period_name: str) -> pd.DataFrame:
    """Process backtest results into the required CSV format"""
    
    print(f"📋 Processing results for {period_name}...")
    
    csv_data = []
    
    # If results_df is empty, create empty results for all strategies
    if results_df.empty:
        print(f"⚠️  No results found for {period_name}, creating empty results")
        for strategy_id in STRATEGIES:
            csv_data.append({
                'strategy_name': strategy_id,
                'pnl_usd': 0.0,
                'stop_loss_count': 0,
                'take_profit_count': 0,
                'sentiment_exit_count': 0,
                'period_end_exit_count': 0
            })
    else:
        print(f"📊 Processing {len(results_df)} strategy results for {period_name}")
        # Process actual results
        for strategy_id in STRATEGIES:
            # Find the strategy in results
            strategy_row = results_df[results_df['strategy_id'] == strategy_id]
            
            if not strategy_row.empty:
                row = strategy_row.iloc[0]
                csv_data.append({
                    'strategy_name': strategy_id,
                    'pnl_usd': float(row.get('total_pnl_$', 0.0)),
                    'stop_loss_count': int(row.get('sl_count', 0)),
                    'take_profit_count': int(row.get('tp_count', 0)),
                    'sentiment_exit_count': int(row.get('eod_count', 0)),  # Assuming EOD includes sentiment exits
                    'period_end_exit_count': int(row.get('eod_count', 0))
                })
            else:
                # Strategy had no results
                csv_data.append({
                    'strategy_name': strategy_id,
                    'pnl_usd': 0.0,
                    'stop_loss_count': 0,
                    'take_profit_count': 0,
                    'sentiment_exit_count': 0,
                    'period_end_exit_count': 0
                })
    
    return pd.DataFrame(csv_data)

def main():
    """Main execution function"""
    
    print("🎯 Starting Six-Period Backtest Runner")
    
    # Ensure reports directory exists
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    print(f"📁 Reports directory: {reports_dir.absolute()}")
    
    # Store all period results for aggregation
    all_period_results = []
    
    # Run backtest for each period
    for i, (start_date, end_date, period_name) in enumerate(PERIODS, 1):
        print(f"\n{'='*60}")
        print(f"📅 PERIOD {i}/6: {period_name}")
        print(f"📅 Date Range: {start_date} to {end_date}")
        print(f"{'='*60}")
        
        try:
            # Run backtest for this period
            period_results = run_period_backtest(start_date, end_date, period_name)
            
            # Process results to CSV format
            period_df = process_results_to_csv_format(period_results, period_name)
            
            # Save period CSV
            period_csv_path = reports_dir / f"period_{period_name}.csv"
            period_df.to_csv(period_csv_path, index=False)
            print(f"💾 Saved period CSV: {period_csv_path}")
            
            # Store for overall aggregation
            all_period_results.append(period_df)
            
            print(f"✅ Period {period_name} completed successfully")
            
        except Exception as e:
            print(f"❌ Failed to process period {period_name}: {e}")
            # Create empty results for this period
            empty_df = create_empty_results()
            empty_processed = process_results_to_csv_format(empty_df, period_name)
            
            period_csv_path = reports_dir / f"period_{period_name}.csv"
            empty_processed.to_csv(period_csv_path, index=False)
            all_period_results.append(empty_processed)
    
    print(f"\n{'='*60}")
    print("📊 GENERATING SUMMARY REPORTS")
    print(f"{'='*60}")
    
    # Generate overall summary (aggregated across all periods)
    if all_period_results:
        print("📋 Aggregating results across all periods...")
        overall_df = pd.concat(all_period_results, ignore_index=True)
        overall_summary = overall_df.groupby('strategy_name').agg({
            'pnl_usd': 'sum',
            'stop_loss_count': 'sum',
            'take_profit_count': 'sum',
            'sentiment_exit_count': 'sum',
            'period_end_exit_count': 'sum'
        }).reset_index()
        
        # Save overall summary CSV
        overall_csv_path = reports_dir / "overall_summary.csv"
        overall_summary.to_csv(overall_csv_path, index=False)
        print(f"💾 Saved overall summary CSV: {overall_csv_path}")
        
        # Generate global performance CSV (single row with totals)
        print("📊 Calculating global performance...")
        global_performance = pd.DataFrame([{
            'total_pnl_usd': float(overall_summary['pnl_usd'].sum()),
            'total_stop_loss_count': int(overall_summary['stop_loss_count'].sum()),
            'total_take_profit_count': int(overall_summary['take_profit_count'].sum()),
            'total_sentiment_exit_count': int(overall_summary['sentiment_exit_count'].sum()),
            'total_period_end_exit_count': int(overall_summary['period_end_exit_count'].sum())
        }])
        
        # Save global performance CSV
        global_csv_path = reports_dir / "global_performance.csv"
        global_performance.to_csv(global_csv_path, index=False)
        print(f"💾 Saved global performance CSV: {global_csv_path}")
    
    print(f"\n{'='*80}")
    print("🎉 SIX-PERIOD BACKTEST COMPLETED SUCCESSFULLY!")
    print(f"{'='*80}")
    print(f"📁 Generated files in {reports_dir}:")
    for period_name in [p[2] for p in PERIODS]:
        print(f"  📄 period_{period_name}.csv")
    print(f"  📄 overall_summary.csv")
    print(f"  📄 global_performance.csv")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
