#!/usr/bin/env python3
"""
FIND ACTUAL TRADE LOGS
======================
Search for where individual trade data is stored in the system
"""

import os
from pathlib import Path
import pandas as pd

def search_for_trade_data():
    """Search for any files that might contain individual trade data"""
    
    print("🔍 SEARCHING FOR INDIVIDUAL TRADE LOGS")
    print("=" * 50)
    
    # Check if the backtest system actually logs individual trades
    print("\n1. CHECKING BACKTEST SYSTEM FOR TRADE LOGGING:")
    
    # Check run_fast_multi_strategy.py - the main backtest runner
    if Path("run_fast_multi_strategy.py").exists():
        with open("run_fast_multi_strategy.py", "r") as f:
            content = f.read()
            
        if "trade_log" in content.lower():
            print("   ✅ Found 'trade_log' references")
        else:
            print("   ❌ No 'trade_log' references found")
            
        if "save.*trade" in content.lower():
            print("   ✅ Found trade saving logic")
        else:
            print("   ❌ No trade saving logic found")
            
        if ".csv" in content and "trade" in content.lower():
            print("   ✅ Found CSV trade file references")
        else:
            print("   ❌ No CSV trade file references")
    
    print("\n2. CHECKING FOR HIDDEN TRADE FILES:")
    
    # Search all directories for any files with 'trade' in name
    current_dir = Path(".")
    trade_files = []
    
    for file_path in current_dir.rglob("*"):
        if file_path.is_file() and "trade" in file_path.name.lower():
            trade_files.append(file_path)
    
    if trade_files:
        print(f"   Found {len(trade_files)} files with 'trade' in name:")
        for f in trade_files:
            print(f"     {f}")
    else:
        print("   ❌ No files with 'trade' in name found")
    
    print("\n3. CHECKING LOGS DIRECTORY:")
    logs_dir = Path("logs")
    if logs_dir.exists():
        log_files = list(logs_dir.glob("*"))
        print(f"   Found {len(log_files)} files in logs/:")
        for f in log_files[:10]:  # Show first 10
            print(f"     {f}")
    else:
        print("   ❌ No logs/ directory found")
    
    print("\n4. CHECKING ARTIFACTS DIRECTORY:")
    artifacts_dir = Path("artifacts")
    if artifacts_dir.exists():
        artifact_files = list(artifacts_dir.glob("*"))
        print(f"   Found {len(artifact_files)} files in artifacts/:")
        for f in artifact_files[:10]:  # Show first 10
            print(f"     {f}")
    else:
        print("   ❌ No artifacts/ directory found")
    
    print("\n5. EXAMINING STRATEGY RESULT FILES:")
    
    # Check if any Excel files contain individual trade sheets
    excel_files = list(Path(".").glob("*.xlsx"))
    for excel_file in excel_files[:5]:  # Check first 5 Excel files
        try:
            xl = pd.ExcelFile(excel_file)
            sheet_names = xl.sheet_names
            print(f"   {excel_file}: {sheet_names}")
            
            # Check if any sheet might contain individual trades
            for sheet in sheet_names:
                if any(word in sheet.lower() for word in ['trade', 'individual', 'detail']):
                    print(f"     → Potential trade sheet: {sheet}")
                    
        except Exception as e:
            print(f"   {excel_file}: Error reading - {e}")

def check_backtest_code_for_logging():
    """Check the backtest code to see if it logs individual trades"""
    
    print("\n🔍 ANALYZING BACKTEST CODE FOR TRADE LOGGING")
    print("=" * 55)
    
    files_to_check = [
        "run_fast_multi_strategy.py",
        "run_real_strategy_batch.py", 
        "historical_backtest.py"
    ]
    
    for filename in files_to_check:
        if Path(filename).exists():
            print(f"\n📄 CHECKING {filename}:")
            
            with open(filename, "r") as f:
                lines = f.readlines()
            
            trade_logging_found = False
            
            for i, line in enumerate(lines):
                line_lower = line.lower()
                
                # Look for trade logging patterns
                if any(pattern in line_lower for pattern in [
                    'trade_log', 'save.*trade', 'log.*trade', 
                    'trades.csv', 'trades.parquet', 'individual.*trade'
                ]):
                    print(f"   Line {i+1}: {line.strip()}")
                    trade_logging_found = True
            
            if not trade_logging_found:
                print("   ❌ No individual trade logging found")
        else:
            print(f"\n📄 {filename}: File not found")

def main():
    """Main search function"""
    
    print("🚨 CRITICAL: SEARCHING FOR ACTUAL TRADE LOGS")
    print("=" * 60)
    print("The user needs REAL individual trade data, not aggregated strategy results")
    print()
    
    search_for_trade_data()
    check_backtest_code_for_logging()
    
    print("\n" + "="*60)
    print("CONCLUSION:")
    print("If no individual trade logs are found, the system needs to be")
    print("modified to log each trade execution with ticker details.")
    print("="*60)

if __name__ == "__main__":
    main()
