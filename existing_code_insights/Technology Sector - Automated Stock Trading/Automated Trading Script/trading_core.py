"""
TRADING CORE UTILITIES
=====================
Shared functions for sentiment analysis, stock screening, and common trading logic
"""

import pandas as pd
import time
import logging
from datetime import datetime
from dotenv import load_dotenv
import os

# NLTK setup with bootstrap
import bootstrap_nltk  # noqa
from nltk.sentiment.vader import SentimentIntensityAnalyzer

# Runtime check for VADER lexicon
try:
    _ = SentimentIntensityAnalyzer()
except LookupError as e:
    raise RuntimeError("VADER lexicon missing. Run: `python3 -m nltk.downloader vader_lexicon -d ./nltk_data`") from e

# Import new modules with error handling
try:
    from config_loader import config
except ImportError:
    logging.warning("config_loader not available, using defaults")
    config = {'strategy': {'trend_filter': {'enabled': False}, 'news_weighting': {'enabled': False}}}

try:
    from trend_filter import apply_trend_filter
except ImportError:
    logging.warning("trend_filter not available, disabling trend filtering")
    def apply_trend_filter(*args, **kwargs):
        return {}

try:
    from news_weighting import apply_news_weighting, log_news_weighting_debug
except ImportError:
    logging.warning("news_weighting not available, using equal weighting")
    def apply_news_weighting(articles):
        return articles
    def log_news_weighting_debug(*args):
        pass

try:
    from finnhub_pool import get_company_news
except ImportError:
    logging.warning("finnhub_pool not available, using basic news fetching")
    def get_company_news(ticker, start_date, end_date):
        import requests
        api_key = os.getenv('FINNHUB_KEYS', '').split(',')[0].strip() or os.getenv('finnhubkey', '').strip()
        if not api_key:
            return []
        try:
            response = requests.get(
                'https://finnhub.io/api/v1/company-news',
                params={'symbol': ticker, 'from': start_date, 'to': end_date, 'token': api_key},
                timeout=10
            )
            return response.json() if response.status_code == 200 else []
        except Exception as e:
            logging.error(f"Error fetching news for {ticker}: {e}")
            return []

# Load environment variables
load_dotenv(dotenv_path=".env")

# Initialize logging (only if not already configured)
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/app.log'),
            logging.StreamHandler()
        ]
    )

def validate_environment():
    """Validate that required environment variables are set"""
    # Check for Finnhub keys (single or multiple)
    finn_api_key = os.getenv("finnhubkey")
    finn_keys = os.getenv("FINNHUB_KEYS")
    
    if not finn_api_key and not finn_keys:
        raise ValueError("Finnhub API key(s) not set in the .env file. Please check your configuration.")
    
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

def get_sentiment(ticker, target_date=None, decision_time=None):
    """
    Get sentiment score for a stock ticker with optional source weighting
    
    Args:
        ticker (str): Stock ticker symbol
        target_date (str, optional): Date in YYYY-MM-DD format. If None, uses today.
        decision_time (datetime, optional): Decision timestamp for time filtering. If None, uses current time.
    
    Returns:
        float: Average sentiment score (-1 to 1)
    """
    try:
        if target_date is None:
            target_date = datetime.now().strftime("%Y-%m-%d")
        
        if decision_time is None:
            decision_time = datetime.now()
        
        # Fetch news for the target date using rate-limited pool
        all_articles = get_company_news(ticker, target_date, target_date)
        
        if not all_articles:
            logging.warning(f"No news found for {ticker} on {target_date}")
            return 0.0
        
        # Initialize sentiment analyzer
        sia = SentimentIntensityAnalyzer()
        valid_articles = []
        sentiment_scores = []
        
        # Process articles with time filtering
        for article in all_articles:
            published_time = datetime.fromtimestamp(article['datetime'])
            
            # Time-based filtering (no look-ahead)
            include_article = False
            
            if target_date == datetime.now().strftime("%Y-%m-%d"):
                # For today's date, include articles published before decision time
                if published_time <= decision_time and published_time.date() == decision_time.date():
                    include_article = True
            else:
                # For historical dates, include all news from that date
                target_dt = datetime.strptime(target_date, "%Y-%m-%d").date()
                if published_time.date() == target_dt:
                    include_article = True
            
            if include_article:
                news_score = sia.polarity_scores(article['summary'])
                valid_articles.append(article)
                sentiment_scores.append(news_score['compound'])
        
        if not valid_articles:
            return 0.0
        
        # Limit to top K articles (configurable)
        top_k = config.get('strategy.sentiment.top_k_articles', 10)
        if len(valid_articles) > top_k:
            valid_articles = valid_articles[:top_k]
            sentiment_scores = sentiment_scores[:top_k]
        
        # Apply news weighting if enabled
        weighting_config = config.get_news_weighting_config()
        final_sentiment, debug_info = apply_news_weighting(
            ticker, valid_articles, sentiment_scores, decision_time, weighting_config
        )
        
        # Debug logging
        debug_enabled = config.get('logging.debug_news_weighting', False)
        log_news_weighting_debug(ticker, debug_info, debug_enabled)
        
        logging.debug(f"{ticker} sentiment on {target_date}: {final_sentiment:.4f} ({len(valid_articles)} articles)")
        return final_sentiment
        
    except Exception as e:
        logging.error(f"Error getting sentiment for {ticker}: {e}")
        return 0.0

def screen_stocks_by_sentiment(stocks, min_sentiment=0.0, max_sentiment=1.0, target_date=None, decision_time=None):
    """
    Screen stocks based on sentiment analysis with optional trend filtering
    
    Args:
        stocks (list): List of stock tickers
        min_sentiment (float): Minimum sentiment threshold
        max_sentiment (float): Maximum sentiment threshold
        target_date (str, optional): Date for historical analysis
        decision_time (datetime, optional): Decision timestamp for filtering
    
    Returns:
        dict: Dictionary with ticker as key and sentiment score as value for qualifying stocks
    """
    if decision_time is None:
        decision_time = datetime.now()
    
    print(f"\n🧠 SENTIMENT ANALYSIS RESULTS ({datetime.now().strftime('%H:%M:%S')})")
    print("=" * 60)
    
    date_str = target_date if target_date else "today"
    logging.info(f"Starting sentiment analysis for {len(stocks)} stocks on {date_str}")
    print(f"📅 Analysis date: {date_str}")
    print(f"📊 Sentiment range: {min_sentiment:.2f} to {max_sentiment:.2f}")
    
    # Apply trend filter first if enabled
    try:
        trend_config = config.get('strategy', {}).get('trend_filter', {'enabled': False})
    except (AttributeError, TypeError):
        trend_config = {'enabled': False}
    
    if trend_config.get('enabled', False):
        print(f"📈 Trend filter: {trend_config.get('comparator', 'none')} (MA{trend_config.get('lookback_days', 20)})")
        
        # Convert target_date to datetime for trend filtering
        if target_date:
            filter_date = datetime.strptime(target_date, "%Y-%m-%d")
        else:
            filter_date = decision_time
        
        trend_results = apply_trend_filter(stocks, filter_date, trend_config)
        trend_passed_stocks = [stock for stock, passed in trend_results.items() if passed]
        trend_failed_stocks = [stock for stock, passed in trend_results.items() if not passed]
        
        print(f"📈 Trend filter results: {len(trend_passed_stocks)} passed, {len(trend_failed_stocks)} failed")
        if trend_failed_stocks:
            print(f"📉 Trend filter excluded: {trend_failed_stocks}")
        
        # Only analyze sentiment for stocks that passed trend filter
        stocks_to_analyze = trend_passed_stocks
    else:
        stocks_to_analyze = stocks
    
    print()
    
    qualified_stocks = {}
    
    for ticker in stocks_to_analyze:
        try:
            score = get_sentiment(ticker, target_date, decision_time)
            
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
    
    # Show stocks excluded by trend filter
    if trend_config.get('enabled', False):
        for ticker in trend_failed_stocks:
            print(f"{ticker:5}: TREND - ❌ No (excluded by trend filter)")
    
    print("=" * 60)
    print(f"📊 SUMMARY: {len(qualified_stocks)} stocks qualify for trading")
    
    if qualified_stocks:
        print(f"🎯 Qualifying stocks: {list(qualified_stocks.keys())}")
        for ticker, score in qualified_stocks.items():
            print(f"   {ticker}: {score:.4f}")
    else:
        print("⚠️  No stocks meet the criteria")
    
    logging.info(f"Stock screening complete: {len(qualified_stocks)} qualifying stocks")
    return qualified_stocks

def calculate_position_size(available_capital, num_stocks, stock_price, min_position_value=100, safety_buffer=0.95):
    """
    Calculate position size for a stock with safety buffer for order execution
    
    Args:
        available_capital (float): Total available capital
        num_stocks (int): Number of stocks to distribute capital across
        stock_price (float): Current stock price
        min_position_value (float): Minimum position value in dollars
        safety_buffer (float): Safety buffer to ensure order can be filled (default 95%)
    
    Returns:
        tuple: (shares, position_value, adjusted_capital_needed)
    """
    if num_stocks == 0 or available_capital <= 0:
        return 0, 0, 0
    
    # Apply safety buffer to available capital
    safe_capital = available_capital * safety_buffer
    position_value = safe_capital / num_stocks
    
    if position_value < min_position_value:
        logging.warning(f"Position value ${position_value:.2f} below minimum ${min_position_value}")
        return 0, 0, 0
    
    # Calculate shares and verify we have enough capital
    shares = int(position_value / stock_price)
    actual_cost = shares * stock_price
    
    # Additional safety check - ensure we don't exceed available capital
    if actual_cost > available_capital:
        # Reduce shares to fit within actual capital
        shares = int(available_capital * safety_buffer / stock_price)
        actual_cost = shares * stock_price
        
    logging.info(f"Position sizing: {shares} shares @ ${stock_price:.2f} = ${actual_cost:.2f} "
                f"(from ${available_capital:.2f} available)")
    
    return max(0, shares), actual_cost, actual_cost

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