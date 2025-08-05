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
        if published_time.date() == datetime.now().date():  # Include all news from today
            news_score = sia.polarity_scores(article['summary']) 
            #print(published_time)
            total_market_score.append(news_score['compound'])  # Append the compound score to the total score list
    final_news_score = total_market_score[:10]
    avg_news_score  = sum(final_news_score) / len(final_news_score) if final_news_score else 0  # Calculate the average score
    return avg_news_score 

# Load technology stock tickers
stocks = pd.read_csv("technology_tickers.csv")['Ticker'].tolist()
reduced_stocks = []


def stock_check(base=0.5, limit=0.7):
    """Screen stocks based on sentiment analysis within specified range."""
    reduced_stocks.clear()  # Clear previous results
    
    print(f"\n🧠 SENTIMENT ANALYSIS RESULTS ({datetime.now().strftime('%H:%M:%S')})")
    print("=" * 60)
    logging.info(f"Starting sentiment analysis for {len(stocks)} stocks at {datetime.now()}")
    
    for ticker in stocks:
        score = get_sentiment(ticker)
        
        # Determine qualification status
        qualified = "✅ QUALIFIED" if base <= score <= limit else "❌ No"
        
        # Log and print sentiment score
        print(f"{ticker:5}: {score:.4f} - {qualified}")
        logging.info(f"{ticker} sentiment: {score:.4f} - {'Qualified' if base <= score <= limit else 'Not qualified'}")
        
        if base <= score <= limit:
            reduced_stocks.append(ticker)
        time.sleep(1)  # Rate limiting for API calls
    
    print("=" * 60)
    print(f"📊 SUMMARY: {len(reduced_stocks)} stocks qualify for trading")
    if reduced_stocks:
        print(f"🎯 Qualifying stocks: {reduced_stocks}")
    else:
        print("⚠️  No stocks meet the sentiment threshold")
    
    logging.info(f"Sentiment analysis complete: {len(reduced_stocks)} qualifying stocks: {reduced_stocks}")

    

def auto_buy(i, shares_to_buy, added_limit, prevent_loss):
    try:
        current_price = paper_api.get_latest_trade(i).price  # Fetch price once
        
        # CRITICAL FIX: Round prices to prevent sub-penny errors
        high_price = round(current_price + added_limit, 2)
        low_price = round(current_price - prevent_loss, 2)
        
        # Validate prices are positive and reasonable
        if low_price <= 0:
            low_price = round(current_price * 0.95, 2)  # 5% stop-loss fallback
        
        logging.info(f"Order preparation for {i}: Price=${current_price:.2f}, High=${high_price:.2f}, Low=${low_price:.2f}")
        
        result = trade_types.bracket_order(
            symbol=i,
            qty=shares_to_buy,
            side="BUY",
            tif="DAY",
            low=low_price,
            high=high_price, 
        )
        
        logging.info(f"✅ SUCCESS: {i} order placed - {result}")
        return True, result
        
    except Exception as e:
        error_msg = f"❌ FAILED: {i} order failed - {str(e)}"
        logging.error(error_msg)
        print(f"   ERROR placing order for {i}: {str(e)}")
        return False, str(e)


def auto_trade():
    from market_utils import pre_trading_validation, log_validation_results
    
    print("🚀 AUTOMATED TRADING SESSION STARTED")
    print("=" * 60)
    print(f"⏰ Session Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Comprehensive pre-trading validation
    print("\n🔍 PERFORMING SAFETY VALIDATIONS...")
    ready_to_trade, validation_results = pre_trading_validation()
    
    # Display validation results
    for result in validation_results:
        status_icon = "✅" if result['passed'] else "❌"
        print(f"{status_icon} {result['check']}: {result['message']}")
    
    log_validation_results(validation_results)
    
    if not ready_to_trade:
        failed_checks = [r['check'] for r in validation_results if not r['passed']]
        error_msg = f"❌ TRADING ABORTED - Failed validation: {', '.join(failed_checks)}"
        print(f"\n{error_msg}")
        logging.error(error_msg)
        return False
    
    print("\n✅ ALL SAFETY CHECKS PASSED - PROCEEDING WITH TRADING")
    print()
    
    # Proceed with sentiment analysis and trading
    stock_check(base=0.0, limit=0.7)  # Updated criteria: 0.0 to 0.7      

    if reduced_stocks:
        print(f"\n💰 EXECUTING TRADES FOR {len(reduced_stocks)} QUALIFIED STOCKS")
        print("=" * 60)
        
        investment_amount = float(buying_power) * 0.9
        amount_per_stock = investment_amount / len(reduced_stocks)
        
        print(f"💵 Investment allocation: ${investment_amount:,.2f} total, ${amount_per_stock:,.2f} per stock")
        print()
        
        # Collect all trade parameters first
        trade_params = []
        for i in reduced_stocks:
            try:
                price = paper_api.get_latest_trade(i).price
                shares_to_buy = int(amount_per_stock / price)
                
                if shares_to_buy <= 0:
                    print(f"❌ {i}: Insufficient funds for minimum share purchase")
                    logging.warning(f"Skipping {i}: calculated {shares_to_buy} shares")
                    continue
                    
                if amount_per_stock < 1:
                    print(f"❌ {i}: Position size too small (${amount_per_stock:.2f})")
                    logging.warning(f"Skipping {i}: position size below minimum")
                    continue
                
                trade_params.append({
                    'symbol': i,
                    'shares': shares_to_buy,
                    'price': price,
                    'cost': shares_to_buy * price
                })
                
            except Exception as e:
                print(f"❌ {i}: Error in preparation - {e}")
                logging.error(f"Trade preparation failed for {i}: {e}")
                continue
        
        if not trade_params:
            print("❌ No trades can be executed due to insufficient capital or errors")
            logging.warning("No trades executed - all stocks failed preparation")
            return
        
        # Execute trades with proper result tracking
        print(f"🚀 Executing {len(trade_params)} trades concurrently...")
        
        futures = {}
        with ThreadPoolExecutor(max_workers=len(trade_params)) as executor:
            for params in trade_params:
                future = executor.submit(auto_buy, params['symbol'], params['shares'], 0.5, 1.5)
                futures[future] = params
        
        # Collect results and provide accurate logging
        successful_trades = []
        failed_trades = []
        
        for future in futures:
            params = futures[future]
            symbol = params['symbol']
            try:
                success, result = future.result(timeout=30)  # 30 second timeout
                if success:
                    successful_trades.append(symbol)
                    print(f"✅ {symbol}: Order placed successfully - {params['shares']} shares @ ${params['price']:.2f}")
                    logging.info(f"✅ SUCCESS: {symbol} trade completed - {result}")
                else:
                    failed_trades.append((symbol, result))
                    print(f"❌ {symbol}: Order failed - {result}")
                    
            except Exception as e:
                failed_trades.append((symbol, str(e)))
                print(f"❌ {symbol}: Execution timeout or error - {e}")
                logging.error(f"Trade execution failed for {symbol}: {e}")
        
        # Final summary
        print("\n" + "=" * 60)
        print(f"📊 TRADING EXECUTION SUMMARY:")
        print(f"✅ Successful: {len(successful_trades)} trades")
        print(f"❌ Failed: {len(failed_trades)} trades")
        
        if successful_trades:
            print(f"✅ Success: {', '.join(successful_trades)}")
            logging.info(f"Trading session completed: {len(successful_trades)} successful trades: {successful_trades}")
            
        if failed_trades:
            print(f"❌ Failures:")
            for symbol, reason in failed_trades:
                print(f"   {symbol}: {reason}")
            logging.error(f"Trading failures: {failed_trades}")
    else:
        print("No stocks met the criteria for trading.")
        print(datetime.now())
        logging.warning(f"No stocks met the criteria for trading at {datetime.now()}.")

#############################################################

# Automated Trading Execution
if __name__ == "__main__":
    
    scheduler = BlockingScheduler()
    # Updated for immediate testing: Trading at 16:17, Cleanup at 16:19
    scheduler.add_job(auto_trade, 'cron', hour=16, minute=17, second=0)
    scheduler.add_job(cancel_all.cancel_all_orders_and_positions, 'cron', hour=16, minute=19, second=0)
    
    print(f"🕐 IMMEDIATE TESTING MODE ACTIVATED")
    print(f"📅 Trading scheduled for: 16:17:00 (in ~1 minute)")
    print(f"📅 Cleanup scheduled for: 16:19:00 (2 minutes after trading)")
    print(f"🔄 System starting... Current time: {datetime.now().strftime('%H:%M:%S')}")

    scheduler.start()

# End of auto_trade.py
# This script checks stock sentiment and executes trades based on predefined criteria.


#####IMPORTANT##### LINES 147-148 - SCHEDULE BASED ON TIME ON LOCAL MACHINE