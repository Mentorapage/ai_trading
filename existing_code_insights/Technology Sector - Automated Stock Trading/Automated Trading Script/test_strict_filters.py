#!/usr/bin/env python3
"""
TEST STRICT FILTERS
===================
Test the system with stricter filters to show varied results
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from real_sentiment_analyzer import get_sentiment_analyzer
from datetime import datetime

def test_strict_filters():
    """Test with progressively stricter sentiment filters"""
    
    print("🧪 TESTING STRICT FILTERS FOR VARIED RESULTS")
    print("=" * 50)
    
    analyzer = get_sentiment_analyzer()
    
    # Test different sentiment thresholds
    test_configs = [
        {"name": "Permissive", "min_sent": 0.1, "max_sent": 1.0},
        {"name": "Moderate", "min_sent": 0.3, "max_sent": 0.8},
        {"name": "Strict", "min_sent": 0.4, "max_sent": 0.7},
        {"name": "Very Strict", "min_sent": 0.5, "max_sent": 0.6},
    ]
    
    test_date = "2024-12-09"
    stocks = ["NVDA", "MSFT", "AAPL", "AMZN", "GOOGL", "META", "AVGO", "TSM", "TSLA", "ORCL", "ADBE", "CSCO", "INTU", "QCOM"]
    
    print(f"📅 Testing date: {test_date}")
    print(f"📊 Stock universe: {len(stocks)} stocks")
    print()
    
    for config in test_configs:
        print(f"🎯 {config['name']} Filter (sentiment {config['min_sent']:.1f}-{config['max_sent']:.1f}):")
        
        qualified = analyzer.screen_stocks_by_sentiment(
            stocks=stocks,
            analysis_date=test_date,
            min_sentiment=config['min_sent'],
            max_sentiment=config['max_sent'],
            min_news_count=2,
            top_k=10  # High top_k to see all qualified
        )
        
        print(f"   Qualified stocks: {len(qualified)}")
        if qualified:
            print("   Top qualified:")
            for i, stock in enumerate(qualified[:5], 1):
                print(f"     {i}. {stock['ticker']}: {stock['sentiment']:.3f}")
        else:
            print("   No stocks qualified!")
        
        print(f"   → top_k=3 would get: {min(len(qualified), 3)} stocks")
        print(f"   → top_k=1 would get: {min(len(qualified), 1)} stocks")
        print()

if __name__ == "__main__":
    test_strict_filters()
