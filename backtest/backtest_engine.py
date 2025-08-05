#!/usr/bin/env python3
"""
Isolated Backtesting Engine for AI Trading System
Simulates trading strategies on historical data without API calls
"""

import sys
import os
import json
import pandas as pd
from datetime import datetime, timedelta, time as time_obj
from typing import Dict, List, Tuple, Optional
import random
import logging

# Add paths for importing sentiment logic
sys.path.append("../existing_code_insights/Technology Sector - Automated Stock Trading/Automated Trading Script")

class BacktestEngine:
    """
    Isolated backtesting engine that simulates trading without live API calls
    """
    
    def __init__(self):
        self.results = []
        self.daily_results = []
        self.total_capital = 100000.0  # Starting capital
        self.current_capital = self.total_capital
        self.positions = {}
        self.trades_log = []
        
        # Default parameters
        self.config = {
            'start_date': '2024-08-01',
            'end_date': '2024-08-31', 
            'entry_time': '06:30',
            'exit_time': '12:59',
            'take_profit': 0.50,
            'stop_loss': 1.50,
            'sentiment_min': 0.0,
            'sentiment_max': 0.7,
            'capital_per_trade': 0.9,  # 90% of available capital
        }
        
        # Stock universe (same as live system)
        self.stocks = [
            'NVDA', 'MSFT', 'AAPL', 'AMZN', 'GOOGL', 
            'META', 'AVGO', 'TSM', 'TSLA', 'ORCL', 
            'ADBE', 'CSCO', 'INTU', 'QCOM'
        ]
        
        self.setup_logging()

    def setup_logging(self):
        """Setup logging for backtest operations"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - BACKTEST - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('reports/backtest.log'),
                logging.StreamHandler()
            ]
        )

    def get_historical_sentiment(self, symbol: str, date: str) -> float:
        """
        Simulate historical sentiment analysis
        In production, this would use cached historical news data
        """
        try:
            # Import the sentiment function from live system
            from technology_auto_trade import get_sentiment
            
            # For backtesting, we'll simulate sentiment with realistic patterns
            # This would be replaced with actual historical sentiment data
            
            # Create realistic sentiment patterns based on stock characteristics
            sentiment_patterns = {
                'NVDA': (0.4, 0.8),    # Generally positive AI/tech sentiment
                'MSFT': (0.3, 0.7),    # Stable positive sentiment  
                'AAPL': (0.2, 0.6),    # Mixed to positive sentiment
                'AMZN': (0.3, 0.7),    # Generally positive
                'GOOGL': (0.4, 0.8),   # Positive tech sentiment
                'META': (0.0, 0.6),    # More volatile sentiment
                'AVGO': (0.3, 0.7),    # Positive tech sentiment
                'TSM': (-0.2, 0.4),    # Mixed sentiment (geopolitical)
                'TSLA': (-0.1, 0.8),   # Highly volatile sentiment
                'ORCL': (0.2, 0.6),    # Stable enterprise sentiment
                'ADBE': (0.3, 0.7),    # Positive creative software
                'CSCO': (0.1, 0.5),    # Conservative networking
                'INTU': (0.2, 0.6),    # Stable financial software
                'QCOM': (0.2, 0.7),    # Positive mobile/5G sentiment
            }
            
            # Get sentiment range for this stock
            min_sent, max_sent = sentiment_patterns.get(symbol, (0.0, 0.5))
            
            # Add some date-based variation to simulate market cycles
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            day_factor = (date_obj.day % 30) / 30  # 0-1 based on day of month
            
            # Generate realistic sentiment with some randomness
            sentiment_range = max_sent - min_sent
            base_sentiment = min_sent + (sentiment_range * day_factor)
            
            # Add random variation (±20%)
            variation = random.uniform(-0.2, 0.2) * sentiment_range
            final_sentiment = base_sentiment + variation
            
            # Clamp to realistic bounds
            return max(-1.0, min(1.0, final_sentiment))
            
        except ImportError:
            # Fallback if sentiment module not available
            return random.uniform(-0.5, 0.8)

    def get_historical_price(self, symbol: str, date: str, time_str: str = '09:30') -> Dict:
        """
        Simulate historical price data
        In production, this would use actual historical price APIs
        """
        
        # Base prices for simulation (approximate recent levels)
        base_prices = {
            'NVDA': 450, 'MSFT': 420, 'AAPL': 190, 'AMZN': 170, 'GOOGL': 170,
            'META': 520, 'AVGO': 870, 'TSM': 140, 'TSLA': 240, 'ORCL': 140,
            'ADBE': 570, 'CSCO': 52, 'INTU': 630, 'QCOM': 170
        }
        
        base_price = base_prices.get(symbol, 100)
        
        # Add some date-based variation to simulate market movement
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        days_from_start = (date_obj - datetime(2024, 8, 1)).days
        
        # Simulate market trend
        trend_factor = 1 + (days_from_start * 0.001)  # Slight upward trend
        
        # Add random daily variation
        daily_variation = random.uniform(0.95, 1.05)
        
        # Calculate simulated price
        price = base_price * trend_factor * daily_variation
        
        # Simulate intraday movement for entry/exit prices
        intraday_factor = random.uniform(0.99, 1.01)
        
        return {
            'open': round(price, 2),
            'current': round(price * intraday_factor, 2),
            'high': round(price * random.uniform(1.01, 1.03), 2),
            'low': round(price * random.uniform(0.97, 0.99), 2)
        }

    def run_interactive_backtest(self):
        """Run interactive backtesting with user input"""
        print("📊 INTERACTIVE BACKTESTING SETUP")
        print("=" * 60)
        
        # Get user parameters
        self.get_backtest_parameters()
        
        # Confirm parameters
        self.display_backtest_config()
        
        confirm = input("\n✅ Proceed with this configuration? (y/n): ").strip().lower()
        if confirm not in ['y', 'yes', '']:
            print("❌ Backtest cancelled by user")
            return
        
        # Run the backtest
        print("\n🚀 STARTING BACKTEST SIMULATION...")
        print("=" * 60)
        
        self.execute_backtest()
        
        # Generate and display results
        self.generate_backtest_report()

    def get_backtest_parameters(self):
        """Get backtest parameters from user input"""
        print("\n🔁 BACKTEST SETUP - Enter your parameters:")
        print("(Press Enter to use default values)")
        
        # Date Range
        start_date = input(f"📅 Start Date [{self.config['start_date']}]: ").strip()
        if start_date:
            self.config['start_date'] = start_date
            
        end_date = input(f"📅 End Date [{self.config['end_date']}]: ").strip()
        if end_date:
            self.config['end_date'] = end_date
        
        # Trading Times
        entry_time = input(f"🕐 Entry Time [{self.config['entry_time']}]: ").strip()
        if entry_time:
            self.config['entry_time'] = entry_time
            
        exit_time = input(f"🕐 Exit Time [{self.config['exit_time']}]: ").strip()
        if exit_time:
            self.config['exit_time'] = exit_time
        
        # Trading Parameters
        take_profit = input(f"💰 Take-Profit [${self.config['take_profit']}]: ").strip()
        if take_profit:
            self.config['take_profit'] = float(take_profit)
            
        stop_loss = input(f"🛡️ Stop-Loss [${self.config['stop_loss']}]: ").strip()
        if stop_loss:
            self.config['stop_loss'] = float(stop_loss)
        
        # Sentiment Parameters
        sentiment_min = input(f"🧠 Sentiment Min [{self.config['sentiment_min']}]: ").strip()
        if sentiment_min:
            self.config['sentiment_min'] = float(sentiment_min)
            
        sentiment_max = input(f"🧠 Sentiment Max [{self.config['sentiment_max']}]: ").strip()
        if sentiment_max:
            self.config['sentiment_max'] = float(sentiment_max)

    def display_backtest_config(self):
        """Display the current backtest configuration"""
        print("\n📋 BACKTEST CONFIGURATION")
        print("=" * 50)
        print(f"📅 Date Range: {self.config['start_date']} → {self.config['end_date']}")
        print(f"🕐 Entry Time: {self.config['entry_time']} AM")
        print(f"🕐 Exit Time: {self.config['exit_time']} PM")
        print(f"💰 Take-Profit: ${self.config['take_profit']}")
        print(f"🛡️ Stop-Loss: ${self.config['stop_loss']}")
        print(f"🧠 Sentiment Range: {self.config['sentiment_min']} → {self.config['sentiment_max']}")
        print(f"💵 Starting Capital: ${self.total_capital:,.2f}")
        print(f"📈 Stocks: {len(self.stocks)} symbols")

    def execute_backtest(self):
        """Execute the main backtesting logic"""
        
        # Generate trading days
        start_date = datetime.strptime(self.config['start_date'], '%Y-%m-%d')
        end_date = datetime.strptime(self.config['end_date'], '%Y-%m-%d')
        
        current_date = start_date
        trading_days = 0
        
        while current_date <= end_date:
            # Skip weekends
            if current_date.weekday() < 5:  # Monday = 0, Friday = 4
                self.simulate_trading_day(current_date.strftime('%Y-%m-%d'))
                trading_days += 1
                
                # Progress indicator
                if trading_days % 5 == 0:
                    print(f"📅 Processed {trading_days} trading days... Capital: ${self.current_capital:,.2f}")
            
            current_date += timedelta(days=1)
        
        print(f"\n✅ Backtest completed: {trading_days} trading days processed")

    def simulate_trading_day(self, date: str):
        """Simulate one trading day"""
        daily_trades = 0
        daily_pnl = 0
        qualifying_stocks = []
        
        logging.info(f"Simulating trading day: {date}")
        
        # Step 1: Analyze sentiment for all stocks
        for stock in self.stocks:
            sentiment = self.get_historical_sentiment(stock, date)
            
            # Check if stock qualifies based on sentiment
            if self.config['sentiment_min'] <= sentiment <= self.config['sentiment_max']:
                qualifying_stocks.append({
                    'symbol': stock,
                    'sentiment': sentiment
                })
        
        if not qualifying_stocks:
            logging.info(f"No qualifying stocks for {date}")
            self.daily_results.append({
                'date': date,
                'trades': 0,
                'pnl': 0,
                'capital': self.current_capital
            })
            return
        
        # Step 2: Execute trades for qualifying stocks
        capital_per_stock = (self.current_capital * self.config['capital_per_trade']) / len(qualifying_stocks)
        
        for stock_info in qualifying_stocks:
            symbol = stock_info['symbol']
            
            # Get entry price
            entry_prices = self.get_historical_price(symbol, date, self.config['entry_time'])
            entry_price = entry_prices['current']
            
            # Calculate position size
            shares = int(capital_per_stock / entry_price)
            if shares <= 0:
                continue
            
            # Simulate the trade outcome
            trade_result = self.simulate_trade_outcome(
                symbol, entry_price, shares, date
            )
            
            if trade_result:
                daily_trades += 1
                daily_pnl += trade_result['pnl']
                self.current_capital += trade_result['pnl']
                
                # Log the trade
                self.trades_log.append({
                    'date': date,
                    'symbol': symbol,
                    'sentiment': stock_info['sentiment'],
                    'entry_price': entry_price,
                    'exit_price': trade_result['exit_price'],
                    'shares': shares,
                    'pnl': trade_result['pnl'],
                    'outcome': trade_result['outcome']
                })
        
        # Record daily results
        self.daily_results.append({
            'date': date,
            'trades': daily_trades,
            'pnl': daily_pnl,
            'capital': self.current_capital,
            'qualifying_stocks': len(qualifying_stocks)
        })
        
        logging.info(f"Day {date}: {daily_trades} trades, P&L: ${daily_pnl:.2f}")

    def simulate_trade_outcome(self, symbol: str, entry_price: float, shares: int, date: str) -> Optional[Dict]:
        """
        Simulate the outcome of a single trade
        Returns trade result or None if trade doesn't execute
        """
        
        # Calculate target prices
        take_profit_price = round(entry_price + self.config['take_profit'], 2)
        stop_loss_price = round(entry_price - self.config['stop_loss'], 2)
        
        # Get exit time prices (simulate intraday movement)
        exit_prices = self.get_historical_price(symbol, date, self.config['exit_time'])
        
        # Simulate realistic price movement during the day
        # We'll use the high/low from our price simulation to determine outcomes
        day_high = exit_prices['high']
        day_low = exit_prices['low']
        final_price = exit_prices['current']
        
        # Determine trade outcome based on price movement
        outcome = None
        exit_price = None
        
        # Check if take-profit was hit
        if day_high >= take_profit_price:
            outcome = 'take_profit'
            exit_price = take_profit_price
        # Check if stop-loss was hit
        elif day_low <= stop_loss_price:
            outcome = 'stop_loss'
            exit_price = stop_loss_price
        # Otherwise, exit at final price
        else:
            outcome = 'time_exit'
            exit_price = final_price
        
        # Calculate P&L
        pnl = (exit_price - entry_price) * shares
        
        return {
            'exit_price': exit_price,
            'pnl': pnl,
            'outcome': outcome
        }

    def generate_backtest_report(self):
        """Generate comprehensive backtest report"""
        print("\n" + "=" * 70)
        print("📊 BACKTEST RESULTS SUMMARY")
        print("=" * 70)
        
        # Calculate statistics
        total_trades = len(self.trades_log)
        winning_trades = len([t for t in self.trades_log if t['pnl'] > 0])
        losing_trades = len([t for t in self.trades_log if t['pnl'] < 0])
        
        total_pnl = self.current_capital - self.total_capital
        total_return = (total_pnl / self.total_capital) * 100
        
        trading_days = len([d for d in self.daily_results if d['trades'] > 0])
        total_days = len(self.daily_results)
        
        avg_daily_return = 0
        if trading_days > 0:
            daily_returns = [(d['capital'] - self.total_capital) / self.total_capital * 100 for d in self.daily_results]
            avg_daily_return = sum(daily_returns) / len(daily_returns)
        
        # Calculate max drawdown
        max_drawdown = self.calculate_max_drawdown()
        
        # Display results
        print(f"📅 Backtest Period:       {self.config['start_date']} → {self.config['end_date']}")
        print(f"📊 Total Trading Days:    {trading_days} / {total_days}")
        print(f"🔢 Total Trades:          {total_trades}")
        print(f"✅ Winning Trades:        {winning_trades}")
        print(f"❌ Losing Trades:         {losing_trades}")
        print(f"📈 Win Rate:              {(winning_trades/total_trades*100):.1f}%" if total_trades > 0 else "N/A")
        print(f"💰 Total P&L:             ${total_pnl:+,.2f}")
        print(f"📊 Total Return:          {total_return:+.2f}%")
        print(f"📅 Avg Daily Return:      {avg_daily_return:+.3f}%")
        print(f"📉 Max Drawdown:          {max_drawdown:.2f}%")
        print(f"💵 Final Capital:         ${self.current_capital:,.2f}")
        
        # Save detailed report
        self.save_detailed_report()
        
        print(f"\n📁 Detailed report saved to: reports/backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

    def calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown during the backtest"""
        if not self.daily_results:
            return 0.0
        
        peak = self.total_capital
        max_dd = 0.0
        
        for day in self.daily_results:
            capital = day['capital']
            if capital > peak:
                peak = capital
            
            drawdown = ((peak - capital) / peak) * 100
            max_dd = max(max_dd, drawdown)
        
        return max_dd

    def save_detailed_report(self):
        """Save detailed backtest results to JSON file"""
        report = {
            'backtest_config': self.config,
            'summary': {
                'total_trades': len(self.trades_log),
                'winning_trades': len([t for t in self.trades_log if t['pnl'] > 0]),
                'losing_trades': len([t for t in self.trades_log if t['pnl'] < 0]),
                'total_pnl': self.current_capital - self.total_capital,
                'total_return_pct': ((self.current_capital - self.total_capital) / self.total_capital) * 100,
                'max_drawdown': self.calculate_max_drawdown(),
                'final_capital': self.current_capital
            },
            'daily_results': self.daily_results,
            'trades_log': self.trades_log,
            'generated_at': datetime.now().isoformat()
        }
        
        # Create reports directory if it doesn't exist
        os.makedirs('reports', exist_ok=True)
        
        # Save to JSON file
        filename = f"reports/backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logging.info(f"Detailed backtest report saved to {filename}")

if __name__ == "__main__":
    # Direct execution for testing
    backtest = BacktestEngine()
    backtest.run_interactive_backtest() 