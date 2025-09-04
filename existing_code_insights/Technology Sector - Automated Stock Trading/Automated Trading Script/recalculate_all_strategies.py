#!/usr/bin/env python3
"""
RECALCULATE ALL 20 STRATEGIES
=============================
Corrects P&L calculations based on maximum concurrent positions for each strategy
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import json

def analyze_strategy_concurrent_exposure(strategy_id, sentiment_range):
    """Analyze concurrent exposure for a specific strategy"""
    
    min_sentiment, max_sentiment = sentiment_range
    
    # Load audit logs to understand daily qualified stocks for this strategy
    audit_dir = Path("audit_logs")
    audit_files = list(audit_dir.glob("volume_news_audit_*.csv"))
    
    daily_qualified = []
    max_concurrent = 0
    
    for audit_file in sorted(audit_files):
        try:
            audit_df = pd.read_csv(audit_file)
            
            # Filter for this strategy's sentiment range
            strategy_qualified = audit_df[
                (audit_df['passed_volume'] == True) & 
                (audit_df['passed_news'] == True) &
                (audit_df['weighted_sentiment'] >= min_sentiment) &
                (audit_df['weighted_sentiment'] <= max_sentiment)
            ]
            
            qualified_count = len(strategy_qualified)
            daily_qualified.append(qualified_count)
            
            if qualified_count > max_concurrent:
                max_concurrent = qualified_count
                
        except Exception as e:
            continue
    
    avg_concurrent = np.mean(daily_qualified) if daily_qualified else 0
    
    return {
        'max_concurrent': max_concurrent,
        'avg_concurrent': avg_concurrent,
        'trading_days': len(daily_qualified)
    }

def recalculate_all_strategies():
    """Recalculate performance for all 20 strategies based on concurrent exposure"""
    
    print("🔄 RECALCULATING ALL 20 STRATEGIES WITH CORRECTED METHODOLOGY")
    print("=" * 80)
    
    # Load original results
    results_file = "extended_strategies_2024-11-10_to_2025-08-20.xlsx"
    
    try:
        df = pd.read_excel(results_file, sheet_name='Strategies')
        print(f"✅ Loaded original results from {results_file}")
    except Exception as e:
        print(f"❌ Error loading results: {e}")
        return
    
    # Strategy sentiment ranges mapping
    strategy_ranges = {
        'S01': (0.10, 0.60), 'S02': (0.10, 0.60), 'S03': (0.20, 0.70), 'S04': (0.20, 0.70),
        'S05': (0.10, 0.60), 'S06': (0.20, 0.70), 'S07': (0.20, 0.70), 'S08': (0.30, 0.80),
        'S09': (0.10, 0.60), 'S10': (0.20, 0.70), 'S11': (0.30, 0.80), 'S12': (0.30, 0.80),
        'S13': (0.10, 0.60), 'S14': (0.20, 0.70), 'S15': (0.30, 0.80), 'S16': (0.15, 0.65),
        'S17': (0.15, 0.65), 'S18': (0.10, 0.60), 'S19': (0.20, 0.70), 'S20': (0.30, 0.80)
    }
    
    corrected_results = []
    
    print(f"\n📊 ANALYZING CONCURRENT EXPOSURE FOR EACH STRATEGY:")
    print("-" * 80)
    
    for idx, row in df.iterrows():
        strategy_id = row['strategy_id']
        sentiment_range = strategy_ranges.get(strategy_id, (0.10, 0.60))
        
        # Analyze concurrent exposure for this strategy
        exposure_data = analyze_strategy_concurrent_exposure(strategy_id, sentiment_range)
        
        # Original metrics
        original_pnl = row['pnl_usd']
        original_trades = row['trades_count']
        
        # Calculate corrected metrics
        max_concurrent = exposure_data['max_concurrent']
        required_capital = max_concurrent * 1_000_000  # $1M per position
        
        if required_capital > 0:
            corrected_return_pct = (original_pnl / required_capital) * 100
            
            # Calculate annualized return (CAGR) for 9+ months
            start_date = datetime.strptime("2024-11-10", "%Y-%m-%d")
            end_date = datetime.strptime("2025-08-20", "%Y-%m-%d")
            years_elapsed = (end_date - start_date).days / 365.25
            
            if original_pnl > 0:
                cagr = ((1 + corrected_return_pct/100) ** (1 / years_elapsed) - 1) * 100
            else:
                cagr = -((1 + abs(corrected_return_pct)/100) ** (1 / years_elapsed) - 1) * 100
        else:
            corrected_return_pct = 0
            cagr = 0
        
        # Create corrected result
        corrected_result = {
            'strategy_id': strategy_id,
            'stop_pct': row['stop_pct'],
            'take_pct': row['take_pct'],
            'min_sentiment': row['min_sentiment'],
            'max_sentiment': row['max_sentiment'],
            'original_trades': original_trades,
            'original_pnl_usd': original_pnl,
            'original_return_pct': row['pnl_pct'],
            'max_concurrent_positions': max_concurrent,
            'required_capital_usd': required_capital,
            'corrected_return_pct': corrected_return_pct,
            'annualized_cagr_pct': cagr,
            'avg_concurrent_positions': exposure_data['avg_concurrent'],
            'capital_efficiency_ratio': (original_trades * 1_000_000) / required_capital if required_capital > 0 else 0
        }
        
        corrected_results.append(corrected_result)
        
        # Print progress
        print(f"{strategy_id}: Max {max_concurrent:2d} pos, Capital ${required_capital:,}, "
              f"Return {corrected_return_pct:+6.2f}%, CAGR {cagr:+6.2f}%")
    
    # Create DataFrame with corrected results
    corrected_df = pd.DataFrame(corrected_results)
    
    # Sort by corrected return percentage (descending)
    corrected_df = corrected_df.sort_values('corrected_return_pct', ascending=False)
    
    print(f"\n📊 CORRECTED PERFORMANCE RANKING:")
    print("=" * 80)
    
    # Display top performers
    display_cols = ['strategy_id', 'max_concurrent_positions', 'required_capital_usd', 
                   'original_pnl_usd', 'corrected_return_pct', 'annualized_cagr_pct']
    
    print(corrected_df[display_cols].to_string(index=False, float_format='%.2f'))
    
    # Save corrected results to Excel
    output_file = "corrected_strategies_performance.xlsx"
    
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # Main corrected results
        corrected_df.to_excel(writer, sheet_name='Corrected_Performance', index=False)
        
        # Comparison sheet
        comparison_df = corrected_df[['strategy_id', 'original_return_pct', 'corrected_return_pct', 
                                    'annualized_cagr_pct', 'capital_efficiency_ratio']].copy()
        comparison_df['improvement_factor'] = corrected_df['corrected_return_pct'] / corrected_df['original_return_pct']
        comparison_df.to_excel(writer, sheet_name='Performance_Comparison', index=False)
        
        # Summary statistics
        summary_stats = {
            'Metric': ['Best Strategy', 'Worst Strategy', 'Average Return', 'Median Return', 
                      'Best CAGR', 'Average CAGR', 'Max Capital Required', 'Min Capital Required'],
            'Value': [
                f"{corrected_df.iloc[0]['strategy_id']} ({corrected_df.iloc[0]['corrected_return_pct']:.2f}%)",
                f"{corrected_df.iloc[-1]['strategy_id']} ({corrected_df.iloc[-1]['corrected_return_pct']:.2f}%)",
                f"{corrected_df['corrected_return_pct'].mean():.2f}%",
                f"{corrected_df['corrected_return_pct'].median():.2f}%",
                f"{corrected_df['annualized_cagr_pct'].max():.2f}%",
                f"{corrected_df['annualized_cagr_pct'].mean():.2f}%",
                f"${corrected_df['required_capital_usd'].max():,}",
                f"${corrected_df['required_capital_usd'].min():,}"
            ]
        }
        summary_df = pd.DataFrame(summary_stats)
        summary_df.to_excel(writer, sheet_name='Summary_Statistics', index=False)
    
    print(f"\n💾 Corrected results saved to: {output_file}")
    
    # Print summary
    print(f"\n🎯 SUMMARY OF CORRECTIONS:")
    print(f"  📈 Best Strategy: {corrected_df.iloc[0]['strategy_id']} with {corrected_df.iloc[0]['corrected_return_pct']:.2f}% return")
    print(f"  📊 Average Return: {corrected_df['corrected_return_pct'].mean():.2f}%")
    print(f"  🎲 Best CAGR: {corrected_df['annualized_cagr_pct'].max():.2f}%")
    print(f"  💰 Capital Range: ${corrected_df['required_capital_usd'].min():,} - ${corrected_df['required_capital_usd'].max():,}")
    print(f"  ⚡ Avg Efficiency: {corrected_df['capital_efficiency_ratio'].mean():.1f}x turnover vs capital")
    
    return corrected_df

if __name__ == "__main__":
    recalculate_all_strategies()
