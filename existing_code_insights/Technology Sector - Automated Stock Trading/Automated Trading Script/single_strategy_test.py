#!/usr/bin/env python3
"""
Single Strategy Test - Test only the first strategy over extended period
"""

import sys
import os
import argparse
import logging
from datetime import datetime, date, time as dt_time
import pandas as pd
from pathlib import Path
import time

# Import from the main batch runner
from run_real_strategy_batch import (
    setup_logging, get_trading_days, run_real_intraday_strategy, 
    calculate_strategy_performance, export_results
)

def main():
    parser = argparse.ArgumentParser(description='Single Strategy Test')
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--out', required=True, help='Output file path')
    parser.add_argument('--log-level', default='INFO', help='Logging level')
    parser.add_argument('--console-minimal', action='store_true', help='Minimal console output')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level, args.console_minimal)
    
    # Parse dates
    start_date = datetime.strptime(args.start, '%Y-%m-%d').date()
    end_date = datetime.strptime(args.end, '%Y-%m-%d').date()
    
    # Only test the first strategy
    SINGLE_STRATEGY = {
        "id": "01", 
        "score_threshold": 0.35, 
        "trend": "ON", 
        "stop_pct": 3, 
        "take_pct": 5, 
        "note": "conservative"
    }
    
    print(f"🚀 SINGLE STRATEGY TEST")
    print(f"=" * 50)
    print(f"Strategy: #{SINGLE_STRATEGY['id']} ({SINGLE_STRATEGY['note']})")
    print(f"Period: {start_date} to {end_date}")
    print(f"Score Threshold: {SINGLE_STRATEGY['score_threshold']}")
    print(f"Trend Filter: {SINGLE_STRATEGY['trend']}")
    print(f"Stop Loss: {SINGLE_STRATEGY['stop_pct']}%")
    print(f"Take Profit: {SINGLE_STRATEGY['take_pct']}%")
    print()
    
    # Record start time
    test_start_time = time.time()
    
    try:
        # Run the single strategy
        print(f"⏱️  Starting at {datetime.now().strftime('%H:%M:%S')}")
        
        # Define the stock universe (same as main batch runner)
        stocks = [
            'NVDA', 'MSFT', 'AAPL', 'AMZN', 'GOOGL', 'META', 'AVGO', 'TSM', 'TSLA', 'ORCL',
            'ADBE', 'CRM', 'NFLX', 'AMD', 'INTC', 'QCOM', 'TXN', 'AMAT', 'MU', 'ADI'
        ]
        
        result = run_real_intraday_strategy(
            strategy=SINGLE_STRATEGY,
            start_date=start_date,
            end_date=end_date,
            stocks=stocks,
            console_minimal=args.console_minimal
        )
        
        # Record end time
        test_end_time = time.time()
        duration_minutes = (test_end_time - test_start_time) / 60
        
        print(f"✅ Strategy completed in {duration_minutes:.2f} minutes")
        print()
        
        # Display key results
        print(f"📊 RESULTS SUMMARY:")
        print(f"Total PnL: ${result['total_pnl_usd']:,.2f}")
        print(f"Return: {result['cumulative_return_pct']*100:+.2f}%")
        print(f"Trades: {result['trades_count']}")
        print(f"Win Rate: {result['win_rate_pct']:.1f}%")
        print(f"EOD Forced Closes: {result['eod_forced_closes']}")
        print(f"Days with Trades: {result['days_with_trades']}")
        print(f"Days with No Trades: {result['days_with_no_trades']}")
        print()
        
        # Critical bug check
        eod_percentage = (result['eod_forced_closes'] / result['trades_count'] * 100) if result['trades_count'] > 0 else 0
        print(f"🔍 BUG CHECK:")
        print(f"EOD exits: {result['eod_forced_closes']}/{result['trades_count']} ({eod_percentage:.1f}%)")
        
        if eod_percentage > 95:
            print(f"🚨 BUG CONFIRMED: {eod_percentage:.1f}% EOD exits means SL/TP are not working!")
        elif eod_percentage < 50:
            print(f"✅ SL/TP WORKING: Only {eod_percentage:.1f}% EOD exits")
        else:
            print(f"⚠️  MIXED RESULTS: {eod_percentage:.1f}% EOD exits")
        
        # Export results
        results_list = [result]
        export_results(results_list, args.out)
        
        print(f"💾 Results saved to: {args.out}")
        print(f"⏱️  Total test duration: {duration_minutes:.2f} minutes")
        
    except Exception as e:
        test_end_time = time.time()
        duration_minutes = (test_end_time - test_start_time) / 60
        print(f"❌ Test failed after {duration_minutes:.2f} minutes: {e}")
        logging.error(f"Single strategy test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
