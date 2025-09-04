#!/usr/bin/env python3
"""
DEBUG: Why are we getting 0 trades when there should be trades?
Let's trace through the logic step by step
"""

import pandas as pd
from datetime import datetime, date
from trading_core import load_stock_universe
from volume_news_analyzer import VolumeNewsAnalyzer
from historical_backtest import get_historical_data

def debug_zero_trades():
    """Debug why we're getting 0 trades for June 1-4, 2025"""
    
    print("🔍 DEBUGGING ZERO TRADES ISSUE")
    print("📅 Period: 2025-06-01 to 2025-06-04")
    
    # Load stocks
    stocks = load_stock_universe()
    print(f"📈 Stock universe: {stocks}")
    
    # Initialize analyzer
    analyzer = VolumeNewsAnalyzer()
    
    # Check each day
    test_dates = ["2025-06-02", "2025-06-03", "2025-06-04"]  # Skip Sunday
    
    for date_str in test_dates:
        print(f"\n📅 DEBUGGING {date_str}")
        print("=" * 50)
        
        try:
            # Step 1: Check qualified stocks
            qualified_stocks = analyzer.screen_stocks_by_volume_and_news(stocks, date_str)
            print(f"✅ Qualified stocks: {len(qualified_stocks)}")
            
            if qualified_stocks:
                for i, stock_data in enumerate(qualified_stocks[:3]):  # Check first 3
                    ticker = stock_data['ticker']
                    sentiment = stock_data['weighted_sentiment']
                    print(f"   {i+1}. {ticker}: sentiment = {sentiment:.3f}")
                    
                    # Step 2: Check strategy matches
                    strategies = [
                        {"id": "S01", "min_sentiment": 0.10, "max_sentiment": 0.60},
                        {"id": "S02", "min_sentiment": 0.10, "max_sentiment": 0.60},
                        {"id": "S03", "min_sentiment": 0.20, "max_sentiment": 0.70}
                    ]
                    
                    for strategy in strategies:
                        if strategy['min_sentiment'] <= sentiment <= strategy['max_sentiment']:
                            print(f"      ✅ Matches {strategy['id']} ({strategy['min_sentiment']}-{strategy['max_sentiment']})")
                            
                            # Step 3: Check price data availability
                            price_data = get_historical_data(ticker, date_str, date_str, '1m')
                            
                            if price_data is not None and not price_data.empty:
                                print(f"      ✅ Price data available: {len(price_data)} bars")
                                print(f"         Open: ${price_data.iloc[0]['Open']:.2f}")
                                print(f"         High: ${price_data['High'].max():.2f}")
                                print(f"         Low: ${price_data['Low'].min():.2f}")
                                print(f"         Close: ${price_data.iloc[-1]['Close']:.2f}")
                                
                                # This should create a trade!
                                print(f"      🎯 THIS SHOULD CREATE A TRADE!")
                                
                            else:
                                print(f"      ❌ No price data for {ticker} on {date_str}")
                        else:
                            print(f"      ❌ No match for {strategy['id']} (sentiment {sentiment:.3f} not in {strategy['min_sentiment']}-{strategy['max_sentiment']})")
            else:
                print("❌ No qualified stocks found")
                
                # Debug why no qualified stocks
                print("\n🔍 Debugging stock screening...")
                for ticker in stocks[:3]:  # Check first 3 stocks
                    print(f"\n   Checking {ticker}:")
                    
                    try:
                        # Check volume data
                        volume_data = analyzer.get_volume_data(ticker, date_str)
                        if volume_data:
                            print(f"      Volume yesterday: {volume_data.get('volume_yesterday', 'N/A')}")
                            print(f"      Volume MA20: {volume_data.get('volume_ma20', 'N/A')}")
                            volume_ok = volume_data.get('volume_yesterday', 0) > volume_data.get('volume_ma20', 0)
                            print(f"      Volume check: {'✅ PASS' if volume_ok else '❌ FAIL'}")
                        else:
                            print(f"      ❌ No volume data")
                        
                        # Check news data
                        news_data = analyzer.get_news_sentiment(ticker, date_str)
                        if news_data:
                            print(f"      News articles: {news_data.get('article_count', 0)}")
                            print(f"      Sentiment: {news_data.get('weighted_sentiment', 'N/A')}")
                        else:
                            print(f"      ❌ No news data")
                            
                    except Exception as e:
                        print(f"      ❌ Error: {e}")
                
        except Exception as e:
            print(f"❌ Error processing {date_str}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    debug_zero_trades()
