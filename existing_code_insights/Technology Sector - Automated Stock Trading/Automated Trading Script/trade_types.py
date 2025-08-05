from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, StopLossRequest, TakeProfitRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv(dotenv_path=".env")
api_key = os.getenv("apikey")
secret_key = os.getenv("apisecret")

# Initialize trading client
trading_client = TradingClient(api_key, secret_key, paper=True)
account = trading_client.get_account()


def get_account_info():
    account = trading_client.get_account()
    info = {
        "account_id": account.id,
        "cash": account.cash,
        "portfolio_value": account.portfolio_value,
        "status": account.status,
        "buying_power": account.buying_power,
        "equity": account.equity
    }
    return info

# Individual getter functions removed - use get_account_info() for comprehensive account data
# Order management functions removed - not used in current trading strategy


def bracket_order(symbol, qty, side, tif, high, low):
    """
    Enhanced bracket order with comprehensive validation and error handling
    """
    import logging
    
    # Input validation
    if not symbol or not symbol.strip():
        raise ValueError("Symbol cannot be empty")
    
    if qty <= 0:
        raise ValueError(f"Quantity must be positive, got {qty}")
    
    if high <= 0 or low <= 0:
        raise ValueError(f"Prices must be positive. High: {high}, Low: {low}")
    
    if side.upper() == "BUY" and low >= high:
        raise ValueError(f"For BUY orders, stop-loss ({low}) must be less than take-profit ({high})")
    
    # Ensure prices are properly rounded to avoid sub-penny issues
    high = round(float(high), 2)
    low = round(float(low), 2)
    
    # Validate price increments (Alpaca requirement) with floating-point tolerance
    high_cents = round(high * 100, 0)
    low_cents = round(low * 100, 0)
    
    if abs(high * 100 - high_cents) > 0.0001 or abs(low * 100 - low_cents) > 0.0001:
        raise ValueError(f"Prices must be in penny increments. High: {high}, Low: {low}")
    
    # Final safety: ensure exact penny precision
    high = round(high_cents / 100, 2)
    low = round(low_cents / 100, 2)
    
    try:
        # Create the bracket order
        my_order = MarketOrderRequest(
            symbol=symbol.upper().strip(),
            qty=int(qty),
            side=OrderSide[side.upper()],
            time_in_force=TimeInForce[tif.upper()],
            order_class=OrderClass.BRACKET,
            stop_loss=StopLossRequest(stop_price=low),
            take_profit=TakeProfitRequest(limit_price=high)
        )
        
        # Submit the order
        submitted_order = trading_client.submit_order(my_order)
        
        # Validate submission was successful
        if not submitted_order or not submitted_order.id:
            raise Exception("Order submission failed - no order ID returned")
        
        success_msg = f"Bracket order submitted. Order ID: {submitted_order.id} Status: {submitted_order.status}"
        logging.info(f"Order validation passed for {symbol}: High=${high}, Low=${low}, Qty={qty}")
        
        return success_msg
        
    except Exception as e:
        error_msg = f"Bracket order failed for {symbol}: {str(e)}"
        logging.error(error_msg)
        raise Exception(error_msg) from e