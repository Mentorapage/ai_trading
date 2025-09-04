#!/usr/bin/env python3
"""
QUICK SYSTEM TEST - Minimal test to verify basic functionality
"""

import sys
import os
from pathlib import Path

def main():
    print("🔍 QUICK SYSTEM TEST")
    print("=" * 30)
    
    # Test 1: Basic Python functionality
    print("✅ Python is working")
    print(f"   Python version: {sys.version}")
    print(f"   Working directory: {os.getcwd()}")
    
    # Test 2: Check if we're in the right directory
    current_dir = Path.cwd()
    expected_files = ['trading_core.py', 'historical_backtest.py', 'live_trading.py']
    missing_files = []
    
    for file in expected_files:
        if (current_dir / file).exists():
            print(f"✅ Found {file}")
        else:
            print(f"❌ Missing {file}")
            missing_files.append(file)
    
    if missing_files:
        print(f"\n❌ ERROR: Missing files: {missing_files}")
        print("Make sure you're in the correct directory:")
        print("cd 'existing_code_insights/Technology Sector - Automated Stock Trading/Automated Trading Script'")
        return False
    
    # Test 3: Try importing core modules
    print("\n🔍 Testing imports...")
    
    try:
        import pandas as pd
        print("✅ pandas imported")
    except ImportError as e:
        print(f"❌ pandas import failed: {e}")
        print("Install with: pip install pandas")
        return False
    
    try:
        import numpy as np
        print("✅ numpy imported")
    except ImportError as e:
        print(f"❌ numpy import failed: {e}")
        print("Install with: pip install numpy")
        return False
    
    try:
        from dotenv import load_dotenv
        print("✅ python-dotenv imported")
    except ImportError as e:
        print(f"❌ python-dotenv import failed: {e}")
        print("Install with: pip install python-dotenv")
        return False
    
    # Test 4: Try importing our modules
    print("\n🔍 Testing our modules...")
    
    try:
        import trading_core
        print("✅ trading_core imported")
    except Exception as e:
        print(f"❌ trading_core import failed: {e}")
        return False
    
    try:
        import historical_backtest
        print("✅ historical_backtest imported")
    except Exception as e:
        print(f"❌ historical_backtest import failed: {e}")
        return False
    
    try:
        import live_trading
        print("✅ live_trading imported")
    except Exception as e:
        print(f"❌ live_trading import failed: {e}")
        return False
    
    # Test 5: Check environment setup
    print("\n🔍 Testing environment...")
    
    env_file = Path('.env')
    if env_file.exists():
        print("✅ .env file exists")
        
        # Load and check basic env vars
        load_dotenv()
        api_key = os.getenv('apikey')
        finnhub_key = os.getenv('FINNHUB_KEYS') or os.getenv('finnhubkey')
        
        if api_key:
            print("✅ Alpaca API key found")
        else:
            print("⚠️  Alpaca API key not found in .env")
        
        if finnhub_key:
            print("✅ Finnhub API key found")
        else:
            print("⚠️  Finnhub API key not found in .env")
    else:
        print("⚠️  .env file not found")
        print("   Copy env_example.txt to .env and add your API keys")
    
    print("\n" + "=" * 30)
    print("🎉 BASIC TEST COMPLETED!")
    print("\nNext steps:")
    print("1. If any ❌ errors above, fix them first")
    print("2. Run: python3 system_diagnose.py")
    print("3. Run: python3 historical_backtest.py --help")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
