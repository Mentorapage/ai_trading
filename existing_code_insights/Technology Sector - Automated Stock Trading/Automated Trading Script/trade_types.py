import alpaca_trade_api as ata
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest, MarketOrderRequest, LimitOrderRequest, StopLossRequest, TrailingStopOrderRequest, StopLimitOrderRequest, TakeProfitRequest
from alpaca.trading.enums import AssetClass, OrderSide, TimeInForce, OrderClass
from alpaca_trade_api.rest import REST
import dotenv as dt
from dotenv import load_dotenv
import os
import websocket as websocket
load_dotenv(dotenv_path=".env")
#load env
api_key = os.getenv("apikey")
secret_key = os.getenv("apisecret")
trading_client = TradingClient(api_key, secret_key, paper=True)
search_params = GetAssetsRequest(asset_class=AssetClass.US_EQUITY)
assets = trading_client.get_all_assets(search_params)
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

def get_account_cash():
    account = trading_client.get_account()
    return account.cash

def get_account_buying_power():
    account = trading_client.get_account()
    return account.buying_power

def get_account_portfolio_value():
    account = trading_client.get_account()
    return account.portfolio_value

def get_account_status():
    account = trading_client.get_account()
    return account.status

def get_account_equity():
    account = trading_client.get_account()
    return account.equity

def get_account_id():
    account = trading_client.get_account()
    return account.id

def get_order_by_id(order_id):
    order = trading_client.get_order_by_id(order_id)
    return order

def get_all_orders():
    orders = trading_client.get_all_orders()
    return orders

def get_open_orders():
    open_orders = trading_client.get_open_orders()
    return open_orders

def get_order_status(order_id):
    order = trading_client.get_order_by_id(order_id)
    return order.status if order else None

def cancel_order(order_id):
    try:
        trading_client.cancel_order(order_id)
        return f"Order {order_id} has been cancelled."
    except Exception as e:
        return f"Error cancelling order {order_id}: {str(e)}"


def bracket_order(symbol, qty, side, tif, high, low):
    my_order = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=OrderSide[side],
        time_in_force=TimeInForce[tif],
        order_class=OrderClass.BRACKET,
        stop_loss=StopLossRequest(stop_price=low,),
        take_profit=TakeProfitRequest(limit_price=high,)
    )
    submitted_order = trading_client.submit_order(my_order)
    info = (f"Bracket order submitted. Order ID: {submitted_order.id} Order Status: {submitted_order.status}")
    return info