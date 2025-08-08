"""
LIVE TRADING MODULE
==================
Handles real-time trading execution with Alpaca API
"""

import time
import logging
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from alpaca_trade_api.rest import REST
from alpaca.trading.client import TradingClient

from trading_core import (
    validate_environment, load_stock_universe, screen_stocks_by_sentiment,
    calculate_position_size, format_currency, log_trade_attempt
)
from trade_types import bracket_order, get_account_info
from cancel_all import cancel_all_orders_and_positions

import os
from dotenv import load_dotenv

# Load API credentials
load_dotenv(dotenv_path=".env")
alpaca_api_key = os.getenv("apikey")
alpaca_secret_key = os.getenv("apisecret")

# Initialize Alpaca clients
trading_client = TradingClient(alpaca_api_key, alpaca_secret_key, paper=True)
paper_api = REST(alpaca_api_key, alpaca_secret_key, base_url="https://paper-api.alpaca.markets")

def wait_for_start_time(target_time):
    """Wait until the specified start time"""
    current_time = datetime.now().time()
    target_datetime = datetime.combine(datetime.now().date(), target_time)
    
    # If target time has already passed today, schedule for tomorrow
    if current_time > target_time:
        target_datetime += timedelta(days=1)
        print(f"⏰ Target time {target_time} has passed today. Scheduling for tomorrow.")
    
    print(f"⏰ Current time: {current_time.strftime('%H:%M:%S')}")
    print(f"🎯 Target start time: {target_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Calculate wait time
    wait_seconds = (target_datetime - datetime.now()).total_seconds()
    
    if wait_seconds > 0:
        print(f"⏳ Waiting {wait_seconds/60:.1f} minutes until start time...")
        
        # Show countdown for last 60 seconds
        while wait_seconds > 60:
            time.sleep(60)
            wait_seconds -= 60
            print(f"⏳ {wait_seconds/60:.1f} minutes remaining...")
        
        # Final countdown
        if wait_seconds > 0:
            print(f"⏳ Final countdown: {wait_seconds:.0f} seconds...")
            time.sleep(wait_seconds)
    
    print("🚀 STARTING LIVE TRADING NOW!")

def execute_trade(ticker, shares, current_price, stop_loss_amount, take_profit_amount):
    """
    Execute a single trade with bracket order
    
    Args:
        ticker (str): Stock ticker
        shares (int): Number of shares to buy
        current_price (float): Current stock price
        stop_loss_amount (float): Stop loss amount in dollars
        take_profit_amount (float): Take profit amount in dollars
    
    Returns:
        tuple: (success, result_message)
    """
    try:
        # Calculate stop loss and take profit prices
        stop_loss_price = round(current_price - stop_loss_amount, 2)
        take_profit_price = round(current_price + take_profit_amount, 2)
        
        # Ensure positive prices
        if stop_loss_price <= 0:
            stop_loss_price = round(current_price * 0.95, 2)  # 5% fallback
        
        log_trade_attempt(
            ticker, 
            "TRADE_ATTEMPT",
            f"{shares} shares @ ${current_price:.2f}, SL: ${stop_loss_price:.2f}, TP: ${take_profit_price:.2f}"
        )
        
        # Execute bracket order
        result = bracket_order(
            symbol=ticker,
            qty=shares,
            side="BUY",
            tif="DAY",
            low=stop_loss_price,
            high=take_profit_price
        )
        
        log_trade_attempt(ticker, "TRADE_SUCCESS", f"Order placed - {result}")
        return True, result
        
    except Exception as e:
        error_msg = f"Trade failed: {str(e)}"
        log_trade_attempt(ticker, "TRADE_FAILED", error_msg)
        return False, error_msg

def run_live_trading(params):
    """
    Main live trading execution function
    
    Args:
        params (dict): Trading parameters from user input
    """
    try:
        print("\n" + "=" * 60)
        print("       🚀 LIVE TRADING SESSION STARTING")
        print("=" * 60)
        
        # Validate environment
        validate_environment()
        print("✅ Environment validation passed")
        
        # Load stock universe
        stocks = load_stock_universe()
        print(f"✅ Loaded {len(stocks)} stocks from universe")
        
        # Display trading parameters
        print(f"\n📋 TRADING PARAMETERS:")
        print(f"⏰ Start time: {params['start_time']}")
        print(f"⏱️  Holding time: {params['holding_minutes']} minutes")
        print(f"📊 Sentiment range: {params['min_sentiment']:.2f} to {params['max_sentiment']:.2f}")
        print(f"🛡️  Stop Loss: ${params['stop_loss']:.2f}")
        print(f"💰 Take Profit: ${params['take_profit']:.2f}")
        
        # Get account information
        account_info = get_account_info()
        buying_power = float(account_info['buying_power'])
        print(f"\n💵 Account buying power: {format_currency(buying_power)}")
        
        # Wait for start time
        wait_for_start_time(params['start_time'])
        
        # Perform sentiment analysis
        qualified_stocks = screen_stocks_by_sentiment(
            stocks,
            params['min_sentiment'],
            params['max_sentiment']
        )
        
        if not qualified_stocks:
            print("\n❌ No stocks qualified for trading. Session ended.")
            return
        
        # Calculate position sizing
        num_stocks = len(qualified_stocks)
        available_capital = buying_power * 0.9  # Use 90% of buying power
        
        print(f"\n💰 POSITION SIZING:")
        print(f"📊 Available capital: {format_currency(available_capital)}")
        print(f"📈 Number of stocks: {num_stocks}")
        print(f"💼 Capital per stock: {format_currency(available_capital / num_stocks)}")
        
        # Prepare trades
        trade_params = []
        for ticker in qualified_stocks:
            try:
                current_price = paper_api.get_latest_trade(ticker).price
                shares = calculate_position_size(available_capital, num_stocks, current_price)
                
                if shares > 0:
                    trade_params.append({
                        'ticker': ticker,
                        'shares': shares,
                        'price': current_price,
                        'sentiment': qualified_stocks[ticker]
                    })
                    print(f"✅ {ticker}: {shares} shares @ ${current_price:.2f} (sentiment: {qualified_stocks[ticker]:.4f})")
                else:
                    print(f"❌ {ticker}: Insufficient capital for minimum position")
                    
            except Exception as e:
                print(f"❌ {ticker}: Error getting price - {e}")
                continue
        
        if not trade_params:
            print("\n❌ No trades can be executed due to insufficient capital. Session ended.")
            return
        
        # Execute trades concurrently
        print(f"\n🚀 EXECUTING {len(trade_params)} TRADES:")
        print("=" * 60)
        
        futures = {}
        with ThreadPoolExecutor(max_workers=len(trade_params)) as executor:
            for trade in trade_params:
                future = executor.submit(
                    execute_trade,
                    trade['ticker'],
                    trade['shares'],
                    trade['price'],
                    params['stop_loss'],
                    params['take_profit']
                )
                futures[future] = trade
        
        # Collect results
        successful_trades = []
        failed_trades = []
        
        for future in futures:
            trade = futures[future]
            ticker = trade['ticker']
            try:
                success, result = future.result(timeout=30)
                if success:
                    successful_trades.append(ticker)
                    print(f"✅ {ticker}: SUCCESS - {result}")
                else:
                    failed_trades.append((ticker, result))
                    print(f"❌ {ticker}: FAILED - {result}")
            except Exception as e:
                failed_trades.append((ticker, str(e)))
                print(f"❌ {ticker}: TIMEOUT/ERROR - {e}")
        
        # Trading summary
        print("\n" + "=" * 60)
        print("📊 TRADING EXECUTION SUMMARY:")
        print(f"✅ Successful trades: {len(successful_trades)}")
        print(f"❌ Failed trades: {len(failed_trades)}")
        
        if successful_trades:
            print(f"✅ Success: {', '.join(successful_trades)}")
        
        if failed_trades:
            print("❌ Failures:")
            for ticker, reason in failed_trades:
                print(f"   {ticker}: {reason}")
        
        # If we have successful trades, set up auto-close
        if successful_trades:
            close_time = datetime.now() + timedelta(minutes=params['holding_minutes'])
            print(f"\n⏰ Positions will be closed at: {close_time.strftime('%H:%M:%S')}")
            print(f"⏳ Holding time: {params['holding_minutes']} minutes")
            
            # Wait for holding period
            print(f"\n⏳ Waiting {params['holding_minutes']} minutes before closing positions...")
            
            # Show countdown every minute for last 10 minutes
            remaining_minutes = params['holding_minutes']
            while remaining_minutes > 10:
                time.sleep(60)
                remaining_minutes -= 1
                print(f"⏳ {remaining_minutes} minutes remaining...")
            
            # Show countdown every 30 seconds for last 10 minutes
            while remaining_minutes > 0:
                if remaining_minutes <= 10:
                    print(f"⏳ {remaining_minutes} minutes remaining...")
                time.sleep(60)
                remaining_minutes -= 1
            
            # Close all positions
            print("\n🔒 CLOSING ALL POSITIONS...")
            try:
                cancel_result = cancel_all_orders_and_positions()
                print(f"✅ Position closure completed: {cancel_result}")
            except Exception as e:
                print(f"❌ Error closing positions: {e}")
                logging.error(f"Failed to close positions: {e}")
        
        print("\n🏁 LIVE TRADING SESSION COMPLETED")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR in live trading: {e}")
        logging.error(f"Critical error in live trading: {e}")
        raise 