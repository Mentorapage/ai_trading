"""
DUAL MODE TRADING SYSTEM
========================
Clean implementation with Live Trading and Historical Backtest modes
"""

import os
import sys
import time
import logging
import pandas as pd
import yfinance as yf
import finnhub
from datetime import datetime, timedelta, time as dt_time
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

# NLTK setup for sentiment analysis
import nltk
try:
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
    nltk.download('vader_lexicon', quiet=True)
except:
    pass
from nltk.sentiment.vader import SentimentIntensityAnalyzer

# Alpaca API imports
from alpaca_trade_api.rest import REST
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, StopLossRequest, TakeProfitRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading.log'),
        logging.StreamHandler()
    ]
)

class TradingSystem:
    def __init__(self):
        """Initialize the trading system with API clients and configuration"""
        # Load environment variables
        load_dotenv(dotenv_path=".env")
        self.finn_api_key = os.getenv("finnhubkey")
        self.alpaca_api_key = os.getenv("apikey")
        self.alpaca_secret_key = os.getenv("apisecret")
        
        # Validate API keys
        if not all([self.finn_api_key, self.alpaca_api_key, self.alpaca_secret_key]):
            raise ValueError("Missing API keys in .env file")
        
        # Initialize API clients
        self.finnhub_client = finnhub.Client(api_key=self.finn_api_key)
        self.trading_client = TradingClient(self.alpaca_api_key, self.alpaca_secret_key, paper=True)
        self.paper_api = REST(self.alpaca_api_key, self.alpaca_secret_key, base_url="https://paper-api.alpaca.markets")
        
        # Initialize sentiment analyzer
        self.sia = SentimentIntensityAnalyzer()
        
        # Load stock universe
        self.stocks = self._load_stock_universe()
        
        logging.info(f"Trading system initialized with {len(self.stocks)} stocks")
    
    def _load_stock_universe(self):
        """Load the predefined stock watchlist"""
        try:
            df = pd.read_csv("technology_tickers.csv")
            stocks = df['Ticker'].tolist()
            return stocks
        except Exception as e:
            logging.error(f"Failed to load stock universe: {e}")
            # Fallback to hardcoded list
            return ['NVDA', 'MSFT', 'AAPL', 'AMZN', 'GOOGL', 'META', 'AVGO', 'TSM', 'TSLA', 'ORCL', 'ADBE', 'CSCO', 'INTU', 'QCOM']
    
    def get_sentiment(self, ticker, target_date=None):
        """
        Get sentiment score for a stock ticker using Finnhub news and VADER analysis
        
        Args:
            ticker (str): Stock ticker symbol
            target_date (str, optional): Date in YYYY-MM-DD format. If None, uses today.
        
        Returns:
            float: Average sentiment score (-1 to 1)
        """
        try:
            if target_date is None:
                target_date = datetime.now().strftime("%Y-%m-%d")
            
            # Fetch news for the target date
            all_articles = self.finnhub_client.company_news(ticker, _from=target_date, to=target_date)
            
            if not all_articles:
                return 0.0
            
            sentiment_scores = []
            
            # Process articles
            for article in all_articles:
                published_time = datetime.fromtimestamp(article['datetime'])
                
                # Include all news from the target date
                if target_date == datetime.now().strftime("%Y-%m-%d"):
                    if published_time.date() == datetime.now().date():
                        news_score = self.sia.polarity_scores(article['summary'])
                        sentiment_scores.append(news_score['compound'])
                else:
                    target_dt = datetime.strptime(target_date, "%Y-%m-%d").date()
                    if published_time.date() == target_dt:
                        news_score = self.sia.polarity_scores(article['summary'])
                        sentiment_scores.append(news_score['compound'])
            
            # Calculate average sentiment (limit to top 10 articles)
            final_scores = sentiment_scores[:10]
            avg_sentiment = sum(final_scores) / len(final_scores) if final_scores else 0.0
            
            return avg_sentiment
            
        except Exception as e:
            logging.error(f"Error getting sentiment for {ticker}: {e}")
            return 0.0
    
    def screen_stocks_by_sentiment(self, sentiment_threshold, target_date=None):
        """
        Screen stocks based on sentiment analysis
        
        Args:
            sentiment_threshold (float): Minimum sentiment threshold
            target_date (str, optional): Date for historical analysis
        
        Returns:
            dict: Dictionary with ticker as key and sentiment score as value for qualifying stocks
        """
        qualified_stocks = {}
        
        print(f"\n🧠 SENTIMENT ANALYSIS RESULTS ({datetime.now().strftime('%H:%M:%S')})")
        print("=" * 60)
        
        date_str = target_date if target_date else "today"
        print(f"📅 Analysis date: {date_str}")
        print(f"📊 Sentiment threshold: {sentiment_threshold:.2f}")
        print()
        
        for ticker in self.stocks:
            try:
                score = self.get_sentiment(ticker, target_date)
                
                # Determine qualification status
                qualified = score >= sentiment_threshold
                status = "✅ QUALIFIED" if qualified else "❌ No"
                
                # Display result
                print(f"{ticker:5}: {score:.4f} - {status}")
                
                if qualified:
                    qualified_stocks[ticker] = score
                    
                # Rate limiting for API calls
                time.sleep(1)
                
            except Exception as e:
                print(f"{ticker:5}: ERROR - {e}")
                logging.error(f"Failed to analyze {ticker}: {e}")
                continue
        
        print("=" * 60)
        print(f"📊 SUMMARY: {len(qualified_stocks)} stocks qualify for trading")
        
        if qualified_stocks:
            print(f"🎯 Qualifying stocks: {list(qualified_stocks.keys())}")
        else:
            print("⚠️  No stocks meet the sentiment threshold")
        
        return qualified_stocks
    
    def place_bracket_order(self, ticker, shares, stop_loss_pct, take_profit_pct):
        """
        Place a bracket order with stop loss and take profit
        
        Args:
            ticker (str): Stock ticker
            shares (int): Number of shares
            stop_loss_pct (float): Stop loss percentage
            take_profit_pct (float): Take profit percentage
        
        Returns:
            tuple: (success, result_message)
        """
        try:
            # Get current price
            current_price = self.paper_api.get_latest_trade(ticker).price
            
            # Calculate stop loss and take profit prices
            stop_loss_price = round(current_price * (1 - stop_loss_pct / 100), 2)
            take_profit_price = round(current_price * (1 + take_profit_pct / 100), 2)
            
            # Create bracket order
            order_request = MarketOrderRequest(
                symbol=ticker,
                qty=shares,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
                order_class=OrderClass.BRACKET,
                stop_loss=StopLossRequest(stop_price=stop_loss_price),
                take_profit=TakeProfitRequest(limit_price=take_profit_price)
            )
            
            # Submit order
            submitted_order = self.trading_client.submit_order(order_request)
            
            if submitted_order and submitted_order.id:
                success_msg = f"Order placed: {shares} shares @ ${current_price:.2f}, SL: ${stop_loss_price:.2f}, TP: ${take_profit_price:.2f}"
                logging.info(f"✅ {ticker}: {success_msg}")
                return True, success_msg
            else:
                error_msg = "Order submission failed"
                logging.error(f"❌ {ticker}: {error_msg}")
                return False, error_msg
                
        except Exception as e:
            error_msg = f"Order failed: {str(e)}"
            logging.error(f"❌ {ticker}: {error_msg}")
            return False, error_msg
    
    def close_all_positions(self):
        """Close all open positions and cancel pending orders"""
        try:
            # Cancel all orders using the correct method
            try:
                orders = self.trading_client.get_orders()
                for order in orders:
                    if order.status in ['new', 'partially_filled', 'pending_new']:
                        self.trading_client.cancel_order_by_id(order.id)
                        logging.info(f"Cancelled order: {order.id}")
            except Exception as e:
                logging.warning(f"Issue cancelling orders: {e}")
                # Try alternative method
                try:
                    open_orders = self.trading_client.get_open_orders()
                    for order in open_orders:
                        self.trading_client.cancel_order_by_id(order.id)
                        logging.info(f"Cancelled order: {order.id}")
                except Exception as e2:
                    logging.warning(f"Could not cancel orders: {e2}")
            
            # Close all positions
            try:
                positions = self.trading_client.get_all_positions()
                closed_positions = 0
                for position in positions:
                    if float(position.qty) != 0:
                        side = OrderSide.SELL if float(position.qty) > 0 else OrderSide.BUY
                        close_order = MarketOrderRequest(
                            symbol=position.symbol,
                            qty=abs(float(position.qty)),
                            side=side,
                            time_in_force=TimeInForce.DAY
                        )
                        self.trading_client.submit_order(close_order)
                        closed_positions += 1
                        logging.info(f"Closed position: {position.symbol} - {position.qty} shares")
                
                success_msg = f"All positions closed successfully ({closed_positions} positions)"
                logging.info(f"✅ {success_msg}")
                return success_msg
                
            except Exception as e:
                error_msg = f"Error closing positions: {e}"
                logging.error(f"❌ {error_msg}")
                return error_msg
            
        except Exception as e:
            error_msg = f"Error in position closure process: {e}"
            logging.error(f"❌ {error_msg}")
            return error_msg
    
    def run_live_trading(self):
        """Execute live trading mode"""
        print("\n" + "=" * 60)
        print("       📈 LIVE TRADING MODE")
        print("=" * 60)
        
        # Confirmation
        confirm = input("\n⚠️  Are you sure you want to start LIVE trading? (yes/no): ").strip().lower()
        if confirm not in ['yes', 'y']:
            print("❌ Live trading cancelled.")
            return
        
        # Get trading parameters
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
        
        while True:
            try:
                holding_minutes = int(input("\n⏱️  Maximum holding time in minutes before closing all positions: "))
                if holding_minutes > 0:
                    break
                else:
                    print("❌ Holding time must be positive")
            except ValueError:
                print("❌ Please enter a valid number")
        
        while True:
            try:
                sentiment_threshold = float(input("\n📊 Sentiment threshold (0.0 to 1.0, e.g., 0.5): "))
                if 0 <= sentiment_threshold <= 1:
                    break
                else:
                    print("❌ Sentiment threshold must be between 0.0 and 1.0")
            except ValueError:
                print("❌ Please enter a valid decimal number")
        
        while True:
            try:
                stop_loss_pct = float(input("\n🛡️  Stop Loss percentage (e.g., 5.0 for 5%): "))
                take_profit_pct = float(input("💰 Take Profit percentage (e.g., 3.0 for 3%): "))
                if stop_loss_pct > 0 and take_profit_pct > 0:
                    break
                else:
                    print("❌ Both Stop Loss and Take Profit must be positive")
            except ValueError:
                print("❌ Please enter valid decimal numbers")
        
        # Wait for start time
        print(f"\n⏰ Waiting for start time: {start_time}")
        current_time = datetime.now().time()
        if current_time < start_time:
            wait_seconds = (datetime.combine(datetime.now().date(), start_time) - datetime.now()).total_seconds()
            print(f"⏳ Waiting {wait_seconds/60:.1f} minutes...")
            time.sleep(wait_seconds)
        
        print("🚀 STARTING LIVE TRADING NOW!")
        
        # Perform sentiment analysis
        qualified_stocks = self.screen_stocks_by_sentiment(sentiment_threshold)
        
        if not qualified_stocks:
            print("❌ No stocks qualified for trading. Session ended.")
            return
        
        # Get account info and calculate position sizing
        account = self.trading_client.get_account()
        buying_power = float(account.buying_power) * 0.9  # Use 90% of buying power
        position_size = buying_power / len(qualified_stocks)
        
        print(f"\n💰 Trading with ${buying_power:,.2f} across {len(qualified_stocks)} stocks")
        print(f"💼 ${position_size:,.2f} per stock")
        
        # Execute trades
        successful_trades = []
        for ticker in qualified_stocks:
            try:
                current_price = self.paper_api.get_latest_trade(ticker).price
                shares = int(position_size / current_price)
                
                if shares > 0:
                    success, result = self.place_bracket_order(ticker, shares, stop_loss_pct, take_profit_pct)
                    if success:
                        successful_trades.append(ticker)
                        print(f"✅ {ticker}: {result}")
                    else:
                        print(f"❌ {ticker}: {result}")
                else:
                    print(f"❌ {ticker}: Position size too small")
                    
            except Exception as e:
                print(f"❌ {ticker}: Error - {e}")
        
        if successful_trades:
            print(f"\n✅ {len(successful_trades)} trades executed successfully")
            print(f"⏳ Positions will be closed in {holding_minutes} minutes")
            
            # Wait for holding period
            time.sleep(holding_minutes * 60)
            
            # Close all positions
            print("\n🔒 Closing all positions...")
            result = self.close_all_positions()
            print(f"✅ {result}")
        
        print("\n🏁 Live trading session completed")
    
    def fetch_historical_data(self, ticker, start_date, end_date):
        """Fetch historical minute-level price data"""
        try:
            # Add buffer days
            start_dt = datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=2)
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            
            # Download 2-minute data
            data = yf.download(
                ticker,
                start=start_dt.strftime('%Y-%m-%d'),
                end=end_dt.strftime('%Y-%m-%d'),
                interval='2m',
                progress=False
            )
            
            if data.empty:
                return None
            
            # Clean data
            data = data.dropna()
            
            # Flatten multi-level columns if they exist
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.droplevel(1)
            
            return data
            
        except Exception as e:
            logging.error(f"Error fetching data for {ticker}: {e}")
            return None
    
    def simulate_trade_execution(self, entry_price, stop_loss_pct, take_profit_pct, price_data, entry_time):
        """Simulate realistic trade execution using minute-level price data"""
        try:
            # Calculate stop loss and take profit levels
            stop_loss_price = entry_price * (1 - stop_loss_pct / 100)
            take_profit_price = entry_price * (1 + take_profit_pct / 100)
            
            # Get price data after entry time
            future_data = price_data[price_data.index > entry_time].head(390)  # Max 6.5 hours
            
            if future_data.empty:
                return {
                    'exit_price': entry_price,
                    'exit_time': entry_time,
                    'exit_reason': 'NO_DATA',
                    'profit_loss_pct': 0.0,
                    'holding_minutes': 0
                }
            
            # Simulate each minute to determine exit
            for timestamp, row in future_data.iterrows():
                high = row['High']
                low = row['Low']
                close = row['Close']
                
                # Check if both levels could be hit in the same candle
                if low <= stop_loss_price and high >= take_profit_price:
                    # Use close price to determine which was likely hit first
                    distance_to_tp = abs(close - take_profit_price)
                    distance_to_sl = abs(close - stop_loss_price)
                    
                    if distance_to_tp < distance_to_sl:
                        exit_price = take_profit_price
                        exit_reason = 'TAKE_PROFIT'
                    else:
                        exit_price = stop_loss_price
                        exit_reason = 'STOP_LOSS'
                        
                    holding_minutes = (timestamp - entry_time).total_seconds() / 60
                    profit_loss_pct = ((exit_price - entry_price) / entry_price) * 100
                    
                    return {
                        'exit_price': exit_price,
                        'exit_time': timestamp,
                        'exit_reason': exit_reason,
                        'profit_loss_pct': profit_loss_pct,
                        'holding_minutes': holding_minutes
                    }
                
                # Check if only stop loss is hit
                elif low <= stop_loss_price:
                    holding_minutes = (timestamp - entry_time).total_seconds() / 60
                    profit_loss_pct = ((stop_loss_price - entry_price) / entry_price) * 100
                    
                    return {
                        'exit_price': stop_loss_price,
                        'exit_time': timestamp,
                        'exit_reason': 'STOP_LOSS',
                        'profit_loss_pct': profit_loss_pct,
                        'holding_minutes': holding_minutes
                    }
                
                # Check if only take profit is hit
                elif high >= take_profit_price:
                    holding_minutes = (timestamp - entry_time).total_seconds() / 60
                    profit_loss_pct = ((take_profit_price - entry_price) / entry_price) * 100
                    
                    return {
                        'exit_price': take_profit_price,
                        'exit_time': timestamp,
                        'exit_reason': 'TAKE_PROFIT',
                        'profit_loss_pct': profit_loss_pct,
                        'holding_minutes': holding_minutes
                    }
            
            # If neither level was hit, close at last available price
            last_row = future_data.iloc[-1]
            last_timestamp = future_data.index[-1]
            exit_price = last_row['Close']
            
            holding_minutes = (last_timestamp - entry_time).total_seconds() / 60
            profit_loss_pct = ((exit_price - entry_price) / entry_price) * 100
            
            return {
                'exit_price': exit_price,
                'exit_time': last_timestamp,
                'exit_reason': 'TIME_LIMIT',
                'profit_loss_pct': profit_loss_pct,
                'holding_minutes': holding_minutes
            }
            
        except Exception as e:
            logging.error(f"Error in trade simulation: {e}")
            return {
                'exit_price': entry_price,
                'exit_time': entry_time,
                'exit_reason': 'ERROR',
                'profit_loss_pct': 0.0,
                'holding_minutes': 0
            }
    
    def run_historical_backtest(self):
        """Execute historical backtest mode"""
        print("\n" + "=" * 60)
        print("       📊 HISTORICAL BACKTEST MODE")
        print("=" * 60)
        
        # Confirmation
        confirm = input("\n📈 Are you sure you want to run a historical backtest? (yes/no): ").strip().lower()
        if confirm not in ['yes', 'y']:
            print("❌ Historical backtest cancelled.")
            return
        
        # Get backtest parameters
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
                print("❌ Invalid date format. Please use YYYY-MM-DD")
        
        while True:
            try:
                sentiment_threshold = float(input("\n📊 Sentiment threshold (0.0 to 1.0, e.g., 0.5): "))
                if 0 <= sentiment_threshold <= 1:
                    break
                else:
                    print("❌ Sentiment threshold must be between 0.0 and 1.0")
            except ValueError:
                print("❌ Please enter a valid decimal number")
        
        while True:
            try:
                stop_loss_pct = float(input("\n🛡️  Stop Loss percentage (e.g., 5.0 for 5%): "))
                take_profit_pct = float(input("💰 Take Profit percentage (e.g., 3.0 for 3%): "))
                if stop_loss_pct > 0 and take_profit_pct > 0:
                    break
                else:
                    print("❌ Both percentages must be positive")
            except ValueError:
                print("❌ Please enter valid decimal numbers")
        
        while True:
            try:
                investment_per_stock = float(input("\n💼 Investment amount per approved stock (USD, e.g., 100000): "))
                if investment_per_stock > 0:
                    break
                else:
                    print("❌ Investment amount must be positive")
            except ValueError:
                print("❌ Please enter a valid number")
        
        print(f"\n🔄 Running backtest from {start_date} to {end_date}")
        print(f"📊 Parameters: Sentiment={sentiment_threshold:.2f}, SL={stop_loss_pct:.1f}%, TP={take_profit_pct:.1f}%")
        print(f"💼 Investment per Stock: ${investment_per_stock:,.0f}")
        
        # Generate date range
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        current_date = start_dt
        all_trades = []
        
        # Process each trading day
        while current_date <= end_dt:
            # Skip weekends
            if current_date.weekday() < 5:
                date_str = current_date.strftime('%Y-%m-%d')
                print(f"\n📅 Processing {date_str}...")
                
                # Screen stocks for this date
                qualified_stocks = self.screen_stocks_by_sentiment(sentiment_threshold, date_str)
                
                if qualified_stocks:
                    # Process each qualified stock
                    for ticker, sentiment in qualified_stocks.items():
                        try:
                            # Fetch price data
                            price_data = self.fetch_historical_data(ticker, date_str, date_str)
                            
                            if price_data is None or price_data.empty:
                                print(f"   ❌ {ticker}: No price data available")
                                continue
                            
                            # Find entry point (market open)
                            target_dt = datetime.strptime(date_str, '%Y-%m-%d')
                            daily_data = price_data[price_data.index.date == target_dt.date()]
                            
                            if daily_data.empty:
                                print(f"   ❌ {ticker}: No trading data for {date_str}")
                                continue
                            
                            entry_time = daily_data.index[0]
                            entry_price = daily_data.iloc[0]['Open']
                            
                            # Calculate position size based on investment amount
                            shares = int(investment_per_stock / entry_price)
                            
                            if shares <= 0:
                                print(f"   ❌ {ticker}: Investment amount too small for minimum share purchase")
                                continue
                            
                            # Calculate actual position value
                            position_value = shares * entry_price
                            
                            # Simulate trade execution
                            trade_result = self.simulate_trade_execution(
                                entry_price, stop_loss_pct, take_profit_pct, price_data, entry_time
                            )
                            
                            # Calculate dollar P&L based on actual position size
                            dollar_profit_loss = (trade_result['exit_price'] - entry_price) * shares
                            
                            # Create trade record
                            trade = {
                                'date': date_str,
                                'ticker': ticker,
                                'sentiment': sentiment,
                                'entry_time': entry_time.strftime('%Y-%m-%d %H:%M:%S'),
                                'entry_price': entry_price,
                                'shares': shares,
                                'position_value': position_value,
                                'exit_time': trade_result['exit_time'].strftime('%Y-%m-%d %H:%M:%S'),
                                'exit_price': trade_result['exit_price'],
                                'exit_reason': trade_result['exit_reason'],
                                'profit_loss_pct': trade_result['profit_loss_pct'],
                                'profit_loss_dollar': dollar_profit_loss,
                                'holding_minutes': trade_result['holding_minutes']
                            }
                            
                            all_trades.append(trade)
                            
                            print(f"   📊 {ticker}: {shares} shares @ ${entry_price:.2f} - {trade_result['exit_reason']} - P&L: ${dollar_profit_loss:.2f} ({trade_result['profit_loss_pct']:.2f}%)")
                            
                        except Exception as e:
                            print(f"   ❌ {ticker}: Error - {e}")
                            continue
                else:
                    print(f"   No stocks qualified for {date_str}")
            
            current_date += timedelta(days=1)
        
        # Generate results report
        self._generate_backtest_report(all_trades, start_date, end_date, {
            'sentiment_threshold': sentiment_threshold,
            'stop_loss_pct': stop_loss_pct,
            'take_profit_pct': take_profit_pct,
            'investment_per_stock': investment_per_stock
        })
    
    def _generate_backtest_report(self, trades, start_date, end_date, params):
        """Generate detailed backtest report"""
        if not trades:
            print("\n❌ No trades to report")
            return
        
        df = pd.DataFrame(trades)
        
        # Calculate statistics
        total_trades = len(df)
        winning_trades = len(df[df['profit_loss_dollar'] > 0])
        losing_trades = len(df[df['profit_loss_dollar'] < 0])
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        
        # Portfolio-level calculations
        total_capital_invested = df['position_value'].sum()
        total_dollar_profit_loss = df['profit_loss_dollar'].sum()
        total_return_pct = (total_dollar_profit_loss / total_capital_invested) * 100 if total_capital_invested > 0 else 0
        
        avg_profit_loss_pct = df['profit_loss_pct'].mean()
        avg_profit_loss_dollar = df['profit_loss_dollar'].mean()
        avg_holding_time = df['holding_minutes'].mean()
        
        best_trade = df.loc[df['profit_loss_dollar'].idxmax()] if not df.empty else None
        worst_trade = df.loc[df['profit_loss_dollar'].idxmin()] if not df.empty else None
        
        # Display summary
        print("\n" + "=" * 80)
        print("                     📊 BACKTEST RESULTS SUMMARY")
        print("=" * 80)
        print(f"📅 Period: {start_date} to {end_date}")
        print(f"📊 Parameters: Sentiment={params['sentiment_threshold']:.2f}, SL={params['stop_loss_pct']:.1f}%, TP={params['take_profit_pct']:.1f}%")
        print(f"💼 Investment per Stock: ${params['investment_per_stock']:,.0f}")
        print()
        print(f"📈 Total Trades: {total_trades}")
        print(f"✅ Winning Trades: {winning_trades} ({win_rate:.1f}%)")
        print(f"❌ Losing Trades: {losing_trades} ({100-win_rate:.1f}%)")
        print()
        print(f"💰 Total Capital Invested: ${total_capital_invested:,.2f}")
        print(f"💵 Total Dollar P&L: ${total_dollar_profit_loss:,.2f}")
        print(f"📈 Total Portfolio Return: {total_return_pct:.2f}%")
        print(f"📊 Average P&L per Trade: ${avg_profit_loss_dollar:.2f} ({avg_profit_loss_pct:.2f}%)")
        print(f"⏱️  Average Holding Time: {avg_holding_time:.0f} minutes")
        
        if best_trade is not None:
            print(f"\n🏆 Best Trade: {best_trade['ticker']} on {best_trade['date']}")
            print(f"   P&L: ${best_trade['profit_loss_dollar']:.2f} ({best_trade['profit_loss_pct']:.2f}%)")
        
        if worst_trade is not None:
            print(f"\n💥 Worst Trade: {worst_trade['ticker']} on {worst_trade['date']}")
            print(f"   P&L: ${worst_trade['profit_loss_dollar']:.2f} ({worst_trade['profit_loss_pct']:.2f}%)")
        
        # Exit reasons breakdown
        print("\n📋 Exit Reasons:")
        exit_counts = df['exit_reason'].value_counts()
        for reason, count in exit_counts.items():
            pct = (count / total_trades) * 100
            print(f"   {reason}: {count} trades ({pct:.1f}%)")
        
        # Save to Excel
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"backtest_report_{timestamp}.xlsx"
        
        try:
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                # Trade details
                df.to_excel(writer, sheet_name='Trade_Details', index=False)
                
                # Summary
                summary_data = {
                    'Metric': [
                        'Period', 'Sentiment Threshold', 'Stop Loss %', 'Take Profit %', 'Investment per Stock',
                        'Total Trades', 'Win Rate %', 'Total Capital Invested', 'Total Dollar P&L', 'Total Portfolio Return %', 
                        'Avg P&L per Trade ($)', 'Avg P&L per Trade (%)', 'Avg Holding Time (min)'
                    ],
                    'Value': [
                        f"{start_date} to {end_date}",
                        f"{params['sentiment_threshold']:.2f}",
                        f"{params['stop_loss_pct']:.1f}%",
                        f"{params['take_profit_pct']:.1f}%",
                        f"${params['investment_per_stock']:,.0f}",
                        total_trades,
                        f"{win_rate:.1f}%",
                        f"${total_capital_invested:,.2f}",
                        f"${total_dollar_profit_loss:,.2f}",
                        f"{total_return_pct:.2f}%",
                        f"${avg_profit_loss_dollar:.2f}",
                        f"{avg_profit_loss_pct:.2f}%",
                        f"{avg_holding_time:.0f}"
                    ]
                }
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            print(f"\n💾 Detailed report saved to: {filename}")
            
        except Exception as e:
            print(f"\n❌ Error saving Excel report: {e}")
            # Fallback to CSV
            csv_filename = f"backtest_report_{timestamp}.csv"
            df.to_csv(csv_filename, index=False)
            print(f"💾 CSV report saved to: {csv_filename}")
    
    def run(self):
        """Main program entry point"""
        while True:
            try:
                print("\n" + "=" * 60)
                print("       🚀 DUAL MODE TRADING SYSTEM 🚀")
                print("=" * 60)
                print()
                print("Select trading mode:")
                print("1. 📈 Live Trading Mode")
                print("2. 📊 Historical Backtest Mode") 
                print("3. ❌ Exit")
                print()
                
                choice = input("Enter your choice (1-3): ").strip()
                
                if choice == '1':
                    self.run_live_trading()
                    input("\nPress Enter to return to main menu...")
                elif choice == '2':
                    self.run_historical_backtest()
                    input("\nPress Enter to return to main menu...")
                elif choice == '3':
                    print("\n👋 Goodbye!")
                    break
                else:
                    print("❌ Invalid choice. Please enter 1, 2, or 3.")
                    
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ An error occurred: {e}")
                logging.error(f"System error: {e}")

def main():
    """Initialize and run the trading system"""
    try:
        trading_system = TradingSystem()
        trading_system.run()
    except Exception as e:
        print(f"❌ Failed to initialize trading system: {e}")
        logging.error(f"Initialization error: {e}")

if __name__ == "__main__":
    main() 