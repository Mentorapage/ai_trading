#!/usr/bin/env python3
"""
Enhanced Sentiment Analysis with News Logging
Replacement for the original get_sentiment function
"""

import finnhub
import os
from datetime import datetime
from dotenv import load_dotenv
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from news_logger import NewsLogger

# Load environment variables
load_dotenv(dotenv_path='.env')
finn_api_key = os.getenv('finnhubkey')

# Initialize global news logger for the session
news_logger = NewsLogger()

def get_sentiment_with_logging(stock_symbol):
    """
    Enhanced sentiment analysis that logs all news articles
    
    Args:
        stock_symbol: Stock ticker symbol (e.g., 'AAPL')
    
    Returns:
        float: Average sentiment score (-1.0 to 1.0)
    """
    
    if not finn_api_key:
        raise ValueError("Finnhub API key is not set in the environment variables.")
    
    finnhub_client = finnhub.Client(api_key=finn_api_key)
    today = datetime.now()
    today_date = today.strftime("%Y-%m-%d")
    
    print(f"🔍 Analyzing news for {stock_symbol}...")
    
    try:
        # Fetch all articles for the stock
        all_articles = finnhub_client.company_news(stock_symbol, _from=today_date, to=today_date)
        
        if not all_articles:
            print(f"   ⚠️  No articles found for {stock_symbol}")
            news_logger.finalize_stock_analysis(stock_symbol, 0.0)
            return 0.0
        
        sia = SentimentIntensityAnalyzer()
        total_market_score = []
        articles_processed = 0
        
        # Process each article
        for article in all_articles:
            published_time = datetime.fromtimestamp(article['datetime'])
            
            # Only include articles from today
            if published_time.date() == datetime.now().date():
                # Calculate sentiment for this article
                news_score = sia.polarity_scores(article['summary'])
                sentiment_score = news_score['compound']
                
                # Log the article with its sentiment
                news_logger.log_article_analysis(stock_symbol, article, sentiment_score)
                
                # Add to total for averaging
                total_market_score.append(sentiment_score)
                articles_processed += 1
                
                # Print article details for transparency
                print(f"   📰 {article['headline'][:60]}...")
                print(f"      📊 Sentiment: {sentiment_score:.4f} | Source: {article['source']}")
        
        # Calculate final sentiment score
        final_news_score = total_market_score[:10]  # Limit to first 10 articles
        avg_news_score = sum(final_news_score) / len(final_news_score) if final_news_score else 0
        
        # Finalize the analysis for this stock
        news_logger.finalize_stock_analysis(stock_symbol, avg_news_score)
        
        print(f"   ✅ {stock_symbol}: {articles_processed} articles processed, sentiment: {avg_news_score:.4f}")
        
        return avg_news_score
        
    except Exception as e:
        print(f"   ❌ Error analyzing {stock_symbol}: {str(e)}")
        news_logger.finalize_stock_analysis(stock_symbol, 0.0)
        return 0.0

def analyze_all_stocks_with_logging(stocks_list, base=0.0, limit=0.7):
    """
    Analyze sentiment for all stocks and save comprehensive logs
    
    Args:
        stocks_list: List of stock symbols to analyze
        base: Minimum sentiment threshold for trading
        limit: Maximum sentiment threshold for trading
    
    Returns:
        tuple: (qualifying_stocks, rejected_stocks)
    """
    
    print(f"\n🧠 ENHANCED SENTIMENT ANALYSIS WITH NEWS LOGGING")
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 Sentiment Range: {base} to {limit}")
    print("=" * 80)
    
    qualifying_stocks = []
    rejected_stocks = []
    
    # Analyze each stock
    for stock in stocks_list:
        sentiment_score = get_sentiment_with_logging(stock)
        
        # Check if stock qualifies for trading
        if base <= sentiment_score <= limit:
            qualifying_stocks.append(stock)
            status = "✅ QUALIFIED"
        else:
            rejected_stocks.append(stock)
            status = "❌ REJECTED"
        
        print(f"🎯 {stock}: {sentiment_score:.4f} - {status}")
        print()
    
    # Generate comprehensive logs
    print("\n📁 GENERATING NEWS LOGS...")
    print("-" * 50)
    
    # Save positive news log
    positive_log_file = news_logger.save_positive_news_log()
    
    # Save complete session log
    session_log_file = news_logger.save_complete_session_log()
    
    # Save trading decisions log
    decision_log_file = news_logger.save_trading_decision_log(qualifying_stocks, rejected_stocks)
    
    # Print session summary
    news_logger.print_session_summary()
    
    print(f"\n📋 ANALYSIS COMPLETE:")
    print(f"✅ {len(qualifying_stocks)} stocks qualified for trading")
    print(f"❌ {len(rejected_stocks)} stocks rejected")
    print(f"📁 All logs saved to: news_logs/ directory")
    
    return qualifying_stocks, rejected_stocks

# Drop-in replacement function for backward compatibility
def get_sentiment(stock_symbol):
    """
    Drop-in replacement for the original get_sentiment function
    Uses the enhanced version with logging
    """
    return get_sentiment_with_logging(stock_symbol)

# Function to enable/disable detailed logging
def set_detailed_logging(enabled=True):
    """
    Enable or disable detailed news article logging
    
    Args:
        enabled: True to enable logging, False to use original behavior
    """
    global use_detailed_logging
    use_detailed_logging = enabled
    
    if enabled:
        print("✅ Detailed news logging ENABLED")
        print("📁 Articles will be saved to news_logs/ directory")
    else:
        print("⚠️  Detailed news logging DISABLED")
        print("📰 Articles will be processed in memory only")

if __name__ == "__main__":
    # Test the enhanced sentiment analysis
    test_stocks = ['AAPL', 'MSFT', 'NVDA']
    
    print("🧪 TESTING ENHANCED SENTIMENT ANALYSIS")
    print("=" * 60)
    
    qualifying, rejected = analyze_all_stocks_with_logging(test_stocks)
    
    print(f"\n🎯 RESULTS:")
    print(f"✅ Qualifying: {qualifying}")
    print(f"❌ Rejected: {rejected}") 