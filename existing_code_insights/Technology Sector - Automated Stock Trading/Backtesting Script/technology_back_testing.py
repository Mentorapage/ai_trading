##########BACTESTING - TECHNOLOGY STOCKS##########

import finnhub
import settings
import os
import nltk
import pandas as pd
import time
import datetime


from alpaca.data.timeframe import TimeFrame

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime

from dotenv import load_dotenv
from datetime import datetime, time as t_time

load_dotenv(dotenv_path=".env")
api_key = os.getenv("finnhubkey")
key = os.getenv("apikey")
secret = os.getenv("apisecret")

if not os.getenv("finnhubkey"):
    raise ValueError("Finnhub API key is not set in the .env file.")

nltk.download('vader_lexicon')  #KEY# DDD
from nltk.sentiment.vader import SentimentIntensityAnalyzer

def news_score(ticker):
    finnhub_client = finnhub.Client(api_key=api_key)
    finn_start_date = settings.base_date
    finn_end_date = settings.base_date
    all_articles = finnhub_client.company_news(ticker, _from=finn_start_date, to=finn_end_date) 
    sia = SentimentIntensityAnalyzer()
    total_market_score = []
    
    for article in all_articles:
        published_time = datetime.fromtimestamp(article['datetime'])
        if t_time(13, 0) <= published_time.time() <= t_time(13, 30):  #KEY# CCC
            news_score = sia.polarity_scores(article['summary']) 
            #print(published_time)
            total_market_score.append(news_score['compound'])
    final_news_score = total_market_score[:10]
    avg_news_score  = sum(final_news_score) / len(final_news_score) if final_news_score else 0  # Calculate the average score
    print(avg_news_score)
    return avg_news_score 



def backtest(base, limit, buying_power, added_limit, prevent_loss):
    read_my_list = pd.read_csv('technology.csv') ###########CSV WITH STOCK TICKERS###########
    stocks = read_my_list['Ticker'].tolist()

    reduced_stocks = []

    for i in stocks:
        score = news_score(i)
        print(i)
        if limit >= score >= base:
            reduced_stocks.append(i)
            time.sleep(0.1)
        else:
            time.sleep(0.1)

    client = StockHistoricalDataClient(api_key=key, secret_key=secret)
    investment_ammount = buying_power * 0.9
    ammount_spent = []
    ammount_gained = []
    date = settings.base_date
    print(reduced_stocks)
    for ticker in reduced_stocks:
        print(ticker)
        request_params = StockBarsRequest(
                                symbol_or_symbols=[ticker],
                                timeframe=TimeFrame.Minute,
                                start=datetime(2025, 5, 31), #KEY# EEE
                                end=datetime(2025, 7, 1),    
                        )

        bars = client.get_stock_bars(request_params)

        list_df= [dict(val) for _, val in enumerate(bars.data[ticker])]  
        bars_df = pd.DataFrame(list_df)

        bars_df.set_index('timestamp', inplace=True)
        time_set = settings.timestamp_13
        bars_filter = bars_df[bars_df.index == time_set]['open']     

        bars_df.to_csv(f"{ticker}_backtest_data.csv")
        price = (bars_filter.iloc[0])
        print(f"${price} for share of {ticker} at {time_set}")
        
        shares = investment_ammount / len(reduced_stocks) / price
        print(f"Buying {shares} shares of {ticker} at ${price} each.")
        total_cost = shares * price
        ammount_spent.append(total_cost)
    
        check_bars = client.get_stock_bars(request_params)
    
        check_list_df = [dict(val) for _, val in enumerate(check_bars.data[ticker])]  
        check_bars_df = pd.DataFrame(check_list_df)
        
        check_bars_df.set_index('timestamp', inplace=True)
        start_set = settings.timestamp_13
        end_set = settings.timestamp_20
        start_set_converted = datetime.fromisoformat(start_set)
        end_set_converted = datetime.fromisoformat(end_set)
        check_bars_filter = check_bars_df[check_bars_df.index == start_set]['open']
        check_price = (check_bars_filter.iloc[0])

        is_sold = False
       
        
        for i in check_bars_df.index:
            if start_set_converted <= i <= end_set_converted:
                
                check_bars_filter = check_bars_df[check_bars_df.index == i]['open']
                check_price = (check_bars_filter.iloc[0])
                
                if check_price >= price + added_limit:
                    
                    sell_bars = client.get_stock_bars(request_params)

                    sell_list_df = [dict(val) for _, val in enumerate(sell_bars.data[ticker])]  
                    sell_bars_df = pd.DataFrame(sell_list_df)

                    sell_bars_df.set_index('timestamp', inplace=True)
                    sell_bars_filter = sell_bars_df[bars_df.index == i]['open']     
                    
                    sell_price = (sell_bars_filter.iloc[0])
                    
                        
                    print(f"${sell_price} for share of {ticker} at {i}")
                    
                    
                    print(f"Selling {shares} shares of {ticker} at ${sell_price} each.")
                    total_sell_cost = shares * sell_price
                    print(total_sell_cost - total_cost)
                    ammount_gained.append(total_sell_cost)
                    print("_" * 50)
                    is_sold = True
                    break
                
                elif check_price <= price - prevent_loss:
                    sell_bars = client.get_stock_bars(request_params)

                    sell_list_df = [dict(val) for _, val in enumerate(sell_bars.data[ticker])]  
                    sell_bars_df = pd.DataFrame(sell_list_df)

                    sell_bars_df.set_index('timestamp', inplace=True)
                    sell_bars_filter = sell_bars_df[bars_df.index == i]['open']     
                    
                    sell_price = (sell_bars_filter.iloc[0])
       
                    print(f"${sell_price} for share of {ticker} at {i}")

                    print(f"Selling {shares} shares of {ticker} at ${sell_price} each.")
                    
                    total_sell_cost = shares * sell_price
                    print(total_sell_cost - total_cost)
                    ammount_gained.append(total_sell_cost)
                    print("_" * 50)
                    is_sold = True
                    break
            
        if not is_sold:
            sell_bars = client.get_stock_bars(request_params)
            
            sell_list_df = [dict(val) for _, val in enumerate(sell_bars.data[ticker])]  
            sell_bars_df = pd.DataFrame(sell_list_df)

            sell_bars_df.set_index('timestamp', inplace=True)
            time_set2 = settings.timestamp_20
            sell_bars_filter = sell_bars_df[bars_df.index == time_set2]['close']     

            sell_price = (sell_bars_filter.iloc[0])
            
                
            print(f"${sell_price} for share of {ticker} at {time_set2}")
            
            
            print(f"Selling {shares} shares of {ticker} at ${sell_price} each.")
            total_sell_cost = shares * sell_price
            print(total_sell_cost - total_cost)
            ammount_gained.append(total_sell_cost)
            print("_" * 50)
 
    
    profit = sum(ammount_gained) - sum(ammount_spent)
    print(f"Total profit from backtest: ${profit}")
    
    print("_" * 50)

    buying_power += profit
    print(f"Buying power after backtest: ${buying_power}")
    profit_df = pd.DataFrame({
        'Total Profit': [profit],
        'Date': [date],
        'Buying Power': [buying_power],
    })

    profit_df.to_csv('profit.csv', index=False, mode='a')
    
    return profit

 
#############################################################################################################################

#RUN BACKTESTING#

if __name__ == "__main__":
    profit = backtest(0.5, 0.7,  100000, 0.5, 1.5) #KEY# AAA

####################INSTRUCTIONS FOR USE####################

####KEYS IN CODE ASSOCIATED WITH INFO BELOW####: AAA, BBB, CCC, DDD, EEE

###IMPORTANT - AAA### back_testing.py BACKTEST FUNCTION ARGS: base, limit, initial balance, added_limit, prevent_loss

# base - lowest news score for ticker to be traded (if news score is lower than limit, stock will not be traded)
# limit - highest news score for ticker to be traded (if news score is higher than limit, stock will not be traded)
# initial balance - starting balance to calculate profit after backtesting for a certain day (in the past)
# added_limit - limits how high the stock's price goes before making a sell/liquidate
# prevent_loss - limits how low the stock's goes before making a sell/liquidate

###IMPORTANT - BBB### settings.py VARIABLES: BASE_DATE & TIMESTAMP_13/20

# base_date - trading day to backtest on
# timestamp_13 - buying time (ERRORS WILL OCCUR IF CHANGED)
# timestamp_20 - "worst case" selling time (ERRORS WILL OCCUR IF CHANGED)

###NOTE - CCC### back_testing.py DATETIME FUNCTION: t_time()

# t_time(13,0) - news articles published after this time
# t_time(13,30) - news articles published before this time
###SEE KEY CCC IN CODE TO SEE EXAMPLE###

###NOTE - DDD### back_testing.py NLTK DOWNLOAD: VADER LEXICON

# nltk.download('vader_lexicon') - designed for inital use only; please comment the line after first run to save time and avoid multiple downloads

###IMPORTANT - EEE### back_testing.py VARIABLES WITH DATETIME FUNCTIONS: TIMEFRAME FOR BACKTESTING

# start=datetime(2025, 5, 31) - start date for backtesting (ALPACA DATA DOES NOT INCLUDE THIS DATE)
# end=datetime(2025, 7, 1) - end date for backtesting (ALPACA DATA DOES NOT INCLUDE THIS DATE)