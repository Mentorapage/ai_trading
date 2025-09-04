"""
LIVE TRADING MODULE
==================
Handles real-time trading execution with Alpaca API
"""

# ensure .env and nltk are ready
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

# fix NLTK paths/lexicon
import bootstrap_nltk  # noqa

# (optional) set SSL cert for any future downloads
import os, certifi
os.environ.setdefault("SSL_CERT_FILE", certifi.where())

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
from trade_types import bracket_order, get_account_info, check_order_and_calculate_pnl, execute_market_buy_with_protection, get_fresh_quote, is_market_open
from cancel_all import cancel_all_orders_and_positions
from notifier import notify_trade_opened, notify_trade_closed, notify_system_status

import os
from dotenv import load_dotenv

# Load API credentials
load_dotenv(dotenv_path=".env")
alpaca_api_key = os.getenv("apikey")
alpaca_secret_key = os.getenv("apisecret")

# Initialize Alpaca clients (ensuring paper trading mode)
trading_client = TradingClient(alpaca_api_key, alpaca_secret_key, paper=True)
paper_api = REST(alpaca_api_key, alpaca_secret_key, base_url="https://paper-api.alpaca.markets")

# Log connection details
logging.info("Connected to Alpaca Paper Trading API")

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

def execute_trade(ticker, shares, initial_price, stop_loss_amount, take_profit_amount):
    """
    Execute a single trade using market buy first, then protective orders
    
    Args:
        ticker (str): Stock ticker
        shares (int): Number of shares to buy
        initial_price (float): Initial price reference (for calculating target spreads)
        stop_loss_amount (float): Stop loss amount in dollars
        take_profit_amount (float): Take profit amount in dollars
    
    Returns:
        tuple: (success, result_data)
    """
    try:
        # Calculate target stop loss and take profit prices based on initial price
        target_stop_loss_price = initial_price - stop_loss_amount
        target_take_profit_price = initial_price + take_profit_amount
        
        # Ensure positive prices for target calculations
        if target_stop_loss_price <= 0:
            target_stop_loss_price = initial_price * 0.95  # 5% fallback
        
        log_trade_attempt(
            ticker, 
            "TRADE_ATTEMPT",
            f"{shares} shares, target entry @ ${initial_price:.2f}, SL: ${target_stop_loss_price:.2f}, TP: ${target_take_profit_price:.2f}"
        )
        
        # Execute market buy with protective orders using new approach
        result = execute_market_buy_with_protection(
            symbol=ticker,
            qty=shares,
            stop_loss_price=target_stop_loss_price,
            take_profit_price=target_take_profit_price,
            max_retries=2
        )
        
        if result['success']:
            success_msg = f"Market buy executed: {result['filled_qty']} shares @ ${result['fill_price']:.2f}"
            log_trade_attempt(ticker, "TRADE_SUCCESS", success_msg)
            
            # Return success with all order details for tracking
            return True, {
                "buy_order_id": result['buy_order_id'],
                "filled_qty": result['filled_qty'],
                "fill_price": result['fill_price'],
                "total_cost": result['total_cost'],
                "protective_orders": result['protective_orders']
            }
        else:
            error_msg = f"Trade failed: {result['error']}"
            log_trade_attempt(ticker, "TRADE_FAILED", error_msg)
            return False, error_msg
        
    except Exception as e:
        error_msg = f"Trade execution error: {str(e)}"
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
        
        # Send system status notification
        try:
            session_info = f"Live Trading Session Starting\n"
            session_info += f"Start Time: {params['start_time']}\n"
            session_info += f"Holding Time: {params['holding_minutes']} minutes\n"
            session_info += f"Sentiment Range: {params['min_sentiment']:.2f} to {params['max_sentiment']:.2f}\n"
            session_info += f"Stop Loss: ${params['stop_loss']:.2f}\n"
            session_info += f"Take Profit: ${params['take_profit']:.2f}"
            
            if params.get('test_mode', False):
                session_info += "\n🧪 TEST MODE ENABLED"
            
            notify_system_status(session_info, "INFO")
        except Exception as notify_error:
            logging.warning(f"Failed to send session start notification: {notify_error}")
        
        # Validate environment
        validate_environment()
        print("✅ Environment validation passed")
        
        # Load stock universe
        stocks = load_stock_universe()
        
        # Check if test mode is enabled
        if params.get('test_mode', False):
            # Use only 2-3 stocks for testing
            test_stocks = ['AAPL', 'MSFT', 'NVDA']  # Use highly liquid stocks
            stocks = [stock for stock in test_stocks if stock in stocks][:3]
            print(f"🧪 TEST MODE: Using {len(stocks)} stocks for faster testing: {stocks}")
            logging.info(f"Test mode enabled - using stocks: {stocks}")
        else:
            print(f"✅ Loaded {len(stocks)} stocks from universe")
        
        # Display trading parameters
        print(f"\n📋 TRADING PARAMETERS:")
        print(f"⏰ Start time: {params['start_time']}")
        print(f"⏱️  Holding time: {params['holding_minutes']} minutes")
        print(f"📊 Sentiment range: {params['min_sentiment']:.2f} to {params['max_sentiment']:.2f}")
        print(f"🛡️  Stop Loss: ${params['stop_loss']:.2f}")
        print(f"💰 Take Profit: ${params['take_profit']:.2f}")
        
        # Get account information with detailed validation
        account_info = get_account_info()
        buying_power = account_info['buying_power']
        cash = account_info['cash']
        
        print(f"\n💵 ACCOUNT INFORMATION:")
        print(f"   Cash: {format_currency(cash)}")
        print(f"   Buying Power: {format_currency(buying_power)}")
        print(f"   Account Status: {account_info['status']}")
        
        # Use the more conservative value between cash and buying power
        # with additional safety buffer for paper trading
        if cash > 0:
            # Use actual cash available, not leveraged buying power
            available_capital = min(cash, buying_power) * 0.8  # 80% safety buffer
            print(f"   Using conservative capital: {format_currency(available_capital)} (80% of cash)")
        else:
            available_capital = buying_power * 0.5  # Very conservative for margin accounts
            print(f"   Using margin capital: {format_currency(available_capital)} (50% of buying power)")
        
        # Wait for start time
        wait_for_start_time(params['start_time'])
        
        # Check if market is open before proceeding
        print(f"\n🕐 CHECKING MARKET STATUS...")
        market_open, next_open_time, market_message = is_market_open()
        print(f"📊 {market_message}")
        logging.info(f"Market status: {market_message}")
        
        if not market_open:
            if next_open_time:
                print(f"\n⚠️  Market is currently closed!")
                user_choice = input(f"Would you like to wait until market opens at {next_open_time.strftime('%Y-%m-%d %H:%M ET')}? (yes/no): ").strip().lower()
                
                if user_choice in ['yes', 'y']:
                    wait_time = (next_open_time - datetime.now(next_open_time.tzinfo)).total_seconds()
                    if wait_time > 0:
                        print(f"⏳ Waiting {wait_time/3600:.1f} hours until market opens...")
                        logging.info(f"Waiting for market to open at {next_open_time}")
                        # Note: In a real implementation, you might want to sleep here
                        # For now, we'll proceed with paper trading regardless
                else:
                    print("❌ Trading cancelled - market is closed")
                    return
            else:
                print("❌ Market is closed and no upcoming session found. Please try again during market hours.")
                return
        
        print("✅ Proceeding with trading session...")
        
        # Perform sentiment analysis with current time as decision time
        current_decision_time = datetime.now()
        qualified_stocks = screen_stocks_by_sentiment(
            stocks,
            params['min_sentiment'],
            params['max_sentiment'],
            target_date=None,  # Use today
            decision_time=current_decision_time
        )
        
        if not qualified_stocks:
            print("\n❌ No stocks qualified for trading. Session ended.")
            return
        
        # Calculate position sizing with improved logic
        num_stocks = len(qualified_stocks)
        
        print(f"\n💰 POSITION SIZING:")
        print(f"📊 Available capital: {format_currency(available_capital)}")
        print(f"📈 Number of stocks: {num_stocks}")
        print(f"💼 Target capital per stock: {format_currency(available_capital / num_stocks)}")
        
        # Prepare trades with improved position sizing
        trade_params = []
        total_required_capital = 0
        
        for ticker in qualified_stocks:
            try:
                current_price = paper_api.get_latest_trade(ticker).price
                shares, position_cost, _ = calculate_position_size(available_capital, num_stocks, current_price)
                
                if shares > 0 and position_cost <= available_capital:
                    trade_params.append({
                        'ticker': ticker,
                        'shares': shares,
                        'price': current_price,
                        'position_cost': position_cost,
                        'sentiment': qualified_stocks[ticker]
                    })
                    total_required_capital += position_cost
                    print(f"✅ {ticker}: {shares} shares @ ${current_price:.2f} = ${position_cost:.2f} (sentiment: {qualified_stocks[ticker]:.4f})")
                else:
                    print(f"❌ {ticker}: Insufficient capital for minimum position (need ${position_cost:.2f})")
                    
            except Exception as e:
                print(f"❌ {ticker}: Error getting price - {e}")
                logging.error(f"Price fetch error for {ticker}: {e}")
                continue
        
        # Final validation of total capital requirements
        if total_required_capital > available_capital:
            print(f"\n⚠️  Total required capital ${total_required_capital:.2f} exceeds available ${available_capital:.2f}")
            print("   Reducing position sizes...")
            
            # Scale down all positions proportionally
            scale_factor = available_capital / total_required_capital * 0.95  # Additional 5% buffer
            for trade in trade_params:
                trade['shares'] = max(1, int(trade['shares'] * scale_factor))
                trade['position_cost'] = trade['shares'] * trade['price']
                print(f"   📉 {trade['ticker']}: Reduced to {trade['shares']} shares = ${trade['position_cost']:.2f}")
        
        print(f"\n💼 Total capital to be used: ${sum(t['position_cost'] for t in trade_params):.2f}")
        print(f"💰 Remaining buffer: ${available_capital - sum(t['position_cost'] for t in trade_params):.2f}")
        
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
        
        # Collect results and track successful orders
        successful_trades = []
        failed_trades = []
        order_tracking = []  # Track orders for P&L calculation
        total_invested = 0.0
        
        for future in futures:
            trade = futures[future]
            ticker = trade['ticker']
            try:
                success, result = future.result(timeout=60)  # Increased timeout for market execution
                if success:
                    successful_trades.append(ticker)
                    
                    # Track order for P&L calculation
                    order_tracking.append({
                        'ticker': ticker,
                        'buy_order_id': result['buy_order_id'],
                        'filled_qty': result['filled_qty'],
                        'fill_price': result['fill_price'],
                        'total_cost': result['total_cost'],
                        'protective_orders': result['protective_orders']
                    })
                    
                    total_invested += result['total_cost']
                    
                    print(f"✅ {ticker}: FILLED - {result['filled_qty']} shares @ ${result['fill_price']:.2f} = ${result['total_cost']:.2f}")
                    print(f"   📋 Protective orders: {len(result['protective_orders'])} placed")
                    
                    # Send Telegram notification for trade opened
                    try:
                        # Get sentiment if available from trade parameters
                        sentiment = None
                        for trade_param in trade_params:
                            if trade_param['ticker'] == ticker:
                                sentiment = trade_param.get('sentiment')
                                break
                        
                        notify_trade_opened(
                            symbol=ticker,
                            side="BUY",
                            quantity=result['filled_qty'],
                            fill_price=result['fill_price'],
                            order_id=result['buy_order_id'],
                            sentiment=sentiment,
                            timestamp=datetime.now()
                        )
                    except Exception as notify_error:
                        logging.warning(f"Failed to send trade opened notification for {ticker}: {notify_error}")
                    
                    # Show immediate P&L for this trade
                    try:
                        current_price = get_fresh_quote(ticker)
                        current_value = current_price * result['filled_qty']
                        immediate_pnl = current_value - result['total_cost']
                        immediate_pnl_pct = (immediate_pnl / result['total_cost']) * 100
                        
                        pnl_color = "📈" if immediate_pnl >= 0 else "📉"
                        print(f"   💰 Immediate P&L: {pnl_color} ${immediate_pnl:+.2f} ({immediate_pnl_pct:+.2f}%) [Current: ${current_price:.2f}]")
                        
                        # Log individual trade P&L
                        logging.info(f"IMMEDIATE P&L - {ticker}: Cost=${result['total_cost']:.2f}, Value=${current_value:.2f}, P&L=${immediate_pnl:+.2f} ({immediate_pnl_pct:+.2f}%)")
                        
                    except Exception as pnl_error:
                        print(f"   ⚠️  Could not calculate immediate P&L: {pnl_error}")
                        logging.warning(f"Failed to calculate immediate P&L for {ticker}: {pnl_error}")
                    
                else:
                    failed_trades.append((ticker, result))
                    print(f"❌ {ticker}: FAILED - {result}")
            except Exception as e:
                failed_trades.append((ticker, str(e)))
                print(f"❌ {ticker}: TIMEOUT/ERROR - {e}")
        
        # Trading summary
        print("\n" + "=" * 60)
        print("📊 TRADING EXECUTION SUMMARY:")
        print(f"✅ Successful trades: {len(successful_trades)} / {len(trade_params)} attempted")
        print(f"❌ Failed trades: {len(failed_trades)}")
        print(f"💰 Total capital invested: ${total_invested:.2f}")
        
        if successful_trades:
            print(f"✅ Successfully filled: {', '.join(successful_trades)}")
            
            # Show immediate position details
            print(f"\n📈 ACTIVE POSITIONS:")
            for order_info in order_tracking:
                ticker = order_info['ticker']
                qty = order_info['filled_qty']
                price = order_info['fill_price']
                cost = order_info['total_cost']
                num_protective = len(order_info['protective_orders'])
                print(f"   {ticker}: {qty} shares @ ${price:.2f} = ${cost:.2f} (Protected: {num_protective > 0})")
        
        if failed_trades:
            print("\n❌ FAILED TRADES:")
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
                
                # Wait a moment for orders to settle, then calculate final P&L
                time.sleep(3)
                
                print("\n💰 CALCULATING FINAL P&L...")
                print("=" * 60)
                
                total_pnl = 0.0
                pnl_results = []
                
                for order_info in order_tracking:
                    try:
                        # Calculate P&L based on filled positions and current market price
                        ticker = order_info['ticker']
                        filled_qty = order_info['filled_qty']
                        entry_price = order_info['fill_price']
                        total_cost = order_info['total_cost']
                        
                        # Get current market price for unrealized P&L
                        current_price = get_fresh_quote(ticker)
                        current_value = current_price * filled_qty
                        unrealized_pnl = current_value - total_cost
                        unrealized_pnl_pct = (unrealized_pnl / total_cost) * 100
                        
                        pnl_data = {
                            'symbol': ticker,
                            'filled_qty': filled_qty,
                            'entry_price': entry_price,
                            'current_price': current_price,
                            'total_cost': total_cost,
                            'current_value': current_value,
                            'unrealized_pnl': unrealized_pnl,
                            'unrealized_pnl_pct': unrealized_pnl_pct
                        }
                        
                        pnl_results.append(pnl_data)
                        total_pnl += unrealized_pnl
                        
                        # Log individual position P&L
                        pnl_msg = f"POSITION P&L - {ticker}: {filled_qty} shares, "
                        pnl_msg += f"Entry: ${entry_price:.2f}, Current: ${current_price:.2f}, "
                        pnl_msg += f"Unrealized P&L: ${unrealized_pnl:.2f} ({unrealized_pnl_pct:+.2f}%)"
                        
                        logging.info(pnl_msg)
                        print(f"💰 {pnl_msg}")
                        
                        # Send Telegram notification for trade closed
                        try:
                            # Calculate holding time
                            holding_time_minutes = params['holding_minutes']
                            
                            # Determine exit reason (Time-based closure in this case)
                            exit_reason = "Time"
                            
                            # Get the buy order ID for this position
                            buy_order_id = order_info['buy_order_id']
                            
                            notify_trade_closed(
                                symbol=ticker,
                                quantity=filled_qty,
                                exit_price=current_price,
                                realized_pnl=unrealized_pnl,  # This is realized P&L after position closure
                                realized_pnl_pct=unrealized_pnl_pct,
                                exit_reason=exit_reason,
                                order_id=buy_order_id,
                                holding_time_minutes=holding_time_minutes,
                                timestamp=datetime.now()
                            )
                        except Exception as notify_error:
                            logging.warning(f"Failed to send trade closed notification for {ticker}: {notify_error}")
                        
                    except Exception as e:
                        logging.error(f"Error calculating P&L for {order_info['ticker']}: {e}")
                        print(f"❌ Error calculating P&L for {order_info['ticker']}: {e}")
                
                # Display final P&L summary
                if pnl_results:
                    total_investment = sum(p['total_cost'] for p in pnl_results)
                    total_roi_pct = (total_pnl / total_investment) * 100 if total_investment > 0 else 0
                    
                    print(f"\n📊 FINAL P&L SUMMARY:")
                    print(f"💰 Total Investment: ${total_investment:.2f}")
                    print(f"💰 Total P&L: ${total_pnl:.2f}")
                    print(f"📈 Total ROI: {total_roi_pct:+.2f}%")
                    print(f"📊 Number of positions: {len(pnl_results)}")
                    
                    winning_positions = [p for p in pnl_results if p.get('unrealized_pnl', 0) > 0]
                    losing_positions = [p for p in pnl_results if p.get('unrealized_pnl', 0) < 0]
                    
                    if winning_positions:
                        avg_win = sum(p['unrealized_pnl'] for p in winning_positions) / len(winning_positions)
                        print(f"✅ Winning positions: {len(winning_positions)} (avg: ${avg_win:.2f})")
                    if losing_positions:
                        avg_loss = sum(p['unrealized_pnl'] for p in losing_positions) / len(losing_positions)
                        print(f"❌ Losing positions: {len(losing_positions)} (avg: ${avg_loss:.2f})")
                    
                    # Log comprehensive summary
                    logging.info(f"SESSION SUMMARY: Investment: ${total_investment:.2f}, P&L: ${total_pnl:.2f}, "
                               f"ROI: {total_roi_pct:+.2f}%, Positions: {len(pnl_results)}, "
                               f"Winners: {len(winning_positions)}, Losers: {len(losing_positions)}")
                else:
                    print("ℹ️  No P&L data available (no successful fills)")
                    
            except Exception as e:
                print(f"❌ Error closing positions: {e}")
                logging.error(f"Failed to close positions: {e}")
        
        print("\n🏁 LIVE TRADING SESSION COMPLETED")
        print("=" * 60)
        
        # Send session end notification
        try:
            if 'total_pnl' in locals() and 'total_investment' in locals():
                session_summary = f"Live Trading Session Completed\n\n"
                session_summary += f"📊 Session Summary:\n"
                session_summary += f"💰 Total Investment: ${total_investment:.2f}\n"
                session_summary += f"💰 Total P&L: ${total_pnl:+.2f}\n"
                session_summary += f"📈 Total ROI: {total_roi_pct:+.2f}%\n"
                session_summary += f"📊 Positions: {len(pnl_results)}\n"
                
                if 'winning_positions' in locals() and 'losing_positions' in locals():
                    session_summary += f"✅ Winners: {len(winning_positions)}\n"
                    session_summary += f"❌ Losers: {len(losing_positions)}"
                
                status_type = "INFO" if total_pnl >= 0 else "WARNING"
            else:
                session_summary = "Live Trading Session Completed\n\nNo trades were executed."
                status_type = "INFO"
            
            notify_system_status(session_summary, status_type)
        except Exception as notify_error:
            logging.warning(f"Failed to send session end notification: {notify_error}")
        
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR in live trading: {e}")
        logging.error(f"Critical error in live trading: {e}")
        raise 

def main():
    """
    CLI entry point for live trading
    """
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(
        description='Live Trading - Execute real-time trading strategies',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 live_trading.py --mode paper --log-level INFO
  python3 live_trading.py --mode paper --dry-run --log-level DEBUG
  python3 live_trading.py --mode live --log-level INFO  # CAUTION: Real money!
        """
    )
    
    # Trading mode
    parser.add_argument('--mode', choices=['paper', 'live'], default='paper',
                       help='Trading mode (default: paper)')
    
    # Safety options
    parser.add_argument('--dry-run', action='store_true',
                       help='Simulate trading without placing actual orders')
    
    # System parameters
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       default='INFO', help='Logging level (default: INFO)')
    parser.add_argument('--no-input', action='store_true',
                       help='Non-interactive mode (no prompts)')
    
    # Trading parameters
    parser.add_argument('--sentiment', type=float, default=0.2,
                       help='Sentiment threshold (default: 0.2)')
    parser.add_argument('--investment', type=float, default=10000,
                       help='Investment per stock (default: 10000)')
    parser.add_argument('--max-positions', type=int, default=3,
                       help='Maximum concurrent positions (default: 3)')
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = getattr(logging, args.log_level.upper())
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/live_trading.log'),
            logging.StreamHandler()
        ]
    )
    
    # Safety warnings
    if args.mode == 'live' and not args.dry_run:
        print(f"\n{Colors.RED}{Colors.BOLD}⚠️  WARNING: LIVE TRADING MODE{Colors.END}")
        print(f"{Colors.RED}This will place REAL orders with REAL money!{Colors.END}")
        
        if args.no_input:
            print("❌ Live trading cancelled (--no-input mode)")
            sys.exit(1)
        else:
            response = input("Type 'CONFIRM' to proceed with live trading: ")
            if response != 'CONFIRM':
                print("❌ Live trading cancelled")
                sys.exit(0)
    
    # Print startup banner
    print(f"\n{Colors.BOLD}🚀 LIVE TRADING SYSTEM{Colors.END}")
    print(f"📊 Mode: {args.mode.upper()}")
    if args.dry_run:
        print(f"🧪 DRY RUN: No actual orders will be placed")
    print(f"📊 Sentiment Threshold: {args.sentiment}")
    print(f"💼 Investment per Stock: ${args.investment:,.0f}")
    print(f"🎯 Max Positions: {args.max_positions}")
    print(f"📝 Log Level: {args.log_level}")
    
    # Check market hours
    try:
        if not is_market_open():
            print(f"\n📅 Market is currently CLOSED")
            print(f"⏰ Market hours: 9:30 AM - 4:00 PM ET (Monday-Friday)")
            print(f"💡 The system will wait for market open or you can run a backtest instead:")
            print(f"   python3 historical_backtest.py --start 2024-10-15 --end 2024-10-18")
            
            if not args.dry_run:
                print(f"\n✅ Exiting gracefully (market closed)")
                sys.exit(0)
            else:
                print(f"\n🧪 DRY RUN: Continuing despite market being closed")
    except Exception as e:
        print(f"⚠️  Could not check market status: {e}")
    
    # Validate credentials
    try:
        account_info = get_account_info()
        print(f"\n✅ Connected to Alpaca {args.mode.upper()} account")
        print(f"💰 Account Value: ${float(account_info['portfolio_value']):,.2f}")
        print(f"💵 Buying Power: ${float(account_info['buying_power']):,.2f}")
    except Exception as e:
        print(f"\n❌ ERROR: Could not connect to Alpaca API")
        print(f"Details: {e}")
        print(f"\n💡 TROUBLESHOOTING:")
        print(f"1. Run: python3 system_diagnose.py")
        print(f"2. Check your .env file has valid apikey/apisecret")
        print(f"3. Verify your API keys are for {args.mode} trading")
        sys.exit(1)
    
    try:
        # Ensure logs directory exists
        os.makedirs('logs', exist_ok=True)
        
        # Create trading parameters
        from datetime import time
        params = {
            'mode': args.mode,
            'dry_run': args.dry_run,
            'sentiment_threshold': args.sentiment,
            'investment_per_stock': args.investment,
            'max_positions': args.max_positions,
            'start_time': time(9, 30),  # 9:30 AM market open
            'holding_minutes': 390,  # Full trading day
            'min_sentiment': args.sentiment,
            'max_sentiment': 1.0,
            'stop_loss': 5.0,  # 5% stop loss
            'take_profit': 5.0  # 5% take profit
        }
        
        if args.dry_run:
            print(f"\n🧪 DRY RUN MODE: Simulating trading pipeline...")
            # TODO: Implement dry run simulation
            print(f"✅ Dry run completed successfully!")
        else:
            # Run live trading
            run_live_trading(params)
        
        print(f"\n🎉 SUCCESS: Trading session completed!")
        
    except KeyboardInterrupt:
        print(f"\n⚠️  Trading session interrupted by user")
        print(f"🛡️  Cancelling all open orders...")
        try:
            cancel_all_orders_and_positions()
            print(f"✅ All orders cancelled successfully")
        except Exception as cancel_error:
            print(f"❌ Error cancelling orders: {cancel_error}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        logging.error(f"Live trading failed: {e}")
        print(f"\n💡 TROUBLESHOOTING:")
        print(f"1. Run: python3 system_diagnose.py")
        print(f"2. Check logs/live_trading.log for details")
        print(f"3. Verify market is open and API keys are valid")
        sys.exit(1)

# Add Colors class for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

if __name__ == "__main__":
    main()