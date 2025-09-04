#!/usr/bin/env python3
"""
TRADING SYSTEM - MAIN ENTRY POINT
=================================
Unified CLI interface for all trading system operations
"""

import argparse
import sys
import os
from pathlib import Path

# Add current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def main():
    """Main entry point with mode selection"""
    parser = argparse.ArgumentParser(
        description='Trading System - Unified Interface',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available Modes:
  diagnose    - Run system health diagnostics
  backtest    - Run historical backtesting
  live        - Run live/paper trading
  cancel      - Cancel all orders and positions

Examples:
  python3 main.py diagnose
  python3 main.py backtest --start 2024-10-15 --end 2024-10-18 --log-level INFO
  python3 main.py live --mode paper --dry-run --log-level INFO
  python3 main.py cancel
        """
    )
    
    parser.add_argument('mode', choices=['diagnose', 'backtest', 'live', 'cancel'],
                       help='Operation mode')
    
    # Parse known args to get the mode, then delegate to specific parsers
    args, remaining_args = parser.parse_known_args()
    
    # Delegate to appropriate module
    if args.mode == 'diagnose':
        from system_diagnose import main as diagnose_main
        sys.argv = ['system_diagnose.py'] + remaining_args
        diagnose_main()
        
    elif args.mode == 'backtest':
        from historical_backtest import main as backtest_main
        sys.argv = ['historical_backtest.py'] + remaining_args
        backtest_main()
        
    elif args.mode == 'live':
        from live_trading import main as live_main
        sys.argv = ['live_trading.py'] + remaining_args
        live_main()
        
    elif args.mode == 'cancel':
        from cancel_all import cancel_all_orders_and_positions
        print("🛡️  Cancelling all orders and positions...")
        try:
            cancel_all_orders_and_positions()
            print("✅ All orders cancelled successfully")
        except Exception as e:
            print(f"❌ Error: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()