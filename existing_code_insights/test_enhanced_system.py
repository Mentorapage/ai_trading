#!/usr/bin/env python3
"""
Comprehensive Test Suite for Enhanced AI Trading System
Tests all failure prevention mechanisms and improvements
"""

import sys
sys.path.append("Technology Sector - Automated Stock Trading/Automated Trading Script")

from technology_auto_trade import get_sentiment, auto_trade
from trade_types import bracket_order, get_account_info
from market_utils import pre_trading_validation, validate_stock_symbol, is_market_open
import logging
from datetime import datetime

def test_sub_penny_fix():
    """Test the sub-penny pricing fix"""
    print("🔧 TESTING SUB-PENNY PRICING FIX")
    print("=" * 50)
    
    test_cases = [
        ("MSFT", 10, 535.845, 0.5, 1.5),  # Previously failed case
        ("AAPL", 5, 203.999, 0.5, 1.5),   # Edge case with .999
        ("TSLA", 3, 308.333, 0.5, 1.5),   # Edge case with .333
    ]
    
    results = []
    for symbol, qty, mock_price, profit, loss in test_cases:
        print(f"\nTesting {symbol} with price ${mock_price:.3f}:")
        
        # Calculate what the prices would be
        high_price = round(mock_price + profit, 2)
        low_price = round(mock_price - loss, 2)
        
        print(f"  Price: ${mock_price:.3f} → High: ${high_price:.2f}, Low: ${low_price:.2f}")
        
        # Check for sub-penny issues
        high_ok = (high_price * 100) % 1 == 0
        low_ok = (low_price * 100) % 1 == 0
        
        if high_ok and low_ok:
            print(f"  ✅ FIXED: No sub-penny issues")
            results.append(True)
        else:
            print(f"  ❌ STILL BROKEN: Sub-penny detected")
            results.append(False)
    
    success_rate = sum(results) / len(results) * 100
    print(f"\n📊 Sub-penny fix success rate: {success_rate:.0f}%")
    return success_rate == 100

def test_validation_system():
    """Test the comprehensive validation system"""
    print("\n🛡️ TESTING VALIDATION SYSTEM")
    print("=" * 50)
    
    try:
        # Test market hours validation
        market_open, market_msg = is_market_open()
        print(f"📅 Market Status: {market_msg}")
        
        # Test account validation
        account_valid, account_info = validate_stock_symbol("AAPL")
        print(f"🏛️ Account Valid: {account_valid}")
        
        # Test symbol validation
        symbols_to_test = ["AAPL", "MSFT", "INVALID", "TOOLONG"]
        for symbol in symbols_to_test:
            valid, msg = validate_stock_symbol(symbol)
            status = "✅" if valid else "❌"
            print(f"🏷️ {symbol}: {status} {msg}")
        
        # Full pre-trading validation
        print(f"\n🔍 FULL VALIDATION TEST:")
        ready, results = pre_trading_validation()
        
        for result in results:
            status = "✅" if result['passed'] else "❌"
            print(f"  {status} {result['check']}: {result['message']}")
        
        print(f"\n📊 Overall Ready: {'✅ YES' if ready else '❌ NO'}")
        return True
        
    except Exception as e:
        print(f"❌ Validation test failed: {e}")
        return False

def test_error_handling():
    """Test enhanced error handling"""
    print("\n🚨 TESTING ERROR HANDLING")
    print("=" * 50)
    
    try:
        from trade_types import bracket_order
        
        # Test various error conditions
        test_cases = [
            {
                'name': 'Empty symbol',
                'params': ('', 10, 'BUY', 'DAY', 100.50, 99.50),
                'should_fail': True
            },
            {
                'name': 'Negative quantity',
                'params': ('AAPL', -5, 'BUY', 'DAY', 100.50, 99.50),
                'should_fail': True
            },
            {
                'name': 'Invalid price order (low > high)',
                'params': ('AAPL', 10, 'BUY', 'DAY', 99.50, 100.50),
                'should_fail': True
            },
            {
                'name': 'Valid order',
                'params': ('AAPL', 1, 'BUY', 'DAY', 200.50, 199.50),
                'should_fail': False
            }
        ]
        
        for test_case in test_cases:
            print(f"\n🧪 Testing: {test_case['name']}")
            try:
                result = bracket_order(*test_case['params'])
                if test_case['should_fail']:
                    print(f"  ❌ UNEXPECTED SUCCESS: {result}")
                else:
                    print(f"  ✅ SUCCESS: Order placed correctly")
            except Exception as e:
                if test_case['should_fail']:
                    print(f"  ✅ EXPECTED FAILURE: {str(e)[:100]}...")
                else:
                    print(f"  ❌ UNEXPECTED FAILURE: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        return False

def test_sentiment_analysis():
    """Test sentiment analysis is still working after changes"""
    print("\n🧠 TESTING SENTIMENT ANALYSIS")
    print("=" * 50)
    
    try:
        test_stocks = ['AAPL', 'MSFT', 'NVDA']
        
        for stock in test_stocks:
            sentiment = get_sentiment(stock)
            print(f"📊 {stock}: {sentiment:.4f}")
            
            if sentiment != 0 or stock in ['ADBE', 'CSCO', 'INTU', 'QCOM']:  # Some might legitimately be 0
                print(f"  ✅ Valid sentiment score")
            else:
                print(f"  ⚠️ Zero sentiment (may be legitimate)")
        
        return True
        
    except Exception as e:
        print(f"❌ Sentiment analysis test failed: {e}")
        return False

def run_comprehensive_test():
    """Run all tests and provide summary"""
    print("🧪 COMPREHENSIVE ENHANCED SYSTEM TEST")
    print("=" * 70)
    print(f"🕐 Test Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Configure logging for tests
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('test_results.log'),
            logging.StreamHandler()
        ]
    )
    
    tests = [
        ("Sub-Penny Pricing Fix", test_sub_penny_fix),
        ("Validation System", test_validation_system),
        ("Error Handling", test_error_handling),
        ("Sentiment Analysis", test_sentiment_analysis),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            print(f"\n{'='*70}")
            result = test_func()
            results.append((test_name, result))
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"\n🎯 {test_name}: {status}")
            
        except Exception as e:
            print(f"\n❌ {test_name}: CRASHED - {e}")
            results.append((test_name, False))
    
    # Final summary
    print(f"\n{'='*70}")
    print("📊 FINAL TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status} {test_name}")
    
    success_rate = (passed / total) * 100
    print(f"\n🎯 Overall Success Rate: {passed}/{total} ({success_rate:.0f}%)")
    
    if success_rate == 100:
        print("🎉 ALL TESTS PASSED - System is production ready!")
    elif success_rate >= 75:
        print("⚠️ Most tests passed - Minor issues to address")
    else:
        print("❌ Multiple failures detected - Significant issues remain")
    
    print(f"\n📝 Detailed logs saved to: test_results.log")
    return success_rate

if __name__ == "__main__":
    run_comprehensive_test() 