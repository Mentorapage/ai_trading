#!/usr/bin/env python3
"""
TERMINAL DIAGNOSTICS - Comprehensive Command Execution Analysis
==============================================================
Diagnoses why commands hang, fail, or execute slowly with actionable fixes
"""

import os
import sys
import json
import subprocess
import time
import socket
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any
import re

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

class TerminalDiagnostics:
    def __init__(self):
        self.results = {}
        self.issues = []
        self.fixes = []
        self.working_dir = Path.cwd()
        
        # Ensure diagnostics directory exists
        self.diagnostics_dir = self.working_dir / 'diagnostics'
        self.diagnostics_dir.mkdir(exist_ok=True)
        
        # Ensure logs directory exists
        self.logs_dir = self.working_dir / 'logs'
        self.logs_dir.mkdir(exist_ok=True)
    
    def print_check(self, name: str, status: bool, details: str = ""):
        """Print a check result with color coding"""
        symbol = f"{Colors.GREEN}✔{Colors.END}" if status else f"{Colors.RED}✖{Colors.END}"
        print(f"{symbol} {name}")
        if details:
            print(f"  {details}")
        return status
    
    def print_section(self, title: str):
        """Print a section header"""
        print(f"\n{Colors.BOLD}{Colors.BLUE}=== {title} ==={Colors.END}")
    
    def check_environment_and_paths(self) -> bool:
        """A. Environment & Paths"""
        self.print_section("Environment & Paths")
        all_good = True
        
        # Python version
        try:
            result = subprocess.run([sys.executable, '-V'], capture_output=True, text=True, timeout=5)
            python_version = result.stdout.strip()
            self.print_check("Python Version", True, python_version)
            self.results['python_version'] = python_version
        except Exception as e:
            all_good = False
            self.print_check("Python Version", False, f"Error: {e}")
            self.issues.append("Cannot determine Python version")
        
        # Pip version
        try:
            result = subprocess.run([sys.executable, '-m', 'pip', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            pip_version = result.stdout.strip()
            self.print_check("Pip Version", True, pip_version)
            self.results['pip_version'] = pip_version
        except Exception as e:
            self.print_check("Pip Version", False, f"Error: {e}")
        
        # Working directory
        expected_files = ['trading_core.py', 'historical_backtest.py', 'live_trading.py']
        missing_files = []
        for file in expected_files:
            if not (self.working_dir / file).exists():
                missing_files.append(file)
        
        if missing_files:
            all_good = False
            self.print_check("Working Directory", False, f"Missing: {missing_files}")
            self.issues.append(f"Wrong directory - missing files: {missing_files}")
            self.fixes.append("Navigate to the correct directory with trading scripts")
        else:
            self.print_check("Working Directory", True, str(self.working_dir))
        
        # Directory permissions
        for dir_name in ['logs', 'diagnostics']:
            dir_path = self.working_dir / dir_name
            try:
                dir_path.mkdir(exist_ok=True)
                test_file = dir_path / 'test_write.tmp'
                test_file.write_text('test')
                test_file.unlink()
                self.print_check(f"{dir_name}/ Directory", True, "Writable")
            except Exception as e:
                all_good = False
                self.print_check(f"{dir_name}/ Directory", False, f"Not writable: {e}")
                self.issues.append(f"Cannot write to {dir_name}/ directory")
                self.fixes.append(f"Fix permissions for {dir_name}/ directory")
        
        return all_good
    
    def check_config_env_load(self) -> bool:
        """B. Config/Env Load"""
        self.print_section("Config/Env Load")
        all_good = True
        
        # Check .env file
        env_file = self.working_dir / '.env'
        if env_file.exists():
            self.print_check(".env File", True, str(env_file))
            
            # Load and check environment variables
            try:
                from dotenv import load_dotenv
                load_dotenv(dotenv_path=env_file)
                self.print_check("Load .env", True, "Successfully loaded")
                
                # Check critical variables
                env_vars = {
                    'FINNHUB_KEYS': 'Finnhub API Keys (preferred)',
                    'finnhubkey': 'Finnhub API Key (legacy)',
                    'apikey': 'Alpaca API Key',
                    'apisecret': 'Alpaca Secret Key'
                }
                
                env_status = {}
                for var, description in env_vars.items():
                    value = os.getenv(var, '').strip()
                    has_value = bool(value)
                    
                    if var in ['FINNHUB_KEYS', 'finnhubkey'] and has_value:
                        if var == 'FINNHUB_KEYS':
                            keys_count = len([k.strip() for k in value.split(',') if k.strip()])
                            masked_value = f"{keys_count} keys"
                        else:
                            masked_value = f"{value[:8]}..." if len(value) > 8 else "Set"
                    elif has_value:
                        masked_value = f"{value[:8]}..." if len(value) > 8 else "Set"
                    else:
                        masked_value = "Not set"
                    
                    self.print_check(f"ENV: {var}", has_value, f"{description}: {masked_value}")
                    env_status[var] = has_value
                
                self.results['environment_variables'] = env_status
                
                # Check for required credentials
                has_finnhub = env_status.get('FINNHUB_KEYS') or env_status.get('finnhubkey')
                has_alpaca = env_status.get('apikey') and env_status.get('apisecret')
                
                if not has_finnhub:
                    all_good = False
                    self.issues.append("No Finnhub API keys found")
                    self.fixes.append("Add FINNHUB_KEYS to .env file (get from https://finnhub.io)")
                
                if not has_alpaca:
                    all_good = False
                    self.issues.append("Missing Alpaca API credentials")
                    self.fixes.append("Add apikey and apisecret to .env file (get from Alpaca)")
                
            except ImportError:
                all_good = False
                self.print_check("Load .env", False, "python-dotenv not installed")
                self.issues.append("python-dotenv package missing")
                self.fixes.append("Install with: pip install python-dotenv")
            except Exception as e:
                all_good = False
                self.print_check("Load .env", False, f"Error: {e}")
                self.issues.append(f".env loading failed: {e}")
        else:
            all_good = False
            self.print_check(".env File", False, "File not found")
            self.issues.append(".env file missing")
            self.fixes.append("Copy env_example.txt to .env and configure API keys")
        
        # Check config.yml
        config_file = self.working_dir / 'config.yml'
        if config_file.exists():
            self.print_check("config.yml", True, str(config_file))
            try:
                import yaml
                with open(config_file, 'r') as f:
                    config_data = yaml.safe_load(f)
                self.print_check("Parse config.yml", True, f"Loaded {len(config_data)} sections")
            except ImportError:
                self.print_check("Parse config.yml", False, "PyYAML not installed")
                self.fixes.append("Install with: pip install PyYAML")
            except Exception as e:
                self.print_check("Parse config.yml", False, f"Error: {e}")
                self.issues.append(f"config.yml parsing failed: {e}")
        else:
            self.print_check("config.yml", False, "File not found")
            self.fixes.append("Copy config.default.yml to config.yml")
        
        return all_good
    
    def check_external_probes(self) -> bool:
        """C. External Probes (fast, safe)"""
        self.print_section("External Services")
        all_good = True
        
        # DNS/Network latency check
        hosts_to_check = [
            ('finnhub.io', 443),
            ('paper-api.alpaca.markets', 443),
            ('api.alpaca.markets', 443)
        ]
        
        for host, port in hosts_to_check:
            try:
                start_time = time.time()
                sock = socket.create_connection((host, port), timeout=3)
                sock.close()
                latency = (time.time() - start_time) * 1000
                self.print_check(f"Network: {host}", True, f"Latency: {latency:.0f}ms")
            except Exception as e:
                all_good = False
                self.print_check(f"Network: {host}", False, f"Error: {e}")
                self.issues.append(f"Cannot reach {host}")
                self.fixes.append("Check internet connection and firewall settings")
        
        # Finnhub API test
        finnhub_key = os.getenv('FINNHUB_KEYS', '').split(',')[0].strip() or os.getenv('finnhubkey', '').strip()
        if finnhub_key:
            try:
                import requests
                start_time = time.time()
                response = requests.get(
                    'https://finnhub.io/api/v1/news',
                    params={'category': 'general', 'token': finnhub_key},
                    timeout=3
                )
                latency = (time.time() - start_time) * 1000
                
                if response.status_code == 200:
                    self.print_check("Finnhub API", True, f"Status: 200, Latency: {latency:.0f}ms")
                else:
                    all_good = False
                    self.print_check("Finnhub API", False, f"Status: {response.status_code}")
                    if response.status_code == 401:
                        self.issues.append("Finnhub API key invalid")
                        self.fixes.append("Check your Finnhub API key in .env file")
                    elif response.status_code == 429:
                        self.issues.append("Finnhub API rate limit exceeded")
                        self.fixes.append("Wait or add more API keys to FINNHUB_KEYS")
                        
            except ImportError:
                self.print_check("Finnhub API", False, "requests package not installed")
                self.fixes.append("Install with: pip install requests")
            except Exception as e:
                all_good = False
                self.print_check("Finnhub API", False, f"Error: {e}")
                self.issues.append(f"Finnhub API connection failed: {e}")
        else:
            self.print_check("Finnhub API", False, "No API key to test")
        
        # Alpaca API test
        api_key = os.getenv('apikey')
        secret_key = os.getenv('apisecret')
        if api_key and secret_key:
            try:
                from alpaca.trading.client import TradingClient
                start_time = time.time()
                client = TradingClient(api_key, secret_key, paper=True)
                account = client.get_account()
                latency = (time.time() - start_time) * 1000
                self.print_check("Alpaca API", True, f"Account: {account.account_number}, Latency: {latency:.0f}ms")
            except ImportError:
                self.print_check("Alpaca API", False, "alpaca-py package not installed")
                self.fixes.append("Install with: pip install alpaca-py")
            except Exception as e:
                all_good = False
                self.print_check("Alpaca API", False, f"Error: {e}")
                self.issues.append(f"Alpaca API connection failed: {e}")
                if "unauthorized" in str(e).lower():
                    self.fixes.append("Check your Alpaca API keys in .env file")
        else:
            self.print_check("Alpaca API", False, "No credentials to test")
        
        return all_good
    
    def check_rate_limit_traps(self) -> bool:
        """D. Rate-Limit / Sleep Traps"""
        self.print_section("Rate Limiting")
        all_good = True
        
        # Check if we're near minute boundary and might sleep
        current_second = datetime.now().second
        if current_second > 55:
            self.print_check("Rate Limit Timing", False, 
                           f"Near minute end (:{current_second:02d}s) - short sleep expected")
            print(f"  {Colors.YELLOW}Note: Commands may pause briefly for rate limit reset{Colors.END}")
        else:
            self.print_check("Rate Limit Timing", True, f"Safe time (:{current_second:02d}s)")
        
        # Check for rate limiting configuration
        try:
            from finnhub_pool import FINNHUB_GLOBAL_RPM
            self.print_check("Rate Limit Config", True, f"Global RPM: {FINNHUB_GLOBAL_RPM}")
        except ImportError:
            self.print_check("Rate Limit Config", False, "finnhub_pool not available")
        except Exception as e:
            self.print_check("Rate Limit Config", False, f"Error: {e}")
        
        return all_good
    
    def check_non_interactive_safety(self) -> bool:
        """E. Non-interactive Safety"""
        self.print_section("Interactive Prompts")
        all_good = True
        
        # Search for input() calls in key files
        files_to_check = ['historical_backtest.py', 'live_trading.py', 'trading_core.py']
        input_found = []
        
        for filename in files_to_check:
            filepath = self.working_dir / filename
            if filepath.exists():
                try:
                    content = filepath.read_text()
                    lines = content.split('\n')
                    for i, line in enumerate(lines, 1):
                        if 'input(' in line and not line.strip().startswith('#'):
                            input_found.append(f"{filename}:{i}")
                except Exception as e:
                    print(f"  Warning: Could not check {filename}: {e}")
        
        if input_found:
            all_good = False
            self.print_check("Interactive Prompts", False, f"Found input() calls: {input_found}")
            self.issues.append("Interactive prompts found in code")
            self.fixes.append("Add --no-input flags to disable prompts")
        else:
            self.print_check("Interactive Prompts", True, "No blocking input() calls found")
        
        return all_good
    
    def check_pandas_time_handling(self) -> bool:
        """F. Pandas Time Handling"""
        self.print_section("Pandas Operations")
        all_good = True
        
        try:
            import pandas as pd
            import numpy as np
            
            # Create test DataFrame with datetime index
            dates = pd.date_range('2024-01-01', periods=3, freq='D', tz='UTC')
            test_df = pd.DataFrame({
                'price': [100, 101, 99],
                'volume': [1000, 1100, 900]
            }, index=dates)
            
            self.print_check("DataFrame Creation", True, f"Created {len(test_df)} rows")
            
            # Test datetime operations
            first_date = test_df.index[0].date()
            self.print_check("DateTime Index Access", True, f"First date: {first_date}")
            
            # Test normalize operation
            normalized = test_df.index.normalize()
            self.print_check("DateTime Normalize", True, f"Normalized {len(normalized)} timestamps")
            
            # Test timezone conversion
            ny_times = test_df.index.tz_convert('America/New_York')
            self.print_check("Timezone Convert", True, f"Converted to NY timezone")
            
        except ImportError as e:
            all_good = False
            self.print_check("Pandas Import", False, f"Error: {e}")
            self.issues.append("Pandas not available")
            self.fixes.append("Install with: pip install pandas")
        except Exception as e:
            all_good = False
            self.print_check("Pandas Operations", False, f"Error: {e}")
            self.issues.append(f"Pandas datetime operations failed: {e}")
            self.fixes.append("Check pandas installation and datetime handling")
        
        return all_good
    
    def run_smoke_tests(self) -> bool:
        """Run smoke tests using watchdog"""
        self.print_section("Smoke Tests")
        all_good = True
        
        # Ensure watchdog exists
        watchdog_path = self.working_dir / 'tools' / 'exec_watchdog.py'
        if not watchdog_path.exists():
            self.print_check("Watchdog Available", False, "exec_watchdog.py not found")
            self.issues.append("Execution watchdog not available")
            self.fixes.append("Ensure tools/exec_watchdog.py exists")
            return False
        
        self.print_check("Watchdog Available", True, str(watchdog_path))
        
        # Test 1: Backtest smoke test
        print(f"\n{Colors.BLUE}Running backtest smoke test...{Colors.END}")
        backtest_cmd = [
            sys.executable, str(watchdog_path),
            '--timeout', '300',
            '--',
            sys.executable, 'historical_backtest.py',
            '--start', '2024-10-15',
            '--end', '2024-10-18',
            '--log-level', 'INFO',
            '--no-input'
        ]
        
        try:
            result = subprocess.run(backtest_cmd, capture_output=True, text=True, timeout=320)
            if result.returncode == 0:
                self.print_check("Backtest Smoke", True, "Completed successfully")
            else:
                all_good = False
                self.print_check("Backtest Smoke", False, f"Exit code: {result.returncode}")
                self.issues.append("Backtest smoke test failed")
                
                # Try to classify the failure
                if "TIMEOUT" in result.stderr:
                    self.fixes.append("Backtest is taking too long - check for infinite loops or slow API calls")
                elif "MISSING_ENV" in result.stderr:
                    self.fixes.append("Configure API keys in .env file")
                elif "CONFIG_ERROR" in result.stderr:
                    self.fixes.append("Fix configuration file issues")
                else:
                    self.fixes.append("Check logs/exec_watchdog.log for detailed error information")
                    
        except subprocess.TimeoutExpired:
            all_good = False
            self.print_check("Backtest Smoke", False, "Watchdog itself timed out")
            self.issues.append("Watchdog execution failed")
        except Exception as e:
            all_good = False
            self.print_check("Backtest Smoke", False, f"Error: {e}")
            self.issues.append(f"Backtest smoke test error: {e}")
        
        # Test 2: Live trading dry-run smoke test
        print(f"\n{Colors.BLUE}Running live trading dry-run smoke test...{Colors.END}")
        live_cmd = [
            sys.executable, str(watchdog_path),
            '--timeout', '180',
            '--',
            sys.executable, 'live_trading.py',
            '--mode', 'paper',
            '--dry-run',
            '--log-level', 'INFO',
            '--no-input'
        ]
        
        try:
            result = subprocess.run(live_cmd, capture_output=True, text=True, timeout=200)
            if result.returncode == 0:
                self.print_check("Live Trading Smoke", True, "Completed successfully")
            else:
                all_good = False
                self.print_check("Live Trading Smoke", False, f"Exit code: {result.returncode}")
                self.issues.append("Live trading smoke test failed")
                
                # Try to classify the failure
                if "TIMEOUT" in result.stderr:
                    self.fixes.append("Live trading is hanging - check for blocking operations")
                elif "MISSING_ENV" in result.stderr:
                    self.fixes.append("Configure API keys in .env file")
                else:
                    self.fixes.append("Check logs/exec_watchdog.log for detailed error information")
                    
        except subprocess.TimeoutExpired:
            all_good = False
            self.print_check("Live Trading Smoke", False, "Watchdog itself timed out")
            self.issues.append("Live trading watchdog execution failed")
        except Exception as e:
            all_good = False
            self.print_check("Live Trading Smoke", False, f"Error: {e}")
            self.issues.append(f"Live trading smoke test error: {e}")
        
        return all_good
    
    def generate_reports(self):
        """Generate diagnostic reports"""
        # Generate summary
        total_issues = len(self.issues)
        total_fixes = len(self.fixes)
        
        self.results.update({
            'timestamp': datetime.now().isoformat(),
            'working_directory': str(self.working_dir),
            'total_issues': total_issues,
            'total_fixes': total_fixes,
            'issues': self.issues,
            'fixes': self.fixes,
            'status': 'PASS' if total_issues == 0 else 'FAIL'
        })
        
        # Write JSON report
        json_file = self.diagnostics_dir / 'terminal_health.json'
        try:
            with open(json_file, 'w') as f:
                json.dump(self.results, f, indent=2, default=str)
            print(f"\n📄 JSON report: {json_file}")
        except Exception as e:
            print(f"{Colors.RED}Error writing JSON report: {e}{Colors.END}")
        
        # Write Markdown report
        md_file = self.diagnostics_dir / 'terminal_report.md'
        try:
            with open(md_file, 'w') as f:
                f.write("# Terminal Diagnostics Report\n\n")
                f.write(f"**Generated:** {datetime.now().isoformat()}\n")
                f.write(f"**Working Directory:** {self.working_dir}\n")
                f.write(f"**Status:** {self.results['status']}\n")
                f.write(f"**Issues Found:** {total_issues}\n\n")
                
                if self.issues:
                    f.write("## Issues Found\n\n")
                    for i, issue in enumerate(self.issues, 1):
                        f.write(f"{i}. {issue}\n")
                    f.write("\n")
                
                if self.fixes:
                    f.write("## Recommended Fixes\n\n")
                    for i, fix in enumerate(self.fixes, 1):
                        f.write(f"{i}. {fix}\n")
                    f.write("\n")
                
                f.write("## Environment Details\n\n")
                f.write(f"- Python: {self.results.get('python_version', 'Unknown')}\n")
                f.write(f"- Pip: {self.results.get('pip_version', 'Unknown')}\n")
                f.write(f"- Working Directory: {self.working_dir}\n\n")
                
                if 'environment_variables' in self.results:
                    f.write("## Environment Variables\n\n")
                    for var, status in self.results['environment_variables'].items():
                        status_text = "✅ Set" if status else "❌ Missing"
                        f.write(f"- {var}: {status_text}\n")
                    f.write("\n")
            
            print(f"📄 Markdown report: {md_file}")
            
        except Exception as e:
            print(f"{Colors.RED}Error writing Markdown report: {e}{Colors.END}")
    
    def run_all_diagnostics(self) -> bool:
        """Run all diagnostic checks"""
        print(f"{Colors.BOLD}{Colors.BLUE}🔍 TERMINAL DIAGNOSTICS{Colors.END}")
        print(f"Working Directory: {self.working_dir}")
        print(f"Timestamp: {datetime.now().isoformat()}")
        
        all_passed = True
        
        # Run all checks
        all_passed &= self.check_environment_and_paths()
        all_passed &= self.check_config_env_load()
        all_passed &= self.check_external_probes()
        all_passed &= self.check_rate_limit_traps()
        all_passed &= self.check_non_interactive_safety()
        all_passed &= self.check_pandas_time_handling()
        all_passed &= self.run_smoke_tests()
        
        # Generate summary
        self.print_section("Summary")
        
        if all_passed and not self.issues:
            print(f"{Colors.GREEN}{Colors.BOLD}🎉 ALL DIAGNOSTICS PASSED!{Colors.END}")
            print("The terminal execution system should work reliably.")
        else:
            print(f"{Colors.RED}{Colors.BOLD}❌ {len(self.issues)} ISSUES FOUND{Colors.END}")
            
            if self.fixes:
                print(f"\n{Colors.YELLOW}{Colors.BOLD}🔧 TOP FIXES:{Colors.END}")
                for i, fix in enumerate(self.fixes[:3], 1):
                    print(f"{Colors.YELLOW}{i}.{Colors.END} {fix}")
                
                if len(self.fixes) > 3:
                    print(f"   ... and {len(self.fixes) - 3} more fixes")
        
        # Generate reports
        self.generate_reports()
        
        return all_passed

def main():
    """Main diagnostic function"""
    diagnostics = TerminalDiagnostics()
    success = diagnostics.run_all_diagnostics()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
