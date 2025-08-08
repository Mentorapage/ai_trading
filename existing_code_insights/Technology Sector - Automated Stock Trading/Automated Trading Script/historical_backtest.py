"""
HISTORICAL BACKTEST MODULE
=========================
Handles historical backtesting with real minute-level price data
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import os
from typing import Dict, List, Tuple
import time

from trading_core import (
    validate_environment, load_stock_universe, get_sentiment,
    format_currency, format_percentage
)

def fetch_historical_data(ticker, start_date, end_date, interval='2m'):
    """
    Fetch historical price data for a ticker
    
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
        
        # Download data using yfinance
        data = yf.download(
            ticker,
            start=start_dt.strftime('%Y-%m-%d'),
            end=end_dt.strftime('%Y-%m-%d'),
            interval=interval,
            progress=False
        )
        
        if data.empty:
            logging.warning(f"No data available for {ticker} in the specified period")
            return None
        
        # Clean and prepare data
        data = data.dropna()
        
        # Flatten multi-level columns if they exist
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(1)
        
        # Ensure we have required columns
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in data.columns for col in required_cols):
            logging.error(f"Missing required columns for {ticker}: {data.columns.tolist()}")
            return None
        
        logging.info(f"Fetched {len(data)} data points for {ticker} from {start_date} to {end_date}")
        return data
        
    except Exception as e:
        logging.error(f"Error fetching data for {ticker}: {e}")
        return None

def simulate_trade_execution(entry_price, stop_loss_pct, take_profit_pct, price_data, entry_time):
    """
    Simulate realistic trade execution using minute-level price data
    
    Args:
        entry_price (float): Entry price
        stop_loss_pct (float): Stop loss percentage
        take_profit_pct (float): Take profit percentage
        price_data (pd.DataFrame): Price data for the trading period
        entry_time (pd.Timestamp): Trade entry timestamp
    
    Returns:
        dict: Trade result with exit price, time, and reason
    """
    try:
        # Calculate stop loss and take profit levels
        stop_loss_price = entry_price * (1 - stop_loss_pct / 100)
        take_profit_price = entry_price * (1 + take_profit_pct / 100)
        
        # Get price data after entry time
        future_data = price_data[price_data.index > entry_time].head(390)  # Max 6.5 hours of trading
        
        if future_data.empty:
            return {
                'exit_price': entry_price,
                'exit_time': entry_time,
                'exit_reason': 'NO_DATA',
                'profit_loss': 0.0,
                'profit_loss_pct': 0.0,
                'holding_minutes': 0
            }
        
        # Simulate each minute to determine which level is hit first
        for timestamp, row in future_data.iterrows():
            high = row['High']
            low = row['Low']
            close = row['Close']
            
            # Determine which level is hit first within this candle
            # Use a more sophisticated approach based on the price movement pattern
            
            # If both levels could be hit in the same candle
            if low <= stop_loss_price and high >= take_profit_price:
                # Use close price to determine which was likely hit first
                # If close is closer to take profit, assume TP was hit first
                distance_to_tp = abs(close - take_profit_price)
                distance_to_sl = abs(close - stop_loss_price)
                
                if distance_to_tp < distance_to_sl:
                    # Take profit hit first
                    exit_price = take_profit_price
                    exit_reason = 'TAKE_PROFIT'
                else:
                    # Stop loss hit first
                    exit_price = stop_loss_price
                    exit_reason = 'STOP_LOSS'
                    
                holding_minutes = (timestamp - entry_time).total_seconds() / 60
                profit_loss = exit_price - entry_price
                profit_loss_pct = (profit_loss / entry_price) * 100
                
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
                holding_minutes = (timestamp - entry_time).total_seconds() / 60
                profit_loss = stop_loss_price - entry_price
                profit_loss_pct = (profit_loss / entry_price) * 100
                
                return {
                    'exit_price': stop_loss_price,
                    'exit_time': timestamp,
                    'exit_reason': 'STOP_LOSS',
                    'profit_loss': profit_loss,
                    'profit_loss_pct': profit_loss_pct,
                    'holding_minutes': holding_minutes
                }
            
            # Check if only take profit is hit
            elif high >= take_profit_price:
                holding_minutes = (timestamp - entry_time).total_seconds() / 60
                profit_loss = take_profit_price - entry_price
                profit_loss_pct = (profit_loss / entry_price) * 100
                
                return {
                    'exit_price': take_profit_price,
                    'exit_time': timestamp,
                    'exit_reason': 'TAKE_PROFIT',
                    'profit_loss': profit_loss,
                    'profit_loss_pct': profit_loss_pct,
                    'holding_minutes': holding_minutes
                }
        
        # If neither level was hit, close at the last available price
        last_row = future_data.iloc[-1]
        last_timestamp = future_data.index[-1]
        exit_price = last_row['Close']
        
        holding_minutes = (last_timestamp - entry_time).total_seconds() / 60
        profit_loss = exit_price - entry_price
        profit_loss_pct = (profit_loss / entry_price) * 100
        
        return {
            'exit_price': exit_price,
            'exit_time': last_timestamp,
            'exit_reason': 'TIME_LIMIT',
            'profit_loss': profit_loss,
            'profit_loss_pct': profit_loss_pct,
            'holding_minutes': holding_minutes
        }
        
    except Exception as e:
        logging.error(f"Error in trade simulation: {e}")
        return {
            'exit_price': entry_price,
            'exit_time': entry_time,
            'exit_reason': 'ERROR',
            'profit_loss': 0.0,
            'profit_loss_pct': 0.0,
            'holding_minutes': 0
        }

def run_single_day_backtest(stocks, target_date, sentiment_threshold, stop_loss_pct, take_profit_pct, investment_per_stock):
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
    
    print(f"\n📅 Processing {target_date}...")
    
    # Screen stocks by sentiment for this date
    qualified_stocks = {}
    for ticker in stocks:
        try:
            sentiment = get_sentiment(ticker, target_date)
            if sentiment >= sentiment_threshold:
                qualified_stocks[ticker] = sentiment
                print(f"✅ {ticker}: {sentiment:.4f} (qualified)")
            else:
                print(f"❌ {ticker}: {sentiment:.4f} (not qualified)")
            
            time.sleep(0.5)  # Rate limiting
            
        except Exception as e:
            print(f"❌ {ticker}: Error getting sentiment - {e}")
            continue
    
    if not qualified_stocks:
        print(f"   No stocks qualified for {target_date}")
        return trades
    
    print(f"   {len(qualified_stocks)} stocks qualified: {list(qualified_stocks.keys())}")
    
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
            
            # Simulate trade execution
            trade_result = simulate_trade_execution(
                entry_price, stop_loss_pct, take_profit_pct, price_data, entry_time
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
    total_return_pct = (total_profit_loss / total_position_value) * 100 if total_position_value > 0 else 0
    
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
                    'Investment per Stock', 'Total Trades', 'Winning Trades', 'Win Rate %',
                    'Total Capital Invested', 'Total P&L', 'Total Return %', 
                    'Avg P&L per Trade', 'Avg Holding Time (min)'
                ],
                'Value': [
                    f"{start_date} to {end_date}",
                    f"{params['sentiment_threshold']:.2f}",
                    f"{params['stop_loss_pct']:.1f}%",
                    f"{params['take_profit_pct']:.1f}%",
                    f"${params['investment_per_stock']:,.0f}",
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

def run_historical_backtest(params):
    """
    Main historical backtest execution function
    
    Args:
        params (dict): Backtest parameters from user input
    """
    try:
        print("\n" + "=" * 60)
        print("       📊 HISTORICAL BACKTEST STARTING")
        print("=" * 60)
        
        # Validate environment
        validate_environment()
        print("✅ Environment validation passed")
        
        # Load stock universe
        stocks = load_stock_universe()
        print(f"✅ Loaded {len(stocks)} stocks from universe")
        
        # Display parameters
        print(f"\n📋 BACKTEST PARAMETERS:")
        print(f"📅 Date range: {params['start_date']} to {params['end_date']}")
        print(f"📊 Sentiment threshold: {params['sentiment_threshold']:.2f}")
        print(f"🛡️  Stop Loss: {params['stop_loss_pct']:.1f}%")
        print(f"💰 Take Profit: {params['take_profit_pct']:.1f}%")
        print(f"💼 Investment per Stock: {format_currency(params['investment_per_stock'])}")
        
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