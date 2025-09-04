#!/usr/bin/env python3
"""
WATCHDOG TEST - Test the execution watchdog system
=================================================
Simple test to verify the watchdog can execute and timeout commands properly
"""

import sys
import subprocess
import time
from pathlib import Path

def test_basic_execution():
    """Test basic command execution through watchdog"""
    print("🧪 Testing basic command execution...")
    
    watchdog_path = Path('tools/exec_watchdog.py')
    if not watchdog_path.exists():
        print("❌ Watchdog not found at tools/exec_watchdog.py")
        return False
    
    # Test simple command that should succeed quickly
    cmd = [
        sys.executable, str(watchdog_path),
        '--timeout', '10',
        '--',
        sys.executable, '-c', 'print("Hello from watchdog!"); import time; time.sleep(1); print("Done!")'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0:
            print("✅ Basic execution test passed")
            return True
        else:
            print(f"❌ Basic execution test failed: exit code {result.returncode}")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Basic execution test timed out")
        return False
    except Exception as e:
        print(f"❌ Basic execution test error: {e}")
        return False

def test_timeout_functionality():
    """Test that watchdog properly times out long-running commands"""
    print("\n🧪 Testing timeout functionality...")
    
    watchdog_path = Path('tools/exec_watchdog.py')
    
    # Test command that should timeout
    cmd = [
        sys.executable, str(watchdog_path),
        '--timeout', '3',
        '--',
        sys.executable, '-c', 'import time; print("Starting long task..."); time.sleep(10); print("Should not reach here")'
    ]
    
    try:
        start_time = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        duration = time.time() - start_time
        
        if result.returncode == 124 and duration < 8:  # 124 is timeout exit code
            print("✅ Timeout test passed")
            return True
        else:
            print(f"❌ Timeout test failed: exit code {result.returncode}, duration {duration:.1f}s")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Timeout test itself timed out")
        return False
    except Exception as e:
        print(f"❌ Timeout test error: {e}")
        return False

def test_diagnostics_script():
    """Test that the diagnostics script can run"""
    print("\n🧪 Testing diagnostics script...")
    
    diagnostics_path = Path('system_diagnose_terminal.py')
    if not diagnostics_path.exists():
        print("❌ Diagnostics script not found")
        return False
    
    try:
        # Run diagnostics with a reasonable timeout
        result = subprocess.run([sys.executable, str(diagnostics_path)], 
                              capture_output=True, text=True, timeout=60)
        
        if result.returncode in [0, 1]:  # 0 = success, 1 = issues found but script worked
            print("✅ Diagnostics script test passed")
            return True
        else:
            print(f"❌ Diagnostics script test failed: exit code {result.returncode}")
            print("STDOUT:", result.stdout[-500:])  # Last 500 chars
            print("STDERR:", result.stderr[-500:])
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Diagnostics script timed out")
        return False
    except Exception as e:
        print(f"❌ Diagnostics script error: {e}")
        return False

def main():
    """Run all watchdog tests"""
    print("🚀 WATCHDOG SYSTEM TEST")
    print("=" * 40)
    
    tests_passed = 0
    total_tests = 3
    
    # Test 1: Basic execution
    if test_basic_execution():
        tests_passed += 1
    
    # Test 2: Timeout functionality
    if test_timeout_functionality():
        tests_passed += 1
    
    # Test 3: Diagnostics script
    if test_diagnostics_script():
        tests_passed += 1
    
    print("\n" + "=" * 40)
    print(f"📊 RESULTS: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("🎉 ALL TESTS PASSED!")
        print("\nThe watchdog system is working correctly.")
        print("You can now run:")
        print("  python3 system_diagnose_terminal.py")
        return True
    else:
        print("❌ SOME TESTS FAILED")
        print("\nThe watchdog system needs attention.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
