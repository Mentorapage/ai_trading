#!/usr/bin/env python3
"""
DEBUG MULTI-STRATEGY RUNNER
===========================
Debug version with verbose output to identify hanging issues
"""

import sys
import os
import argparse
import logging
from datetime import datetime, date, time as dt_time
import pandas as pd
import numpy as np
from pathlib import Path
import time
from typing import Dict, List, Optional
import pandas_market_calendars as mcal

# Import existing modules
from volume_news_analyzer import VolumeNewsAnalyzer
from trading_core import load_stock_universe
import bootstrap_nltk  # noqa

# Just first 3 strategies for debugging
DEBUG_STRATEGIES = [
    {"id": "S01", "stop_pct": 3, "take_pct": 5, "min_sentiment": 0.10, "max_sentiment": 0.60},
    {"id": "S02", "stop_pct": 3, "take_pct": 8, "min_sentiment": 0.10, "max_sentiment": 0.60},
    {"id": "S03", "stop_pct": 3, "take_pct": 12, "min_sentiment": 0.20, "max_sentiment": 0.70},
]

def get_trading_days(start_date: date, end_date: date) -> List[date]:
    """Get trading days using NYSE calendar"""
    nyse = mcal.get_calendar('NYSE')
    trading_days = nyse.valid_days(start_date=start_date, end_date=end_date)
    return [day.date() if hasattr(day, 'date') else day for day in trading_days]

def debug_single_day_screening(analyzer, stocks, test_date):
    """Debug the screening process for a single day"""
    print(f"\n🔍 DEBUG: Screening stocks for {test_date}")
    print(f"📊 Testing with {len(stocks)} stocks")
    
    try:
        start_time = time.time()
        qualified_stocks = analyzer.screen_stocks_by_volume_and_news(
            stocks=stocks,
            analysis_date=test_date,
            min_news_count=2,
            min_sentiment=0.10,
            max_sentiment=0.60
        )
        elapsed = time.time() - start_time
        
        print(f"✅ Screening completed in {elapsed:.1f} seconds")
        print(f"📈 Qualified stocks: {len(qualified_stocks)}")
        
        return qualified_stocks
        
    except Exception as e:
        print(f"❌ Screening failed: {e}")
        import traceback
        traceback.print_exc()
        return []

def main():
    """Debug main function"""
    print("🚀 DEBUG MULTI-STRATEGY RUNNER")
    print("=" * 50)
    
    # Parse dates
    start_date = date(2025, 4, 7)
    end_date = date(2025, 4, 7)  # Just one day for debugging
    
    print(f"📅 Debug period: {start_date}")
    
    # Load stock universe
    print("\n📊 Loading stock universe...")
    stocks = load_stock_universe()
    print(f"✅ Loaded {len(stocks)} stocks: {stocks}")
    
    # Get trading days
    print(f"\n📅 Getting trading days...")
    trading_days = get_trading_days(start_date, end_date)
    print(f"✅ Trading days: {trading_days}")
    
    # Initialize analyzer
    print(f"\n🔧 Initializing VolumeNewsAnalyzer...")
    try:
        analyzer = VolumeNewsAnalyzer()
        print("✅ Analyzer initialized")
    except Exception as e:
        print(f"❌ Analyzer initialization failed: {e}")
        return
    
    # Test screening for first day
    if trading_days:
        test_date = trading_days[0].strftime('%Y-%m-%d')
        qualified_stocks = debug_single_day_screening(analyzer, stocks, test_date)
        
        if qualified_stocks:
            print(f"\n📋 Sample qualified stock:")
            print(qualified_stocks[0])
    
    # Test with first strategy
    print(f"\n🎯 Testing first strategy: {DEBUG_STRATEGIES[0]}")
    
    print("\n✅ Debug completed successfully!")

if __name__ == "__main__":
    main()
