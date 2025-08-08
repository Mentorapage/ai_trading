"""
DUAL MODE TRADING SYSTEM
========================
Main entry point for Live Trading and Historical Backtest modes
"""

import os
import sys
from datetime import datetime, time as dt_time
import time

def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def display_main_menu():
    """Display the main menu and get user choice"""
    clear_screen()
    print("=" * 60)
    print("       🚀 DUAL MODE TRADING SYSTEM 🚀")
    print("=" * 60)
    print()
    print("Select trading mode:")
    print("1. 📈 Live Trading Mode")
    print("2. 📊 Historical Backtest Mode")
    print("3. ❌ Exit")
    print()
    
    while True:
        try:
            choice = input("Enter your choice (1-3): ").strip()
            if choice in ['1', '2', '3']:
                return int(choice)
            else:
                print("❌ Invalid choice. Please enter 1, 2, or 3.")
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            sys.exit(0)

def get_live_trading_params():
    """Get parameters for live trading mode"""
    print("\n" + "=" * 50)
    print("       📈 LIVE TRADING CONFIGURATION")
    print("=" * 50)
    
    # Confirmation
    confirm = input("\n⚠️  Are you sure you want to start LIVE trading? (yes/no): ").strip().lower()
    if confirm not in ['yes', 'y']:
        print("❌ Live trading cancelled.")
        return None
    
    # Get trading start time
    while True:
        try:
            time_input = input("\n⏰ Enter exact time to start trading (HH:MM, 24-hour format): ").strip()
            hour, minute = map(int, time_input.split(':'))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                start_time = dt_time(hour, minute)
                break
            else:
                print("❌ Invalid time. Please use HH:MM format (00:00 to 23:59)")
        except ValueError:
            print("❌ Invalid format. Please use HH:MM format (e.g., 09:30)")
    
    # Get holding time
    while True:
        try:
            holding_minutes = int(input("\n⏱️  Maximum holding time in minutes before closing all positions: "))
            if holding_minutes > 0:
                break
            else:
                print("❌ Holding time must be positive")
        except ValueError:
            print("❌ Please enter a valid number")
    
    # Get sentiment threshold
    while True:
        try:
            min_sentiment = float(input("\n📊 Minimum sentiment score (e.g., 0.0): "))
            max_sentiment = float(input("📊 Maximum sentiment score (e.g., 0.7): "))
            if 0 <= min_sentiment < max_sentiment <= 1:
                break
            else:
                print("❌ Invalid range. Min must be >= 0, Max must be <= 1, and Min < Max")
        except ValueError:
            print("❌ Please enter valid decimal numbers")
    
    # Get Stop Loss and Take Profit
    while True:
        try:
            stop_loss = float(input("\n🛡️  Stop Loss amount ($): "))
            take_profit = float(input("💰 Take Profit amount ($): "))
            if stop_loss > 0 and take_profit > 0:
                break
            else:
                print("❌ Both Stop Loss and Take Profit must be positive")
        except ValueError:
            print("❌ Please enter valid decimal numbers")
    
    return {
        'start_time': start_time,
        'holding_minutes': holding_minutes,
        'min_sentiment': min_sentiment,
        'max_sentiment': max_sentiment,
        'stop_loss': stop_loss,
        'take_profit': take_profit
    }

def get_backtest_params():
    """Get parameters for historical backtest mode"""
    print("\n" + "=" * 50)
    print("       📊 HISTORICAL BACKTEST CONFIGURATION")
    print("=" * 50)
    
    # Confirmation
    confirm = input("\n📈 Are you sure you want to run a historical backtest? (yes/no): ").strip().lower()
    if confirm not in ['yes', 'y']:
        print("❌ Historical backtest cancelled.")
        return None
    
    # Get date range
    while True:
        try:
            start_date = input("\n📅 Enter start date (YYYY-MM-DD): ").strip()
            end_date = input("📅 Enter end date (YYYY-MM-DD): ").strip()
            
            # Validate date format
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
            
            if start_date <= end_date:
                break
            else:
                print("❌ Start date must be before or equal to end date")
        except ValueError:
            print("❌ Invalid date format. Please use YYYY-MM-DD (e.g., 2024-01-15)")
    
    # Get sentiment threshold
    while True:
        try:
            sentiment_threshold = float(input("\n📊 Sentiment threshold (0.0 to 1.0, e.g., 0.5): "))
            if 0 <= sentiment_threshold <= 1:
                break
            else:
                print("❌ Sentiment threshold must be between 0.0 and 1.0")
        except ValueError:
            print("❌ Please enter a valid decimal number")
    
    # Get Stop Loss percentage
    while True:
        try:
            stop_loss_pct = float(input("\n🛡️  Stop Loss percentage (e.g., 5.0 for 5%): "))
            if stop_loss_pct > 0:
                break
            else:
                print("❌ Stop Loss percentage must be positive")
        except ValueError:
            print("❌ Please enter a valid decimal number")
    
    # Get Take Profit percentage
    while True:
        try:
            take_profit_pct = float(input("💰 Take Profit percentage (e.g., 3.0 for 3%): "))
            if take_profit_pct > 0:
                break
            else:
                print("❌ Take Profit percentage must be positive")
        except ValueError:
            print("❌ Please enter a valid decimal number")
    
    # Get investment amount per stock
    while True:
        try:
            investment_per_stock = float(input("\n💼 Investment amount per approved stock (USD, e.g., 100000): "))
            if investment_per_stock > 0:
                break
            else:
                print("❌ Investment amount must be positive")
        except ValueError:
            print("❌ Please enter a valid number")
    
    return {
        'start_date': start_date,
        'end_date': end_date,
        'sentiment_threshold': sentiment_threshold,
        'stop_loss_pct': stop_loss_pct,
        'take_profit_pct': take_profit_pct,
        'investment_per_stock': investment_per_stock
    }

def main():
    """Main program entry point"""
    try:
        while True:
            choice = display_main_menu()
            
            if choice == 1:
                # Live Trading Mode
                params = get_live_trading_params()
                if params:
                    from live_trading import run_live_trading
                    run_live_trading(params)
                    
                    input("\n\nPress Enter to return to main menu...")
                    
            elif choice == 2:
                # Historical Backtest Mode
                params = get_backtest_params()
                if params:
                    from historical_backtest import run_historical_backtest
                    run_historical_backtest(params)
                    
                    input("\n\nPress Enter to return to main menu...")
                    
            elif choice == 3:
                print("\n👋 Goodbye!")
                break
                
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
        print("Please check your configuration and try again.")

if __name__ == "__main__":
    main() 