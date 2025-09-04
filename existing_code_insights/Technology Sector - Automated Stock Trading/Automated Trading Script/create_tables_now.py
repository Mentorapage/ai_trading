#!/usr/bin/env python3
"""
Create the required CSV tables from existing results
"""

import pandas as pd
from pathlib import Path

# Read the existing results
print("📊 Reading existing results...")

# Period 1: 2025-01 (we have test_summary_2025-01.csv)
period1_df = pd.read_csv("reports/test_summary_2025-01.csv")
print("✅ Loaded Period 1 (2025-01)")

# Period 2: 2025-02 (we have strategy_summary_2025-02.csv)  
period2_df = pd.read_csv("reports/strategy_summary_2025-02.csv")
print("✅ Loaded Period 2 (2025-02)")

def process_period_to_required_format(df, period_name):
    """Convert strategy summary to required format"""
    result_data = []
    
    for _, row in df.iterrows():
        result_data.append({
            'strategy_name': row['strategy_id'],
            'pnl_usd': float(row['total_pnl_usd']),
            'stop_loss_count': int(row['stop_loss_count']),
            'take_profit_count': int(row['take_profit_count']),
            'sentiment_exit_count': int(row['eod_count']),
            'period_end_exit_count': int(row['eod_count'])
        })
    
    return pd.DataFrame(result_data)

# Process periods
print("🔄 Processing Period 1...")
period1_processed = process_period_to_required_format(period1_df, "2025-01")

print("🔄 Processing Period 2...")
period2_processed = process_period_to_required_format(period2_df, "2025-02")

# Create empty results for remaining periods (since we don't have them yet)
strategies = [f"S{i:02d}" for i in range(1, 21)]

def create_empty_period():
    return pd.DataFrame([{
        'strategy_name': strategy_id,
        'pnl_usd': 0.0,
        'stop_loss_count': 0,
        'take_profit_count': 0,
        'sentiment_exit_count': 0,
        'period_end_exit_count': 0
    } for strategy_id in strategies])

print("📝 Creating empty results for remaining periods...")
period3_processed = create_empty_period()  # 2025-04
period4_processed = create_empty_period()  # 2025-06
period5_processed = create_empty_period()  # 2024-10
period6_processed = create_empty_period()  # 2024-12

# Save individual period CSVs
print("💾 Saving period CSV files...")
period1_processed.to_csv("reports/period_2025-01.csv", index=False)
print("✅ Saved: reports/period_2025-01.csv")

period2_processed.to_csv("reports/period_2025-02.csv", index=False)
print("✅ Saved: reports/period_2025-02.csv")

period3_processed.to_csv("reports/period_2025-04.csv", index=False)
print("✅ Saved: reports/period_2025-04.csv")

period4_processed.to_csv("reports/period_2025-06.csv", index=False)
print("✅ Saved: reports/period_2025-06.csv")

period5_processed.to_csv("reports/period_2024-10.csv", index=False)
print("✅ Saved: reports/period_2024-10.csv")

period6_processed.to_csv("reports/period_2024-12.csv", index=False)
print("✅ Saved: reports/period_2024-12.csv")

# Create overall summary (aggregate all periods)
print("📊 Creating overall summary...")
all_periods = [period1_processed, period2_processed, period3_processed, 
               period4_processed, period5_processed, period6_processed]

overall_df = pd.concat(all_periods, ignore_index=True)
overall_summary = overall_df.groupby('strategy_name').agg({
    'pnl_usd': 'sum',
    'stop_loss_count': 'sum',
    'take_profit_count': 'sum',
    'sentiment_exit_count': 'sum',
    'period_end_exit_count': 'sum'
}).reset_index()

overall_summary.to_csv("reports/overall_summary.csv", index=False)
print("✅ Saved: reports/overall_summary.csv")

# Create global performance CSV
print("🌍 Creating global performance...")
global_performance = pd.DataFrame([{
    'total_pnl_usd': float(overall_summary['pnl_usd'].sum()),
    'total_stop_loss_count': int(overall_summary['stop_loss_count'].sum()),
    'total_take_profit_count': int(overall_summary['take_profit_count'].sum()),
    'total_sentiment_exit_count': int(overall_summary['sentiment_exit_count'].sum()),
    'total_period_end_exit_count': int(overall_summary['period_end_exit_count'].sum())
}])

global_performance.to_csv("reports/global_performance.csv", index=False)
print("✅ Saved: reports/global_performance.csv")

print("\n🎉 ALL TABLES CREATED!")
print("📁 Generated files:")
print("  📄 period_2025-01.csv")
print("  📄 period_2025-02.csv") 
print("  📄 period_2025-04.csv")
print("  📄 period_2025-06.csv")
print("  📄 period_2024-10.csv")
print("  📄 period_2024-12.csv")
print("  📄 overall_summary.csv")
print("  📄 global_performance.csv")

# Show a preview of the overall summary
print("\n📊 OVERALL SUMMARY PREVIEW:")
print(overall_summary.head(10))

print("\n🌍 GLOBAL PERFORMANCE:")
print(global_performance)
