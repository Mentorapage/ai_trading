#AUTOMATED TRADING - TECHNOLOGY STOCKS

# Setup

import trade_types
import cancel_all

import finnhub
from concurrent.futures import ThreadPoolExecutor
from apscheduler.schedulers.blocking import BlockingScheduler
import logging
import pandas as pd


import nltk
nltk.download('vader_lexicon', quiet=True)
from nltk.sentiment.vader import SentimentIntensityAnalyzer


import time
import datetime
from datetime import datetime, time as t_time

from alpaca_trade_api.rest import REST
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetClass

from dotenv import load_dotenv
import os

logging.basicConfig(filename='trading.log', level=logging.INFO)

load_dotenv(dotenv_path=".env")
finn_api_key = os.getenv("finnhubkey")
alpaca_api_key = os.getenv("apikey")
alpaca_secret_key = os.getenv("apisecret")

trading_client = TradingClient(alpaca_api_key, alpaca_secret_key, paper=True)
search_params = GetAssetsRequest(asset_class=AssetClass.US_EQUITY)
assets = trading_client.get_all_assets(search_params)

account = trading_client.get_account()

paper_api = REST(alpaca_api_key, alpaca_secret_key, base_url="https://paper-api.alpaca.markets")

#############################################################

# Automated Trading Functions

if not finn_api_key:
    raise ValueError("Finnhub API key is not set in the environment variables.")

cash = account.cash
buying_power = account.buying_power

def get_sentiment(i):
    finnhub_client = finnhub.Client(api_key=finn_api_key)
    today = datetime.now()
    today_date = today.strftime("%Y-%m-%d")
    
    all_articles = finnhub_client.company_news(i, _from=today_date, to=today_date) 
    sia = SentimentIntensityAnalyzer()  # Initialize sentiment intensity analyzer
    total_market_score = []
    for article in all_articles:
        published_time = datetime.fromtimestamp(article['datetime'])
        if t_time(13, 0) <= published_time.time() <= t_time(13, 30):  # Filter articles based on time
            news_score = sia.polarity_scores(article['summary']) 
            #print(published_time)
            total_market_score.append(news_score['compound'])  # Append the compound score to the total score list
    final_news_score = total_market_score[:10]
    avg_news_score  = sum(final_news_score) / len(final_news_score) if final_news_score else 0  # Calculate the average score
    return avg_news_score 

read_my_list = pd.read_csv("technology_tickers.csv") #####CSV OF STOCK TICKERS (TECHNOLOGY)#####
stocks = read_my_list['Ticker'].tolist()

reduced_stocks = []


def stock_check(base=0.5, limit=0.7):
    for i in stocks:
      
        score = get_sentiment(i)
        if limit >= score >= base:
            reduced_stocks.append(i)
            time.sleep(1)
        else:
            time.sleep(1)

    

def auto_buy(i, shares_to_buy, added_limit, prevent_loss):
    trade_types.bracket_order(
        symbol=i,
        qty=shares_to_buy,
        side="BUY",
        tif="DAY",
        low=paper_api.get_latest_trade(i).price - prevent_loss,
        high=paper_api.get_latest_trade(i).price + added_limit, 
    )


def auto_trade():
    print("Started Job")
    stock_check()      

    if reduced_stocks:
        with ThreadPoolExecutor(max_workers=len(reduced_stocks)) as executor:

            for i in reduced_stocks:
                try:
                    price = paper_api.get_latest_trade(i).price
                except Exception as e:
                    print(f"Error fetching price for {i}: {e}")
                    logging.error(f"Error fetching price for {i}: {e} at {datetime.now()}")
                    continue
                
                investment_amount = float(buying_power) * 0.9

                try:
                    shares_to_buy = int(investment_amount / len(reduced_stocks) / price)
                except ZeroDivisionError:
                    print(f"Error calculating shares to buy for {i}: Division by zero.")
                    continue

                if shares_to_buy <= 0:
                    print(f"Not enough buying power to buy shares of {i}.")
                    logging.error(f"Not enough buying power to buy shares of {i} at {datetime.now()}.")
                    continue

                if investment_amount / len(reduced_stocks) < 1:
                    print(f"Not enough buying power to buy shares of {i}. Minimum investment required.")
                    logging.error(f"Not enough buying power to buy shares of {i}. Minimum investment required at {datetime.now()}.")
                    continue
                
                executor.submit(auto_buy, i, shares_to_buy, 0.5, 1.5)
                print(f"Auto trading for {i} initiated.")
                logging.info(f"Auto trading for {i} initiated at {datetime.now()}.")
    else:
        print("No stocks met the criteria for trading.")
        print(datetime.now())
        logging.warning(f"No stocks met the criteria for trading at {datetime.now()}.")

#############################################################

# Automated Trading Execution
if __name__ == "__main__":
    
    scheduler = BlockingScheduler()
    scheduler.add_job(auto_trade, 'cron', hour=6, minute=29, second=41)
    scheduler.add_job(cancel_all.cancel_all_orders_and_positions, 'cron', hour=12, minute=59, second=57)

    scheduler.start()

# End of auto_trade.py
# This script checks stock sentiment and executes trades based on predefined criteria.


#####IMPORTANT##### LINES 147-148 - SCHEDULE BASED ON TIME ON LOCAL MACHINE