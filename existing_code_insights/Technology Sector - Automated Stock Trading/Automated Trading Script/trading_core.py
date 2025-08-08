"""
TRADING CORE UTILITIES
=====================
Shared functions for sentiment analysis, stock screening, and common trading logic
"""

import finnhub
import pandas as pd
import time
import logging
from datetime import datetime
from dotenv import load_dotenv
import os

# NLTK setup
import nltk
nltk.download('vader_lexicon', quiet=True)
from nltk.sentiment.vader import SentimentIntensityAnalyzer

# Load environment variables
load_dotenv(dotenv_path=".env")
finn_api_key = os.getenv("finnhubkey")

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading.log'),
        logging.StreamHandler()
    ]
)

def validate_environment():
    """Validate that required environment variables are set"""
    if not finn_api_key:
        raise ValueError("Finnhub API key is not set in the .env file. Please check your configuration.")
    
    alpaca_api_key = os.getenv("apikey")
    alpaca_secret_key = os.getenv("apisecret")
    
    if not alpaca_api_key or not alpaca_secret_key:
        raise ValueError("Alpaca API keys are not set in the .env file. Please check your configuration.")
    
    return True

def load_stock_universe():
    """Load the stock universe from CSV file"""
    try:
        stocks_df = pd.read_csv("technology_tickers.csv")
        stocks = stocks_df['Ticker'].tolist()
        logging.info(f"Loaded {len(stocks)} stocks from universe: {stocks}")
        return stocks
    except Exception as e:
        logging.error(f"Failed to load stock universe: {e}")
        raise

def get_sentiment(ticker, target_date=None):
    """
    Get sentiment score for a stock ticker
    
    Args:
        ticker (str): Stock ticker symbol
        target_date (str, optional): Date in YYYY-MM-DD format. If None, uses today.
    
    Returns:
        float: Average sentiment score (-1 to 1)
    """
    try:
        finnhub_client = finnhub.Client(api_key=finn_api_key)
        
        if target_date is None:
            target_date = datetime.now().strftime("%Y-%m-%d")
        
        # Fetch news for the target date
        all_articles = finnhub_client.company_news(ticker, _from=target_date, to=target_date)
        
        if not all_articles:
            logging.warning(f"No news found for {ticker} on {target_date}")
            return 0.0
        
        # Initialize sentiment analyzer
        sia = SentimentIntensityAnalyzer()
        sentiment_scores = []
        
        # Process articles
        for article in all_articles:
            published_time = datetime.fromtimestamp(article['datetime'])
            
            # For today's date, include all news from the same date
            if target_date == datetime.now().strftime("%Y-%m-%d"):
                if published_time.date() == datetime.now().date():
                    news_score = sia.polarity_scores(article['summary'])
                    sentiment_scores.append(news_score['compound'])
            else:
                # For historical dates, include all news from that date
                target_dt = datetime.strptime(target_date, "%Y-%m-%d").date()
                if published_time.date() == target_dt:
                    news_score = sia.polarity_scores(article['summary'])
                    sentiment_scores.append(news_score['compound'])
        
        # Calculate average sentiment (limit to top 10 articles)
        final_scores = sentiment_scores[:10]
        avg_sentiment = sum(final_scores) / len(final_scores) if final_scores else 0.0
        
        logging.debug(f"{ticker} sentiment on {target_date}: {avg_sentiment:.4f} ({len(final_scores)} articles)")
        return avg_sentiment
        
    except Exception as e:
        logging.error(f"Error getting sentiment for {ticker}: {e}")
        return 0.0

def screen_stocks_by_sentiment(stocks, min_sentiment=0.0, max_sentiment=1.0, target_date=None):
    """
    Screen stocks based on sentiment analysis
    
    Args:
        stocks (list): List of stock tickers
        min_sentiment (float): Minimum sentiment threshold
        max_sentiment (float): Maximum sentiment threshold
        target_date (str, optional): Date for historical analysis
    
    Returns:
        dict: Dictionary with ticker as key and sentiment score as value for qualifying stocks
    """
    qualified_stocks = {}
    
    print(f"\n🧠 SENTIMENT ANALYSIS RESULTS ({datetime.now().strftime('%H:%M:%S')})")
    print("=" * 60)
    
    date_str = target_date if target_date else "today"
    logging.info(f"Starting sentiment analysis for {len(stocks)} stocks on {date_str}")
    print(f"📅 Analysis date: {date_str}")
    print(f"📊 Sentiment range: {min_sentiment:.2f} to {max_sentiment:.2f}")
    print()
    
    for ticker in stocks:
        try:
            score = get_sentiment(ticker, target_date)
            
            # Determine qualification status
            qualified = min_sentiment <= score <= max_sentiment
            status = "✅ QUALIFIED" if qualified else "❌ No"
            
            # Display result
            print(f"{ticker:5}: {score:.4f} - {status}")
            
            if qualified:
                qualified_stocks[ticker] = score
                
            # Rate limiting for API calls
            time.sleep(1)
            
        except Exception as e:
            print(f"{ticker:5}: ERROR - {e}")
            logging.error(f"Failed to analyze {ticker}: {e}")
            continue
    
    print("=" * 60)
    print(f"📊 SUMMARY: {len(qualified_stocks)} stocks qualify for trading")
    
    if qualified_stocks:
        print(f"🎯 Qualifying stocks: {list(qualified_stocks.keys())}")
        for ticker, score in qualified_stocks.items():
            print(f"   {ticker}: {score:.4f}")
    else:
        print("⚠️  No stocks meet the sentiment threshold")
    
    logging.info(f"Sentiment analysis complete: {len(qualified_stocks)} qualifying stocks")
    return qualified_stocks

def calculate_position_size(available_capital, num_stocks, stock_price, min_position_value=100):
    """
    Calculate position size for a stock
    
    Args:
        available_capital (float): Total available capital
        num_stocks (int): Number of stocks to distribute capital across
        stock_price (float): Current stock price
        min_position_value (float): Minimum position value in dollars
    
    Returns:
        int: Number of shares to buy (0 if position too small)
    """
    if num_stocks == 0:
        return 0
    
    position_value = available_capital / num_stocks
    
    if position_value < min_position_value:
        return 0
    
    shares = int(position_value / stock_price)
    return max(0, shares)

def format_currency(amount):
    """Format amount as currency"""
    return f"${amount:,.2f}"

def format_percentage(value):
    """Format value as percentage"""
    return f"{value:.2f}%"

def log_trade_attempt(ticker, action, details):
    """Log trade attempt with consistent formatting"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    message = f"[{timestamp}] {action} - {ticker}: {details}"
    logging.info(message)
    print(f"📝 {message}") 