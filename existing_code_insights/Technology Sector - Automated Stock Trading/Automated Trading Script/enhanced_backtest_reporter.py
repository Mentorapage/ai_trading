#!/usr/bin/env python3
"""
Enhanced Backtesting System with Comprehensive Excel Reporting
Generates detailed reports with trade summaries, news analysis, and performance metrics
"""

import sys
import os
from datetime import datetime, timedelta, time as dt_time
import pandas as pd
import json
import random
from typing import Dict, List, Tuple
import logging
import finnhub
from dotenv import load_dotenv

# Import existing trading components
from technology_auto_trade import get_sentiment, stocks
from news_logger import NewsLogger

# Load environment variables
load_dotenv(dotenv_path='.env')

class EnhancedBacktestReporter:
    """
    Enhanced backtesting system with comprehensive reporting and news analysis
    """
    
    def __init__(self):
        self.setup_logging()
        self.news_logger = NewsLogger(log_directory="backtest_logs")
        self.trades_data = []
        self.news_data = []
        self.summary_stats = {}
        
        # Initialize Finnhub client for real news data
        self.finnhub_api_key = os.getenv('finnhubkey')
        if self.finnhub_api_key:
            self.finnhub_client = finnhub.Client(api_key=self.finnhub_api_key)
        else:
            self.finnhub_client = None
            print("⚠️  Finnhub API key not found - using simulated news data")
        
    def setup_logging(self):
        """Configure logging for backtest operations"""
        os.makedirs('backtest_logs', exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - BACKTEST - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('backtest_logs/backtest_execution.log'),
                logging.StreamHandler()
            ]
        )
        
    def display_banner(self):
        """Display enhanced system banner"""
        print("🚀" + "=" * 68 + "🚀")
        print("    ENHANCED AI TRADING SYSTEM - COMPREHENSIVE BACKTESTING")
        print("=" * 70)
        print("💰 Automated Stock Trading with Sentiment Analysis")
        print("📊 Advanced Backtesting with Excel Reporting")
        print("📰 Real News Analysis & Trade Documentation") 
        print("🧠 VADER Sentiment Analysis Engine")
        print("=" * 70)
        print(f"🕐 System Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("🚀" + "=" * 68 + "🚀")
        
    def get_backtest_parameters(self):
        """Get comprehensive backtest parameters from user"""
        print("\n📊 ENHANCED BACKTEST CONFIGURATION")
        print("=" * 60)
        print("Configure your backtest parameters:")
        
        # Date range
        start_date = input("📅 Start date (YYYY-MM-DD) [2024-12-01]: ").strip()
        if not start_date:
            start_date = "2024-12-01"
            
        end_date = input("📅 End date (YYYY-MM-DD) [2024-12-05]: ").strip()
        if not end_date:
            end_date = "2024-12-05"
            
        # Trading parameters
        take_profit = input("💰 Take profit (+$0.50): ").strip()
        take_profit = 0.50 if not take_profit else float(take_profit.replace('$', '').replace('+', ''))
        
        stop_loss = input("🛡️ Stop loss (-$1.50): ").strip()
        stop_loss = 1.50 if not stop_loss else abs(float(stop_loss.replace('$', '').replace('-', '')))
        
        # Sentiment parameters
        sentiment_lower = input("🧠 Sentiment lower bound [0.0]: ").strip()
        sentiment_lower = 0.0 if not sentiment_lower else float(sentiment_lower)
        
        sentiment_upper = input("🧠 Sentiment upper bound [0.7]: ").strip()
        sentiment_upper = 0.7 if not sentiment_upper else float(sentiment_upper)
        
        # Trading times
        entry_time = input("🕐 Entry time (HH:MM) [09:30]: ").strip()
        if not entry_time:
            entry_time = "09:30"
            
        exit_time = input("🕐 Exit time (HH:MM) [15:59]: ").strip()
        if not exit_time:
            exit_time = "15:59"
        
        return {
            'start_date': start_date,
            'end_date': end_date,
            'take_profit': take_profit,
            'stop_loss': stop_loss,
            'sentiment_lower': sentiment_lower,
            'sentiment_upper': sentiment_upper,
            'entry_time': entry_time,
            'exit_time': exit_time
        }
        
    def get_real_news_sentiment(self, stock: str, date: str) -> Tuple[float, List[Dict]]:
        """
        Get real news sentiment for a stock on a specific date
        Returns: (sentiment_score, news_articles_list)
        """
        articles_data = []
        
        if self.finnhub_client:
            try:
                # Try to get real news data
                all_articles = self.finnhub_client.company_news(stock, _from=date, to=date)
                
                if all_articles:
                    # Use real sentiment analysis (same as live system)
                    sentiment_score = get_sentiment(stock)
                    
                    # Process articles for reporting
                    for article in all_articles[:10]:  # Limit to 10 articles
                        published_time = datetime.fromtimestamp(article['datetime'])
                        
                        articles_data.append({
                            'date': date,
                            'stock': stock,
                            'headline': article.get('headline', 'No headline'),
                            'summary': article.get('summary', 'No summary')[:200] + '...',
                            'source': article.get('source', 'Unknown'),
                            'url': article.get('url', ''),
                            'published_time': published_time.strftime('%Y-%m-%d %H:%M:%S'),
                            'sentiment_score': sentiment_score,
                            'sentiment_category': self.categorize_sentiment(sentiment_score)
                        })
                    
                    return sentiment_score, articles_data
                    
            except Exception as e:
                logging.warning(f"Error fetching real news for {stock} on {date}: {e}")
        
        # Fallback to simulated sentiment
        sentiment_score = self.simulate_historical_sentiment(stock, date)
        
        # Create simulated news data for reporting
        simulated_articles = self.generate_simulated_news(stock, date, sentiment_score)
        articles_data.extend(simulated_articles)
        
        return sentiment_score, articles_data
        
    def categorize_sentiment(self, score: float) -> str:
        """Categorize sentiment score"""
        if score >= 0.6:
            return "Very Positive"
        elif score >= 0.2:
            return "Positive"
        elif score >= -0.2:
            return "Neutral"
        elif score >= -0.6:
            return "Negative"
        else:
            return "Very Negative"
            
    def simulate_historical_sentiment(self, stock: str, date: str) -> float:
        """Simulate historical sentiment (fallback when real data unavailable)"""
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
        
    def generate_simulated_news(self, stock: str, date: str, sentiment: float) -> List[Dict]:
        """Generate simulated news articles for reporting when real data unavailable"""
        
        # Sample news templates based on sentiment
        if sentiment > 0.4:
            headlines = [
                f"{stock} Reports Strong Quarterly Earnings Beat",
                f"{stock} Announces Strategic Partnership Expansion", 
                f"Analysts Upgrade {stock} Price Target on Innovation",
                f"{stock} Launches Revolutionary Product Line"
            ]
        elif sentiment > 0.0:
            headlines = [
                f"{stock} Maintains Steady Market Position",
                f"{stock} CEO Discusses Future Growth Plans",
                f"{stock} Quarterly Results Meet Expectations",
                f"Market Outlook Positive for {stock} Sector"
            ]
        else:
            headlines = [
                f"{stock} Faces Regulatory Challenges",
                f"Market Volatility Affects {stock} Performance",
                f"{stock} Reports Mixed Quarterly Results",
                f"Analysts Express Caution on {stock} Outlook"
            ]
        
        articles = []
        for i, headline in enumerate(headlines[:3]):  # Generate 3 articles
            articles.append({
                'date': date,
                'stock': stock,
                'headline': headline,
                'summary': f"Simulated news summary for {stock} indicating {self.categorize_sentiment(sentiment).lower()} market sentiment...",
                'source': 'Simulated Data',
                'url': f'https://simulated-news.com/{stock.lower()}-{date}-{i+1}',
                'published_time': f"{date} {9+i:02d}:30:00",
                'sentiment_score': round(sentiment, 4),
                'sentiment_category': self.categorize_sentiment(sentiment)
            })
            
        return articles
        
    def get_historical_prices(self, stock: str, date: str) -> Dict:
        """Get historical price data (simulated for backtesting)"""
        base_prices = {
            'NVDA': 420, 'MSFT': 380, 'AAPL': 180, 'AMZN': 160, 'GOOGL': 160,
            'META': 480, 'AVGO': 820, 'TSM': 130, 'TSLA': 220, 'ORCL': 130,
            'ADBE': 520, 'CSCO': 48, 'INTU': 580, 'QCOM': 160
        }
        
        base_price = base_prices.get(stock, 100)
        
        # Add realistic price variation
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        days_from_start = (date_obj - datetime(2024, 12, 1)).days
        
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
        
    def simulate_trade_execution(self, entry_price: float, take_profit: float, 
                                stop_loss: float, price_data: Dict, 
                                entry_time: str, exit_time: str) -> Dict:
        """Simulate detailed trade execution with timing"""
        tp_price = round(entry_price + take_profit, 2)
        sl_price = round(entry_price - stop_loss, 2)
        
        high = price_data['high']
        low = price_data['low']
        close = price_data['close']
        
        # Determine outcome and exit details
        if high >= tp_price:
            outcome = 'take_profit'
            exit_price = tp_price
            # Simulate random time during trading day when TP was hit
            exit_time_actual = self.generate_random_exit_time(entry_time, exit_time)
        elif low <= sl_price:
            outcome = 'stop_loss'
            exit_price = sl_price
            # Simulate random time when SL was hit
            exit_time_actual = self.generate_random_exit_time(entry_time, exit_time)
        else:
            outcome = 'market_close'
            exit_price = close
            exit_time_actual = exit_time
        
        return {
            'outcome': outcome,
            'exit_price': exit_price,
            'exit_time': exit_time_actual
        }
        
    def generate_random_exit_time(self, entry_time: str, max_exit_time: str) -> str:
        """Generate random exit time between entry and max exit"""
        entry_hour, entry_minute = map(int, entry_time.split(':'))
        exit_hour, exit_minute = map(int, max_exit_time.split(':'))
        
        # Convert to minutes for easier calculation
        entry_minutes = entry_hour * 60 + entry_minute
        exit_minutes = exit_hour * 60 + exit_minute
        
        # Random time between entry and exit
        random_minutes = random.randint(entry_minutes + 30, exit_minutes)  # At least 30 min holding
        
        hour = random_minutes // 60
        minute = random_minutes % 60
        
        return f"{hour:02d}:{minute:02d}"
        
    def calculate_holding_duration(self, entry_time: str, exit_time: str) -> str:
        """Calculate holding duration in hours and minutes"""
        entry_hour, entry_minute = map(int, entry_time.split(':'))
        exit_hour, exit_minute = map(int, exit_time.split(':'))
        
        entry_total_minutes = entry_hour * 60 + entry_minute
        exit_total_minutes = exit_hour * 60 + exit_minute
        
        duration_minutes = exit_total_minutes - entry_total_minutes
        
        hours = duration_minutes // 60
        minutes = duration_minutes % 60
        
        return f"{hours}h {minutes}m"
        
    def run_enhanced_backtest(self):
        """Execute comprehensive backtesting with detailed reporting"""
        self.display_banner()
        
        params = self.get_backtest_parameters()
        
        print(f"\n📋 ENHANCED BACKTEST CONFIGURATION:")
        print(f"📅 Period: {params['start_date']} → {params['end_date']}")
        print(f"💰 TP: +${params['take_profit']}, SL: -${params['stop_loss']}")
        print(f"🧠 Sentiment: {params['sentiment_lower']} → {params['sentiment_upper']}")
        print(f"🕐 Trading Hours: {params['entry_time']} → {params['exit_time']}")
        
        confirm = input("\n✅ Start enhanced backtest with Excel reporting? (y/n): ").strip().lower()
        if confirm not in ['y', 'yes', '']:
            print("❌ Backtest cancelled")
            return
            
        print(f"\n🚀 EXECUTING ENHANCED BACKTEST...")
        print("=" * 60)
        
        # Initialize tracking
        self.trades_data = []
        self.news_data = []
        total_capital = 100000.0
        current_capital = total_capital
        
        # Generate date range
        start_date = datetime.strptime(params['start_date'], '%Y-%m-%d')
        end_date = datetime.strptime(params['end_date'], '%Y-%m-%d')
        
        current_date = start_date
        trading_days = 0
        
        while current_date <= end_date:
            if current_date.weekday() < 5:  # Weekdays only
                date_str = current_date.strftime('%Y-%m-%d')
                
                print(f"📅 Processing {date_str}...")
                
                # Analyze all stocks for sentiment and news
                qualified_stocks = []
                
                for stock in stocks:
                    # Get real or simulated sentiment and news
                    sentiment, articles = self.get_real_news_sentiment(stock, date_str)
                    
                    # Add news data for reporting
                    self.news_data.extend(articles)
                    
                    # Check qualification
                    if params['sentiment_lower'] <= sentiment <= params['sentiment_upper']:
                        qualified_stocks.append({
                            'symbol': stock,
                            'sentiment': sentiment
                        })
                        print(f"   ✅ {stock}: {sentiment:.4f} - QUALIFIED")
                    else:
                        print(f"   ❌ {stock}: {sentiment:.4f} - rejected")
                
                # Execute trades for qualified stocks
                if qualified_stocks:
                    capital_per_stock = (current_capital * 0.9) / len(qualified_stocks)
                    
                    for stock_info in qualified_stocks:
                        stock = stock_info['symbol']
                        
                        # Get price data
                        price_data = self.get_historical_prices(stock, date_str)
                        entry_price = price_data['open']
                        
                        # Calculate shares
                        shares = int(capital_per_stock / entry_price)
                        if shares <= 0:
                            continue
                        
                        # Simulate trade execution
                        trade_result = self.simulate_trade_execution(
                            entry_price, params['take_profit'], params['stop_loss'],
                            price_data, params['entry_time'], params['exit_time']
                        )
                        
                        # Calculate P&L
                        exit_price = trade_result['exit_price']
                        trade_pnl = (exit_price - entry_price) * shares
                        current_capital += trade_pnl
                        
                        # Calculate holding duration
                        holding_duration = self.calculate_holding_duration(
                            params['entry_time'], trade_result['exit_time']
                        )
                        
                        # Record detailed trade data
                        trade_record = {
                            'Date': date_str,
                            'Stock': stock,
                            'Entry_Price': entry_price,
                            'Exit_Price': exit_price,
                            'Entry_Time': params['entry_time'],
                            'Exit_Time': trade_result['exit_time'],
                            'Take_Profit': round(entry_price + params['take_profit'], 2),
                            'Stop_Loss': round(entry_price - params['stop_loss'], 2),
                            'Trade_Result': trade_result['outcome'],
                            'Holding_Duration': holding_duration,
                            'Shares': shares,
                            'Profit_Loss': round(trade_pnl, 2),
                            'Sentiment_Score': round(stock_info['sentiment'], 4)
                        }
                        
                        self.trades_data.append(trade_record)
                        
                        print(f"   💰 {stock}: {shares} shares @ ${entry_price:.2f} → ${exit_price:.2f} "
                              f"({trade_result['outcome']}) = ${trade_pnl:+.2f}")
                
                trading_days += 1
                print(f"   📊 Day Capital: ${current_capital:,.2f}")
                print()
            
            current_date += timedelta(days=1)
        
        # Generate comprehensive summary
        self.summary_stats = self.calculate_summary_statistics(
            params, self.trades_data, total_capital, current_capital
        )
        
        # Display results
        self.display_comprehensive_results()
        
        # Generate Excel report
        self.generate_excel_report(params)
        
        return True
        
    def calculate_summary_statistics(self, params: Dict, trades: List[Dict], 
                                   initial_capital: float, final_capital: float) -> Dict:
        """Calculate comprehensive summary statistics"""
        if not trades:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'avg_holding_time': '0h 0m',
                'total_pnl': 0,
                'total_return': 0,
                'best_stock': 'N/A',
                'worst_stock': 'N/A'
            }
        
        winning_trades = [t for t in trades if t['Profit_Loss'] > 0]
        losing_trades = [t for t in trades if t['Profit_Loss'] < 0]
        
        # Calculate average holding time
        total_minutes = 0
        for trade in trades:
            duration = trade['Holding_Duration']
            if 'h' in duration and 'm' in duration:
                parts = duration.replace('h', '').replace('m', '').split()
                hours = int(parts[0])
                minutes = int(parts[1])
                total_minutes += hours * 60 + minutes
        
        avg_minutes = total_minutes // len(trades) if trades else 0
        avg_hours = avg_minutes // 60
        avg_mins = avg_minutes % 60
        avg_holding_time = f"{avg_hours}h {avg_mins}m"
        
        # Stock performance analysis
        stock_performance = {}
        for trade in trades:
            stock = trade['Stock']
            if stock not in stock_performance:
                stock_performance[stock] = 0
            stock_performance[stock] += trade['Profit_Loss']
        
        best_stock = max(stock_performance.items(), key=lambda x: x[1]) if stock_performance else ('N/A', 0)
        worst_stock = min(stock_performance.items(), key=lambda x: x[1]) if stock_performance else ('N/A', 0)
        
        return {
            'total_trades': len(trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': (len(winning_trades) / len(trades)) * 100 if trades else 0,
            'avg_holding_time': avg_holding_time,
            'total_pnl': final_capital - initial_capital,
            'total_return': ((final_capital - initial_capital) / initial_capital) * 100,
            'best_stock': f"{best_stock[0]} (${best_stock[1]:+.2f})",
            'worst_stock': f"{worst_stock[0]} (${worst_stock[1]:+.2f})",
            'best_trade': max(trades, key=lambda x: x['Profit_Loss']) if trades else None,
            'worst_trade': min(trades, key=lambda x: x['Profit_Loss']) if trades else None
        }
        
    def display_comprehensive_results(self):
        """Display comprehensive backtest results"""
        print(f"\n" + "=" * 80)
        print("📊 COMPREHENSIVE BACKTEST RESULTS")
        print("=" * 80)
        
        stats = self.summary_stats
        
        print(f"🔢 Total Trades:          {stats['total_trades']}")
        print(f"✅ Winning Trades:        {stats['winning_trades']}")
        print(f"❌ Losing Trades:         {stats['losing_trades']}")
        print(f"📈 Win Rate:              {stats['win_rate']:.1f}%")
        print(f"⏱️ Average Holding Time:  {stats['avg_holding_time']}")
        print(f"💰 Total P&L:             ${stats['total_pnl']:+,.2f}")
        print(f"📊 Total Return:          {stats['total_return']:+.2f}%")
        print(f"🏆 Best Performing Stock: {stats['best_stock']}")
        print(f"📉 Worst Performing Stock:{stats['worst_stock']}")
        
        if stats['best_trade']:
            best = stats['best_trade']
            print(f"🥇 Best Trade:            {best['Stock']} on {best['Date']}: ${best['Profit_Loss']:+.2f}")
        
        if stats['worst_trade']:
            worst = stats['worst_trade']
            print(f"📉 Worst Trade:           {worst['Stock']} on {worst['Date']}: ${worst['Profit_Loss']:+.2f}")
        
        print(f"\n📰 News Articles Analyzed: {len(self.news_data)}")
        print(f"📊 Trades Logged:         {len(self.trades_data)}")
        
    def generate_excel_report(self, params: Dict):
        """Generate comprehensive Excel report"""
        timestamp = datetime.now().strftime('%Y-%m-%d_%H%M')
        filename = f"backtest_logs/backtest_report_{timestamp}.xlsx"
        
        print(f"\n📁 GENERATING EXCEL REPORT...")
        print("=" * 50)
        
        try:
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                
                # 1. Trade Summary Sheet
                if self.trades_data:
                    trades_df = pd.DataFrame(self.trades_data)
                    trades_df.to_excel(writer, sheet_name='Trade Summary', index=False)
                    print("✅ Trade Summary sheet created")
                
                # 2. Analyzed News Sheet
                if self.news_data:
                    news_df = pd.DataFrame(self.news_data)
                    news_df.to_excel(writer, sheet_name='Analyzed News', index=False)
                    print("✅ Analyzed News sheet created")
                
                # 3. Summary Sheet
                summary_data = {
                    'Metric': [
                        'Backtest Period',
                        'Total Trades Placed',
                        'Winning Trades',
                        'Losing Trades', 
                        'Win Rate (%)',
                        'Average Holding Time',
                        'Total Profit/Loss ($)',
                        'Total Return (%)',
                        'Best Performing Stock',
                        'Worst Performing Stock',
                        'Take Profit Setting',
                        'Stop Loss Setting',
                        'Sentiment Range',
                        'Trading Hours',
                        'News Articles Analyzed'
                    ],
                    'Value': [
                        f"{params['start_date']} to {params['end_date']}",
                        self.summary_stats['total_trades'],
                        self.summary_stats['winning_trades'],
                        self.summary_stats['losing_trades'],
                        f"{self.summary_stats['win_rate']:.1f}%",
                        self.summary_stats['avg_holding_time'],
                        f"${self.summary_stats['total_pnl']:+,.2f}",
                        f"{self.summary_stats['total_return']:+.2f}%",
                        self.summary_stats['best_stock'],
                        self.summary_stats['worst_stock'],
                        f"+${params['take_profit']}",
                        f"-${params['stop_loss']}",
                        f"{params['sentiment_lower']} to {params['sentiment_upper']}",
                        f"{params['entry_time']} - {params['exit_time']}",
                        len(self.news_data)
                    ]
                }
                
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
                print("✅ Summary sheet created")
                
            print(f"\n📊 EXCEL REPORT GENERATED SUCCESSFULLY!")
            print(f"📁 File saved: {filename}")
            print(f"📈 Contains: {len(self.trades_data)} trades, {len(self.news_data)} news articles")
            
            logging.info(f"Excel report generated: {filename}")
            
        except Exception as e:
            print(f"❌ Error generating Excel report: {e}")
            logging.error(f"Excel report generation failed: {e}")
            
            # Fallback to CSV
            self.generate_csv_fallback(params, timestamp)
            
    def generate_csv_fallback(self, params: Dict, timestamp: str):
        """Generate CSV files as fallback if Excel fails"""
        print("📁 Generating CSV fallback files...")
        
        try:
            # Save trades to CSV
            if self.trades_data:
                trades_df = pd.DataFrame(self.trades_data)
                trades_filename = f"backtest_logs/trades_{timestamp}.csv"
                trades_df.to_csv(trades_filename, index=False)
                print(f"✅ Trades saved: {trades_filename}")
            
            # Save news to CSV
            if self.news_data:
                news_df = pd.DataFrame(self.news_data)
                news_filename = f"backtest_logs/news_{timestamp}.csv"
                news_df.to_csv(news_filename, index=False)
                print(f"✅ News saved: {news_filename}")
                
        except Exception as e:
            print(f"❌ CSV fallback failed: {e}")

def main():
    """Main execution function"""
    reporter = EnhancedBacktestReporter()
    reporter.run_enhanced_backtest()

if __name__ == "__main__":
    main() 