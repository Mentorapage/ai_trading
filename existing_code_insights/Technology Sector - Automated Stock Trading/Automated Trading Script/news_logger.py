#!/usr/bin/env python3
"""
News Article Logger for AI Trading System
Logs and tracks news articles used in sentiment analysis
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any
import logging

class NewsLogger:
    """
    Handles logging and storage of news articles during sentiment analysis
    """
    
    def __init__(self, log_directory: str = "news_logs"):
        """Initialize the news logger"""
        self.log_directory = log_directory
        self.setup_logging_directory()
        self.session_news = {}  # Store news for current session
        
    def setup_logging_directory(self):
        """Create logging directory if it doesn't exist"""
        if not os.path.exists(self.log_directory):
            os.makedirs(self.log_directory)
            print(f"📁 Created news logging directory: {self.log_directory}")
    
    def log_article_analysis(self, stock: str, article: Dict[Any, Any], sentiment_score: float):
        """
        Log a single article with its sentiment analysis result
        
        Args:
            stock: Stock symbol (e.g., 'AAPL')
            article: Full article data from Finnhub API
            sentiment_score: Calculated sentiment score for this article
        """
        
        if stock not in self.session_news:
            self.session_news[stock] = {
                'total_articles': 0,
                'positive_articles': [],
                'negative_articles': [],
                'neutral_articles': [],
                'average_sentiment': 0.0
            }
        
        # Extract relevant article information
        article_data = {
            'timestamp': datetime.now().isoformat(),
            'published_time': datetime.fromtimestamp(article['datetime']).isoformat(),
            'headline': article.get('headline', 'No headline'),
            'source': article.get('source', 'Unknown'),
            'url': article.get('url', ''),
            'summary': article.get('summary', 'No summary')[:200] + '...',  # Truncate for storage
            'sentiment_score': round(sentiment_score, 4),
            'category': self.categorize_sentiment(sentiment_score)
        }
        
        # Categorize and store the article
        if sentiment_score > 0.1:
            self.session_news[stock]['positive_articles'].append(article_data)
        elif sentiment_score < -0.1:
            self.session_news[stock]['negative_articles'].append(article_data)
        else:
            self.session_news[stock]['neutral_articles'].append(article_data)
        
        self.session_news[stock]['total_articles'] += 1
    
    def categorize_sentiment(self, score: float) -> str:
        """Categorize sentiment score into readable categories"""
        if score >= 0.5:
            return "Very Positive"
        elif score >= 0.1:
            return "Positive"
        elif score >= -0.1:
            return "Neutral"
        elif score >= -0.5:
            return "Negative"
        else:
            return "Very Negative"
    
    def finalize_stock_analysis(self, stock: str, final_sentiment: float):
        """
        Finalize analysis for a stock and calculate aggregated metrics
        
        Args:
            stock: Stock symbol
            final_sentiment: Final average sentiment score for the stock
        """
        if stock in self.session_news:
            self.session_news[stock]['average_sentiment'] = round(final_sentiment, 4)
            self.session_news[stock]['analysis_completed'] = datetime.now().isoformat()
    
    def save_positive_news_log(self):
        """Save positive news articles to a dedicated file"""
        today = datetime.now().strftime('%Y-%m-%d')
        positive_log_file = os.path.join(self.log_directory, f"positive_news_{today}.txt")
        
        with open(positive_log_file, 'w', encoding='utf-8') as f:
            f.write(f"📰 POSITIVE NEWS ARTICLES - {today}\n")
            f.write("=" * 80 + "\n\n")
            
            for stock, data in self.session_news.items():
                positive_articles = data.get('positive_articles', [])
                if positive_articles:
                    f.write(f"🟢 {stock} - Average Sentiment: {data['average_sentiment']:.4f}\n")
                    f.write("-" * 60 + "\n")
                    
                    for i, article in enumerate(positive_articles, 1):
                        f.write(f"{i}. {article['headline']}\n")
                        f.write(f"   📊 Sentiment: {article['sentiment_score']:.4f} ({article['category']})\n")
                        f.write(f"   📅 Published: {article['published_time']}\n")
                        f.write(f"   📰 Source: {article['source']}\n")
                        f.write(f"   🔗 URL: {article['url']}\n")
                        f.write(f"   📝 Summary: {article['summary']}\n")
                        f.write("\n")
                    f.write("\n")
        
        print(f"✅ Positive news saved to: {positive_log_file}")
        return positive_log_file
    
    def save_complete_session_log(self):
        """Save complete session analysis to JSON file"""
        today = datetime.now().strftime('%Y-%m-%d')
        timestamp = datetime.now().strftime('%H%M%S')
        session_log_file = os.path.join(self.log_directory, f"session_analysis_{today}_{timestamp}.json")
        
        # Add session metadata
        session_data = {
            'session_info': {
                'date': today,
                'timestamp': datetime.now().isoformat(),
                'total_stocks_analyzed': len(self.session_news),
                'total_articles_processed': sum(data['total_articles'] for data in self.session_news.values())
            },
            'stock_analysis': self.session_news
        }
        
        with open(session_log_file, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Complete session log saved to: {session_log_file}")
        return session_log_file
    
    def save_trading_decision_log(self, qualified_stocks: List[str], rejected_stocks: List[str]):
        """Save a summary of trading decisions based on sentiment analysis"""
        today = datetime.now().strftime('%Y-%m-%d')
        decision_log_file = os.path.join(self.log_directory, f"trading_decisions_{today}.txt")
        
        with open(decision_log_file, 'w', encoding='utf-8') as f:
            f.write(f"🎯 TRADING DECISIONS BASED ON NEWS SENTIMENT - {today}\n")
            f.write("=" * 80 + "\n\n")
            
            f.write(f"✅ QUALIFIED FOR TRADING ({len(qualified_stocks)} stocks):\n")
            f.write("-" * 50 + "\n")
            for stock in qualified_stocks:
                if stock in self.session_news:
                    data = self.session_news[stock]
                    f.write(f"• {stock}: Sentiment {data['average_sentiment']:.4f} ")
                    f.write(f"({data['total_articles']} articles, ")
                    f.write(f"{len(data['positive_articles'])} positive)\n")
            
            f.write(f"\n❌ REJECTED STOCKS ({len(rejected_stocks)} stocks):\n")
            f.write("-" * 50 + "\n")
            for stock in rejected_stocks:
                if stock in self.session_news:
                    data = self.session_news[stock]
                    f.write(f"• {stock}: Sentiment {data['average_sentiment']:.4f} ")
                    f.write(f"({data['total_articles']} articles, ")
                    f.write(f"{len(data['negative_articles'])} negative)\n")
        
        print(f"✅ Trading decisions log saved to: {decision_log_file}")
        return decision_log_file
    
    def print_session_summary(self):
        """Print a summary of the current session's news analysis"""
        print("\n📊 NEWS ANALYSIS SESSION SUMMARY")
        print("=" * 60)
        
        total_articles = sum(data['total_articles'] for data in self.session_news.values())
        total_positive = sum(len(data['positive_articles']) for data in self.session_news.values())
        total_negative = sum(len(data['negative_articles']) for data in self.session_news.values())
        
        print(f"📰 Total Articles Analyzed: {total_articles}")
        print(f"🟢 Positive Articles: {total_positive}")
        print(f"🔴 Negative Articles: {total_negative}")
        print(f"⚪ Neutral Articles: {total_articles - total_positive - total_negative}")
        print(f"📈 Stocks Analyzed: {len(self.session_news)}")
        
        # Show top positive sentiment stocks
        if self.session_news:
            sorted_stocks = sorted(
                self.session_news.items(), 
                key=lambda x: x[1]['average_sentiment'], 
                reverse=True
            )
            
            print(f"\n🏆 TOP POSITIVE SENTIMENT:")
            for stock, data in sorted_stocks[:5]:
                print(f"   {stock}: {data['average_sentiment']:.4f} ({data['total_articles']} articles)")

# Example usage and testing
if __name__ == "__main__":
    # Test the news logger
    logger = NewsLogger()
    
    # Simulate some article logging
    sample_article = {
        'datetime': 1754400370,
        'headline': "Apple Announces Revolutionary AI Features",
        'source': "TechCrunch",
        'url': "https://example.com/news",
        'summary': "Apple unveils groundbreaking AI capabilities that could transform the smartphone industry.",
        'category': 'company'
    }
    
    logger.log_article_analysis('AAPL', sample_article, 0.75)
    logger.finalize_stock_analysis('AAPL', 0.65)
    logger.save_positive_news_log()
    logger.print_session_summary() 