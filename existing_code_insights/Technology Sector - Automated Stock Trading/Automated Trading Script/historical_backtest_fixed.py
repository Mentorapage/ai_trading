"""
HISTORICAL BACKTEST MODULE
=========================
Handles historical backtesting with real minute-level price data from Alpaca
"""

# ensure .env and nltk are ready
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

# fix NLTK paths/lexicon
import bootstrap_nltk  # noqa

# (optional) set SSL cert for any future downloads
import os, certifi
os.environ.setdefault("SSL_CERT_FILE", certifi.where())

# Removed yfinance - now using Alpaca historical data
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import os
from typing import Dict, List, Tuple
import time
from dotenv import load_dotenv

# Alpaca historical data imports
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

# Backtest realism settings (internal defaults, not user-facing)
DEFAULT_SLIPPAGE = 0.01  # $0.01 slippage per side (entry and exit)
DEFAULT_SETUP_DELAY_SECONDS = 2  # 2-second delay for TP/SL setup

# Load Alpaca API credentials
load_dotenv(dotenv_path=".env")
api_key = os.getenv("apikey")
secret_key = os.getenv("apisecret")

# Initialize Alpaca historical data client
historical_client = StockHistoricalDataClient(api_key, secret_key)

from trading_core import (
    validate_environment, load_stock_universe, get_sentiment, screen_stocks_by_sentiment,
    format_currency, format_percentage
)

def get_historical_data(ticker: str, start_date: datetime, end_date: datetime, timeframe: str = '1Min') -> pd.DataFrame:
    """
    Get historical intraday data for a ticker
    
    Args:
        ticker: Stock ticker symbol
        start_date: Start date
        end_date: End date  
        timeframe: Data timeframe ('1Min', '5Min', etc.)
    
    Returns:
        DataFrame with OHLCV data indexed by timestamp
    """
    try:
        # Map timeframe to Alpaca format
        timeframe_mapping = {
            '1Min': TimeFrame.Minute,
            '5Min': TimeFrame(5, TimeFrameUnit.Minute),
            '15Min': TimeFrame(15, TimeFrameUnit.Minute),
            '30Min': TimeFrame(30, TimeFrameUnit.Minute),
            '1Hour': TimeFrame.Hour,
            '1Day': TimeFrame.Day
        }
        
        alpaca_timeframe = timeframe_mapping.get(timeframe, TimeFrame.Minute)
        
        # Create request
        request = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=alpaca_timeframe,
            start=start_date,
            end=end_date
        )
        
        # Fetch data
        bars = historical_client.get_stock_bars(request)
        
        if not bars.data or ticker not in bars.data:
            return None
        
        # Convert to DataFrame
        bar_data = bars.data[ticker]
        
        if not bar_data:
            return None
        
        # Create DataFrame
        data = []
        for bar in bar_data:
            data.append({
                'timestamp': bar.timestamp,
                'open': float(bar.open),
                'high': float(bar.high),
                'low': float(bar.low),
                'close': float(bar.close),
                'volume': int(bar.volume)
            })
        
        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)
        
        # Convert to ET timezone
        import pytz
        et_tz = pytz.timezone('America/New_York')
        df.index = df.index.tz_convert(et_tz)
        
        return df
        
    except Exception as e:
        logging.error(f"Error fetching historical data for {ticker}: {e}")
        return None

def fetch_historical_data(ticker, start_date, end_date, interval='2m'):
    """
    Fetch historical price data for a ticker using Alpaca API
    
    Args:
        ticker (str): Stock ticker
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
        interval (str): Data interval (1m, 2m, 5m, etc.)
    
    Returns:
        pd.DataFrame: Historical OHLCV data
    """
    try:
        # Add buffer days to ensure we have enough data
        start_dt = datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=5)
        end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        
        # Map interval string to Alpaca TimeFrame
        interval_mapping = {
            '1m': TimeFrame.Minute,
            '2m': TimeFrame(2, TimeFrameUnit.Minute),
            '5m': TimeFrame(5, TimeFrameUnit.Minute),
            '15m': TimeFrame(15, TimeFrameUnit.Minute),
            '30m': TimeFrame(30, TimeFrameUnit.Minute),
            '1h': TimeFrame.Hour,
            '1d': TimeFrame.Day
        }
        
        timeframe = interval_mapping.get(interval, TimeFrame(2, TimeFrameUnit.Minute))  # Default to 2-minute
        
        # Create request for historical bars
        request = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=timeframe,
            start=start_dt,
            end=end_dt
        )
        
        # Fetch data from Alpaca
        bars = historical_client.get_stock_bars(request)
        
        if not bars.data or ticker not in bars.data:
            logging.warning(f"No data available for {ticker} in the specified period")
            return None
        
        # Convert to pandas DataFrame
        bar_data = bars.data[ticker]
        
        if not bar_data:
            logging.warning(f"No bar data available for {ticker}")
            return None
        
        # Create DataFrame with proper structure
        data_rows = []
        for bar in bar_data:
            data_rows.append({
                'timestamp': bar.timestamp,
                'Open': float(bar.open),
                'High': float(bar.high),
                'Low': float(bar.low),
                'Close': float(bar.close),
                'Volume': int(bar.volume)
            })
        
        data = pd.DataFrame(data_rows)
        
        if data.empty:
            logging.warning(f"No data available for {ticker} in the specified period")
            return None
        
        # Set timestamp as index and ensure timezone-aware
        data.set_index('timestamp', inplace=True)
        data.index = pd.to_datetime(data.index)
        
        # Sort by timestamp
        data.sort_index(inplace=True)
        
        # Clean and prepare data
        data = data.dropna()
        
        # Ensure we have required columns
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in data.columns for col in required_cols):
            logging.error(f"Missing required columns for {ticker}: {data.columns.tolist()}")
            return None
        
        logging.info(f"Fetched {len(data)} data points for {ticker} from {start_date} to {end_date} using Alpaca API")
        return data
        
    except Exception as e:
        logging.error(f"Error fetching Alpaca data for {ticker}: {e}")
        return None

def check_intraday_stop_loss_take_profit(entry_price, stop_loss_pct, take_profit_pct, price_data, entry_time, 
                                        slippage=DEFAULT_SLIPPAGE, setup_delay_seconds=DEFAULT_SETUP_DELAY_SECONDS,
                                        investment_per_stock=1_000_000):
    """
    Simple intraday monitoring for stop-loss and take-profit ONLY
    No sentiment logic - pure risk management
    """
    try:
        # Calculate stop loss and take profit levels
        stop_loss_price = entry_price * (1 - stop_loss_pct / 100)
        take_profit_price = entry_price * (1 + take_profit_pct / 100)
        
        # Calculate setup delay timestamp
        setup_active_time = entry_time + timedelta(seconds=setup_delay_seconds)
        
        # Get price data after entry time
        future_data = price_data[price_data.index > entry_time]
        
        if future_data.empty:
            return {'exit_reason': 'NO_DATA'}
        
        # Check each minute for SL/TP hits
        for timestamp, row in future_data.iterrows():
            # Skip if setup delay hasn't passed
            if timestamp < setup_active_time:
                continue
                
            low = row['Low']
            high = row['High']
            close = row['Close']
            
            # Check if both levels could be hit in the same candle
            if low <= stop_loss_price and high >= take_profit_price:
                # Use close price to determine which was likely hit first
                distance_to_tp = abs(close - take_profit_price)
                distance_to_sl = abs(close - stop_loss_price)
                
                if distance_to_tp < distance_to_sl:
                    exit_price = take_profit_price - slippage
                    exit_reason = 'TAKE_PROFIT'
                else:
                    exit_price = stop_loss_price - slippage
                    exit_reason = 'STOP_LOSS'
                    
                holding_minutes = (timestamp - entry_time).total_seconds() / 60
                profit_loss = exit_price - entry_price
                # Calculate P&L as percentage of total capital (14M for 14 stocks)
                total_capital = 14_000_000  # 14M total capital for 14 stocks
                shares = int(investment_per_stock / entry_price)
                profit_loss_pct = (profit_loss * shares / total_capital) * 100
                
                return {
                    'exit_price': exit_price,
                    'exit_time': timestamp,
                    'exit_reason': exit_reason,
                    'profit_loss': profit_loss,
                    'profit_loss_pct': profit_loss_pct,
                    'holding_minutes': holding_minutes
                }
            
            # Check if only stop loss is hit
            elif low <= stop_loss_price:
                exit_price = stop_loss_price - slippage
                holding_minutes = (timestamp - entry_time).total_seconds() / 60
                profit_loss = exit_price - entry_price
                # Calculate P&L as percentage of total capital (14M for 14 stocks)
                total_capital = 14_000_000  # 14M total capital for 14 stocks
                shares = int(investment_per_stock / entry_price)
                profit_loss_pct = (profit_loss * shares / total_capital) * 100
                
                return {
                    'exit_price': exit_price,
                    'exit_time': timestamp,
                    'exit_reason': 'STOP_LOSS',
                    'profit_loss': profit_loss,
                    'profit_loss_pct': profit_loss_pct,
                    'holding_minutes': holding_minutes
                }
            
            # Check if only take profit is hit
            elif high >= take_profit_price:
                exit_price = take_profit_price - slippage
                holding_minutes = (timestamp - entry_time).total_seconds() / 60
                profit_loss = exit_price - entry_price
                # Calculate P&L as percentage of total capital (14M for 14 stocks)
                total_capital = 14_000_000  # 14M total capital for 14 stocks
                shares = int(investment_per_stock / entry_price)
                profit_loss_pct = (profit_loss * shares / total_capital) * 100
                
                return {
                    'exit_price': exit_price,
                    'exit_time': timestamp,
                    'exit_reason': 'TAKE_PROFIT',
                    'profit_loss': profit_loss,
                    'profit_loss_pct': profit_loss_pct,
                    'holding_minutes': holding_minutes
                }
        
        # If no SL/TP hit, position stays open
        return {'exit_reason': 'POSITION_OPEN'}
        
    except Exception as e:
        logging.error(f"Error in intraday SL/TP check: {e}")
        return {'exit_reason': 'ERROR'}

def simulate_trade_execution(entry_price, stop_loss_pct, take_profit_pct, price_data, entry_time, 
                           slippage=DEFAULT_SLIPPAGE, setup_delay_seconds=DEFAULT_SETUP_DELAY_SECONDS,
                           ticker=None, overnight_manager=None, investment_per_stock=1_000_000):
    """
    Simulate realistic trade execution with sentiment-range overnight holding
    
    Args:
        entry_price (float): Entry price
        stop_loss_pct (float): Stop loss percentage
        take_profit_pct (float): Take profit percentage
        price_data (pd.DataFrame): Price data for the trading period
        entry_time (pd.Timestamp): Trade entry timestamp
        slippage (float): Slippage per side in dollars (default: $0.01)
        setup_delay_seconds (int): Delay before TP/SL become active (default: 2 seconds)
        ticker (str): Stock ticker for sentiment analysis
        overnight_manager: Overnight holding manager instance
    
    Returns:
        dict: Trade result with exit price, time, and reason
    """
    try:
        # Apply entry slippage (realistic execution)
        realistic_entry_price = entry_price + slippage
        
        # Calculate stop loss and take profit levels based on original entry price
        stop_loss_price = entry_price * (1 - stop_loss_pct / 100)
        take_profit_price = entry_price * (1 + take_profit_pct / 100)
        
        # Calculate setup delay timestamp (when TP/SL become active)
        setup_active_time = entry_time + timedelta(seconds=setup_delay_seconds)
        
        # Get price data after entry time
        future_data = price_data[price_data.index > entry_time]
        
        # Initialize tracking variables
        current_day = entry_time.date()
        position_open = True
        
        # Log realism parameters
        logging.info(f"Backtest realism: Entry slippage=${slippage:.2f}, Setup delay={setup_delay_seconds}s, "
                    f"Entry: ${entry_price:.2f} -> ${realistic_entry_price:.2f}")
        
        if future_data.empty:
            return {
                'exit_price': realistic_entry_price,
                'exit_time': entry_time,
                'exit_reason': 'NO_DATA',
                'profit_loss': 0.0,
                'profit_loss_pct': 0.0,
                'holding_minutes': 0
            }
        
        # Track current position state
        position_open = True
        current_day = entry_time.date()
        
        # Simulate each minute to determine which level is hit first
        for timestamp, row in future_data.iterrows():
            high = row['High']
            low = row['Low']
            close = row['Close']
            
            # Only check TP/SL levels after setup delay has passed
            if timestamp < setup_active_time:
                continue
            
            # PRIORITY 1: Check stop-loss/take-profit FIRST (risk management takes priority over sentiment)
            # Standard TP/SL logic
            # If both levels could be hit in the same candle
            if low <= stop_loss_price and high >= take_profit_price:
                # Use close price to determine which was likely hit first
                distance_to_tp = abs(close - take_profit_price)
                distance_to_sl = abs(close - stop_loss_price)
                
                if distance_to_tp < distance_to_sl:
                    exit_price = take_profit_price - slippage
                    exit_reason = 'TAKE_PROFIT'
                else:
                    exit_price = stop_loss_price - slippage
                    exit_reason = 'STOP_LOSS'
                    
                holding_minutes = (timestamp - entry_time).total_seconds() / 60
                profit_loss = exit_price - realistic_entry_price
                # Calculate P&L as percentage of total capital (14M for 14 stocks)
                investment_per_stock = 1_000_000  # $1M per stock
                shares = int(investment_per_stock / realistic_entry_price)
                total_capital = 14_000_000  # 14M total capital for 14 stocks
                profit_loss_pct = (profit_loss * shares / total_capital) * 100
                
                return {
                    'exit_price': exit_price,
                    'exit_time': timestamp,
                    'exit_reason': exit_reason,
                    'profit_loss': profit_loss,
                    'profit_loss_pct': profit_loss_pct,
                    'holding_minutes': holding_minutes
                }
            
            # Check if only stop loss is hit
            elif low <= stop_loss_price:
                exit_price = stop_loss_price - slippage
                holding_minutes = (timestamp - entry_time).total_seconds() / 60
                profit_loss = exit_price - realistic_entry_price
                # Calculate P&L as percentage of total capital (14M for 14 stocks)
                investment_per_stock = 1_000_000  # $1M per stock
                shares = int(investment_per_stock / realistic_entry_price)
                total_capital = 14_000_000  # 14M total capital for 14 stocks
                profit_loss_pct = (profit_loss * shares / total_capital) * 100
                
                return {
                    'exit_price': exit_price,
                    'exit_time': timestamp,
                    'exit_reason': 'STOP_LOSS',
                    'profit_loss': profit_loss,
                    'profit_loss_pct': profit_loss_pct,
                    'holding_minutes': holding_minutes
                }
            
            # Check if only take profit is hit
            elif high >= take_profit_price:
                exit_price = take_profit_price - slippage
                holding_minutes = (timestamp - entry_time).total_seconds() / 60
                profit_loss = exit_price - realistic_entry_price
                # Calculate P&L as percentage of total capital (14M for 14 stocks)
                investment_per_stock = 1_000_000  # $1M per stock
                shares = int(investment_per_stock / realistic_entry_price)
                total_capital = 14_000_000  # 14M total capital for 14 stocks
                profit_loss_pct = (profit_loss * shares / total_capital) * 100
                
                return {
                    'exit_price': exit_price,
                    'exit_time': timestamp,
                    'exit_reason': 'TAKE_PROFIT',
                    'profit_loss': profit_loss,
                    'profit_loss_pct': profit_loss_pct,
                    'holding_minutes': holding_minutes
                }
            
            # PRIORITY 2: If no SL/TP hit, check sentiment-based decisions
            # Check for day change - handle overnight holding decision
            if timestamp.date() != current_day and position_open:
                current_day = timestamp.date()
                
                # If overnight holding is enabled and we have the manager
                if overnight_manager and ticker:
                    # End-of-day decision (use previous day's close time)
                    eod_time = timestamp.replace(hour=16, minute=0, second=0, microsecond=0) - timedelta(days=1)
                    
                    # Check if we should hold overnight
                    should_hold = overnight_manager.should_hold_overnight_eod(ticker, eod_time)
                    
                    if not should_hold:
                        # SELL MOC - close at previous day's close price
                        prev_day_data = future_data[future_data.index.date == (current_day - timedelta(days=1))]
                        if not prev_day_data.empty:
                            exit_price = prev_day_data.iloc[-1]['Close'] - slippage
                            exit_time = prev_day_data.index[-1]
                            holding_minutes = (exit_time - entry_time).total_seconds() / 60
                            profit_loss = exit_price - realistic_entry_price
                            # Calculate P&L as percentage of total capital (14M for 14 stocks)
                            investment_per_stock = 1_000_000  # $1M per stock
                            shares = int(investment_per_stock / realistic_entry_price)
                            total_capital = 14_000_000  # 14M total capital for 14 stocks
                            profit_loss_pct = (profit_loss * shares / total_capital) * 100
                            
                            return {
                                'exit_price': exit_price,
                                'exit_time': exit_time,
                                'exit_reason': 'SENTIMENT_EOD_SELL',
                                'profit_loss': profit_loss,
                                'profit_loss_pct': profit_loss_pct,
                                'holding_minutes': holding_minutes
                            }
                    
                    # Morning decision (at market open)
                    morning_time = timestamp.replace(hour=9, minute=30, second=0, microsecond=0)
                    should_hold_morning = overnight_manager.should_hold_overnight_morning(ticker, morning_time)
                    
                    if not should_hold_morning:
                        # SELL at open
                        morning_data = future_data[future_data.index >= morning_time]
                        if not morning_data.empty:
                            exit_price = morning_data.iloc[0]['Open'] - slippage
                            exit_time = morning_data.index[0]
                            holding_minutes = (exit_time - entry_time).total_seconds() / 60
                            profit_loss = exit_price - realistic_entry_price
                            # Calculate P&L as percentage of total capital (14M for 14 stocks)
                            investment_per_stock = 1_000_000  # $1M per stock
                            shares = int(investment_per_stock / realistic_entry_price)
                            total_capital = 14_000_000  # 14M total capital for 14 stocks
                            profit_loss_pct = (profit_loss * shares / total_capital) * 100
                            
                            return {
                                'exit_price': exit_price,
                                'exit_time': exit_time,
                                'exit_reason': 'SENTIMENT_MORNING_SELL',
                                'profit_loss': profit_loss,
                                'profit_loss_pct': profit_loss_pct,
                                'holding_minutes': holding_minutes
                            }
        
        # If neither level was hit and we reach end of data, position stays open
        # Don't close the position - it should be available for evening sentiment analysis
        return {
            'exit_price': None,
            'exit_time': None,
            'exit_reason': 'POSITION_OPEN',
            'profit_loss': None,
            'profit_loss_pct': None,
            'holding_minutes': None
        }
        
    except Exception as e:
        logging.error(f"Error in trade simulation: {e}")
        return {
            'exit_price': realistic_entry_price if 'realistic_entry_price' in locals() else entry_price,
            'exit_time': entry_time,
            'exit_reason': 'ERROR',
            'profit_loss': 0.0,
            'profit_loss_pct': 0.0,
            'holding_minutes': 0
        }

def run_single_day_backtest(stocks, target_date, sentiment_threshold, stop_loss_pct, take_profit_pct, investment_per_stock, 
                           existing_positions=None, overnight_manager=None):
    """
    Run backtest for a single day
    
    Args:
        stocks (list): List of stock tickers
        target_date (str): Date in YYYY-MM-DD format
        sentiment_threshold (float): Minimum sentiment score
        stop_loss_pct (float): Stop loss percentage
        take_profit_pct (float): Take profit percentage
        investment_per_stock (float): Investment amount per stock in USD
    
    Returns:
        list: List of trade results
    """
    trades = []
    
    print(f"\n📅 Processing {target_date}...", flush=True)
    
    # Create decision time for this date (market open)
    decision_date = datetime.strptime(target_date, '%Y-%m-%d')
    # Assume market opens at 9:30 AM ET for decision time
    decision_time = decision_date.replace(hour=9, minute=30)
    
    # Screen stocks by sentiment for this date with new integrated function
    qualified_stocks = screen_stocks_by_sentiment(
        stocks, 
        min_sentiment=sentiment_threshold, 
        max_sentiment=1.0, 
        target_date=target_date,
        decision_time=decision_time
    )
    
    if not qualified_stocks:
        print(f"   No stocks qualified for {target_date}", flush=True)
        return trades
    
    print(f"   📊 {len(qualified_stocks)} stocks qualified: {list(qualified_stocks.keys())}", flush=True)
    
    # For each qualified stock, simulate trading
    for ticker, sentiment in qualified_stocks.items():
        try:
            # Fetch price data for this date and surrounding days
            start_date = (datetime.strptime(target_date, '%Y-%m-%d') - timedelta(days=2)).strftime('%Y-%m-%d')
            end_date = (datetime.strptime(target_date, '%Y-%m-%d') + timedelta(days=2)).strftime('%Y-%m-%d')
            
            price_data = fetch_historical_data(ticker, start_date, end_date, '2m')
            
            if price_data is None or price_data.empty:
                print(f"   ❌ {ticker}: No price data available")
                continue
            
            # Find trading entry point (e.g., market open on target date)
            target_dt = datetime.strptime(target_date, '%Y-%m-%d')
            
            # Look for price data on the target date
            daily_data = price_data[price_data.index.date == target_dt.date()]
            
            if daily_data.empty:
                print(f"   ❌ {ticker}: No trading data for {target_date}")
                continue
            
            # Use the first available price as entry (market open)
            entry_time = daily_data.index[0]
            entry_price = daily_data.iloc[0]['Open']
            
            # Calculate position size based on investment amount
            shares = int(investment_per_stock / entry_price)
            
            if shares <= 0:
                print(f"   ❌ {ticker}: Investment amount too small for minimum share purchase")
                continue
            
            # Import overnight manager
            from overnight_holding import get_overnight_manager
            overnight_manager = get_overnight_manager()
            
            # Simulate trade execution
            trade_result = simulate_trade_execution(
                entry_price, stop_loss_pct, take_profit_pct, price_data, entry_time,
                ticker=ticker, overnight_manager=overnight_manager, investment_per_stock=investment_per_stock
            )
            
            # Calculate dollar P&L based on actual position size
            dollar_profit_loss = (trade_result['exit_price'] - entry_price) * shares
            position_value = entry_price * shares
            
            # Create trade record
            trade = {
                'date': target_date,
                'ticker': ticker,
                'sentiment': sentiment,
                'entry_time': entry_time,
                'entry_price': entry_price,
                'shares': shares,
                'position_value': position_value,
                'exit_time': trade_result['exit_time'],
                'exit_price': trade_result['exit_price'],
                'exit_reason': trade_result['exit_reason'],
                'profit_loss': dollar_profit_loss,
                'profit_loss_pct': trade_result['profit_loss_pct'],
                'holding_minutes': trade_result['holding_minutes']
            }
            
            trades.append(trade)
            
            print(f"   📊 {ticker}: {shares} shares @ ${entry_price:.2f} - {trade_result['exit_reason']} - "
                  f"P&L: ${dollar_profit_loss:.2f} ({trade_result['profit_loss_pct']:.2f}%)")
            
        except Exception as e:
            print(f"   ❌ {ticker}: Error in simulation - {e}")
            logging.error(f"Error simulating trade for {ticker} on {target_date}: {e}")
            continue
    
    return trades

def generate_backtest_report(all_trades, start_date, end_date, params):
    """
    Generate and save detailed backtest report
    
    Args:
        all_trades (list): List of all trade results
        start_date (str): Backtest start date
        end_date (str): Backtest end date
        params (dict): Backtest parameters
    """
    if not all_trades:
        print("\n❌ No trades to report")
        return
    
    # Create DataFrame
    df = pd.DataFrame(all_trades)
    
    # Calculate summary statistics
    total_trades = len(df)
    winning_trades = len(df[df['profit_loss'] > 0])
    losing_trades = len(df[df['profit_loss'] < 0])
    win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
    
    total_profit_loss = df['profit_loss'].sum()
    avg_profit_loss = df['profit_loss'].mean()
    avg_holding_time = df['holding_minutes'].mean()
    total_position_value = df['position_value'].sum()
    # Calculate return as percentage of total capital (14M for 14 stocks)
    total_capital = 14_000_000  # 14M total capital for 14 stocks
    total_return_pct = (total_profit_loss / total_capital) * 100
    
    best_trade = df.loc[df['profit_loss'].idxmax()] if not df.empty else None
    worst_trade = df.loc[df['profit_loss'].idxmin()] if not df.empty else None
    
    # Display summary
    print("\n" + "=" * 80)
    print("                     📊 BACKTEST RESULTS SUMMARY")
    print("=" * 80)
    print(f"📅 Period: {start_date} to {end_date}")
    print(f"📊 Sentiment Threshold: {params['sentiment_threshold']:.2f}")
    print(f"🛡️  Stop Loss: {params['stop_loss_pct']:.1f}%")
    print(f"💰 Take Profit: {params['take_profit_pct']:.1f}%")
    print()
    print(f"📈 Total Trades: {total_trades}")
    print(f"✅ Winning Trades: {winning_trades} ({win_rate:.1f}%)")
    print(f"❌ Losing Trades: {losing_trades} ({100-win_rate:.1f}%)")
    print()
    print(f"💼 Total Capital Invested: {format_currency(total_position_value)}")
    print(f"💵 Total P&L: {format_currency(total_profit_loss)}")
    print(f"📈 Total Return: {total_return_pct:.2f}%")
    print(f"📊 Average P&L per Trade: {format_currency(avg_profit_loss)}")
    print(f"⏱️  Average Holding Time: {avg_holding_time:.0f} minutes")
    
    if best_trade is not None:
        print(f"\n🏆 Best Trade: {best_trade['ticker']} on {best_trade['date']}")
        print(f"   P&L: {format_currency(best_trade['profit_loss'])} ({best_trade['profit_loss_pct']:.2f}%)")
    
    if worst_trade is not None:
        print(f"\n💥 Worst Trade: {worst_trade['ticker']} on {worst_trade['date']}")
        print(f"   P&L: {format_currency(worst_trade['profit_loss'])} ({worst_trade['profit_loss_pct']:.2f}%)")
    
    # Exit reasons breakdown
    print("\n📋 Exit Reasons:")
    exit_counts = df['exit_reason'].value_counts()
    for reason, count in exit_counts.items():
        pct = (count / total_trades) * 100
        print(f"   {reason}: {count} trades ({pct:.1f}%)")
    
    # Save detailed report to Excel
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"backtest_report_{timestamp}.xlsx"
    
    try:
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Trade details sheet
            df_formatted = df.copy()
            df_formatted['entry_time'] = df_formatted['entry_time'].dt.strftime('%Y-%m-%d %H:%M:%S')
            df_formatted['exit_time'] = df_formatted['exit_time'].dt.strftime('%Y-%m-%d %H:%M:%S')
            df_formatted.to_excel(writer, sheet_name='Trade_Details', index=False)
            
            # Summary sheet
            summary_data = {
                'Metric': [
                    'Period', 'Sentiment Threshold', 'Stop Loss %', 'Take Profit %',
                    'Investment per Stock', 'Slippage per Side', 'Setup Delay (seconds)',
                    'Total Trades', 'Winning Trades', 'Win Rate %',
                    'Total Capital Invested', 'Total P&L', 'Total Return %', 
                    'Avg P&L per Trade', 'Avg Holding Time (min)'
                ],
                'Value': [
                    f"{start_date} to {end_date}",
                    f"{params['sentiment_threshold']:.2f}",
                    f"{params['stop_loss_pct']:.1f}%",
                    f"{params['take_profit_pct']:.1f}%",
                    f"${params['investment_per_stock']:,.0f}",
                    f"${DEFAULT_SLIPPAGE:.2f}",
                    f"{DEFAULT_SETUP_DELAY_SECONDS}",
                    total_trades,
                    winning_trades,
                    f"{win_rate:.1f}%",
                    f"${total_position_value:,.2f}",
                    f"${total_profit_loss:.2f}",
                    f"{total_return_pct:.2f}%",
                    f"${avg_profit_loss:.2f}",
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

def run_historical_backtest_with_overnight(params):
    """
    Historical backtest with sentiment-range overnight holding support
    
    Args:
        params (dict): Backtest parameters from user input
    """
    try:
        print("\n" + "=" * 60)
        print("   📊 HISTORICAL BACKTEST WITH OVERNIGHT HOLDING")
        print("=" * 60)
        
        # Validate environment
        validate_environment()
        print("✅ Environment validation passed")
        
        # Load stock universe
        stocks = load_stock_universe()
        print(f"✅ Loaded {len(stocks)} stocks from universe")
        
        # Initialize overnight manager
        from overnight_holding import get_overnight_manager
        overnight_manager = get_overnight_manager()
        
        # Apply command line overrides for sentiment range
        if params.get('sentiment_min_override') is not None:
            overnight_manager.sentiment_min = params['sentiment_min_override']
            print(f"🔧 Override sentiment_min: {overnight_manager.sentiment_min}")
        
        if params.get('sentiment_max_override') is not None:
            overnight_manager.sentiment_max = params['sentiment_max_override']
            print(f"🔧 Override sentiment_max: {overnight_manager.sentiment_max}")
        
        print(f"✅ Overnight holding: {'enabled' if overnight_manager.enabled else 'disabled'}")
    # BUG FIX: Clear any existing positions at backtest start
    # This prevents carrying over positions from before the backtest period
    active_positions = {}  # Reset positions for clean backtest
    
        
        # Display parameters
        print(f"\n📋 BACKTEST PARAMETERS:")
        print(f"📅 Date range: {params['start_date']} to {params['end_date']}")
        print(f"📊 Sentiment threshold: {params['sentiment_threshold']:.2f}")
        print(f"🛡️  Stop Loss: {params['stop_loss_pct']:.1f}%")
        print(f"💰 Take Profit: {params['take_profit_pct']:.1f}%")
        print(f"💼 Investment per Stock: {format_currency(params['investment_per_stock'])}")
        print(f"🌙 Overnight Range: [{overnight_manager.sentiment_min:.2f}, {overnight_manager.sentiment_max:.2f}]")
        
        # Generate date range
        start_dt = datetime.strptime(params['start_date'], '%Y-%m-%d')
        end_dt = datetime.strptime(params['end_date'], '%Y-%m-%d')
        
        # Track positions across days
        active_positions = {}  # ticker -> position_info
        all_trades = []
        
        current_date = start_dt
        print(f"\n🔄 Processing {(end_dt - start_dt).days + 1} days...")
        
        day_counter = 1
        while current_date <= end_dt:
            # Skip weekends
            if current_date.weekday() < 5:
                date_str = current_date.strftime('%Y-%m-%d')
                print(f"\n" + "="*80)
                print(f"📅 DAY {day_counter} - {date_str}")
                print("="*80)
                
                # 1. MORNING SENTIMENT CALCULATIONS
                morning_time = current_date.replace(hour=9, minute=30)
                print(f"\n🌅 MORNING SENTIMENT CALCULATIONS ({morning_time.strftime('%H:%M:%S')}):")
                print("-" * 60)
                
                # Calculate morning sentiment for all existing positions
                morning_sentiments = {}
                for ticker, position in active_positions.items():
                    sentiment = overnight_manager.get_sentiment_for_holding_decision(ticker, morning_time)
                    morning_sentiments[ticker] = sentiment
                    sentiment_str = f"{sentiment:.4f}" if sentiment is not None else "NO NEWS"
                    print(f"   {ticker}: Morning sentiment = {sentiment_str}")
                
                if not active_positions:
                    print("   No existing positions to check")
                
                # 2. MORNING SELLS (positions sold due to inappropriate sentiment)
                print(f"\n📉 MORNING SELLS (Inappropriate Sentiment):")
                print("-" * 60)
                
                positions_to_close = []
                morning_sells = []
                for ticker, position in active_positions.items():
                    should_hold = overnight_manager.should_hold_overnight_morning(ticker, morning_time)
                    
                    if not should_hold:
                        # Close position at market open
                        try:
                            # Get opening price
                            price_data = fetch_historical_data(ticker, date_str, date_str, '1m')
                            if price_data is not None and not price_data.empty:
                                open_price = price_data.iloc[0]['Open'] - DEFAULT_SLIPPAGE
                                
                                # Calculate P&L
                                profit_loss = (open_price - position['entry_price']) * position['shares']
                                # Calculate P&L as percentage of total capital (14M for 14 stocks)
                                total_capital = 14_000_000  # 14M total capital for 14 stocks
                                profit_loss_pct = (profit_loss / total_capital) * 100
                                # Handle timezone differences
                                if hasattr(position['entry_time'], 'tz') and position['entry_time'].tz is not None:
                                    # entry_time is timezone-aware, make morning_time timezone-aware too
                                    morning_time_tz = morning_time.replace(tzinfo=position['entry_time'].tz)
                                    holding_minutes = (morning_time_tz - position['entry_time']).total_seconds() / 60
                                else:
                                    # Both are naive
                                    holding_minutes = (morning_time - position['entry_time']).total_seconds() / 60
                                
                                trade = {
                                    'date': position['entry_date'],
                                    'ticker': ticker,
                                    'sentiment': position['sentiment'],
                                    'entry_time': position['entry_time'],
                                    'entry_price': position['entry_price'],
                                    'shares': position['shares'],
                                    'position_value': position['position_value'],
                                    'exit_time': morning_time,
                                    'exit_price': open_price,
                                    'exit_reason': 'SENTIMENT_MORNING_SELL',
                                    'profit_loss': profit_loss,
                                    'profit_loss_pct': profit_loss_pct,
                                    'holding_minutes': holding_minutes
                                }
                                
                                all_trades.append(trade)
                                positions_to_close.append(ticker)
                                morning_sells.append({
                                    'ticker': ticker,
                                    'price': open_price,
                                    'pnl': profit_loss,
                                    'pnl_pct': profit_loss_pct,
                                    'sentiment': morning_sentiments[ticker]
                                })
                                
                                sentiment_str = f"{morning_sentiments[ticker]:.4f}" if morning_sentiments[ticker] is not None else "NO NEWS"
                                print(f"   ❌ SOLD {ticker} @ ${open_price:.2f} - P&L: ${profit_loss:.2f} ({profit_loss_pct:.2f}%) - Sentiment: {sentiment_str}")
                        
                        except Exception as e:
                            print(f"   ❌ {ticker}: Error closing morning position - {e}")
                            positions_to_close.append(ticker)
                
                if not morning_sells:
                    print("   No positions sold due to sentiment")
                
                # Remove closed positions
                for ticker in positions_to_close:
                    del active_positions[ticker]
                
                # 3. MORNING HOLDS (positions kept due to appropriate sentiment)
                print(f"\n📈 MORNING HOLDS (Appropriate Sentiment):")
                print("-" * 60)
                
                if active_positions:
                    for ticker, position in active_positions.items():
                        sentiment_str = f"{morning_sentiments[ticker]:.4f}" if morning_sentiments[ticker] is not None else "NO NEWS"
                        print(f"   ✅ HOLDING {ticker} - Sentiment: {sentiment_str}")
                else:
                    print("   No positions held from previous day")
                
                # 4. NEW STOCK PURCHASES
                print(f"\n🛒 NEW STOCK PURCHASES:")
                print("-" * 60)
                
                available_stocks = [s for s in stocks if s not in active_positions]
                qualified_stocks = {}
                new_purchases = []
                
                if available_stocks:
                    # Get all stocks that meet sentiment range [X, Y] for qualification
                    sentiment_min_qual = params.get('sentiment_min_override', overnight_manager.sentiment_min)
                    sentiment_max_qual = params.get('sentiment_max_override', overnight_manager.sentiment_max)
                    
                    all_qualified = screen_stocks_by_sentiment(
                        available_stocks, sentiment_min_qual, sentiment_max_qual, date_str
                    )
                    
                    # If stocks are already qualified by sentiment range, BUY them!
                    # No additional filtering needed - they passed the range test
                    qualified_stocks = all_qualified
                    
                    if current_date == start_dt:
                        reason = "First Day"
                    else:
                        reason = "Qualified by Sentiment Range"
                    
                    # We'll show actual purchases in the DAY ACTIVITY section after confirming price data
                else:
                    print("   No available stocks to purchase (all positions already held)")
                    
                if not qualified_stocks:
                    print("   No new stocks purchased")
                
                # 5. EXECUTE PURCHASES AND DAY ACTIVITY
                print(f"\n⚡ DAY ACTIVITY (Intraday Trading):")
                print("-" * 60)
                
                day_activity = []
                
                # First, monitor existing positions for intraday stop-loss/take-profit
                existing_positions_to_close = []
                for ticker, position in list(active_positions.items()):
                    try:
                        # Get price data for monitoring existing position
                        price_data = fetch_historical_data(ticker, date_str, 
                                                         (current_date + timedelta(days=5)).strftime('%Y-%m-%d'), '1m')
                        
                        if price_data is not None and not price_data.empty:
                            # Simulate intraday monitoring from market open
                            market_open_time = price_data.index[0]
                            
                            # Check if position hits stop-loss or take-profit during this day
                            entry_price = position['entry_price']
                            stop_loss_price = entry_price * (1 - params['stop_loss_pct'] / 100)
                            take_profit_price = entry_price * (1 + params['take_profit_pct'] / 100)
                            
                            print(f"   🔍 Monitoring {ticker}: Entry=${entry_price:.2f}, SL=${stop_loss_price:.2f}, TP=${take_profit_price:.2f}")
                            
                            # Check each minute of today's trading for SL/TP hits
                            exit_reason = None
                            exit_price = None
                            exit_time = None
                            
                            min_low = float('inf')
                            max_high = 0
                            
                            for timestamp, row in price_data.iterrows():
                                low = row['Low']
                                high = row['High']
                                min_low = min(min_low, low)
                                max_high = max(max_high, high)
                                
                                # Check if stop loss is hit
                                if low <= stop_loss_price:
                                    exit_reason = 'STOP_LOSS'
                                    exit_price = stop_loss_price - 0.01  # Add slippage
                                    exit_time = timestamp
                                    print(f"   💥 {ticker} HIT STOP-LOSS at {timestamp}: Low=${low:.2f} <= SL=${stop_loss_price:.2f}")
                                    break
                                
                                # Check if take profit is hit
                                elif high >= take_profit_price:
                                    exit_reason = 'TAKE_PROFIT'
                                    exit_price = take_profit_price - 0.01  # Add slippage
                                    exit_time = timestamp
                                    print(f"   🎯 {ticker} HIT TAKE-PROFIT at {timestamp}: High=${high:.2f} >= TP=${take_profit_price:.2f}")
                                    break
                            
                            if not exit_reason:
                                print(f"   📊 {ticker} No SL/TP hit - Min Low: ${min_low:.2f}, Max High: ${max_high:.2f}")
                            
                            # Create trade result
                            if exit_reason:
                                trade_result = {
                                    'exit_reason': exit_reason,
                                    'exit_price': exit_price,
                                    'exit_time': exit_time,
                                    'profit_loss_pct': ((exit_price - entry_price) * shares / 14_000_000) * 100,
                                    'holding_minutes': (exit_time - position['entry_time']).total_seconds() / 60
                                }
                            else:
                                trade_result = {'exit_reason': 'POSITION_OPEN'}
                            
                            # If position was closed during intraday monitoring
                            if trade_result['exit_reason'] in ['TAKE_PROFIT', 'STOP_LOSS']:
                                shares = position['shares']
                                dollar_profit_loss = (trade_result['exit_price'] - position['entry_price']) * shares
                                
                                trade = {
                                    'date': position['entry_date'],
                                    'ticker': ticker,
                                    'sentiment': position['sentiment'],
                                    'entry_time': position['entry_time'],
                                    'entry_price': position['entry_price'],
                                    'shares': shares,
                                    'position_value': position['entry_price'] * shares,
                                    'exit_time': trade_result['exit_time'],
                                    'exit_price': trade_result['exit_price'],
                                    'exit_reason': trade_result['exit_reason'],
                                    'profit_loss': dollar_profit_loss,
                                    'profit_loss_pct': trade_result['profit_loss_pct'],
                                    'holding_minutes': trade_result['holding_minutes']
                                }
                                
                                all_trades.append(trade)
                                existing_positions_to_close.append(ticker)
                                
                                profit_loss_pct = trade_result['profit_loss_pct']
                                print(f"   💰 CLOSED {ticker} ({trade_result['exit_reason']}) @ ${trade_result['exit_price']:.2f} - P&L: ${dollar_profit_loss:.2f} ({profit_loss_pct:.2f}%)")
                                
                                day_activity.append({
                                    'ticker': ticker,
                                    'action': 'CLOSED',
                                    'reason': trade_result['exit_reason'],
                                    'price': trade_result['exit_price'],
                                    'pnl': dollar_profit_loss,
                                    'pnl_pct': profit_loss_pct
                                })
                    except Exception as e:
                        print(f"   ❌ {ticker}: Error monitoring existing position - {e}")
                
                # Remove closed existing positions
                for ticker in existing_positions_to_close:
                    if ticker in active_positions:
                        del active_positions[ticker]
                
                # Enter positions for qualified stocks
                for ticker, sentiment in qualified_stocks.items():
                        try:
                            # Get price data and enter position
                            price_data = fetch_historical_data(ticker, date_str, 
                                                             (current_date + timedelta(days=5)).strftime('%Y-%m-%d'), '1m')
                            
                            if price_data is not None and not price_data.empty:
                                entry_time = price_data.index[0]
                                entry_price = price_data.iloc[0]['Open'] + DEFAULT_SLIPPAGE
                                shares = int(params['investment_per_stock'] / entry_price)
                                
                                if shares > 0:
                                    # Store position for tracking
                                    active_positions[ticker] = {
                                        'entry_date': date_str,
                                        'entry_time': entry_time,
                                        'entry_price': entry_price,
                                        'shares': shares,
                                        'position_value': entry_price * shares,
                                        'sentiment': sentiment
                                    }
                                    new_purchases.append({
                                        'ticker': ticker,
                                        'price': entry_price,
                                        'shares': shares,
                                        'sentiment': sentiment
                                    })
                                    
                                    print(f"   📈 OPENED {ticker} @ ${entry_price:.2f} ({shares} shares) - Sentiment: {sentiment:.4f}")
                                    
                                    # Run SIMPLE intraday monitoring (only SL/TP, no sentiment)
                                    trade_result = check_intraday_stop_loss_take_profit(
                                        entry_price, params['stop_loss_pct'], params['take_profit_pct'], 
                                        price_data, entry_time, investment_per_stock=params['investment_per_stock']
                                    )
                                    
                                    print(f"   🔍 {ticker} simulation result: {trade_result['exit_reason']}")
                                    if trade_result['exit_reason'] == 'SENTIMENT_EOD_SELL':
                                        print(f"   ⚠️  {ticker} SHOULD HAVE HIT STOP-LOSS! Entry: ${entry_price:.2f}, SL: ${entry_price * 0.95:.2f}")
                                    
                                    # If position was closed during simulation, record the trade
                                    if trade_result['exit_reason'] in ['TAKE_PROFIT', 'STOP_LOSS']:
                                        dollar_profit_loss = (trade_result['exit_price'] - entry_price) * shares
                                        
                                        trade = {
                                            'date': date_str,
                                            'ticker': ticker,
                                            'sentiment': sentiment,
                                            'entry_time': entry_time,
                                            'entry_price': entry_price,
                                            'shares': shares,
                                            'position_value': entry_price * shares,
                                            'exit_time': trade_result['exit_time'],
                                            'exit_price': trade_result['exit_price'],
                                            'exit_reason': trade_result['exit_reason'],
                                            'profit_loss': dollar_profit_loss,
                                            'profit_loss_pct': trade_result['profit_loss_pct'],
                                            'holding_minutes': trade_result['holding_minutes']
                                        }
                                        
                                        all_trades.append(trade)
                                        del active_positions[ticker]  # Remove closed position
                                        
                                        profit_loss_pct = trade_result['profit_loss_pct']
                                        print(f"   💰 CLOSED {ticker} ({trade_result['exit_reason']}) @ ${trade_result['exit_price']:.2f} - P&L: ${dollar_profit_loss:.2f} ({profit_loss_pct:.2f}%)")
                                        
                                        day_activity.append({
                                            'ticker': ticker,
                                            'action': 'CLOSED',
                                            'reason': trade_result['exit_reason'],
                                            'price': trade_result['exit_price'],
                                            'pnl': dollar_profit_loss,
                                            'pnl_pct': profit_loss_pct
                                        })
                                    elif trade_result['exit_reason'] in ['POSITION_OPEN', 'NO_DATA']:
                                        # Position stays open for evening analysis - do NOT remove from active_positions
                                        pass  # Position remains in active_positions
                        
                            else:
                                print(f"   ⚠️  {ticker}: No price data available - skipping purchase")
                        except Exception as e:
                            print(f"   ❌ {ticker}: Error in position simulation - {e}")
                
                if not day_activity:
                    print("   No intraday closures (all positions held)")
                
                # Show summary of what happened to all opened positions
                print(f"\n📋 POSITION STATUS SUMMARY:")
                print("-" * 60)
                for purchase in new_purchases:
                    ticker = purchase['ticker']
                    if ticker in active_positions:
                        print(f"   ✅ {ticker}: Still open (will check evening sentiment)")
                    else:
                        # Find the closure in day_activity
                        closure = next((act for act in day_activity if act['ticker'] == ticker), None)
                        if closure:
                            print(f"   💰 {ticker}: CLOSED intraday ({closure['reason']}) - P&L: ${closure['pnl']:.2f}")
                        else:
                            print(f"   ❓ {ticker}: Status unknown")
                
                # 6. EVENING SENTIMENT CALCULATIONS
                eod_time = current_date.replace(hour=16, minute=0)
                print(f"\n🌆 EVENING SENTIMENT CALCULATIONS ({eod_time.strftime('%H:%M:%S')}):")
                print("-" * 60)
                
                # Calculate evening sentiment for all active positions
                evening_sentiments = {}
                for ticker, position in active_positions.items():
                    sentiment = overnight_manager.get_sentiment_for_holding_decision(ticker, eod_time)
                    evening_sentiments[ticker] = sentiment
                    sentiment_str = f"{sentiment:.4f}" if sentiment is not None else "NO NEWS"
                    print(f"   {ticker}: Evening sentiment = {sentiment_str}")
                
                if not active_positions:
                    print("   No positions to check")
                
                # 7. EOD DECISIONS (Sell vs Hold Overnight)
                print(f"\n🌙 EOD DECISIONS (Sell vs Hold Overnight):")
                print("-" * 60)
                
                positions_to_close_eod = []
                eod_sells = []
                eod_holds = []
                
                for ticker, position in active_positions.items():
                    eod_sentiment = evening_sentiments[ticker]
                    should_hold_eod = overnight_manager.should_hold_overnight_eod(ticker, eod_time)
                    
                    sentiment_str = f"{eod_sentiment:.4f}" if eod_sentiment is not None else "NO NEWS"
                    
                    if should_hold_eod:
                        eod_holds.append({'ticker': ticker, 'sentiment': eod_sentiment})
                        print(f"   🌙 HOLD OVERNIGHT {ticker} - Sentiment: {sentiment_str}")
                    else:
                        eod_sells.append({'ticker': ticker, 'sentiment': eod_sentiment})
                        print(f"   📉 SELL EOD {ticker} - Sentiment: {sentiment_str}")
                    
                    if not should_hold_eod:
                        # Close position at EOD (Market-On-Close)
                        try:
                            # Get closing price
                            price_data = fetch_historical_data(ticker, date_str, date_str, '1m')
                            if price_data is not None and not price_data.empty:
                                close_price = price_data.iloc[-1]['Close'] - DEFAULT_SLIPPAGE
                                
                                # Calculate P&L
                                profit_loss = (close_price - position['entry_price']) * position['shares']
                                # Calculate P&L as percentage of total capital (14M for 14 stocks)
                                total_capital = 14_000_000  # 14M total capital for 14 stocks
                                profit_loss_pct = (profit_loss / total_capital) * 100
                                # Handle timezone differences
                                if hasattr(position['entry_time'], 'tz') and position['entry_time'].tz is not None:
                                    # entry_time is timezone-aware, make eod_time timezone-aware too
                                    eod_time_tz = eod_time.replace(tzinfo=position['entry_time'].tz)
                                    holding_minutes = (eod_time_tz - position['entry_time']).total_seconds() / 60
                                else:
                                    # Both are naive
                                    holding_minutes = (eod_time - position['entry_time']).total_seconds() / 60
                                
                                trade = {
                                    'date': position['entry_date'],
                                    'ticker': ticker,
                                    'sentiment': position['sentiment'],
                                    'entry_time': position['entry_time'],
                                    'entry_price': position['entry_price'],
                                    'shares': position['shares'],
                                    'position_value': position['position_value'],
                                    'exit_time': eod_time,
                                    'exit_price': close_price,
                                    'exit_reason': 'SENTIMENT_EOD_SELL',
                                    'profit_loss': profit_loss,
                                    'profit_loss_pct': profit_loss_pct,
                                    'holding_minutes': holding_minutes
                                }
                                
                                all_trades.append(trade)
                                positions_to_close_eod.append(ticker)
                                
                                print(f"   💰 EXECUTED SELL {ticker} @ ${close_price:.2f} - P&L: ${profit_loss:.2f} ({profit_loss_pct:.2f}%)")
                        
                        except Exception as e:
                            print(f"   ❌ {ticker}: Error closing EOD position - {e}")
                            positions_to_close_eod.append(ticker)
                
                # Remove EOD closed positions
                for ticker in positions_to_close_eod:
                    if ticker in active_positions:
                        del active_positions[ticker]
                
                # End of day summary
                print(f"\n📊 END OF DAY SUMMARY:")
                print("-" * 60)
                print(f"   Active positions for overnight: {len(active_positions)}")
                if active_positions:
                    for ticker in active_positions.keys():
                        print(f"   🌙 {ticker} - Holding overnight")
                
                day_counter += 1
            
            current_date += timedelta(days=1)
        
        # Close any remaining positions at backtest end
        print(f"\n🔚 Closing {len(active_positions)} remaining positions at backtest end...")
        for ticker, position in active_positions.items():
            try:
                # Use last available price
                last_date = end_dt.strftime('%Y-%m-%d')
                price_data = fetch_historical_data(ticker, last_date, last_date, '1m')
                
                if price_data is not None and not price_data.empty:
                    exit_price = price_data.iloc[-1]['Close'] - DEFAULT_SLIPPAGE
                    exit_time = price_data.index[-1]
                    
                    profit_loss = (exit_price - position['entry_price']) * position['shares']
                    # Calculate P&L as percentage of total capital (14M for 14 stocks)
                    total_capital = 14_000_000  # 14M total capital for 14 stocks
                    profit_loss_pct = (profit_loss / total_capital) * 100
                    # Handle timezone differences for backtest end
                    if hasattr(position['entry_time'], 'tz') and position['entry_time'].tz is not None:
                        # entry_time is timezone-aware, make exit_time timezone-aware too
                        if hasattr(exit_time, 'tz') and exit_time.tz is not None:
                            holding_minutes = (exit_time - position['entry_time']).total_seconds() / 60
                        else:
                            exit_time_tz = exit_time.replace(tzinfo=position['entry_time'].tz)
                            holding_minutes = (exit_time_tz - position['entry_time']).total_seconds() / 60
                    else:
                        # Both are naive
                        holding_minutes = (exit_time - position['entry_time']).total_seconds() / 60
                    
                    trade = {
                        'date': position['entry_date'],
                        'ticker': ticker,
                        'sentiment': position['sentiment'],
                        'entry_time': position['entry_time'],
                        'entry_price': position['entry_price'],
                        'shares': position['shares'],
                        'position_value': position['position_value'],
                        'exit_time': exit_time,
                        'exit_price': exit_price,
                        'exit_reason': 'BACKTEST_END',
                        'profit_loss': profit_loss,
                        'profit_loss_pct': profit_loss_pct,
                        'holding_minutes': holding_minutes
                    }
                    
                    all_trades.append(trade)
                    print(f"   🔚 {ticker}: Final close @ ${exit_price:.2f} - P&L: ${profit_loss:.2f}")
            
            except Exception as e:
                print(f"   ❌ {ticker}: Error closing final position - {e}")
        
        # Generate report
        if all_trades:
            generate_backtest_report(all_trades, params['start_date'], params['end_date'], params)
        else:
            print("\n❌ No trades executed during backtest period")
        
        return all_trades
        
    except Exception as e:
        print(f"\n❌ Backtest failed: {e}")
        logging.error(f"Historical backtest failed: {e}")
        return []

def run_historical_backtest(params):
    """
    Main historical backtest execution function
    
    Args:
        params (dict): Backtest parameters from user input
    """
    try:
        # Check if overnight holding is enabled
        from overnight_holding import get_overnight_manager
        overnight_manager = get_overnight_manager()
        
        # Always use the overnight holding backtest logic (unified logic)
        # When overnight holding is disabled, it will just force EOD closure
        return run_historical_backtest_with_overnight(params)
        
        print("\n" + "=" * 60)
        print("       📊 HISTORICAL BACKTEST STARTING")
        print("=" * 60)
        
        # Validate environment
        validate_environment()
        print("✅ Environment validation passed")
        
        # Load stock universe
        stocks = load_stock_universe()
        print(f"✅ Loaded {len(stocks)} stocks from universe")
        
        # Display parameters (including realism settings)
        print(f"\n📋 BACKTEST PARAMETERS:")
        print(f"📅 Date range: {params['start_date']} to {params['end_date']}")
        print(f"📊 Sentiment threshold: {params['sentiment_threshold']:.2f}")
        print(f"🛡️  Stop Loss: {params['stop_loss_pct']:.1f}%")
        print(f"💰 Take Profit: {params['take_profit_pct']:.1f}%")
        print(f"💼 Investment per Stock: {format_currency(params['investment_per_stock'])}")
        print(f"🎯 Realism: Slippage=${DEFAULT_SLIPPAGE:.2f}/side, Setup delay={DEFAULT_SETUP_DELAY_SECONDS}s")
        
        # Log realism settings for the report
        logging.info(f"Backtest realism settings: Slippage=${DEFAULT_SLIPPAGE:.2f}, Setup delay={DEFAULT_SETUP_DELAY_SECONDS}s")
        
        # Generate date range
        start_dt = datetime.strptime(params['start_date'], '%Y-%m-%d')
        end_dt = datetime.strptime(params['end_date'], '%Y-%m-%d')
        
        current_date = start_dt
        all_trades = []
        
        print(f"\n🔄 Processing {(end_dt - start_dt).days + 1} days...")
        
        # Process each day
        while current_date <= end_dt:
            # Skip weekends (assuming market is closed)
            if current_date.weekday() < 5:  # Monday = 0, Friday = 4
                date_str = current_date.strftime('%Y-%m-%d')
                
                day_trades = run_single_day_backtest(
                    stocks, date_str, params['sentiment_threshold'],
                    params['stop_loss_pct'], params['take_profit_pct'], 
                    params['investment_per_stock']
                )
                
                all_trades.extend(day_trades)
            
            current_date += timedelta(days=1)
        
        # Generate report
        generate_backtest_report(all_trades, params['start_date'], params['end_date'], params)
        
        print("\n🏁 HISTORICAL BACKTEST COMPLETED")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR in historical backtest: {e}")
        logging.error(f"Critical error in historical backtest: {e}")
        raise 

def main():
    """
    CLI entry point for historical backtesting
    """
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(
        description='Historical Backtest - Test trading strategies on historical data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 historical_backtest.py --start 2024-10-15 --end 2024-10-18 --log-level INFO
  python3 historical_backtest.py --start 2024-12-01 --end 2024-12-05 --sentiment 0.3 --stop-loss 3 --take-profit 5
        """
    )
    
    # Required arguments
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    
    # Optional trading parameters
    parser.add_argument('--sentiment', type=float, default=0.2, help='Sentiment threshold (default: 0.2)')
    parser.add_argument('--sentiment-min', type=float, help='Overnight holding sentiment minimum (x) - overrides config')
    parser.add_argument('--sentiment-max', type=float, help='Overnight holding sentiment maximum (y) - overrides config')
    parser.add_argument('--stop-loss', type=float, default=5.0, help='Stop loss percentage (default: 5.0)')
    parser.add_argument('--take-profit', type=float, default=5.0, help='Take profit percentage (default: 5.0)')
    parser.add_argument('--investment', type=float, default=10000, help='Investment per stock (default: 10000)')
    
    # System parameters
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       default='INFO', help='Logging level (default: INFO)')
    parser.add_argument('--no-input', action='store_true',
                       help='Non-interactive mode (no prompts)')
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = getattr(logging, args.log_level.upper())
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/backtest.log'),
            logging.StreamHandler()
        ]
    )
    
    # Validate date format
    try:
        start_dt = datetime.strptime(args.start, '%Y-%m-%d')
        end_dt = datetime.strptime(args.end, '%Y-%m-%d')
        
        if start_dt >= end_dt:
            print("❌ ERROR: Start date must be before end date")
            sys.exit(1)
            
        if (end_dt - start_dt).days > 30:
            print("⚠️  WARNING: Date range is longer than 30 days, this may take a while...")
            
    except ValueError as e:
        print(f"❌ ERROR: Invalid date format: {e}")
        print("Please use YYYY-MM-DD format (e.g., 2024-10-15)")
        sys.exit(1)
    
    # Create parameters dictionary
    params = {
        'start_date': args.start,
        'end_date': args.end,
        'sentiment_threshold': args.sentiment,
        'stop_loss_pct': args.stop_loss,
        'take_profit_pct': args.take_profit,
        'investment_per_stock': args.investment,
        'sentiment_min_override': getattr(args, 'sentiment_min', None),
        'sentiment_max_override': getattr(args, 'sentiment_max', None)
    }
    
    print(f"\n🚀 STARTING HISTORICAL BACKTEST", flush=True)
    print(f"📅 Period: {args.start} to {args.end}", flush=True)
    print(f"📊 Sentiment Threshold: {args.sentiment}", flush=True)
    print(f"🛡️  Stop Loss: {args.stop_loss}%", flush=True)
    print(f"💰 Take Profit: {args.take_profit}%", flush=True)
    print(f"💼 Investment per Stock: ${args.investment:,.0f}", flush=True)
    print(f"📝 Log Level: {args.log_level}", flush=True)
    
    try:
        # Ensure logs directory exists
        os.makedirs('logs', exist_ok=True)
        
        print("📂 Loading configuration...", flush=True)
        print("🔧 Validating environment...", flush=True)
        
        # Run the backtest
        run_historical_backtest(params)
        
        print(f"\n🎉 SUCCESS: Backtest completed successfully!")
        print(f"📁 Check the reports/ directory for output files")
        
    except KeyboardInterrupt:
        print(f"\n⚠️  Backtest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        logging.error(f"Backtest failed: {e}")
        print(f"\n💡 TROUBLESHOOTING:")
        print(f"1. Run: python3 system_diagnose.py")
        print(f"2. Check logs/backtest.log for details")
        print(f"3. Verify your .env file has valid API keys")
        sys.exit(1)

if __name__ == "__main__":
    main()