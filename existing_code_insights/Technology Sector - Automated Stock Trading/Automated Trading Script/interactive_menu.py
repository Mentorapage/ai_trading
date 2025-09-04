#!/usr/bin/env python3
"""
INTERACTIVE TRADING SYSTEM MENU
===============================
User-friendly interface for the AI Trading System
"""

import os
import sys
from datetime import datetime, timedelta
import subprocess
import csv
import hashlib
from pathlib import Path
import pandas as pd
import pandas_market_calendars as mcal

# Strategy definitions (S01-S20)
AVAILABLE_STRATEGIES = [
    {"id": "S01", "stop_pct": 3, "take_pct": 5, "min_sentiment": 0.10, "max_sentiment": 0.60},
    {"id": "S02", "stop_pct": 3, "take_pct": 8, "min_sentiment": 0.10, "max_sentiment": 0.60},
    {"id": "S03", "stop_pct": 3, "take_pct": 12, "min_sentiment": 0.20, "max_sentiment": 0.70},
    {"id": "S04", "stop_pct": 3, "take_pct": 20, "min_sentiment": 0.20, "max_sentiment": 0.70},
    {"id": "S05", "stop_pct": 5, "take_pct": 5, "min_sentiment": 0.10, "max_sentiment": 0.60},
    {"id": "S06", "stop_pct": 5, "take_pct": 8, "min_sentiment": 0.20, "max_sentiment": 0.70},
    {"id": "S07", "stop_pct": 5, "take_pct": 12, "min_sentiment": 0.20, "max_sentiment": 0.70},
    {"id": "S08", "stop_pct": 5, "take_pct": 20, "min_sentiment": 0.30, "max_sentiment": 0.80},
    {"id": "S09", "stop_pct": 7, "take_pct": 5, "min_sentiment": 0.10, "max_sentiment": 0.60},
    {"id": "S10", "stop_pct": 7, "take_pct": 8, "min_sentiment": 0.20, "max_sentiment": 0.70},
    {"id": "S11", "stop_pct": 7, "take_pct": 12, "min_sentiment": 0.30, "max_sentiment": 0.80},
    {"id": "S12", "stop_pct": 7, "take_pct": 20, "min_sentiment": 0.30, "max_sentiment": 0.80},
    {"id": "S13", "stop_pct": 10, "take_pct": 5, "min_sentiment": 0.10, "max_sentiment": 0.60},
    {"id": "S14", "stop_pct": 10, "take_pct": 8, "min_sentiment": 0.20, "max_sentiment": 0.70},
    {"id": "S15", "stop_pct": 10, "take_pct": 12, "min_sentiment": 0.30, "max_sentiment": 0.80},
    {"id": "S16", "stop_pct": 10, "take_pct": 20, "min_sentiment": 0.15, "max_sentiment": 0.65},
    {"id": "S17", "stop_pct": 4, "take_pct": 6, "min_sentiment": 0.15, "max_sentiment": 0.65},
    {"id": "S18", "stop_pct": 6, "take_pct": 9, "min_sentiment": 0.10, "max_sentiment": 0.60},
    {"id": "S19", "stop_pct": 8, "take_pct": 15, "min_sentiment": 0.20, "max_sentiment": 0.70},
    {"id": "S20", "stop_pct": 12, "take_pct": 20, "min_sentiment": 0.30, "max_sentiment": 0.80},
]

def print_banner():
    """Print system banner"""
    print("\n" + "="*60)
    print("🤖 AI TRADING SYSTEM - INTERACTIVE MENU")
    print("="*60)
    print("📊 Technology Sector Automated Trading")
    print("🔒 Paper Trading Mode (Safe Testing)")
    
    # Show overnight holding status
    try:
        from overnight_holding import get_overnight_manager
        overnight_manager = get_overnight_manager()
        if overnight_manager.enabled:
            print(f"🌙 Overnight Holding: ENABLED (range: {overnight_manager.sentiment_min:.1f}-{overnight_manager.sentiment_max:.1f})")
        else:
            print("🌙 Overnight Holding: DISABLED")
    except Exception as e:
        print("🌙 Overnight Holding: ERROR loading config")
    
    print("="*60)

def print_menu():
    """Print main menu options"""
    print("\n📋 AVAILABLE OPTIONS:")
    print("1. 🔍 System Diagnostics - Check system health")
    print("2. 📈 Run Backtest - Test on historical data")
    print("3. 📊 Paper Trading (Live) - Real paper trading")
    print("4. 🛡️  Cancel All Orders - Emergency stop")
    print("5. 📁 View Reports - Check trading results")
    print("6. ⚙️  System Information - About this system")
    print("7. 📊 Run Multi-Strategy Backtest - Test multiple strategies simultaneously")
    print("8. 🚪 Exit")
    print("-" * 60)

def run_diagnostics():
    """Run system diagnostics"""
    print("\n🔍 Running System Diagnostics...")
    print("-" * 40)
    result = subprocess.run([sys.executable, "system_diagnose.py"], 
                          capture_output=False, text=True)
    return result.returncode == 0

def run_backtest():
    """Interactive backtest setup"""
    print("\n📈 HISTORICAL BACKTEST SETUP")
    print("-" * 40)
    
    # Get date range
    print("📅 Date Range Selection:")
    print("1. Last week")
    print("2. Last month") 
    print("3. Custom range")
    
    choice = input("\nSelect option (1-3): ").strip()
    
    if choice == "1":
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
    elif choice == "2":
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)
    elif choice == "3":
        start_str = input("Start date (YYYY-MM-DD): ").strip()
        end_str = input("End date (YYYY-MM-DD): ").strip()
        try:
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
        except ValueError:
            print("❌ Invalid date format. Using last week.")
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=7)
    else:
        print("❌ Invalid choice. Using last week.")
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
    
    # Get parameters
    print(f"\n📊 Sentiment Range [X, Y] for qualification AND overnight holding:")
    print("(This range controls both entry qualification and overnight decisions)")
    
    # Show current overnight settings
    try:
        from overnight_holding import get_overnight_manager
        overnight_manager = get_overnight_manager()
        if overnight_manager.enabled:
            print(f"🌙 Current overnight range: [{overnight_manager.sentiment_min:.1f}, {overnight_manager.sentiment_max:.1f}]")
        else:
            print("🌙 Overnight holding is DISABLED")
    except:
        pass
    
    sentiment_min = input("Lower boundary X (default: 0.2): ").strip() or "0.2"
    sentiment_max = input("Upper boundary Y (default: 0.6): ").strip() or "0.6"
    
    stop_loss = input("\n🛡️  Stop loss % (default: 5.0): ").strip() or "5.0"
    take_profit = input("💰 Take profit % (default: 5.0): ").strip() or "5.0"
    investment = input("💼 Investment per stock $ (default: 10000): ").strip() or "10000"
    
    # Run backtest
    cmd = [
        sys.executable, "historical_backtest.py",
        "--start", str(start_date),
        "--end", str(end_date),
        "--sentiment", sentiment_min,  # Use lower boundary for basic screening
        "--sentiment-min", sentiment_min,  # Overnight holding lower boundary
        "--sentiment-max", sentiment_max,  # Overnight holding upper boundary
        "--stop-loss", stop_loss,
        "--take-profit", take_profit,
        "--investment", investment,
        "--log-level", "INFO",
        "--no-input"
    ]
    
    print(f"\n🚀 Running backtest from {start_date} to {end_date}...")
    result = subprocess.run(cmd, capture_output=False, text=True)
    return result.returncode == 0

def run_paper_trading(dry_run=True):
    """Run paper trading"""
    mode_str = "DRY RUN" if dry_run else "LIVE PAPER"
    print(f"\n🧪 PAPER TRADING - {mode_str}")
    print("-" * 40)
    
    if not dry_run:
        confirm = input("⚠️  This will place actual paper trades. Continue? (y/N): ").strip().lower()
        if confirm != 'y':
            print("❌ Cancelled by user")
            return False
    
    # Get parameters
    print(f"\n📊 Parameters (press Enter for defaults):")
    sentiment = input("Sentiment threshold (default: 0.2): ").strip() or "0.2"
    investment = input("Investment per stock $ (default: 10000): ").strip() or "10000"
    max_positions = input("Max concurrent positions (default: 3): ").strip() or "3"
    
    # Build command
    cmd = [
        sys.executable, "live_trading.py",
        "--mode", "paper",
        "--sentiment", sentiment,
        "--investment", investment,
        "--max-positions", max_positions,
        "--log-level", "INFO",
        "--no-input"
    ]
    
    if dry_run:
        cmd.append("--dry-run")
    
    print(f"\n🚀 Starting paper trading ({mode_str})...")
    if not dry_run:
        print("⚠️  Press Ctrl+C to stop trading")
    
    result = subprocess.run(cmd, capture_output=False, text=True)
    return result.returncode == 0

def cancel_all_orders():
    """Cancel all orders and positions"""
    print("\n🛡️  EMERGENCY STOP")
    print("-" * 40)
    confirm = input("⚠️  Cancel ALL orders and positions? (y/N): ").strip().lower()
    if confirm != 'y':
        print("❌ Cancelled by user")
        return False
    
    result = subprocess.run([sys.executable, "cancel_all.py"], 
                          capture_output=False, text=True)
    return result.returncode == 0

def view_reports():
    """View available reports"""
    print("\n📁 AVAILABLE REPORTS")
    print("-" * 40)
    
    reports_dir = "reports"
    if not os.path.exists(reports_dir):
        print("❌ No reports directory found")
        return
    
    files = [f for f in os.listdir(reports_dir) if f.endswith(('.xlsx', '.csv', '.log'))]
    if not files:
        print("❌ No reports found")
        return
    
    print("📊 Recent reports:")
    for i, file in enumerate(sorted(files, reverse=True)[:10], 1):
        file_path = os.path.join(reports_dir, file)
        size = os.path.getsize(file_path)
        print(f"{i:2d}. {file} ({size:,} bytes)")
    
    print(f"\n📁 Reports location: {os.path.abspath(reports_dir)}")

def show_system_info():
    """Show system information"""
    print("\n⚙️  SYSTEM INFORMATION")
    print("-" * 40)
    print("🤖 AI Trading System v1.0")
    print("📊 Technology Sector Focus")
    print("🎯 Target: 14 major tech stocks")
    print("📈 Strategy: Sentiment-based trading")
    print("🔒 Safety: Paper trading default")
    print("\n📋 Features:")
    print("• News sentiment analysis (NLTK VADER)")
    print("• Risk management (stop-loss/take-profit)")
    print("• Historical backtesting")
    print("• Real-time paper trading")
    print("• Comprehensive reporting")
    print("\n⚠️  Disclaimer:")
    print("This system is for educational purposes.")
    print("Always test with paper trading first!")
    print("Past performance doesn't guarantee future results.")

def validate_date_range(start_str, end_str):
    """Validate date range input"""
    try:
        start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
        
        if start_date >= end_date:
            return None, None, "Start date must be before end date"
        
        # Check if dates are reasonable (not too far in future/past)
        today = datetime.now().date()
        if start_date > today:
            return None, None, "Start date cannot be in the future"
        
        if (today - start_date).days > 365 * 3:  # 3 years max
            return None, None, "Start date cannot be more than 3 years ago"
            
        return start_date, end_date, None
    except ValueError:
        return None, None, "Invalid date format. Use YYYY-MM-DD"

def parse_strategy_selection(selection_str):
    """Parse strategy selection input"""
    if selection_str.upper() == "ALL":
        return [s["id"] for s in AVAILABLE_STRATEGIES], None
    
    try:
        # Parse comma-separated list
        strategy_ids = [s.strip().upper() for s in selection_str.split(",")]
        
        # Validate each strategy ID
        valid_ids = [s["id"] for s in AVAILABLE_STRATEGIES]
        invalid_ids = [sid for sid in strategy_ids if sid not in valid_ids]
        
        if invalid_ids:
            return None, f"Invalid strategy IDs: {', '.join(invalid_ids)}"
        
        # Remove duplicates while preserving order
        unique_ids = []
        for sid in strategy_ids:
            if sid not in unique_ids:
                unique_ids.append(sid)
        
        return unique_ids, None
    except Exception as e:
        return None, f"Error parsing strategy selection: {e}"

def get_trading_days(start_date, end_date):
    """Get trading days using NYSE calendar"""
    try:
        nyse = mcal.get_calendar('NYSE')
        trading_days = nyse.valid_days(start_date=start_date, end_date=end_date)
        return [day.date() if hasattr(day, 'date') else day for day in trading_days]
    except Exception as e:
        print(f"❌ Error getting trading days: {e}")
        return []

def make_trade_id(strategy_id, symbol, open_time, close_time, entry_price, exit_price, qty):
    """Generate unique trade ID"""
    basis = f"{strategy_id}|{symbol}|{open_time}|{close_time}|{entry_price}|{exit_price}|{qty}"
    return hashlib.sha256(basis.encode('utf-8')).hexdigest()[:16]

def run_multi_strategy_backtest():
    """Run multi-strategy backtest"""
    print("\n📊 MULTI-STRATEGY BACKTEST SETUP")
    print("-" * 50)
    
    # Strategy selection
    print("📋 Available strategies: S01-S20")
    print("Examples: 'S01,S02,S05' or 'ALL' for all strategies")
    strategy_input = input("Select strategies: ").strip()
    
    if not strategy_input:
        print("❌ No strategies selected")
        return False
    
    selected_strategy_ids, error = parse_strategy_selection(strategy_input)
    if error:
        print(f"❌ {error}")
        return False
    
    print(f"✅ Selected {len(selected_strategy_ids)} strategies: {', '.join(selected_strategy_ids)}")
    
    # Date range selection
    print("\n📅 Date Range:")
    start_str = input("Start date (YYYY-MM-DD): ").strip()
    end_str = input("End date (YYYY-MM-DD): ").strip()
    
    start_date, end_date, error = validate_date_range(start_str, end_str)
    if error:
        print(f"❌ {error}")
        return False
    
    print(f"✅ Date range: {start_date} to {end_date}")
    
    # Get trading days
    trading_days = get_trading_days(start_date, end_date)
    if not trading_days:
        print("❌ No trading days found in the specified range")
        return False
    
    print(f"✅ Found {len(trading_days)} trading days")
    
    # Prepare output files
    date_str = f"{start_date}_{end_date}"
    logs_dir = Path("logs")
    reports_dir = Path("reports")
    logs_dir.mkdir(exist_ok=True)
    reports_dir.mkdir(exist_ok=True)
    
    trade_log_file = logs_dir / f"multi_strategy_{date_str}.csv"
    strategy_summary_file = reports_dir / f"multi_strategy_summary_{date_str}.csv"
    ticker_summary_file = reports_dir / f"multi_strategy_per_ticker_{date_str}.csv"
    
    # Initialize CSV files
    trade_headers = [
        'trade_id', 'open_time', 'close_time', 'symbol', 'strategy_id', 'qty',
        'entry_price', 'exit_price', 'fees_usd', 'pnl_usd', 'pnl_pct', 'exit_reason',
        'stop_pct', 'take_pct', 'sentiment_score', 'sentiment_label', 'news_headline'
    ]
    
    with open(trade_log_file, 'w', newline='') as f:
        csv.writer(f).writerow(trade_headers)
    
    print(f"\n🚀 Starting multi-strategy backtest...")
    print(f"📁 Trade log: {trade_log_file}")
    print(f"📁 Strategy summary: {strategy_summary_file}")
    print(f"📁 Ticker summary: {ticker_summary_file}")
    
    # Run the actual backtest using existing script
    selected_strategies = [s for s in AVAILABLE_STRATEGIES if s["id"] in selected_strategy_ids]
    
    # Build command to run multi-strategy backtest
    cmd = [
        sys.executable, "run_multi_strategy_backtest.py",
        "--start", str(start_date),
        "--end", str(end_date),
        "--strategies", ",".join(selected_strategy_ids),
        "--trade-log", str(trade_log_file),
        "--strategy-summary", str(strategy_summary_file),
        "--ticker-summary", str(ticker_summary_file)
    ]
    
    print(f"\n🔄 Executing backtest...")
    try:
        result = subprocess.run(cmd, capture_output=False, text=True, cwd=".")
        
        if result.returncode == 0:
            print(f"\n✅ Multi-strategy backtest completed successfully!")
            print(f"📊 Results saved to:")
            print(f"   • Trade log: {trade_log_file}")
            print(f"   • Strategy summary: {strategy_summary_file}")
            print(f"   • Ticker summary: {ticker_summary_file}")
            return True
        else:
            print(f"\n❌ Backtest failed with return code {result.returncode}")
            return False
            
    except FileNotFoundError:
        print("❌ Multi-strategy backtest script not found. Creating fallback implementation...")
        return run_multi_strategy_backtest_fallback(
            selected_strategies, start_date, end_date, trading_days,
            trade_log_file, strategy_summary_file, ticker_summary_file
        )
    except Exception as e:
        print(f"❌ Error running backtest: {e}")
        return False

def run_multi_strategy_backtest_fallback(strategies, start_date, end_date, trading_days, 
                                       trade_log_file, strategy_summary_file, ticker_summary_file):
    """Fallback implementation using existing run_S01_S20_backtest.py"""
    print("🔄 Using fallback implementation...")
    
    # Use existing S01-S20 backtest script
    cmd = [
        sys.executable, "run_S01_S20_backtest.py",
        "--start", str(start_date),
        "--end", str(end_date),
        "--out", str(trade_log_file)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=False, text=True)
        
        if result.returncode == 0:
            print(f"\n✅ Fallback backtest completed!")
            
            # Generate summary reports from the trade log
            if trade_log_file.exists():
                generate_summary_reports(trade_log_file, strategy_summary_file, ticker_summary_file)
            
            return True
        else:
            print(f"❌ Fallback backtest failed with return code {result.returncode}")
            return False
            
    except Exception as e:
        print(f"❌ Error running fallback backtest: {e}")
        return False

def generate_summary_reports(trade_log_file, strategy_summary_file, ticker_summary_file):
    """Generate summary reports from trade log"""
    try:
        # Read trade log
        df = pd.read_csv(trade_log_file)
        
        if len(df) == 0:
            print("⚠️  No trades found in log file")
            return
        
        # Strategy summary
        strategy_summary = df.groupby('strategy_id').agg({
            'pnl_usd': ['sum', 'mean', 'count'],
            'pnl_pct': ['mean', 'std'],
            'exit_reason': lambda x: (x == 'TAKE_PROFIT').sum()
        }).round(2)
        
        strategy_summary.columns = ['total_pnl_usd', 'avg_pnl_usd', 'trade_count', 
                                  'avg_pnl_pct', 'pnl_std_pct', 'take_profit_count']
        strategy_summary['win_rate_pct'] = (df.groupby('strategy_id')['pnl_usd'] > 0).mean() * 100
        strategy_summary.to_csv(strategy_summary_file)
        
        # Ticker summary
        ticker_summary = df.groupby(['symbol', 'strategy_id']).agg({
            'pnl_usd': ['sum', 'count'],
            'pnl_pct': 'mean'
        }).round(2)
        
        ticker_summary.columns = ['total_pnl_usd', 'trade_count', 'avg_pnl_pct']
        ticker_summary.to_csv(ticker_summary_file)
        
        # Print reconciliation
        total_pnl = df['pnl_usd'].sum()
        strategy_total = strategy_summary['total_pnl_usd'].sum()
        ticker_total = ticker_summary.groupby(level=0)['total_pnl_usd'].sum().sum()
        
        print(f"\n📊 RECONCILIATION:")
        print(f"   Total PnL (trades): ${total_pnl:,.2f}")
        print(f"   Total PnL (strategies): ${strategy_total:,.2f}")
        print(f"   Total PnL (tickers): ${ticker_total:,.2f}")
        
        if abs(total_pnl - strategy_total) < 0.01 and abs(total_pnl - ticker_total) < 0.01:
            print("   ✅ STATUS: PASS - All totals match")
        else:
            print("   ❌ STATUS: FAIL - Inconsistent totals detected")
        
        print(f"\n📈 GRAND TOTAL PnL: ${total_pnl:,.2f}")
        
    except Exception as e:
        print(f"❌ Error generating summary reports: {e}")

def main():
    """Main interactive menu loop"""
    while True:
        print_banner()
        print_menu()
        
        try:
            choice = input("Select option (1-8): ").strip()
            
            if choice == "1":
                run_diagnostics()
            elif choice == "2":
                run_backtest()
            elif choice == "3":
                run_paper_trading(dry_run=False)
            elif choice == "4":
                cancel_all_orders()
            elif choice == "5":
                view_reports()
            elif choice == "6":
                show_system_info()
            elif choice == "7":
                run_multi_strategy_backtest()
            elif choice == "8":
                print("\n👋 Goodbye! Trade safely!")
                break
            else:
                print("❌ Invalid choice. Please select 1-8.")
            
            input("\nPress Enter to continue...")
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye! Trade safely!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            input("Press Enter to continue...")

if __name__ == "__main__":
    main()
