#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Set up the environment
current_dir = Path("/Users/bocharovmaxim/Desktop/ai trading/ai_trading/existing_code_insights/Technology Sector - Automated Stock Trading/Automated Trading Script")
os.chdir(current_dir)
sys.path.insert(0, str(current_dir))

print("🚀 TESTING TRADING SYSTEM")
print(f"📁 Directory: {os.getcwd()}")

# Check files exist
files = ['trading_core.py', 'historical_backtest.py', 'live_trading.py']
for f in files:
    exists = Path(f).exists()
    print(f"{'✅' if exists else '❌'} {f}: {'Found' if exists else 'Missing'}")

# Test imports
print("\n📦 Testing imports...")
try:
    import pandas as pd
    print("✅ pandas imported")
except Exception as e:
    print(f"❌ pandas: {e}")

try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ dotenv imported and loaded")
except Exception as e:
    print(f"❌ dotenv: {e}")

try:
    import trading_core
    print("✅ trading_core imported")
except Exception as e:
    print(f"❌ trading_core: {e}")

# Test environment
print("\n🔑 Testing environment...")
api_key = os.getenv('apikey', '')
finnhub_key = os.getenv('FINNHUB_KEYS', '') or os.getenv('finnhubkey', '')

print(f"{'✅' if api_key else '⚠️ '} Alpaca API: {'Found' if api_key else 'Missing'}")
print(f"{'✅' if finnhub_key else '⚠️ '} Finnhub API: {'Found' if finnhub_key else 'Missing'}")

# Test basic functionality
print("\n🧪 Testing basic functions...")
try:
    stocks = trading_core.load_stock_universe()
    print(f"✅ Stock universe: {len(stocks)} stocks loaded")
except Exception as e:
    print(f"❌ Stock universe: {e}")

try:
    trading_core.validate_environment()
    print("✅ Environment validation passed")
except Exception as e:
    print(f"⚠️  Environment validation: {e}")

print("\n🏁 Test complete!")
print("If you see ✅ for most items, the system should work.")
print("If you see ❌ errors, those need to be fixed first.")

# Show what commands to run
print("\n📋 NEXT STEPS:")
print("1. Fix any ❌ errors shown above")
print("2. Run: python3 system_diagnose.py")
print("3. Run: python3 historical_backtest.py --start 2024-10-15 --end 2024-10-16 --log-level INFO")
print("4. Run: python3 live_trading.py --mode paper --dry-run --log-level INFO")
