#!/usr/bin/env python3
"""
AI Trading System - Main Entry Point
Interactive menu for Live Trading vs Backtesting
"""

import sys
import os
from datetime import datetime

# Add the trading script directory to Python path
sys.path.append("existing_code_insights/Technology Sector - Automated Stock Trading/Automated Trading Script")
sys.path.append("backtest")

def display_banner():
    """Display the system banner"""
    print("🚀" + "=" * 68 + "🚀")
    print("           AI TRADING SYSTEM - VANTAGE AI TECHNOLOGY")
    print("=" * 70)
    print("💰 Automated Stock Trading with Sentiment Analysis")
    print("🧠 Enhanced AI-Powered Decision Making")
    print("🛡️ Production-Ready with Comprehensive Safety Features")
    print("=" * 70)
    print(f"🕐 System Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🚀" + "=" * 68 + "🚀")

def display_menu():
    """Display the main menu options"""
    print("\n🎯 SYSTEM OPERATIONS")
    print("=" * 50)
    print("1. 🔴 Run Real-Time Trading (LIVE)")
    print("   └── Execute live trading with Alpaca API")
    print("   └── Uses real money (paper trading)")
    print("   └── Requires API keys and market hours")
    print("")
    print("2. 📊 Run Backtest on Historical Data")
    print("   └── Simulate trading on past data")
    print("   └── Safe offline testing")
    print("   └── Generate performance reports")
    print("")
    print("3. 🔧 System Status & Configuration")
    print("   └── Check API connections")
    print("   └── Validate settings")
    print("   └── View account information")
    print("")
    print("4. 🚪 Exit")
    print("=" * 50)

def get_user_choice():
    """Get and validate user menu choice"""
    while True:
        try:
            choice = input("\n👉 Enter your choice (1-4): ").strip()
            if choice in ['1', '2', '3', '4']:
                return int(choice)
            else:
                print("❌ Invalid choice. Please enter 1, 2, 3, or 4.")
        except KeyboardInterrupt:
            print("\n\n👋 Exiting system...")
            sys.exit(0)
        except Exception as e:
            print(f"❌ Error: {e}. Please try again.")

def run_live_trading():
    """Execute real-time trading"""
    print("\n🔴 STARTING LIVE TRADING MODE")
    print("=" * 50)
    
    # Check if .env file exists
    env_path = "existing_code_insights/Technology Sector - Automated Stock Trading/Automated Trading Script/.env"
    if not os.path.exists(env_path):
        print("❌ ERROR: .env file not found!")
        print("📝 Please create .env file with your API keys:")
        print(f"   Location: {env_path}")
        print("   Use env_template.txt as reference")
        return False
    
    try:
        # Import and run the enhanced trading system
        from technology_auto_trade import auto_trade
        from market_utils import pre_trading_validation, log_validation_results
        
        print("🔍 Performing pre-trading validation...")
        ready, results = pre_trading_validation()
        
        for result in results:
            status = "✅" if result['passed'] else "❌"
            print(f"{status} {result['check']}: {result['message']}")
        
        if not ready:
            print("\n❌ TRADING ABORTED - System not ready")
            return False
        
        print("\n✅ All validations passed. Starting trading...")
        print("⚠️  Press Ctrl+C to stop trading")
        
        # Run the actual trading
        auto_trade()
        return True
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Trading stopped by user")
        return True
    except Exception as e:
        print(f"\n❌ Trading error: {e}")
        return False

def run_backtesting():
    """Execute backtesting workflow"""
    print("\n📊 STARTING BACKTESTING MODE")
    print("=" * 50)
    
    try:
        # Import the backtesting module
        from backtest_engine import BacktestEngine
        
        # Create and run backtest
        backtest = BacktestEngine()
        backtest.run_interactive_backtest()
        return True
        
    except ImportError:
        print("❌ Backtesting module not found. Creating it now...")
        create_backtest_module()
        print("✅ Backtesting module created. Please restart and try again.")
        return False
    except Exception as e:
        print(f"❌ Backtesting error: {e}")
        return False

def check_system_status():
    """Check system status and configuration"""
    print("\n🔧 SYSTEM STATUS & CONFIGURATION")
    print("=" * 50)
    
    try:
        # Check file structure
        print("📂 File Structure:")
        required_files = [
            "existing_code_insights/Technology Sector - Automated Stock Trading/Automated Trading Script/.env",
            "existing_code_insights/Technology Sector - Automated Stock Trading/Automated Trading Script/technology_auto_trade.py",
            "existing_code_insights/Technology Sector - Automated Stock Trading/Automated Trading Script/trade_types.py",
            "existing_code_insights/Technology Sector - Automated Stock Trading/Automated Trading Script/market_utils.py",
        ]
        
        for file_path in required_files:
            if os.path.exists(file_path):
                print(f"   ✅ {os.path.basename(file_path)}")
            else:
                print(f"   ❌ {os.path.basename(file_path)} - MISSING")
        
        # Check API connectivity if .env exists
        env_path = "existing_code_insights/Technology Sector - Automated Stock Trading/Automated Trading Script/.env"
        if os.path.exists(env_path):
            print("\n🔗 API Connectivity:")
            sys.path.append("existing_code_insights/Technology Sector - Automated Stock Trading/Automated Trading Script")
            
            try:
                from market_utils import pre_trading_validation
                ready, results = pre_trading_validation()
                
                for result in results:
                    status = "✅" if result['passed'] else "❌"
                    print(f"   {status} {result['check']}: {result['message']}")
                    
            except Exception as e:
                print(f"   ❌ API Check Failed: {e}")
        else:
            print("\n⚠️  API keys not configured (no .env file)")
        
        print(f"\n📊 System Status: {'✅ READY' if os.path.exists(env_path) else '⚠️ NEEDS CONFIGURATION'}")
        
    except Exception as e:
        print(f"❌ Status check error: {e}")

def create_backtest_module():
    """Create the backtesting module if it doesn't exist"""
    # This will be handled in the next step
    pass

def main():
    """Main application entry point"""
    try:
        display_banner()
        
        while True:
            display_menu()
            choice = get_user_choice()
            
            if choice == 1:
                run_live_trading()
            elif choice == 2:
                run_backtesting()
            elif choice == 3:
                check_system_status()
            elif choice == 4:
                print("\n👋 Thank you for using AI Trading System!")
                print("💰 Trade safely and profitably!")
                break
            
            # Ask if user wants to continue
            if choice != 4:
                print("\n" + "=" * 50)
                continue_choice = input("🔄 Return to main menu? (y/n): ").strip().lower()
                if continue_choice not in ['y', 'yes', '']:
                    print("\n👋 Goodbye!")
                    break
    
    except KeyboardInterrupt:
        print("\n\n👋 System shutdown by user. Goodbye!")
    except Exception as e:
        print(f"\n❌ System error: {e}")
        print("Please check your configuration and try again.")

if __name__ == "__main__":
    main() 