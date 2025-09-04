#!/usr/bin/env python3
"""
SYSTEM TEST - Quick functionality test
=====================================
Simple test to verify core system components work
"""

import sys
import os
from pathlib import Path

def test_imports():
    """Test that core modules can be imported"""
    print("🔍 Testing module imports...")
    
    try:
        import trading_core
        print("✅ trading_core imported successfully")
    except Exception as e:
        print(f"❌ trading_core import failed: {e}")
        return False
    
    try:
        import historical_backtest
        print("✅ historical_backtest imported successfully")
    except Exception as e:
        print(f"❌ historical_backtest import failed: {e}")
        return False
    
    try:
        import live_trading
        print("✅ live_trading imported successfully")
    except Exception as e:
        print(f"❌ live_trading import failed: {e}")
        return False
    
    return True

def test_environment():
    """Test environment setup"""
    print("\n🔧 Testing environment...")
    
    # Check .env file
    env_file = Path('.env')
    if env_file.exists():
        print("✅ .env file found")
    else:
        print("⚠️  .env file not found (copy from env_example.txt)")
    
    # Check config file
    config_file = Path('config.yml')
    if config_file.exists():
        print("✅ config.yml found")
    else:
        print("⚠️  config.yml not found (copy from config.default.yml)")
    
    # Check directories
    for dir_name in ['logs', 'reports']:
        dir_path = Path(dir_name)
        if dir_path.exists():
            print(f"✅ {dir_name}/ directory exists")
        else:
            try:
                dir_path.mkdir(exist_ok=True)
                print(f"✅ {dir_name}/ directory created")
            except Exception as e:
                print(f"❌ Cannot create {dir_name}/ directory: {e}")
                return False
    
    return True

def test_basic_functionality():
    """Test basic functionality"""
    print("\n🧪 Testing basic functionality...")
    
    try:
        from trading_core import validate_environment
        validate_environment()
        print("✅ Environment validation passed")
    except Exception as e:
        print(f"⚠️  Environment validation failed: {e}")
        print("   This is expected if API keys are not configured")
    
    try:
        from trading_core import load_stock_universe
        stocks = load_stock_universe()
        print(f"✅ Stock universe loaded: {len(stocks)} stocks")
    except Exception as e:
        print(f"❌ Stock universe loading failed: {e}")
        return False
    
    return True

def main():
    """Run all tests"""
    print("🚀 TRADING SYSTEM - QUICK TEST")
    print("=" * 50)
    
    all_passed = True
    
    # Test imports
    if not test_imports():
        all_passed = False
    
    # Test environment
    if not test_environment():
        all_passed = False
    
    # Test basic functionality
    if not test_basic_functionality():
        all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print("\nNext steps:")
        print("1. Configure your .env file with API keys")
        print("2. Run: python3 system_diagnose.py")
        print("3. Try: python3 historical_backtest.py --start 2024-10-15 --end 2024-10-18")
    else:
        print("❌ SOME TESTS FAILED")
        print("\nTroubleshooting:")
        print("1. Make sure you're in the correct directory")
        print("2. Check that all Python files are present")
        print("3. Run: python3 system_diagnose.py for detailed analysis")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
