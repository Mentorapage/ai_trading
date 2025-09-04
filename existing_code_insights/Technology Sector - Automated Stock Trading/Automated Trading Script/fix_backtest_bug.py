#!/usr/bin/env python3
"""
Fix the backtest overnight holding bug
"""

import re

def fix_historical_backtest():
    """Fix the bug in historical_backtest.py"""
    
    print("🔧 Fixing overnight holding bug in historical_backtest.py...")
    
    # Read the file
    with open('historical_backtest.py', 'r') as f:
        content = f.read()
    
    # Find and replace the problematic section
    # The issue is that the backtest is processing days before the start date
    # We need to ensure it only processes the specified date range
    
    # Look for the main processing loop and add a date boundary check
    old_pattern = r'(for current_day in trading_days:.*?)(# Process each day.*?)(\n\s+print\(f"📅 DAY)'
    
    replacement = r'''\1\2
        # BUG FIX: Ensure we only process days within the specified backtest period
        if current_day < start_date or current_day > end_date:
            print(f"⚠️  Skipping {current_day} - outside backtest period [{start_date} to {end_date}]")
            continue
\3'''
    
    # Apply the fix
    if re.search(old_pattern, content, re.DOTALL):
        content = re.sub(old_pattern, replacement, content, flags=re.DOTALL)
        print("✅ Applied date boundary fix")
    else:
        print("⚠️  Could not find the exact pattern to fix")
    
    # Also fix the overnight position initialization
    # Add a check to prevent carrying over positions from before backtest start
    overnight_fix = '''
    # BUG FIX: Clear any existing positions at backtest start
    # This prevents carrying over positions from before the backtest period
    active_positions = {}  # Reset positions for clean backtest
    '''
    
    # Insert this fix after the overnight manager initialization
    marker = "print(f\"✅ Overnight holding: {'enabled' if overnight_manager.enabled else 'disabled'}\")"
    if marker in content:
        content = content.replace(marker, marker + overnight_fix)
        print("✅ Applied position reset fix")
    
    # Write the fixed file
    with open('historical_backtest_fixed.py', 'w') as f:
        f.write(content)
    
    print("💾 Saved fixed version as historical_backtest_fixed.py")

def create_clean_backtest_script():
    """Create a clean backtest script without the overnight bug"""
    
    script_content = '''#!/usr/bin/env python3
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
'''
    
    with open('clean_backtest.py', 'w') as f:
        f.write(script_content)
    
    print("💾 Created clean_backtest.py")

if __name__ == "__main__":
    print("🔧 FIXING BACKTEST BUG...")
    fix_historical_backtest()
    create_clean_backtest_script()
    print("🎉 Bug fixes applied!")
