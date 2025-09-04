#!/usr/bin/env python3
"""
PROGRAM RUNNER - Execute trading system commands with timeout protection
"""

import subprocess
import sys
import os
import time
import signal
from pathlib import Path

def run_with_timeout(command, timeout=60, cwd=None):
    """Run a command with timeout protection"""
    print(f"🚀 RUNNING: {' '.join(command)}")
    print(f"⏱️  Timeout: {timeout}s")
    print("-" * 50)
    
    try:
        # Change to the correct directory
        if cwd:
            os.chdir(cwd)
        
        # Start the process
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # Read output line by line with timeout
        start_time = time.time()
        output_lines = []
        
        while True:
            # Check if process has finished
            if process.poll() is not None:
                break
            
            # Check timeout
            if time.time() - start_time > timeout:
                print(f"\n⏰ TIMEOUT: Killing process after {timeout}s")
                try:
                    process.terminate()
                    time.sleep(2)
                    if process.poll() is None:
                        process.kill()
                except:
                    pass
                return False, "TIMEOUT"
            
            # Try to read a line
            try:
                line = process.stdout.readline()
                if line:
                    line = line.rstrip()
                    print(line, flush=True)
                    output_lines.append(line)
                else:
                    time.sleep(0.1)
            except:
                time.sleep(0.1)
        
        # Get final output
        remaining_output, _ = process.communicate()
        if remaining_output:
            for line in remaining_output.split('\n'):
                if line.strip():
                    print(line, flush=True)
                    output_lines.append(line)
        
        duration = time.time() - start_time
        
        if process.returncode == 0:
            print(f"\n✅ SUCCESS (Exit: {process.returncode}, Duration: {duration:.1f}s)")
            return True, "SUCCESS"
        else:
            print(f"\n❌ FAILED (Exit: {process.returncode}, Duration: {duration:.1f}s)")
            return False, f"EXIT_CODE_{process.returncode}"
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False, f"ERROR: {e}"

def main():
    """Run the trading system programs"""
    
    # Set working directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    print("🚀 TRADING SYSTEM EXECUTION")
    print(f"📁 Working Directory: {os.getcwd()}")
    print("=" * 60)
    
    # Test 1: Quick system test
    print("\n1️⃣  QUICK SYSTEM TEST")
    success, result = run_with_timeout([
        sys.executable, 'quick_test.py'
    ], timeout=30)
    
    if not success:
        print(f"❌ Quick test failed: {result}")
        print("Fix basic issues before proceeding")
        return False
    
    # Test 2: System diagnostics
    print("\n2️⃣  SYSTEM DIAGNOSTICS")
    success, result = run_with_timeout([
        sys.executable, 'system_diagnose.py'
    ], timeout=60)
    
    if not success:
        print(f"⚠️  Diagnostics had issues: {result}")
        print("Continuing anyway...")
    
    # Test 3: Historical backtest (short)
    print("\n3️⃣  HISTORICAL BACKTEST TEST")
    success, result = run_with_timeout([
        sys.executable, 'historical_backtest.py',
        '--start', '2024-10-15',
        '--end', '2024-10-16',  # Just 1 day for quick test
        '--log-level', 'INFO',
        '--no-input'
    ], timeout=120)
    
    if success:
        print("🎉 Backtest test PASSED!")
    else:
        print(f"❌ Backtest test failed: {result}")
    
    # Test 4: Live trading dry run
    print("\n4️⃣  LIVE TRADING DRY RUN TEST")
    success, result = run_with_timeout([
        sys.executable, 'live_trading.py',
        '--mode', 'paper',
        '--dry-run',
        '--log-level', 'INFO',
        '--no-input'
    ], timeout=60)
    
    if success:
        print("🎉 Live trading dry run PASSED!")
    else:
        print(f"❌ Live trading dry run failed: {result}")
    
    print("\n" + "=" * 60)
    print("🏁 EXECUTION COMPLETE")
    print("\nIf any tests failed, check the error messages above.")
    print("For detailed diagnostics, the system_diagnose.py should have created reports.")
    
    return True

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
