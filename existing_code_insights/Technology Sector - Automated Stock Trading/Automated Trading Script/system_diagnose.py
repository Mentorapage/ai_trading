#!/usr/bin/env python3
"""
SYSTEM DIAGNOSTICS - TRADING SYSTEM HEALTH CHECK
===============================================
Comprehensive diagnostics to identify why the trading system isn't running properly.
"""

import os
import sys
import json
import subprocess
import platform
from datetime import datetime, timezone
from pathlib import Path
import importlib.util
from typing import Dict, List, Tuple, Any
import traceback

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_check(name: str, status: bool, details: str = ""):
    """Print a check result with color coding"""
    symbol = f"{Colors.GREEN}✔{Colors.END}" if status else f"{Colors.RED}✖{Colors.END}"
    print(f"{symbol} {name}")
    if details:
        print(f"  {details}")

def print_section(title: str):
    """Print a section header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== {title} ==={Colors.END}")

class SystemDiagnostics:
    def __init__(self):
        self.results = {}
        self.issues = []
        self.working_dir = Path.cwd()
        
    def run_all_checks(self):
        """Run all diagnostic checks"""
        print(f"{Colors.BOLD}🔍 TRADING SYSTEM DIAGNOSTICS{Colors.END}")
        print(f"Working Directory: {self.working_dir}")
        print(f"Timestamp: {datetime.now().isoformat()}")
        
        # Run all checks
        self.check_environment()
        self.check_config_files()
        self.check_external_services()
        self.check_filesystem()
        self.check_timezone_handling()
        self.check_pandas_operations()
        self.check_python_modules()
        
        # Generate reports
        self.generate_summary()
        self.write_reports()
        
        return len(self.issues) == 0
    
    def check_environment(self):
        """Check Python environment and dependencies"""
        print_section("Environment & Versions")
        
        # Python version
        py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        print_check("Python Version", True, f"Python {py_version}")
        self.results['python_version'] = py_version
        
        # OS Info
        os_info = f"{platform.system()} {platform.release()}"
        print_check("Operating System", True, os_info)
        self.results['os_info'] = os_info
        
        # Check key dependencies
        required_packages = [
            'pandas', 'numpy', 'requests', 'python-dotenv', 
            'alpaca-py', 'openpyxl', 'pyyaml'
        ]
        
        missing_packages = []
        installed_packages = {}
        
        for package in required_packages:
            try:
                if package == 'alpaca-py':
                    import alpaca
                    version = getattr(alpaca, '__version__', 'unknown')
                elif package == 'python-dotenv':
                    import dotenv
                    version = getattr(dotenv, '__version__', 'unknown')
                elif package == 'pyyaml':
                    import yaml
                    version = getattr(yaml, '__version__', 'unknown')
                else:
                    module = importlib.import_module(package.replace('-', '_'))
                    version = getattr(module, '__version__', 'unknown')
                
                installed_packages[package] = version
                print_check(f"Package: {package}", True, f"v{version}")
            except ImportError:
                missing_packages.append(package)
                print_check(f"Package: {package}", False, "NOT INSTALLED")
        
        self.results['installed_packages'] = installed_packages
        self.results['missing_packages'] = missing_packages
        
        if missing_packages:
            self.issues.append(f"Missing packages: {', '.join(missing_packages)}")
    
    def check_config_files(self):
        """Check configuration files and environment variables"""
        print_section("Config & Environment Variables")
        
        # Check .env file
        env_file = self.working_dir / '.env'
        env_exists = env_file.exists()
        print_check(".env file", env_exists, str(env_file) if env_exists else "File not found")
        
        if env_exists:
            try:
                from dotenv import load_dotenv
                load_dotenv(dotenv_path=env_file)
                print_check("Load .env", True, "Successfully loaded")
            except Exception as e:
                print_check("Load .env", False, f"Error: {e}")
                self.issues.append(f".env loading failed: {e}")
        else:
            self.issues.append(".env file missing")
        
        # Check config.yml
        config_file = self.working_dir / 'config.yml'
        config_exists = config_file.exists()
        print_check("config.yml file", config_exists, str(config_file) if config_exists else "File not found")
        
        if config_exists:
            try:
                import yaml
                with open(config_file, 'r') as f:
                    config_data = yaml.safe_load(f)
                print_check("Parse config.yml", True, f"Loaded {len(config_data)} sections")
                self.results['config_data'] = config_data
            except Exception as e:
                print_check("Parse config.yml", False, f"Error: {e}")
                self.issues.append(f"config.yml parsing failed: {e}")
        
        # Check critical environment variables
        critical_vars = {
            'apikey': 'Alpaca API Key',
            'apisecret': 'Alpaca Secret Key',
            'FINNHUB_KEYS': 'Finnhub API Keys (preferred)',
            'finnhubkey': 'Finnhub API Key (legacy)'
        }
        
        env_status = {}
        for var, description in critical_vars.items():
            value = os.getenv(var)
            has_value = bool(value and value.strip())
            masked_value = f"{value[:8]}..." if has_value and len(value) > 8 else "Not set"
            print_check(f"ENV: {var}", has_value, f"{description}: {masked_value}")
            env_status[var] = has_value
        
        self.results['environment_variables'] = env_status
        
        # Check Finnhub keys specifically
        finnhub_keys = os.getenv('FINNHUB_KEYS', '').strip()
        if finnhub_keys:
            keys_list = [k.strip() for k in finnhub_keys.split(',') if k.strip()]
            print_check("Finnhub Keys Count", len(keys_list) > 0, f"{len(keys_list)} keys found")
            self.results['finnhub_keys_count'] = len(keys_list)
        elif os.getenv('finnhubkey'):
            print_check("Finnhub Keys Count", True, "1 legacy key found")
            self.results['finnhub_keys_count'] = 1
        else:
            print_check("Finnhub Keys Count", False, "No Finnhub keys found")
            self.results['finnhub_keys_count'] = 0
            self.issues.append("No Finnhub API keys found")
        
        # Check for required Alpaca credentials
        if not (env_status.get('apikey') and env_status.get('apisecret')):
            self.issues.append("Missing Alpaca credentials (apikey/apisecret)")
    
    def check_external_services(self):
        """Test external service connectivity"""
        print_section("External Services")
        
        # Test Finnhub API
        finnhub_key = os.getenv('FINNHUB_KEYS', '').split(',')[0].strip() or os.getenv('finnhubkey', '').strip()
        if finnhub_key:
            try:
                import requests
                response = requests.get(
                    'https://finnhub.io/api/v1/news',
                    params={'category': 'general', 'token': finnhub_key},
                    timeout=10
                )
                success = response.status_code == 200
                print_check("Finnhub API", success, f"Status: {response.status_code}")
                if not success:
                    self.issues.append(f"Finnhub API failed: HTTP {response.status_code}")
            except Exception as e:
                print_check("Finnhub API", False, f"Error: {e}")
                self.issues.append(f"Finnhub API connection failed: {e}")
        else:
            print_check("Finnhub API", False, "No API key to test")
        
        # Test Alpaca API
        api_key = os.getenv('apikey')
        secret_key = os.getenv('apisecret')
        if api_key and secret_key:
            try:
                from alpaca.trading.client import TradingClient
                client = TradingClient(api_key, secret_key, paper=True)
                account = client.get_account()
                print_check("Alpaca API (Paper)", True, f"Account: {account.account_number}")
            except Exception as e:
                print_check("Alpaca API (Paper)", False, f"Error: {e}")
                self.issues.append(f"Alpaca API connection failed: {e}")
        else:
            print_check("Alpaca API (Paper)", False, "No credentials to test")
    
    def check_filesystem(self):
        """Check filesystem permissions and directories"""
        print_section("Filesystem")
        
        # Check required directories
        required_dirs = ['logs', 'cache_finnhub', 'reports']
        for dir_name in required_dirs:
            dir_path = self.working_dir / dir_name
            exists = dir_path.exists()
            
            if not exists:
                try:
                    dir_path.mkdir(exist_ok=True)
                    print_check(f"Directory: {dir_name}", True, f"Created {dir_path}")
                except Exception as e:
                    print_check(f"Directory: {dir_name}", False, f"Cannot create: {e}")
                    self.issues.append(f"Cannot create directory {dir_name}: {e}")
            else:
                # Test write permissions
                test_file = dir_path / 'test_write.tmp'
                try:
                    test_file.write_text('test')
                    test_file.unlink()
                    print_check(f"Directory: {dir_name}", True, f"Writable: {dir_path}")
                except Exception as e:
                    print_check(f"Directory: {dir_name}", False, f"Not writable: {e}")
                    self.issues.append(f"Directory {dir_name} not writable: {e}")
        
        # Check for problematic files
        problematic_patterns = ['*.tmp', '*.lock', '*test*', '*demo*']
        found_files = []
        for pattern in problematic_patterns:
            found_files.extend(list(self.working_dir.glob(pattern)))
        
        if found_files:
            print_check("Temp/Test Files", False, f"Found {len(found_files)} files that may interfere")
            for f in found_files[:5]:  # Show first 5
                print(f"    {f.name}")
        else:
            print_check("Temp/Test Files", True, "No problematic files found")
    
    def check_timezone_handling(self):
        """Check timezone operations"""
        print_section("Timezone Handling")
        
        try:
            # Current UTC time
            utc_now = datetime.now(timezone.utc)
            print_check("UTC Time", True, f"Current UTC: {utc_now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            
            # NY market time conversion
            import pytz
            ny_tz = pytz.timezone('America/New_York')
            ny_time = utc_now.astimezone(ny_tz)
            market_open = ny_time.replace(hour=9, minute=30, second=0, microsecond=0)
            print_check("NY Timezone", True, f"NY Time: {ny_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            print_check("Market Open Time", True, f"Market Open: {market_open.strftime('%H:%M %Z')}")
            
        except Exception as e:
            print_check("Timezone Operations", False, f"Error: {e}")
            self.issues.append(f"Timezone handling failed: {e}")
    
    def check_pandas_operations(self):
        """Test pandas datetime operations"""
        print_section("Pandas Operations")
        
        try:
            import pandas as pd
            import numpy as np
            
            # Create test DataFrame with datetime index
            dates = pd.date_range('2024-01-01', periods=5, freq='D', tz='UTC')
            test_df = pd.DataFrame({
                'price': [100, 101, 99, 102, 98],
                'volume': [1000, 1100, 900, 1200, 800]
            }, index=dates)
            
            print_check("DataFrame Creation", True, f"Created {len(test_df)} rows")
            
            # Test datetime operations
            first_date = test_df.index[0].date()
            print_check("DateTime Index Access", True, f"First date: {first_date}")
            
            # Test time filtering
            filtered = test_df[test_df.index.date == first_date]
            print_check("DateTime Filtering", True, f"Filtered to {len(filtered)} rows")
            
        except Exception as e:
            print_check("Pandas Operations", False, f"Error: {e}")
            self.issues.append(f"Pandas datetime operations failed: {e}")
    
    def check_python_modules(self):
        """Check if core trading modules can be imported"""
        print_section("Trading Modules")
        
        core_modules = [
            'trading_core',
            'historical_backtest', 
            'live_trading',
            'trend_filter',
            'news_weighting',
            'finnhub_pool'
        ]
        
        for module_name in core_modules:
            try:
                spec = importlib.util.find_spec(module_name)
                if spec is None:
                    # Try to find the file in current directory
                    module_file = self.working_dir / f"{module_name}.py"
                    if module_file.exists():
                        print_check(f"Module: {module_name}", True, f"Found: {module_file}")
                    else:
                        print_check(f"Module: {module_name}", False, "File not found")
                        self.issues.append(f"Missing module file: {module_name}.py")
                else:
                    print_check(f"Module: {module_name}", True, f"Importable: {spec.origin}")
            except Exception as e:
                print_check(f"Module: {module_name}", False, f"Error: {e}")
                self.issues.append(f"Module {module_name} check failed: {e}")
    
    def generate_summary(self):
        """Generate diagnostic summary"""
        print_section("Summary")
        
        if not self.issues:
            print(f"{Colors.GREEN}{Colors.BOLD}🎉 ALL CHECKS PASSED!{Colors.END}")
            print("The trading system should be ready to run.")
        else:
            print(f"{Colors.RED}{Colors.BOLD}❌ {len(self.issues)} ISSUES FOUND{Colors.END}")
            print("\nTop issues to fix:")
            for i, issue in enumerate(self.issues[:3], 1):
                print(f"{Colors.YELLOW}{i}.{Colors.END} {issue}")
            
            if len(self.issues) > 3:
                print(f"   ... and {len(self.issues) - 3} more issues")
        
        self.results['issues'] = self.issues
        self.results['total_issues'] = len(self.issues)
        self.results['status'] = 'PASS' if not self.issues else 'FAIL'
    
    def write_reports(self):
        """Write diagnostic reports to files"""
        try:
            # Write JSON report
            json_file = self.working_dir / 'system_health.json'
            with open(json_file, 'w') as f:
                json.dump(self.results, f, indent=2, default=str)
            print(f"\n📄 JSON report: {json_file}")
            
            # Write Markdown report
            md_file = self.working_dir / 'diagnostics_report.md'
            with open(md_file, 'w') as f:
                f.write("# Trading System Diagnostics Report\n\n")
                f.write(f"**Generated:** {datetime.now().isoformat()}\n")
                f.write(f"**Status:** {self.results['status']}\n")
                f.write(f"**Issues Found:** {len(self.issues)}\n\n")
                
                if self.issues:
                    f.write("## Issues to Fix\n\n")
                    for i, issue in enumerate(self.issues, 1):
                        f.write(f"{i}. {issue}\n")
                    f.write("\n")
                
                f.write("## Environment\n\n")
                f.write(f"- Python: {self.results.get('python_version', 'Unknown')}\n")
                f.write(f"- OS: {self.results.get('os_info', 'Unknown')}\n")
                f.write(f"- Working Directory: {self.working_dir}\n\n")
                
                if 'installed_packages' in self.results:
                    f.write("## Installed Packages\n\n")
                    for pkg, version in self.results['installed_packages'].items():
                        f.write(f"- {pkg}: {version}\n")
                    f.write("\n")
                
                if 'missing_packages' in self.results:
                    f.write("## Missing Packages\n\n")
                    for pkg in self.results['missing_packages']:
                        f.write(f"- {pkg}\n")
                    f.write("\n")
            
            print(f"📄 Markdown report: {md_file}")
            
        except Exception as e:
            print(f"{Colors.RED}Error writing reports: {e}{Colors.END}")

def main():
    """Main diagnostic function"""
    diagnostics = SystemDiagnostics()
    success = diagnostics.run_all_checks()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
