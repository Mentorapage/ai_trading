#!/usr/bin/env python3
"""
Enhanced Trading System Launcher
Provides startup menu for live trading vs backtesting
"""

import sys
import os
from datetime import datetime, timedelta
import pandas as pd
import json
import random
from typing import Dict, List, Tuple

# Import existing trading components
from technology_auto_trade import get_sentiment, auto_trade, stocks

def display_banner():
    """Display system banner"""
    print("🚀" + "=" * 68 + "🚀")
    print("           ENHANCED AI TRADING SYSTEM - VANTAGE AI")
    print("=" * 70)
    print("💰 Automated Stock Trading with Sentiment Analysis")
    print("📊 Live Trading & Historical Backtesting")
    print("🧠 VADER Sentiment Analysis Engine")
    print("=" * 70)
    print(f"🕐 System Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🚀" + "=" * 68 + "🚀")

def display_menu():
    """Display main menu options"""
    print("\n🎯 What would you like to do?")
    print("=" * 40)
    print("1️⃣  Run real-time trading now")
    print("2️⃣  Run a backtest for a specific date range")
    print("3️⃣  Exit")
    print("=" * 40)

def get_user_choice():
    """Get and validate user choice"""
    while True:
        try:
            choice = input("\n👉 Enter your choice (1-3): ").strip()
            if choice in ['1', '2', '3']:
                return int(choice)
            else:
                print("❌ Invalid choice. Please enter 1, 2, or 3.")
        except KeyboardInterrupt:
            print("\n👋 Exiting...")
            return 3
        except Exception as e:
            print(f"❌ Error: {e}. Please try again.")

def run_live_trading():
    """Execute live trading"""
    print("\n🔴 STARTING REAL-TIME TRADING")
    print("=" * 50)
    
    try:
        auto_trade()
        print("\n✅ Trading session completed!")
        return True
    except Exception as e:
        print(f"❌ Trading error: {e}")
        return False

def get_backtest_parameters():
    """Get backtest parameters from user"""
    print("\n📊 BACKTEST CONFIGURATION")
    print("=" * 50)
    
    # Start date
    start_date = input("📅 Start date (YYYY-MM-DD) [2024-11-01]: ").strip()
    if not start_date:
        start_date = "2024-11-01"
        
    # End date  
    end_date = input("📅 End date (YYYY-MM-DD) [2024-11-30]: ").strip()
    if not end_date:
        end_date = "2024-11-30"
        
    # Take profit
    take_profit_input = input("💰 Take profit (+$0.50): ").strip()
    take_profit = 0.50 if not take_profit_input else float(take_profit_input.replace('$', '').replace('+', ''))
    
    # Stop loss
    stop_loss_input = input("🛡️ Stop loss (-$1.50): ").strip()
    stop_loss = 1.50 if not stop_loss_input else abs(float(stop_loss_input.replace('$', '').replace('-', '')))
    
    # Sentiment bounds
    sentiment_lower_input = input("🧠 Sentiment lower bound (0.5): ").strip()
    sentiment_lower = 0.5 if not sentiment_lower_input else float(sentiment_lower_input)
    
    sentiment_upper_input = input("🧠 Sentiment upper bound (0.7): ").strip()
    sentiment_upper = 0.7 if not sentiment_upper_input else float(sentiment_upper_input)
    
    return {
        'start_date': start_date,
        'end_date': end_date,
        'take_profit': take_profit,
        'stop_loss': stop_loss,
        'sentiment_lower': sentiment_lower,
        'sentiment_upper': sentiment_upper
    }

def simulate_historical_sentiment(stock: str, date: str) -> float:
    """Simulate historical sentiment for backtesting"""
    # Realistic sentiment patterns based on stock characteristics
    sentiment_patterns = {
        'NVDA': (0.3, 0.8),   'MSFT': (0.2, 0.7),   'AAPL': (0.1, 0.6),
        'AMZN': (0.2, 0.7),   'GOOGL': (0.3, 0.8),  'META': (-0.1, 0.5),
        'AVGO': (0.2, 0.7),   'TSM': (-0.2, 0.4),   'TSLA': (-0.1, 0.7),
        'ORCL': (0.1, 0.5),   'ADBE': (0.2, 0.6),   'CSCO': (0.0, 0.4),
        'INTU': (0.1, 0.5),   'QCOM': (0.1, 0.6)
    }
    
    min_sent, max_sent = sentiment_patterns.get(stock, (0.0, 0.5))
    
    # Add date-based variation
    date_obj = datetime.strptime(date, '%Y-%m-%d')
    day_factor = (date_obj.day % 30) / 30
    
    # Generate deterministic but varied sentiment
    random.seed(hash(stock + date))
    sentiment_range = max_sent - min_sent
    base_sentiment = min_sent + (sentiment_range * day_factor)
    variation = random.uniform(-0.2, 0.2) * sentiment_range
    
    return max(-1.0, min(1.0, base_sentiment + variation))

def get_historical_prices(stock: str, date: str) -> Dict:
    """Simulate historical price data"""
    base_prices = {
        'NVDA': 420, 'MSFT': 380, 'AAPL': 180, 'AMZN': 160, 'GOOGL': 160,
        'META': 480, 'AVGO': 820, 'TSM': 130, 'TSLA': 220, 'ORCL': 130,
        'ADBE': 520, 'CSCO': 48, 'INTU': 580, 'QCOM': 160
    }
    
    base_price = base_prices.get(stock, 100)
    
    # Add realistic price variation
    date_obj = datetime.strptime(date, '%Y-%m-%d')
    days_from_start = (date_obj - datetime(2024, 11, 1)).days
    
    random.seed(hash(stock + date))
    trend_factor = 1 + (days_from_start * 0.002)
    daily_variation = random.uniform(0.95, 1.05)
    
    price = base_price * trend_factor * daily_variation
    
    return {
        'open': round(price, 2),
        'close': round(price * random.uniform(0.99, 1.01), 2),
        'high': round(price * random.uniform(1.01, 1.03), 2),
        'low': round(price * random.uniform(0.97, 0.99), 2)
    }

def simulate_trade(entry_price: float, take_profit: float, stop_loss: float, 
                  price_data: Dict) -> Tuple[str, float]:
    """Simulate trade outcome"""
    tp_price = round(entry_price + take_profit, 2)
    sl_price = round(entry_price - stop_loss, 2)
    
    high = price_data['high']
    low = price_data['low']
    close = price_data['close']
    
    if high >= tp_price:
        return 'take_profit', tp_price
    elif low <= sl_price:
        return 'stop_loss', sl_price
    else:
        return 'market_close', close

def run_backtest():
    """Execute comprehensive backtesting"""
    print("\n📊 STARTING BACKTEST")
    print("=" * 50)
    
    params = get_backtest_parameters()
    
    print(f"\n📋 Configuration:")
    print(f"📅 Period: {params['start_date']} → {params['end_date']}")
    print(f"💰 TP: +${params['take_profit']}, SL: -${params['stop_loss']}")
    print(f"🧠 Sentiment: {params['sentiment_lower']} → {params['sentiment_upper']}")
    
    confirm = input("\n✅ Start backtest? (y/n): ").strip().lower()
    if confirm not in ['y', 'yes', '']:
        print("❌ Backtest cancelled")
        return
    
    print(f"\n🚀 RUNNING BACKTEST...")
    print("=" * 50)
    
    # Initialize
    all_trades = []
    total_capital = 100000.0
    current_capital = total_capital
    
    # Date range
    start_date = datetime.strptime(params['start_date'], '%Y-%m-%d')
    end_date = datetime.strptime(params['end_date'], '%Y-%m-%d')
    
    current_date = start_date
    trading_days = 0
    
    while current_date <= end_date:
        if current_date.weekday() < 5:  # Weekdays only
            date_str = current_date.strftime('%Y-%m-%d')
            
            # Analyze stocks for this day
            qualified_stocks = []
            
            for stock in stocks:
                sentiment = simulate_historical_sentiment(stock, date_str)
                
                if params['sentiment_lower'] <= sentiment <= params['sentiment_upper']:
                    qualified_stocks.append({
                        'symbol': stock,
                        'sentiment': sentiment
                    })
            
            day_pnl = 0.0
            
            if qualified_stocks:
                capital_per_stock = (current_capital * 0.9) / len(qualified_stocks)
                
                for stock_info in qualified_stocks:
                    stock = stock_info['symbol']
                    
                    # Get prices and execute trade
                    price_data = get_historical_prices(stock, date_str)
                    entry_price = price_data['open']
                    
                    shares = int(capital_per_stock / entry_price)
                    if shares <= 0:
                        continue
                    
                    # Simulate trade outcome
                    outcome, exit_price = simulate_trade(
                        entry_price, params['take_profit'], 
                        params['stop_loss'], price_data
                    )
                    
                    # Calculate P&L
                    trade_pnl = (exit_price - entry_price) * shares
                    day_pnl += trade_pnl
                    current_capital += trade_pnl
                    
                    # Record trade
                    all_trades.append({
                        'date': date_str,
                        'symbol': stock,
                        'sentiment': round(stock_info['sentiment'], 4),
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'shares': shares,
                        'outcome': outcome,
                        'pnl': round(trade_pnl, 2)
                    })
            
            trading_days += 1
            if trading_days % 5 == 0:
                print(f"📅 Processed {trading_days} days, Capital: ${current_capital:,.2f}")
        
        current_date += timedelta(days=1)
    
    # Display results
    display_backtest_results(params, all_trades, total_capital, current_capital)
    
    # Save results
    save_backtest_results(params, all_trades, total_capital, current_capital)

def display_backtest_results(params: Dict, all_trades: List, 
                           initial_capital: float, final_capital: float):
    """Display backtest results"""
    print(f"\n" + "=" * 70)
    print("📊 BACKTEST RESULTS")
    print("=" * 70)
    
    total_trades = len(all_trades)
    winning_trades = len([t for t in all_trades if t['pnl'] > 0])
    losing_trades = len([t for t in all_trades if t['pnl'] < 0])
    
    total_pnl = final_capital - initial_capital
    total_return = (total_pnl / initial_capital) * 100
    
    print(f"📅 Period: {params['start_date']} → {params['end_date']}")
    print(f"🔢 Total Trades: {total_trades}")
    print(f"✅ Winning Trades: {winning_trades}")
    print(f"❌ Losing Trades: {losing_trades}")
    
    if total_trades > 0:
        win_rate = (winning_trades / total_trades) * 100
        print(f"📈 Win Rate: {win_rate:.1f}%")
    
    print(f"💰 Total P&L: ${total_pnl:+,.2f}")
    print(f"📊 Total Return: {total_return:+.2f}%")
    print(f"💵 Final Capital: ${final_capital:,.2f}")
    
    # Show sample trades
    if all_trades:
        print(f"\n📋 SAMPLE TRADES:")
        print("Date       | Stock | Entry   | Exit    | Shares | P&L     | Outcome")
        print("-" * 70)
        
        for trade in all_trades[:10]:  # Show first 10 trades
            print(f"{trade['date']} | {trade['symbol']:>5} | ${trade['entry_price']:>6.2f} | "
                  f"${trade['exit_price']:>6.2f} | {trade['shares']:>6} | ${trade['pnl']:>+7.2f} | "
                  f"{trade['outcome']}")
        
        if len(all_trades) > 10:
            print(f"... and {len(all_trades) - 10} more trades")

def save_backtest_results(params: Dict, all_trades: List, 
                        initial_capital: float, final_capital: float):
    """Save backtest results"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save to CSV
    df = pd.DataFrame(all_trades)
    filename = f"backtest_results_{timestamp}.csv"
    df.to_csv(filename, index=False)
    
    print(f"\n📁 Results saved to: {filename}")

def main():
    """Main launcher function"""
    try:
        display_banner()
        
        while True:
            display_menu()
            choice = get_user_choice()
            
            if choice == 1:
                run_live_trading()
            elif choice == 2:
                run_backtest()
            elif choice == 3:
                print("\n👋 Goodbye!")
                break
            
            if choice != 3:
                continue_choice = input("\n🔄 Continue? (y/n): ").strip().lower()
                if continue_choice not in ['y', 'yes', '']:
                    break
    
    except KeyboardInterrupt:
        print("\n👋 Exiting...")

if __name__ == "__main__":
    main() 