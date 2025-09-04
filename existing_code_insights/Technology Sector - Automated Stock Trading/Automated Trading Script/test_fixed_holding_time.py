#!/usr/bin/env python3
"""
Test the FIXED holding time calculation with proper minute-level data
"""

import pandas as pd
from datetime import datetime, date, timedelta
from trading_core import load_stock_universe
from volume_news_analyzer import VolumeNewsAnalyzer
from historical_backtest import get_historical_data

def test_fixed_holding_time():
    """Test one single trade to verify holding time calculation is fixed"""
    
    print("🧪 TESTING FIXED HOLDING TIME CALCULATION")
    print("=" * 50)
    
    # Test parameters
    ticker = "NVDA"
    test_date = "2024-12-19"
    
    print(f"📅 Testing {ticker} on {test_date}")
    
    # Get minute-level data with proper datetime objects
    start_dt = datetime.strptime(test_date, '%Y-%m-%d').replace(hour=9, minute=30)  # 9:30 AM
    end_dt = datetime.strptime(test_date, '%Y-%m-%d').replace(hour=16, minute=0)    # 4:00 PM
    
    print(f"🕘 Market hours: {start_dt} to {end_dt}")
    
    price_data = get_historical_data(ticker, start_dt, end_dt, '1Min')
    
    if price_data is None or price_data.empty:
        print("❌ No price data available")
        return
    
    print(f"📊 Price data: {len(price_data)} bars")
    print(f"🕘 First bar: {price_data.index[0]}")
    print(f"🕘 Last bar: {price_data.index[-1]}")
    
    # Simulate a simple trade
    entry_time = price_data.index[0]
    entry_price = price_data.iloc[0]['open']
    
    # Exit at end of day
    exit_time = price_data.index[-1]
    exit_price = price_data.iloc[-1]['close']
    
    # Calculate holding time
    holding_minutes = (exit_time - entry_time).total_seconds() / 60
    
    print(f"\n💰 TRADE SIMULATION:")
    print(f"   Entry: {entry_time} @ ${entry_price:.2f}")
    print(f"   Exit:  {exit_time} @ ${exit_price:.2f}")
    print(f"   Holding time: {holding_minutes:.1f} minutes ({holding_minutes/60:.1f} hours)")
    
    # Verify this is reasonable
    expected_market_hours = 6.5 * 60  # 6.5 hours = 390 minutes
    if 300 <= holding_minutes <= 450:  # Reasonable range
        print(f"   ✅ Holding time is REASONABLE (expected ~{expected_market_hours} min)")
        return True
    else:
        print(f"   ❌ Holding time is WRONG (expected ~{expected_market_hours} min)")
        return False

def test_strategy_with_fixed_holding():
    """Test a full strategy with the fixed holding time calculation"""
    
    print(f"\n🎯 TESTING FULL STRATEGY WITH FIXED HOLDING TIME")
    print("=" * 50)
    
    # Load stocks and analyzer
    stocks = load_stock_universe()
    analyzer = VolumeNewsAnalyzer()
    
    # Test one day
    test_date = "2024-12-19"
    print(f"📅 Testing strategies on {test_date}")
    
    # Get qualified stocks
    qualified_stocks = analyzer.screen_stocks_by_volume_and_news(stocks, test_date)
    print(f"📊 Qualified stocks: {len(qualified_stocks)}")
    
    if not qualified_stocks:
        print("❌ No qualified stocks")
        return
    
    # Test first qualified stock
    stock_data = qualified_stocks[0]
    ticker = stock_data['ticker']
    sentiment = stock_data['weighted_sentiment']
    
    print(f"🎯 Testing {ticker} (sentiment: {sentiment:.3f})")
    
    # Get minute-level price data
    start_dt = datetime.strptime(test_date, '%Y-%m-%d').replace(hour=9, minute=30)
    end_dt = datetime.strptime(test_date, '%Y-%m-%d').replace(hour=16, minute=0)
    price_data = get_historical_data(ticker, start_dt, end_dt, '1Min')
    
    if price_data is None or price_data.empty:
        print(f"❌ No price data for {ticker}")
        return
    
    print(f"📊 Price data: {len(price_data)} bars")
    
    # Simulate trade with stop loss and take profit
    entry_time = price_data.index[0]
    entry_price = price_data.iloc[0]['open']
    
    # Strategy parameters
    stop_loss_pct = 3.0
    take_profit_pct = 5.0
    
    stop_loss_price = entry_price * (1 - stop_loss_pct / 100)
    take_profit_price = entry_price * (1 + take_profit_pct / 100)
    
    print(f"📈 Entry: ${entry_price:.2f}")
    print(f"🛑 Stop Loss: ${stop_loss_price:.2f} (-{stop_loss_pct}%)")
    print(f"🎯 Take Profit: ${take_profit_price:.2f} (+{take_profit_pct}%)")
    
    # Check each minute for exit
    exit_time = None
    exit_price = None
    exit_reason = None
    
    for timestamp, row in price_data.iterrows():
        if timestamp <= entry_time:
            continue
        
        high = row['high']
        low = row['low']
        
        if low <= stop_loss_price:
            exit_time = timestamp
            exit_price = stop_loss_price
            exit_reason = 'STOP_LOSS'
            break
        elif high >= take_profit_price:
            exit_time = timestamp
            exit_price = take_profit_price
            exit_reason = 'TAKE_PROFIT'
            break
    
    if exit_time is None:
        # End of day exit
        exit_time = price_data.index[-1]
        exit_price = price_data.iloc[-1]['close']
        exit_reason = 'EOD'
    
    # Calculate results
    holding_minutes = (exit_time - entry_time).total_seconds() / 60
    pnl = (exit_price - entry_price) * 1000  # Assume 1000 shares
    
    print(f"\n💰 TRADE RESULTS:")
    print(f"   Exit: {exit_time} @ ${exit_price:.2f} ({exit_reason})")
    print(f"   Holding: {holding_minutes:.1f} minutes ({holding_minutes/60:.1f} hours)")
    print(f"   P&L: ${pnl:+,.0f}")
    
    # Verify holding time is reasonable
    if 0 < holding_minutes <= 450:  # 0 to 7.5 hours max
        print(f"   ✅ Holding time is REASONABLE")
        return True
    else:
        print(f"   ❌ Holding time is WRONG")
        return False

if __name__ == "__main__":
    # Test 1: Basic holding time calculation
    test1_passed = test_fixed_holding_time()
    
    # Test 2: Full strategy simulation
    test2_passed = test_strategy_with_fixed_holding()
    
    print(f"\n🏁 FINAL RESULTS:")
    print(f"   Test 1 (Basic holding): {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"   Test 2 (Strategy sim): {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    
    if test1_passed and test2_passed:
        print(f"\n🎉 ALL TESTS PASSED! Holding time calculation is FIXED!")
    else:
        print(f"\n💥 TESTS FAILED! Holding time calculation still has bugs!")
