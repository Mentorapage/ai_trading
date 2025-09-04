from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, StopLossRequest, TakeProfitRequest, LimitOrderRequest, StopOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass, OrderType
from dotenv import load_dotenv
import os
import logging
from decimal import Decimal, ROUND_HALF_UP
import time
from datetime import datetime, timedelta
import pytz

# Import notification functions
try:
    from notifier import notify_trade_closed
except ImportError:
    # Fallback if notifier is not available
    def notify_trade_closed(*args, **kwargs):
        pass

# Load environment variables
load_dotenv(dotenv_path=".env")
api_key = os.getenv("apikey")
secret_key = os.getenv("apisecret")

# Initialize trading client (ensuring paper trading mode)
trading_client = TradingClient(api_key, secret_key, paper=True)

# Log connection (basic verification will happen on first API call)
logging.info("Alpaca Trading Client initialized for paper trading")

def is_market_open():
    """
    Check if the US stock market is currently open
    
    Returns:
        tuple: (is_open, next_open_time, message)
    """
    try:
        # Get market calendar
        calendar = trading_client.get_calendar()
        
        # Get current time in ET
        et_tz = pytz.timezone('America/New_York')
        now_et = datetime.now(et_tz)
        current_date = now_et.date()
        
        # Find today's market session
        today_session = None
        for session in calendar:
            if session.date == current_date:
                today_session = session
                break
        
        if today_session is None:
            # Market is closed today
            # Find next trading day
            for session in calendar:
                if session.date > current_date:
                    next_open = datetime.combine(session.date, session.open.time()).replace(tzinfo=et_tz)
                    return False, next_open, f"Market closed today. Next open: {next_open.strftime('%Y-%m-%d %H:%M ET')}"
            
            return False, None, "Market closed - no upcoming sessions found"
        
        # Check if current time is within market hours
        market_open = datetime.combine(current_date, today_session.open.time()).replace(tzinfo=et_tz)
        market_close = datetime.combine(current_date, today_session.close.time()).replace(tzinfo=et_tz)
        
        if now_et < market_open:
            return False, market_open, f"Market opens at {market_open.strftime('%H:%M ET')} (in {(market_open - now_et).total_seconds()/60:.0f} minutes)"
        elif now_et > market_close:
            # Find next trading day
            for session in calendar:
                if session.date > current_date:
                    next_open = datetime.combine(session.date, session.open.time()).replace(tzinfo=et_tz)
                    return False, next_open, f"Market closed. Next open: {next_open.strftime('%Y-%m-%d %H:%M ET')}"
        else:
            minutes_until_close = (market_close - now_et).total_seconds() / 60
            return True, market_close, f"Market is OPEN (closes in {minutes_until_close:.0f} minutes)"
    
    except Exception as e:
        logging.warning(f"Could not check market status: {e}")
        # Default to assuming market is open for paper trading
        return True, None, "Market status unknown - proceeding with paper trading"


def get_account_info():
    """Get comprehensive account information with validation"""
    account = trading_client.get_account()
    info = {
        "account_id": account.id,
        "cash": float(account.cash),
        "portfolio_value": float(account.portfolio_value),
        "status": account.status,
        "buying_power": float(account.buying_power),
        "equity": float(account.equity),
        "account_blocked": getattr(account, 'account_blocked', False),
        "trading_blocked": getattr(account, 'trading_blocked', False),
        "day_trading_buying_power": float(getattr(account, 'day_trading_buying_power', 0)),
        "regt_buying_power": float(getattr(account, 'regt_buying_power', 0))
    }
    
    # Log detailed account info for debugging
    logging.info(f"Account Status: {info['status']}, Cash: ${info['cash']:.2f}, "
                f"Buying Power: ${info['buying_power']:.2f}, Equity: ${info['equity']:.2f}")
    
    if info['account_blocked'] or info['trading_blocked']:
        logging.warning(f"Account restrictions: Blocked={info['account_blocked']}, Trading Blocked={info['trading_blocked']}")
    
    return info

# Individual getter functions removed - use get_account_info() for comprehensive account data
# Order management functions removed - not used in current trading strategy

def _cent(price):
    """
    Round price to nearest cent using Decimal for precision
    
    Args:
        price (float): Price to round
        
    Returns:
        float: Price rounded to nearest cent
    """
    if price is None:
        return 0.0
    return float(Decimal(str(price)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

def sanitize_bracket(base_price, take_profit, stop_loss):
    """
    Sanitize bracket order prices to meet Alpaca requirements
    
    Args:
        base_price (float): Current market price
        take_profit (float): Desired take profit price
        stop_loss (float): Desired stop loss price
        
    Returns:
        tuple: (base_price, take_profit, stop_loss) all rounded and validated
    """
    # Round all prices to cents
    base = _cent(base_price)
    tp = _cent(take_profit)
    sl = _cent(stop_loss)
    
    # Ensure minimum spreads (use $0.02 buffer for safety)
    min_tp = base + 0.02
    max_sl = base - 0.02
    
    # Adjust take profit if too close
    if tp < min_tp:
        tp = min_tp
        logging.warning(f"Take profit adjusted from {_cent(take_profit)} to {tp} (minimum spread requirement)")
    
    # Adjust stop loss if too close
    if sl > max_sl:
        sl = max_sl
        logging.warning(f"Stop loss adjusted from {_cent(stop_loss)} to {sl} (minimum spread requirement)")
    
    # Ensure stop loss is positive
    if sl <= 0:
        sl = base * 0.95  # 5% fallback
        sl = _cent(sl)
        logging.warning(f"Stop loss adjusted to {sl} (positive price requirement)")
    
    return base, tp, sl

def get_fresh_quote(symbol):
    """
    Get the latest market quote for a symbol
    
    Args:
        symbol (str): Stock ticker
        
    Returns:
        float: Latest trade price
    """
    try:
        # Use the same client to get latest trade
        from alpaca_trade_api.rest import REST
        paper_api = REST(api_key, secret_key, base_url="https://paper-api.alpaca.markets")
        latest_trade = paper_api.get_latest_trade(symbol)
        return float(latest_trade.price)
    except Exception as e:
        logging.error(f"Error getting fresh quote for {symbol}: {e}")
        raise


def bracket_order(symbol, qty, side, tif, high, low, max_retries=2):
    """
    Enhanced bracket order with re-quoting, sanitization, and retry logic
    
    Args:
        symbol (str): Stock ticker
        qty (int): Number of shares
        side (str): Order side (BUY/SELL)
        tif (str): Time in force (DAY/GTC)
        high (float): Take profit price (initial target)
        low (float): Stop loss price (initial target)
        max_retries (int): Maximum retry attempts
        
    Returns:
        str: Success message with order details
    """
    # Input validation
    if not symbol or not symbol.strip():
        raise ValueError("Symbol cannot be empty")
    
    if qty <= 0:
        raise ValueError(f"Quantity must be positive, got {qty}")
    
    symbol = symbol.upper().strip()
    
    for attempt in range(max_retries + 1):
        try:
            # Get fresh market price before each attempt
            current_price = get_fresh_quote(symbol)
            logging.info(f"Attempt {attempt + 1}/{max_retries + 1} for {symbol}: Fresh quote = ${current_price:.2f}")
            
            # Calculate target prices based on original dollar amounts
            if side.upper() == "BUY":
                # For buy orders: calculate original spreads and apply to fresh price
                original_tp_spread = high - current_price if attempt == 0 else (high - low) / 2  # Fallback spread
                original_sl_spread = current_price - low if attempt == 0 else (high - low) / 2  # Fallback spread
                
                target_tp = current_price + abs(original_tp_spread)
                target_sl = current_price - abs(original_sl_spread)
            else:
                # For sell orders (reverse logic)
                original_tp_spread = current_price - low if attempt == 0 else (high - low) / 2
                original_sl_spread = high - current_price if attempt == 0 else (high - low) / 2
                
                target_tp = current_price - abs(original_tp_spread)
                target_sl = current_price + abs(original_sl_spread)
            
            # Sanitize prices to meet Alpaca requirements
            base_price, sanitized_tp, sanitized_sl = sanitize_bracket(current_price, target_tp, target_sl)
            
            # Log the prices being used
            logging.info(f"{symbol} Attempt {attempt + 1}: Base=${base_price:.2f}, TP=${sanitized_tp:.2f}, SL=${sanitized_sl:.2f}")
            
            # Validate order structure
            if side.upper() == "BUY":
                if sanitized_sl >= sanitized_tp:
                    raise ValueError(f"Invalid BUY bracket: SL ({sanitized_sl}) must be < TP ({sanitized_tp})")
                stop_loss_req = StopLossRequest(stop_price=sanitized_sl)
                take_profit_req = TakeProfitRequest(limit_price=sanitized_tp)
            else:
                if sanitized_sl <= sanitized_tp:
                    raise ValueError(f"Invalid SELL bracket: SL ({sanitized_sl}) must be > TP ({sanitized_tp})")
                stop_loss_req = StopLossRequest(stop_price=sanitized_sl)
                take_profit_req = TakeProfitRequest(limit_price=sanitized_tp)
            
            # Create the bracket order
            my_order = MarketOrderRequest(
                symbol=symbol,
                qty=int(qty),
                side=OrderSide[side.upper()],
                time_in_force=TimeInForce[tif.upper()],
                order_class=OrderClass.BRACKET,
                stop_loss=stop_loss_req,
                take_profit=take_profit_req
            )
            
            # Submit the order
            submitted_order = trading_client.submit_order(my_order)
            
            # Validate submission was successful
            if not submitted_order or not submitted_order.id:
                raise Exception("Order submission failed - no order ID returned")
            
            # Wait a moment and check order status
            time.sleep(1)
            
            try:
                # Check order status to catch immediate cancellations
                order_status = trading_client.get_order_by_id(submitted_order.id)
                
                if order_status.status.value in ['CANCELED', 'CANCELLED']:
                    # Get cancellation reason if available
                    cancel_reason = getattr(order_status, 'cancel_reason', 'Unknown')
                    error_msg = f"Order immediately cancelled. Reason: {cancel_reason}"
                    logging.error(f"ORDER CANCELLED {symbol}: {error_msg}")
                    print(f"❌ {symbol}: {error_msg}")
                    raise Exception(f"Order cancelled: {cancel_reason}")
                
                elif order_status.status.value == 'REJECTED':
                    reject_reason = getattr(order_status, 'reject_reason', 'Unknown')
                    error_msg = f"Order rejected. Reason: {reject_reason}"
                    logging.error(f"ORDER REJECTED {symbol}: {error_msg}")
                    print(f"❌ {symbol}: {error_msg}")
                    raise Exception(f"Order rejected: {reject_reason}")
                
                # Log successful order with status
                success_msg = f"Bracket order submitted. Order ID: {submitted_order.id}, Status: {order_status.status.value}"
                logging.info(f"SUCCESS {symbol} (attempt {attempt + 1}): Base=${base_price:.2f}, TP=${sanitized_tp:.2f}, SL=${sanitized_sl:.2f}, Status: {order_status.status.value}")
                print(f"✅ {symbol}: Order placed successfully - {order_status.status.value}")
                
                return success_msg
                
            except Exception as status_error:
                # If we can't check status, still return success but log the issue
                logging.warning(f"Could not verify order status for {symbol}: {status_error}")
                success_msg = f"Bracket order submitted. Order ID: {submitted_order.id}, Status: {submitted_order.status}"
                logging.info(f"SUCCESS {symbol} (attempt {attempt + 1}): Base=${base_price:.2f}, TP=${sanitized_tp:.2f}, SL=${sanitized_sl:.2f}")
                return success_msg
            
        except Exception as e:
            error_str = str(e)
            logging.warning(f"ATTEMPT {attempt + 1}/{max_retries + 1} FAILED for {symbol}: {error_str}")
            
            # Check if this is a price validation error that we should retry
            is_price_error = any(keyword in error_str.lower() for keyword in [
                'take_profit.limit_price', 'stop_loss.stop_price', 'base_price', '42210000'
            ])
            
            # If this is the last attempt, or not a price error, give up
            if attempt >= max_retries or not is_price_error:
                final_error = f"Bracket order failed for {symbol} after {attempt + 1} attempts: {error_str}"
                logging.error(final_error)
                raise Exception(final_error) from e
            
            # Wait briefly before retry
            time.sleep(0.5)
    
    # Should never reach here, but just in case
    raise Exception(f"Bracket order failed for {symbol}: Maximum retries exceeded")

def execute_market_buy_with_protection(symbol, qty, stop_loss_price, take_profit_price, max_retries=2, fill_timeout=60):
    """
    Execute market buy order first, then add protective orders after confirmation
    
    Args:
        symbol (str): Stock ticker
        qty (int): Number of shares
        stop_loss_price (float): Stop loss price
        take_profit_price (float): Take profit price
        max_retries (int): Maximum retry attempts
        
    Returns:
        dict: Order execution results with IDs and status
    """
    symbol = symbol.upper().strip()
    
    # Validate quantity against buying power
    account_info = get_account_info()
    available_cash = min(account_info['cash'], account_info['buying_power'])
    
    for attempt in range(max_retries + 1):
        try:
            # Get fresh quote
            current_price = get_fresh_quote(symbol)
            estimated_cost = current_price * qty
            
            # Validate we have enough buying power with buffer
            if estimated_cost > available_cash * 0.95:
                # Reduce quantity to fit available cash
                max_qty = int(available_cash * 0.9 / current_price)
                if max_qty < 1:
                    raise Exception(f"Insufficient buying power. Need ${estimated_cost:.2f}, have ${available_cash:.2f}")
                qty = max_qty
                estimated_cost = current_price * qty
                logging.warning(f"Reduced {symbol} quantity to {qty} shares to fit buying power")
                print(f"⚠️  {symbol}: Reduced to {qty} shares (${estimated_cost:.2f}) to fit available funds")
            
            logging.info(f"MARKET BUY {symbol} (attempt {attempt + 1}): {qty} shares @ ~${current_price:.2f} = ${estimated_cost:.2f}")
            print(f"🛒 {symbol}: Placing market buy for {qty} shares (~${estimated_cost:.2f})")
            
            # Step 1: Place market buy order
            market_order = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY
            )
            
            buy_order = trading_client.submit_order(market_order)
            
            if not buy_order or not buy_order.id:
                raise Exception("Market buy order submission failed")
            
            logging.info(f"Market buy order submitted: {buy_order.id}")
            
            # Step 2: Wait for fill confirmation with configurable timeout
            fill_confirmed = False
            filled_qty = 0
            actual_fill_price = 0
            resubmission_attempted = False
            
            for wait_attempt in range(fill_timeout):  # Configurable timeout
                time.sleep(1)
                
                try:
                    order_status = trading_client.get_order_by_id(buy_order.id)
                    
                    # Log detailed API response for debugging
                    logging.debug(f"Order status for {symbol}: {order_status}")
                    
                    if order_status.status.value == 'FILLED':
                        fill_confirmed = True
                        filled_qty = int(order_status.filled_qty)
                        actual_fill_price = float(order_status.filled_avg_price)
                        logging.info(f"✅ FILLED: {symbol} {filled_qty} shares @ ${actual_fill_price:.2f}")
                        print(f"✅ {symbol}: Market buy FILLED - {filled_qty} shares @ ${actual_fill_price:.2f}")
                        break
                        
                    elif order_status.status.value in ['CANCELED', 'CANCELLED']:
                        cancel_reason = getattr(order_status, 'cancel_reason', 'Unknown')
                        error_msg = f"Market buy order cancelled: {cancel_reason}"
                        logging.error(f"MARKET BUY CANCELLED {symbol}: {error_msg}")
                        print(f"❌ {symbol}: Market buy cancelled - {cancel_reason}")
                        
                        # Log full order details for debugging
                        logging.error(f"Full order details: {order_status}")
                        raise Exception(f"Market buy cancelled: {cancel_reason}")
                        
                    elif order_status.status.value == 'REJECTED':
                        reject_reason = getattr(order_status, 'reject_reason', 'Unknown')
                        error_msg = f"Market buy order rejected: {reject_reason}"
                        logging.error(f"MARKET BUY REJECTED {symbol}: {error_msg}")
                        print(f"❌ {symbol}: Market buy rejected - {reject_reason}")
                        
                        # Log full order details for debugging
                        logging.error(f"Full order details: {order_status}")
                        raise Exception(f"Market buy rejected: {reject_reason}")
                        
                    elif order_status.status.value in ['NEW', 'PENDING_NEW'] and wait_attempt > 30 and not resubmission_attempted:
                        # Order stuck in NEW status - cancel and resubmit with fresh price
                        logging.warning(f"{symbol}: Order stuck in {order_status.status.value} for 30+ seconds. Canceling and resubmitting...")
                        print(f"⚠️  {symbol}: Order stuck in {order_status.status.value}. Resubmitting with fresh price...")
                        
                        try:
                            # Cancel the stuck order
                            trading_client.cancel_order_by_id(buy_order.id)
                            time.sleep(2)  # Wait for cancellation
                            
                            # Get fresh quote and resubmit
                            fresh_price = get_fresh_quote(symbol)
                            fresh_cost = fresh_price * qty
                            
                            # Validate we still have enough buying power
                            if fresh_cost <= available_cash * 0.95:
                                logging.info(f"{symbol}: Resubmitting with fresh price ${fresh_price:.2f}")
                                
                                # Create new market order
                                fresh_market_order = MarketOrderRequest(
                                    symbol=symbol,
                                    qty=qty,
                                    side=OrderSide.BUY,
                                    time_in_force=TimeInForce.DAY
                                )
                                
                                buy_order = trading_client.submit_order(fresh_market_order)
                                resubmission_attempted = True
                                wait_attempt = 0  # Reset timeout counter
                                
                                logging.info(f"Fresh order submitted: {buy_order.id}")
                                print(f"🔄 {symbol}: Fresh order submitted with updated price ${fresh_price:.2f}")
                            else:
                                raise Exception(f"Fresh quote ${fresh_price:.2f} exceeds available funds")
                                
                        except Exception as resubmit_error:
                            logging.error(f"Failed to resubmit order for {symbol}: {resubmit_error}")
                            raise Exception(f"Order resubmission failed: {resubmit_error}")
                        
                    elif wait_attempt % 10 == 0:  # Log every 10 seconds
                        print(f"⏳ {symbol}: Waiting for fill... Status: {order_status.status.value} ({wait_attempt}s)")
                        logging.info(f"{symbol}: Order status after {wait_attempt}s: {order_status.status.value}")
                        
                except Exception as status_error:
                    if wait_attempt > 15:  # Only raise after waiting a bit
                        logging.error(f"Error checking order status for {symbol}: {status_error}")
                        raise status_error
                    continue
            
            if not fill_confirmed:
                final_status = "Unknown"
                try:
                    final_order = trading_client.get_order_by_id(buy_order.id)
                    final_status = final_order.status.value
                    logging.error(f"Order timeout for {symbol}: Final status = {final_status}")
                except:
                    pass
                raise Exception(f"Market buy order did not fill within {fill_timeout}s timeout (final status: {final_status})")
            
            # Step 3: Place protective orders now that we have shares
            protective_orders = []
            
            try:
                # Sanitize protective order prices
                _, sanitized_tp, sanitized_sl = sanitize_bracket(actual_fill_price, take_profit_price, stop_loss_price)
                
                # Place take profit order
                if sanitized_tp > actual_fill_price + 0.01:
                    tp_order = LimitOrderRequest(
                        symbol=symbol,
                        qty=filled_qty,
                        side=OrderSide.SELL,
                        time_in_force=TimeInForce.DAY,
                        limit_price=sanitized_tp
                    )
                    
                    tp_submitted = trading_client.submit_order(tp_order)
                    protective_orders.append(('TAKE_PROFIT', tp_submitted.id, sanitized_tp))
                    logging.info(f"Take profit order placed: {tp_submitted.id} @ ${sanitized_tp:.2f}")
                    print(f"🎯 {symbol}: Take profit set @ ${sanitized_tp:.2f}")
                
                # Place stop loss order
                if sanitized_sl < actual_fill_price - 0.01:
                    sl_order = StopOrderRequest(
                        symbol=symbol,
                        qty=filled_qty,
                        side=OrderSide.SELL,
                        time_in_force=TimeInForce.DAY,
                        stop_price=sanitized_sl
                    )
                    
                    sl_submitted = trading_client.submit_order(sl_order)
                    protective_orders.append(('STOP_LOSS', sl_submitted.id, sanitized_sl))
                    logging.info(f"Stop loss order placed: {sl_submitted.id} @ ${sanitized_sl:.2f}")
                    print(f"🛡️  {symbol}: Stop loss set @ ${sanitized_sl:.2f}")
                
            except Exception as protective_error:
                logging.warning(f"Failed to place protective orders for {symbol}: {protective_error}")
                print(f"⚠️  {symbol}: Protective orders failed - position unprotected!")
            
            # Return success with all order details
            result = {
                'success': True,
                'symbol': symbol,
                'buy_order_id': buy_order.id,
                'filled_qty': filled_qty,
                'fill_price': actual_fill_price,
                'protective_orders': protective_orders,
                'total_cost': actual_fill_price * filled_qty
            }
            
            success_msg = f"Market buy executed: {filled_qty} shares @ ${actual_fill_price:.2f}, protective orders: {len(protective_orders)}"
            logging.info(f"SUCCESS {symbol} (attempt {attempt + 1}): {success_msg}")
            
            return result
            
        except Exception as e:
            error_str = str(e)
            logging.warning(f"ATTEMPT {attempt + 1}/{max_retries + 1} FAILED for {symbol}: {error_str}")
            print(f"❌ {symbol} attempt {attempt + 1} failed: {error_str}")
            
            # Check if this is a retryable error
            retryable_errors = ['timeout', 'connection', 'network', 'temporary']
            is_retryable = any(keyword in error_str.lower() for keyword in retryable_errors)
            
            if attempt >= max_retries or not is_retryable:
                final_error = f"Market buy failed for {symbol} after {attempt + 1} attempts: {error_str}"
                logging.error(final_error)
                return {
                    'success': False,
                    'symbol': symbol,
                    'error': final_error,
                    'filled_qty': 0,
                    'total_cost': 0
                }
            
            time.sleep(1)  # Brief wait before retry
    
    return {
        'success': False,
        'symbol': symbol,
        'error': 'Maximum retries exceeded',
        'filled_qty': 0,
        'total_cost': 0
    }

def check_order_and_calculate_pnl(order_id, symbol, entry_price, shares):
    """
    Check final order status and calculate P&L if filled
    
    Args:
        order_id (str): Alpaca order ID
        symbol (str): Stock ticker
        entry_price (float): Original entry price
        shares (int): Number of shares
        
    Returns:
        dict: Order status and P&L information
    """
    try:
        # Get the main order (parent bracket order)
        main_order = trading_client.get_order_by_id(order_id)
        
        result = {
            'symbol': symbol,
            'order_id': order_id,
            'status': main_order.status.value,
            'filled_qty': int(main_order.filled_qty) if main_order.filled_qty else 0,
            'entry_price': entry_price,
            'shares': shares,
            'pnl': 0.0,
            'pnl_per_share': 0.0,
            'exit_price': None,
            'exit_reason': None
        }
        
        if main_order.status.value == 'FILLED' and result['filled_qty'] > 0:
            # Main order filled, now check for exit orders
            # Get all orders for this symbol to find the exit
            all_orders = trading_client.get_orders(status='all', symbols=[symbol], limit=100)
            
            # Look for filled exit orders related to this position
            for order in all_orders:
                if (order.side.value == 'SELL' and 
                    order.status.value == 'FILLED' and
                    order.created_at > main_order.created_at):
                    
                    exit_price = float(order.filled_avg_price) if order.filled_avg_price else float(order.limit_price or 0)
                    exit_qty = int(order.filled_qty) if order.filled_qty else 0
                    
                    if exit_qty > 0 and exit_price > 0:
                        # Calculate P&L
                        actual_entry_price = float(main_order.filled_avg_price) if main_order.filled_avg_price else entry_price
                        pnl_per_share = exit_price - actual_entry_price
                        total_pnl = pnl_per_share * exit_qty
                        
                        result.update({
                            'exit_price': exit_price,
                            'pnl_per_share': pnl_per_share,
                            'pnl': total_pnl,
                            'exit_reason': 'TAKE_PROFIT' if pnl_per_share > 0 else 'STOP_LOSS',
                            'actual_entry_price': actual_entry_price,
                            'exit_qty': exit_qty
                        })
                        
                        # Log the P&L
                        pnl_msg = f"P&L CALCULATED - {symbol}: {exit_qty} shares, Entry: ${actual_entry_price:.2f}, Exit: ${exit_price:.2f}, "
                        pnl_msg += f"P&L: ${total_pnl:.2f} (${pnl_per_share:.2f}/share), Reason: {result['exit_reason']}"
                        
                        logging.info(pnl_msg)
                        print(f"💰 {pnl_msg}")
                        
                        # Send Telegram notification for trade closed by protective order
                        try:
                            # Calculate holding time
                            entry_time = main_order.created_at
                            exit_time = order.created_at
                            holding_time_delta = exit_time - entry_time
                            holding_time_minutes = holding_time_delta.total_seconds() / 60
                            
                            # Map exit reason for notification
                            exit_reason_map = {
                                'TAKE_PROFIT': 'TP',
                                'STOP_LOSS': 'SL'
                            }
                            notification_exit_reason = exit_reason_map.get(result['exit_reason'], result['exit_reason'])
                            
                            notify_trade_closed(
                                symbol=symbol,
                                quantity=exit_qty,
                                exit_price=exit_price,
                                realized_pnl=total_pnl,
                                realized_pnl_pct=(total_pnl / (actual_entry_price * exit_qty)) * 100,
                                exit_reason=notification_exit_reason,
                                order_id=order_id,
                                holding_time_minutes=holding_time_minutes,
                                timestamp=exit_time
                            )
                        except Exception as notify_error:
                            logging.warning(f"Failed to send trade closed notification for {symbol}: {notify_error}")
                        
                        break
        
        elif main_order.status.value in ['CANCELED', 'CANCELLED']:
            cancel_reason = getattr(main_order, 'cancel_reason', 'Unknown')
            result['exit_reason'] = f'CANCELLED: {cancel_reason}'
            logging.info(f"Order cancelled for {symbol}: {cancel_reason}")
            
        elif main_order.status.value == 'REJECTED':
            reject_reason = getattr(main_order, 'reject_reason', 'Unknown')
            result['exit_reason'] = f'REJECTED: {reject_reason}'
            logging.info(f"Order rejected for {symbol}: {reject_reason}")
        
        return result
        
    except Exception as e:
        logging.error(f"Error checking order status for {symbol}: {e}")
        return {
            'symbol': symbol,
            'order_id': order_id,
            'status': 'ERROR',
            'error': str(e),
            'pnl': 0.0
        }