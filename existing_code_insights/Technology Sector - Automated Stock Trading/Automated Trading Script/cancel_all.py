from alpaca.trading.client import TradingClient

import os
from dotenv import load_dotenv
import logging
from datetime import datetime


load_dotenv(dotenv_path=".env")

alpaca_api_key = os.getenv("apikey")
alpaca_secret_key = os.getenv("apisecret")

def cancel_all_orders_and_positions():

    trading_client = TradingClient(alpaca_api_key, alpaca_secret_key, paper=True)

    trading_client.close_all_positions(cancel_orders=True)
    print("All orders cancelled and all positions closed.")
    logging.info(f"All orders cancelled and all positions closed at {datetime.now()}.")

if __name__ == "__main__":
    cancel_all_orders_and_positions()
    # This will cancel all orders and close all positions when the script is run.