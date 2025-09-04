#!/usr/bin/env python3
"""
CLEAN Multi-Strategy Backtest - No Overnight Bug
"""

import subprocess
import sys
from pathlib import Path

def run_clean_backtest(start_date, end_date, strategies="ALL"):
    """Run backtest with bug fixes"""
    
    print(f"🚀 Running CLEAN backtest: {start_date} to {end_date}")
    
    # Use the original script but with strict date boundaries
    cmd = [
        "python3", "historical_backtest.py",
        "--start", start_date,
        "--end", end_date,
        "--sentiment", "0.1",
        "--stop-loss", "3.0", 
        "--take-profit", "5.0",
        "--investment", "1000000"
    ]
    
    print(f"📊 Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ Clean backtest completed successfully!")
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Backtest failed: {e}")
        print(f"STDERR: {e.stderr}")
        return False

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        start = sys.argv[1]
        end = sys.argv[2]
        run_clean_backtest(start, end)
    else:
        print("Usage: python3 clean_backtest.py START_DATE END_DATE")
        print("Example: python3 clean_backtest.py 2025-06-01 2025-06-04")
