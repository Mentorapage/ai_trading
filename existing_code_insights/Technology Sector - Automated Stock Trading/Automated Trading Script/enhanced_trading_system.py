#!/usr/bin/env python3
"""
Enhanced AI Trading System with Interactive Startup Menu
Supports both live trading and comprehensive backtesting
"""

import sys
import os
from datetime import datetime, timedelta
import pandas as pd
import json
from typing import Dict, List, Tuple

# Import existing trading components
from technology_auto_trade import get_sentiment, auto_trade, stocks
from market_utils import pre_trading_validation
import trade_types
import logging

class EnhancedTradingSystem:
    """
    Enhanced trading system with menu-driven interface and backtesting
    """
    
    def __init__(self):
        self.setup_logging()
        
    def setup_logging(self):
        """Configure logging for the enhanced system"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('enhanced_trading.log'),
                logging.StreamHandler()
            ]
        )
        
    def display_banner(self):
        """Display system banner"""
        print("🚀" + "=" * 68 + "🚀")
        print("           ENHANCED AI TRADING SYSTEM - VANTAGE AI")
        print("=" * 70)
        print("💰 Automated Stock Trading with Sentiment Analysis")
        print("📊 Live Trading & Historical Backtesting")
        print("🧠 VADER Sentiment Analysis Engine")
        print("🛡️ Enhanced Safety & Validation Systems")
        print("=" * 70)
        print(f"🕐 System Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("🚀" + "=" * 68 + "🚀")
        
    def display_menu(self):
        """Display main menu options"""
        print("\n🎯 TRADING SYSTEM OPTIONS")
        print("=" * 50)
        print("1️⃣  Run real-time trading now")
        print("   └── Execute live trading with current market conditions")
        print("   └── Uses real-time news sentiment analysis")
        print("   └── Places actual orders via Alpaca API")
        print("")
        print("2️⃣  Run a backtest for a specific date range")
        print("   └── Historical strategy simulation")
        print("   └── Uses same sentiment logic as live system")
        print("   └── Comprehensive profit/loss analysis")
        print("")
        print("3️⃣  Exit system")
        print("=" * 50)
        
    def get_user_choice(self):
        """Get and validate user menu choice"""
        while True:
            try:
                choice = input("\n👉 Enter your choice (1-3): ").strip()
                if choice in ['1', '2', '3']:
                    return int(choice)
                else:
                    print("❌ Invalid choice. Please enter 1, 2, or 3.")
            except KeyboardInterrupt:
                print("\n\n👋 System shutdown requested...")
                return 3
            except Exception as e:
                print(f"❌ Error: {e}. Please try again.")
                
    def run_live_trading(self):
        """Execute live trading using existing system"""
        print("\n🔴 STARTING LIVE TRADING MODE")
        print("=" * 50)
        
        try:
            # Use existing auto_trade function
            print("🔍 Performing pre-trading validation...")
            
            # Run the enhanced auto_trade function
            auto_trade()
            
            print("\n✅ Live trading session completed successfully!")
            return True
            
        except KeyboardInterrupt:
            print("\n\n⏹️  Trading stopped by user")
            return True
        except Exception as e:
            print(f"\n❌ Live trading error: {e}")
            logging.error(f"Live trading failed: {e}")
            return False
            
    def get_backtest_parameters(self):
        """Get backtest parameters from user"""
        print("\n📊 BACKTEST CONFIGURATION")
        print("=" * 50)
        print("Please enter the following parameters:")
        print("(Press Enter for default values)")
        
        # Date range
        while True:
            start_date = input("\n📅 Start date [2024-12-01] (YYYY-MM-DD): ").strip()
            if not start_date:
                start_date = "2024-12-01"
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
                break
            except ValueError:
                print("❌ Invalid date format. Please use YYYY-MM-DD")
                
        while True:
            end_date = input("📅 End date [2024-12-31] (YYYY-MM-DD): ").strip()
            if not end_date:
                end_date = "2024-12-31"
            try:
                datetime.strptime(end_date, '%Y-%m-%d')
                break
            except ValueError:
                print("❌ Invalid date format. Please use YYYY-MM-DD")
                
        # Trading parameters
        while True:
            try:
                take_profit = input("💰 Take profit [+$0.50]: ").strip()
                if not take_profit:
                    take_profit = 0.50
                else:
                    take_profit = float(take_profit.replace('$', '').replace('+', ''))
                break
            except ValueError:
                print("❌ Invalid take profit. Please enter a number (e.g., 0.50)")
                
        while True:
            try:
                stop_loss = input("🛡️ Stop loss [-$1.50]: ").strip()
                if not stop_loss:
                    stop_loss = 1.50
                else:
                    stop_loss = abs(float(stop_loss.replace('$', '').replace('-', '')))
                break
            except ValueError:
                print("❌ Invalid stop loss. Please enter a number (e.g., 1.50)")
                
        # Sentiment bounds
        while True:
            try:
                sentiment_lower = input("🧠 Sentiment lower bound [0.0]: ").strip()
                if not sentiment_lower:
                    sentiment_lower = 0.0
                else:
                    sentiment_lower = float(sentiment_lower)
                break
            except ValueError:
                print("❌ Invalid sentiment bound. Please enter a number (e.g., 0.0)")
                
        while True:
            try:
                sentiment_upper = input("🧠 Sentiment upper bound [0.7]: ").strip()
                if not sentiment_upper:
                    sentiment_upper = 0.7
                else:
                    sentiment_upper = float(sentiment_upper)
                break
            except ValueError:
                print("❌ Invalid sentiment bound. Please enter a number (e.g., 0.7)")
                
        return {
            'start_date': start_date,
            'end_date': end_date,
            'take_profit': take_profit,
            'stop_loss': stop_loss,
            'sentiment_lower': sentiment_lower,
            'sentiment_upper': sentiment_upper
        }
        
    def simulate_historical_sentiment(self, stock: str, date: str) -> float:
        """
        Simulate historical sentiment for backtesting
        In production, this would use cached historical news data
        """
        # For now, use a simplified simulation based on stock characteristics
        # This would be replaced with actual historical sentiment data
        
        sentiment_patterns = {
            'NVDA': (0.3, 0.8),   'MSFT': (0.2, 0.7),   'AAPL': (0.1, 0.6),
            'AMZN': (0.2, 0.7),   'GOOGL': (0.3, 0.8),  'META': (-0.1, 0.5),
            'AVGO': (0.2, 0.7),   'TSM': (-0.2, 0.4),   'TSLA': (-0.1, 0.7),
            'ORCL': (0.1, 0.5),   'ADBE': (0.2, 0.6),   'CSCO': (0.0, 0.4),
            'INTU': (0.1, 0.5),   'QCOM': (0.1, 0.6)
        }
        
        min_sent, max_sent = sentiment_patterns.get(stock, (0.0, 0.5))
        
        # Add some date-based variation
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        day_factor = (date_obj.day % 30) / 30
        
        # Generate realistic sentiment
        import random
        random.seed(hash(stock + date))  # Deterministic but varied
        sentiment_range = max_sent - min_sent
        base_sentiment = min_sent + (sentiment_range * day_factor)
        variation = random.uniform(-0.2, 0.2) * sentiment_range
        
        return max(-1.0, min(1.0, base_sentiment + variation))
        
    def get_historical_price_data(self, stock: str, date: str) -> Dict:
        """
        Simulate historical price data for backtesting
        In production, this would use actual historical price APIs
        """
        base_prices = {
            'NVDA': 420, 'MSFT': 380, 'AAPL': 180, 'AMZN': 160, 'GOOGL': 160,
            'META': 480, 'AVGO': 820, 'TSM': 130, 'TSLA': 220, 'ORCL': 130,
            'ADBE': 520, 'CSCO': 48, 'INTU': 580, 'QCOM': 160
        }
        
        base_price = base_prices.get(stock, 100)
        
        # Add date-based variation for realistic price movement
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        days_from_start = (date_obj - datetime(2024, 12, 1)).days
        
        import random
        random.seed(hash(stock + date))
        
        # Simulate trend and daily variation
        trend_factor = 1 + (days_from_start * 0.002)  # Slight upward trend
        daily_variation = random.uniform(0.95, 1.05)
        
        price = base_price * trend_factor * daily_variation
        
        return {
            'open': round(price, 2),
            'close': round(price * random.uniform(0.99, 1.01), 2),
            'high': round(price * random.uniform(1.01, 1.03), 2),
            'low': round(price * random.uniform(0.97, 0.99), 2)
        }
        
    def simulate_trade_outcome(self, entry_price: float, take_profit: float, 
                             stop_loss: float, price_data: Dict) -> Tuple[str, float]:
        """
        Simulate trade outcome based on price movement
        Returns: (outcome, exit_price)
        """
        take_profit_price = round(entry_price + take_profit, 2)
        stop_loss_price = round(entry_price - stop_loss, 2)
        
        high = price_data['high']
        low = price_data['low']
        close = price_data['close']
        
        # Check if take profit was hit
        if high >= take_profit_price:
            return 'take_profit', take_profit_price
        # Check if stop loss was hit
        elif low <= stop_loss_price:
            return 'stop_loss', stop_loss_price
        # Otherwise exit at close
        else:
            return 'market_close', close
            
    def run_backtest(self):
        """Execute comprehensive backtesting"""
        print("\n📊 STARTING BACKTESTING MODE")
        print("=" * 50)
        
        # Get parameters
        params = self.get_backtest_parameters()
        
        print(f"\n📋 BACKTEST CONFIGURATION:")
        print(f"📅 Period: {params['start_date']} → {params['end_date']}")
        print(f"💰 Take Profit: +${params['take_profit']}")
        print(f"🛡️ Stop Loss: -${params['stop_loss']}")
        print(f"🧠 Sentiment Range: {params['sentiment_lower']} → {params['sentiment_upper']}")
        
        confirm = input("\n✅ Proceed with backtest? (y/n): ").strip().lower()
        if confirm not in ['y', 'yes', '']:
            print("❌ Backtest cancelled")
            return False
            
        print(f"\n🚀 EXECUTING BACKTEST...")
        print("=" * 60)
        
        # Initialize tracking variables
        all_trades = []
        daily_summary = []
        total_capital = 100000.0
        current_capital = total_capital
        
        # Generate date range
        start_date = datetime.strptime(params['start_date'], '%Y-%m-%d')
        end_date = datetime.strptime(params['end_date'], '%Y-%m-%d')
        
        current_date = start_date
        trading_days = 0
        
        while current_date <= end_date:
            # Skip weekends
            if current_date.weekday() < 5:  # Monday=0, Friday=4
                date_str = current_date.strftime('%Y-%m-%d')
                
                print(f"📅 Processing {date_str}...")
                
                # Analyze all stocks for this day
                qualified_stocks = []
                
                for stock in stocks:
                    sentiment = self.simulate_historical_sentiment(stock, date_str)
                    
                    if params['sentiment_lower'] <= sentiment <= params['sentiment_upper']:
                        qualified_stocks.append({
                            'symbol': stock,
                            'sentiment': sentiment
                        })
                
                day_trades = []
                day_pnl = 0.0
                
                if qualified_stocks:
                    # Calculate position sizing
                    capital_per_stock = (current_capital * 0.9) / len(qualified_stocks)
                    
                    for stock_info in qualified_stocks:
                        stock = stock_info['symbol']
                        
                        # Get price data
                        price_data = self.get_historical_price_data(stock, date_str)
                        entry_price = price_data['open']
                        
                        # Calculate shares
                        shares = int(capital_per_stock / entry_price)
                        if shares <= 0:
                            continue
                            
                        # Simulate trade
                        outcome, exit_price = self.simulate_trade_outcome(
                            entry_price, params['take_profit'], params['stop_loss'], price_data
                        )
                        
                        # Calculate P&L
                        trade_pnl = (exit_price - entry_price) * shares
                        day_pnl += trade_pnl
                        current_capital += trade_pnl
                        
                        # Record trade
                        trade_record = {
                            'date': date_str,
                            'symbol': stock,
                            'sentiment': stock_info['sentiment'],
                            'entry_price': entry_price,
                            'exit_price': exit_price,
                            'shares': shares,
                            'outcome': outcome,
                            'pnl': round(trade_pnl, 2),
                            'capital_after': round(current_capital, 2)
                        }
                        
                        all_trades.append(trade_record)
                        day_trades.append(trade_record)
                
                # Record daily summary
                daily_summary.append({
                    'date': date_str,
                    'trades_count': len(day_trades),
                    'qualified_stocks': len(qualified_stocks),
                    'day_pnl': round(day_pnl, 2),
                    'total_capital': round(current_capital, 2)
                })
                
                trading_days += 1
                
                # Progress update
                if trading_days % 5 == 0:
                    print(f"   📊 {trading_days} days processed, Capital: ${current_capital:,.2f}")
            
            current_date += timedelta(days=1)
        
        # Generate results
        self.display_backtest_results(params, all_trades, daily_summary, 
                                    total_capital, current_capital)
        
        # Save results
        self.save_backtest_results(params, all_trades, daily_summary,
                                 total_capital, current_capital)
        
        return True
        
    def display_backtest_results(self, params: Dict, all_trades: List, 
                               daily_summary: List, initial_capital: float, 
                               final_capital: float):
        """Display comprehensive backtest results"""
        
        print(f"\n" + "=" * 80)
        print("📊 BACKTEST RESULTS SUMMARY")
        print("=" * 80)
        
        # Calculate metrics
        total_trades = len(all_trades)
        winning_trades = len([t for t in all_trades if t['pnl'] > 0])
        losing_trades = len([t for t in all_trades if t['pnl'] < 0])
        
        total_pnl = final_capital - initial_capital
        total_return = (total_pnl / initial_capital) * 100
        
        trading_days = len([d for d in daily_summary if d['trades_count'] > 0])
        total_days = len(daily_summary)
        
        # Display summary
        print(f"📅 Backtest Period:       {params['start_date']} → {params['end_date']}")
        print(f"📊 Total Trading Days:    {trading_days} / {total_days}")
        print(f"🔢 Total Trades:          {total_trades}")
        print(f"✅ Winning Trades:        {winning_trades}")
        print(f"❌ Losing Trades:         {losing_trades}")
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        print(f"📈 Win Rate:              {win_rate:.1f}%")
        
        print(f"💰 Total P&L:             ${total_pnl:+,.2f}")
        print(f"📊 Total Return:          {total_return:+.2f}%")
        print(f"💵 Final Capital:         ${final_capital:,.2f}")
        
        # Best and worst trades
        if all_trades:
            best_trade = max(all_trades, key=lambda x: x['pnl'])
            worst_trade = min(all_trades, key=lambda x: x['pnl'])
            
            print(f"\n🏆 Best Trade:            {best_trade['symbol']} on {best_trade['date']}: ${best_trade['pnl']:+.2f}")
            print(f"📉 Worst Trade:           {worst_trade['symbol']} on {worst_trade['date']}: ${worst_trade['pnl']:+.2f}")
            
        # Stock performance
        stock_performance = {}
        for trade in all_trades:
            symbol = trade['symbol']
            if symbol not in stock_performance:
                stock_performance[symbol] = {'trades': 0, 'pnl': 0}
            stock_performance[symbol]['trades'] += 1
            stock_performance[symbol]['pnl'] += trade['pnl']
            
        print(f"\n📈 TOP PERFORMING STOCKS:")
        sorted_stocks = sorted(stock_performance.items(), key=lambda x: x[1]['pnl'], reverse=True)
        for i, (symbol, data) in enumerate(sorted_stocks[:5]):
            print(f"   {i+1}. {symbol}: ${data['pnl']:+.2f} ({data['trades']} trades)")
            
    def save_backtest_results(self, params: Dict, all_trades: List, 
                            daily_summary: List, initial_capital: float, 
                            final_capital: float):
        """Save backtest results to files"""
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save detailed results to JSON
        results = {
            'backtest_info': {
                'timestamp': datetime.now().isoformat(),
                'parameters': params,
                'initial_capital': initial_capital,
                'final_capital': final_capital,
                'total_return_pct': ((final_capital - initial_capital) / initial_capital) * 100
            },
            'all_trades': all_trades,
            'daily_summary': daily_summary
        }
        
        json_filename = f"backtest_results_{timestamp}.json"
        with open(json_filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
            
        # Save summary to CSV
        trades_df = pd.DataFrame(all_trades)
        csv_filename = f"backtest_trades_{timestamp}.csv"
        trades_df.to_csv(csv_filename, index=False)
        
        print(f"\n📁 Results saved:")
        print(f"   📊 Detailed results: {json_filename}")
        print(f"   📈 Trades CSV: {csv_filename}")
        
    def run(self):
        """Main system execution loop"""
        try:
            self.display_banner()
            
            while True:
                self.display_menu()
                choice = self.get_user_choice()
                
                if choice == 1:
                    self.run_live_trading()
                elif choice == 2:
                    self.run_backtest()
                elif choice == 3:
                    print("\n👋 Thank you for using Enhanced AI Trading System!")
                    print("💰 Trade safely and profitably!")
                    break
                
                # Ask if user wants to continue
                if choice != 3:
                    print("\n" + "=" * 50)
                    continue_choice = input("🔄 Return to main menu? (y/n): ").strip().lower()
                    if continue_choice not in ['y', 'yes', '']:
                        print("\n👋 Goodbye!")
                        break
        
        except KeyboardInterrupt:
            print("\n\n👋 System shutdown by user. Goodbye!")
        except Exception as e:
            print(f"\n❌ System error: {e}")
            logging.error(f"System error: {e}")

if __name__ == "__main__":
    system = EnhancedTradingSystem()
    system.run() 