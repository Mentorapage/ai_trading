#!/usr/bin/env python3
"""
DIRECT EXECUTION - Run the trading system directly
"""

import os
import sys
from pathlib import Path

# Change to the correct directory
script_dir = Path(__file__).parent
os.chdir(script_dir)

print("🚀 DIRECT EXECUTION OF TRADING SYSTEM")
print(f"📁 Directory: {os.getcwd()}")
print("=" * 50)

# Test 1: Check if we're in the right place
print("\n1️⃣  CHECKING ENVIRONMENT...")
required_files = ['trading_core.py', 'historical_backtest.py', 'live_trading.py']
missing = []

for file in required_files:
    if Path(file).exists():
        print(f"✅ Found {file}")
    else:
        print(f"❌ Missing {file}")
        missing.append(file)

if missing:
    print(f"\n❌ ERROR: Missing files: {missing}")
    print("Make sure you're in the correct directory!")
    sys.exit(1)

# Test 2: Try importing our modules
print("\n2️⃣  TESTING IMPORTS...")
try:
    import trading_core
    print("✅ trading_core imported successfully")
except Exception as e:
    print(f"❌ trading_core import failed: {e}")

try:
    import historical_backtest
    print("✅ historical_backtest imported successfully")
except Exception as e:
    print(f"❌ historical_backtest import failed: {e}")

try:
    import live_trading
    print("✅ live_trading imported successfully")
except Exception as e:
    print(f"❌ live_trading import failed: {e}")

# Test 3: Check environment
print("\n3️⃣  CHECKING ENVIRONMENT VARIABLES...")
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv('apikey')
finnhub_key = os.getenv('FINNHUB_KEYS') or os.getenv('finnhubkey')

if api_key:
    print(f"✅ Alpaca API key found: {api_key[:8]}...")
else:
    print("⚠️  Alpaca API key not found")

if finnhub_key:
    print(f"✅ Finnhub API key found")
else:
    print("⚠️  Finnhub API key not found")

# Test 4: Try a simple function call
print("\n4️⃣  TESTING CORE FUNCTIONS...")
try:
    stocks = trading_core.load_stock_universe()
    print(f"✅ Stock universe loaded: {len(stocks)} stocks")
except Exception as e:
    print(f"❌ Stock universe loading failed: {e}")

try:
    trading_core.validate_environment()
    print("✅ Environment validation passed")
except Exception as e:
    print(f"⚠️  Environment validation failed: {e}")
    print("   This is expected if API keys are not configured")

# Test 5: Try running a simple backtest function
print("\n5️⃣  TESTING BACKTEST FUNCTION...")
try:
    # Try to call the main function with test parameters
    from historical_backtest import main as backtest_main
    
    # Mock sys.argv for testing
    original_argv = sys.argv
    sys.argv = [
        'historical_backtest.py',
        '--start', '2024-10-15',
        '--end', '2024-10-15',  # Single day
        '--log-level', 'INFO',
        '--no-input'
    ]
    
    print("🧪 Attempting to run backtest main function...")
    backtest_main()
    print("✅ Backtest function completed!")
    
except SystemExit as e:
    if e.code == 0:
        print("✅ Backtest completed successfully (exit 0)")
    else:
        print(f"⚠️  Backtest exited with code: {e.code}")
except Exception as e:
    print(f"❌ Backtest function failed: {e}")
    import traceback
    traceback.print_exc()
finally:
    sys.argv = original_argv

print("\n" + "=" * 50)
print("🏁 DIRECT EXECUTION COMPLETE")
print("\nIf you see mostly ✅ marks above, the system is working!")
print("If you see ❌ errors, those need to be fixed first.")
