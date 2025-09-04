#!/usr/bin/env python3
"""
Test runner to execute our quick test
"""

import subprocess
import sys
import os
from pathlib import Path

def run_test():
    """Run the quick test and capture output"""
    try:
        # Change to the correct directory
        script_dir = Path(__file__).parent
        os.chdir(script_dir)
        
        print(f"Running test in: {os.getcwd()}")
        
        # Run the quick test
        result = subprocess.run([sys.executable, 'quick_test.py'], 
                              capture_output=True, 
                              text=True, 
                              timeout=30)
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        print(f"Return code: {result.returncode}")
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("❌ Test timed out after 30 seconds")
        return False
    except Exception as e:
        print(f"❌ Error running test: {e}")
        return False

if __name__ == "__main__":
    success = run_test()
    if success:
        print("\n🎉 Test completed successfully!")
    else:
        print("\n❌ Test failed!")
    sys.exit(0 if success else 1)
