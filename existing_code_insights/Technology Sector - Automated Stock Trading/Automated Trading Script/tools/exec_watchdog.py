#!/usr/bin/env python3
"""
EXECUTION WATCHDOG - Command Timeout and Process Management
==========================================================
Executes commands with timeout, live streaming, and automatic recovery
"""

import argparse
import subprocess
import sys
import os
import time
import json
import signal
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re

# Try to import psutil for better process management
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

class ProcessWatchdog:
    def __init__(self, timeout: int = 300, log_file: str = "logs/exec_watchdog.log"):
        self.timeout = timeout
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(exist_ok=True)
        
        # Ensure log rotation
        if self.log_file.exists() and self.log_file.stat().st_size > 10 * 1024 * 1024:  # 10MB
            backup_file = self.log_file.with_suffix('.log.old')
            if backup_file.exists():
                backup_file.unlink()
            self.log_file.rename(backup_file)
    
    def classify_failure(self, stdout: str, stderr: str, exit_code: int) -> str:
        """Classify the type of failure based on output and exit code"""
        combined_output = (stdout + stderr).lower()
        
        if exit_code == 124:
            return "TIMEOUT"
        elif "429" in combined_output or "rate limit" in combined_output or "global rpm cap" in combined_output:
            return "RATE_LIMIT_WAIT"
        elif "apikey" in combined_output and ("missing" in combined_output or "not set" in combined_output):
            return "MISSING_ENV"
        elif "apisecret" in combined_output and ("missing" in combined_output or "not set" in combined_output):
            return "MISSING_ENV"
        elif "finnhub" in combined_output and ("missing" in combined_output or "not set" in combined_output):
            return "MISSING_ENV"
        elif "config" in combined_output and ("error" in combined_output or "invalid" in combined_output):
            return "CONFIG_ERROR"
        elif "connection" in combined_output or "network" in combined_output or "timeout" in combined_output:
            return "NETWORK_ERROR"
        elif exit_code != 0:
            return "RUNTIME_ERROR"
        else:
            return "SUCCESS"
    
    def kill_process_tree(self, process: subprocess.Popen) -> bool:
        """Kill process and all its children (cross-platform)"""
        try:
            if HAS_PSUTIL:
                # Use psutil for better process tree management
                parent = psutil.Process(process.pid)
                children = parent.children(recursive=True)
                
                # Kill children first
                for child in children:
                    try:
                        child.kill()
                    except psutil.NoSuchProcess:
                        pass
                
                # Kill parent
                try:
                    parent.kill()
                except psutil.NoSuchProcess:
                    pass
                
                # Wait for processes to die
                gone, alive = psutil.wait_procs(children + [parent], timeout=3)
                
                return len(alive) == 0
            else:
                # Fallback method using OS signals
                if os.name == 'nt':  # Windows
                    subprocess.call(['taskkill', '/F', '/T', '/PID', str(process.pid)], 
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:  # Unix-like
                    try:
                        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                        time.sleep(2)
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                
                return True
                
        except Exception as e:
            print(f"{Colors.YELLOW}Warning: Error killing process tree: {e}{Colors.END}")
            return False
    
    def stream_output(self, process: subprocess.Popen) -> Tuple[str, str]:
        """Stream stdout and stderr in real-time, return captured output"""
        stdout_lines = []
        stderr_lines = []
        
        def read_stdout():
            for line in iter(process.stdout.readline, b''):
                line_str = line.decode('utf-8', errors='replace').rstrip()
                stdout_lines.append(line_str)
                print(line_str, flush=True)
        
        def read_stderr():
            for line in iter(process.stderr.readline, b''):
                line_str = line.decode('utf-8', errors='replace').rstrip()
                stderr_lines.append(line_str)
                print(f"{Colors.YELLOW}{line_str}{Colors.END}", flush=True)
        
        # Start threads to read stdout and stderr
        stdout_thread = threading.Thread(target=read_stdout)
        stderr_thread = threading.Thread(target=read_stderr)
        
        stdout_thread.daemon = True
        stderr_thread.daemon = True
        
        stdout_thread.start()
        stderr_thread.start()
        
        # Wait for process to complete or timeout
        try:
            process.wait(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            print(f"\n{Colors.RED}{Colors.BOLD}⏰ TIMEOUT: Process exceeded {self.timeout}s limit{Colors.END}")
            self.kill_process_tree(process)
            process.returncode = 124  # Standard timeout exit code
        
        # Wait for threads to finish reading
        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)
        
        return '\n'.join(stdout_lines), '\n'.join(stderr_lines)
    
    def should_retry(self, classification: str, retry_count: int) -> bool:
        """Determine if we should retry based on failure classification"""
        if retry_count >= 1:  # Max 1 retry
            return False
        
        return classification == "RATE_LIMIT_WAIT"
    
    def log_execution(self, command: List[str], start_time: datetime, end_time: datetime, 
                     exit_code: int, stdout_bytes: int, stderr_bytes: int, 
                     classification: str, retry_count: int = 0):
        """Log execution details to JSON log file"""
        log_entry = {
            "timestamp": start_time.isoformat(),
            "command": " ".join(command),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": (end_time - start_time).total_seconds(),
            "exit_code": exit_code,
            "stdout_bytes": stdout_bytes,
            "stderr_bytes": stderr_bytes,
            "classification": classification,
            "retry_count": retry_count
        }
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            print(f"{Colors.YELLOW}Warning: Could not write to log file: {e}{Colors.END}")
    
    def execute(self, command: List[str], max_retries: int = 1) -> Tuple[int, str]:
        """Execute command with watchdog protection"""
        retry_count = 0
        
        while retry_count <= max_retries:
            start_time = datetime.now()
            
            print(f"{Colors.BLUE}{Colors.BOLD}🚀 EXECUTING:{Colors.END} {' '.join(command)}")
            if retry_count > 0:
                print(f"{Colors.YELLOW}   (Retry {retry_count}/{max_retries}){Colors.END}")
            print(f"{Colors.BLUE}⏱️  Timeout: {self.timeout}s{Colors.END}")
            print("-" * 60)
            
            try:
                # Start process with proper settings for cross-platform compatibility
                if os.name == 'nt':  # Windows
                    process = subprocess.Popen(
                        command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=False,
                        bufsize=1,
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                    )
                else:  # Unix-like
                    process = subprocess.Popen(
                        command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=False,
                        bufsize=1,
                        preexec_fn=os.setsid
                    )
                
                # Stream output and wait for completion
                stdout, stderr = self.stream_output(process)
                end_time = datetime.now()
                
                # Classify the result
                classification = self.classify_failure(stdout, stderr, process.returncode)
                
                # Log the execution
                self.log_execution(
                    command, start_time, end_time, process.returncode,
                    len(stdout.encode()), len(stderr.encode()), 
                    classification, retry_count
                )
                
                # Print result
                duration = (end_time - start_time).total_seconds()
                if process.returncode == 0:
                    print(f"\n{Colors.GREEN}{Colors.BOLD}✅ SUCCESS{Colors.END} (Exit: {process.returncode}, Duration: {duration:.1f}s)")
                else:
                    print(f"\n{Colors.RED}{Colors.BOLD}❌ FAILED{Colors.END} (Exit: {process.returncode}, Duration: {duration:.1f}s)")
                    print(f"{Colors.RED}Classification: {classification}{Colors.END}")
                
                # Check if we should retry
                if process.returncode != 0 and self.should_retry(classification, retry_count):
                    retry_count += 1
                    sleep_time = min(60, 10 * retry_count)  # Progressive backoff, max 60s
                    print(f"{Colors.YELLOW}⏳ Retrying in {sleep_time}s due to {classification}...{Colors.END}")
                    time.sleep(sleep_time)
                    continue
                
                return process.returncode, classification
                
            except Exception as e:
                end_time = datetime.now()
                print(f"\n{Colors.RED}{Colors.BOLD}❌ EXECUTION ERROR: {e}{Colors.END}")
                
                # Log the error
                self.log_execution(
                    command, start_time, end_time, -1,
                    0, len(str(e).encode()), "EXECUTION_ERROR", retry_count
                )
                
                return -1, "EXECUTION_ERROR"
        
        return process.returncode, classification

def main():
    """Main watchdog function"""
    parser = argparse.ArgumentParser(
        description='Execute commands with timeout and process management',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 tools/exec_watchdog.py --timeout 300 -- python3 historical_backtest.py --start 2024-10-15 --end 2024-10-18
  python3 tools/exec_watchdog.py --timeout 180 -- python3 live_trading.py --mode paper --dry-run
        """
    )
    
    parser.add_argument('--timeout', type=int, default=300,
                       help='Timeout in seconds (default: 300)')
    parser.add_argument('--log-file', default='logs/exec_watchdog.log',
                       help='Log file path (default: logs/exec_watchdog.log)')
    parser.add_argument('--max-retries', type=int, default=1,
                       help='Maximum number of retries (default: 1)')
    parser.add_argument('command', nargs=argparse.REMAINDER,
                       help='Command to execute (after --)')
    
    args = parser.parse_args()
    
    # Remove '--' if present
    if args.command and args.command[0] == '--':
        args.command = args.command[1:]
    
    if not args.command:
        print(f"{Colors.RED}❌ ERROR: No command specified{Colors.END}")
        print("Usage: python3 tools/exec_watchdog.py --timeout 300 -- <command>")
        sys.exit(1)
    
    # Create watchdog and execute
    watchdog = ProcessWatchdog(timeout=args.timeout, log_file=args.log_file)
    exit_code, classification = watchdog.execute(args.command, args.max_retries)
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
