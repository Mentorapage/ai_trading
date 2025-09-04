#!/usr/bin/env python3
"""
REAL SENTIMENT ANALYZER
=======================
Real sentiment analysis using Finnhub API pool with source weighting and audit logging
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import csv

# Import NLTK components
import bootstrap_nltk  # noqa
from nltk.sentiment.vader import SentimentIntensityAnalyzer

# Import our API pool
from finnhub_api_pool import get_finnhub_pool
from config_loader import config

class RealSentimentAnalyzer:
    """Real sentiment analysis with Finnhub API and source weighting"""
    
    def __init__(self, audit_dir: str = "audit_logs"):
        """
        Initialize the real sentiment analyzer
        
        Args:
            audit_dir: Directory to store audit CSV files
        """
        self.finnhub_pool = get_finnhub_pool()
        self.analyzer = SentimentIntensityAnalyzer()
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(exist_ok=True)
        
        # Load source weights from config
        self.source_weights = self._load_source_weights()
        
        logging.info("Real Sentiment Analyzer initialized")
        logging.info(f"Audit logs will be saved to: {self.audit_dir}")
    
    def _load_source_weights(self) -> Dict[str, float]:
        """Load news source weights from configuration"""
        try:
            weights = config.get('strategy', {}).get('news_weighting', {}).get('source_weights', {})
            default_weight = config.get('strategy', {}).get('news_weighting', {}).get('default_weight', 1.0)
            
            # Add default weight for unknown sources
            weights['unknown'] = default_weight
            
            logging.info(f"Loaded {len(weights)} source weights")
            return weights
            
        except Exception as e:
            logging.warning(f"Could not load source weights: {e}, using defaults")
            return {
                'bloomberg.com': 1.30,
                'reuters.com': 1.25,
                'wsj.com': 1.20,
                'cnbc.com': 1.10,
                'marketwatch.com': 1.05,
                'yahoo.com': 0.90,
                'unknown': 1.00
            }
    
    def _get_source_weight(self, url: str) -> float:
        """Get weight for a news source URL"""
        if not url:
            return self.source_weights.get('unknown', 1.0)
        
        # Extract domain from URL
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.lower()
            
            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            
            return self.source_weights.get(domain, self.source_weights.get('unknown', 1.0))
            
        except Exception:
            return self.source_weights.get('unknown', 1.0)
    
    def _analyze_article_sentiment(self, article: Dict) -> Dict:
        """Analyze sentiment of a single article"""
        # Combine headline and summary for analysis
        text_parts = []
        
        if article.get('headline'):
            text_parts.append(article['headline'])
        
        if article.get('summary'):
            text_parts.append(article['summary'])
        
        if not text_parts:
            return {
                'sentiment_score': 0.0,
                'confidence': 0.0,
                'text_length': 0
            }
        
        combined_text = ' '.join(text_parts)
        
        # Get VADER sentiment
        scores = self.analyzer.polarity_scores(combined_text)
        
        return {
            'sentiment_score': scores['compound'],  # -1 to +1
            'confidence': max(abs(scores['pos']), abs(scores['neg'])),
            'text_length': len(combined_text),
            'pos': scores['pos'],
            'neu': scores['neu'],
            'neg': scores['neg']
        }
    
    def get_stock_sentiment(self, symbol: str, analysis_date: str, min_news_count: int = 2) -> Dict:
        """
        Get sentiment analysis for a stock on a specific date
        
        Args:
            symbol: Stock symbol
            analysis_date: Date for analysis (YYYY-MM-DD)
            min_news_count: Minimum number of articles required
            
        Returns:
            Dict with sentiment analysis results
        """
        # Calculate date range (look back 2 days for news)
        target_date = datetime.strptime(analysis_date, '%Y-%m-%d')
        from_date = (target_date - timedelta(days=2)).strftime('%Y-%m-%d')
        to_date = analysis_date
        
        # Fetch news from Finnhub
        logging.debug(f"Fetching news for {symbol} from {from_date} to {to_date}")
        articles = self.finnhub_pool.get_company_news(symbol, from_date, to_date)
        
        if not articles:
            logging.debug(f"No articles found for {symbol}")
            return {
                'symbol': symbol,
                'date': analysis_date,
                'articles_count': 0,
                'sentiment_score': 0.0,
                'weighted_sentiment': 0.0,
                'meets_min_news': False,
                'source_breakdown': {},
                'articles_analyzed': []
            }
        
        # Filter articles published before decision time (09:30 ET on analysis_date)
        decision_time = datetime.strptime(f"{analysis_date} 09:30:00", '%Y-%m-%d %H:%M:%S')
        decision_timestamp = decision_time.timestamp()
        
        valid_articles = []
        for article in articles:
            article_time = article.get('datetime', 0)
            if article_time <= decision_timestamp:
                valid_articles.append(article)
        
        if len(valid_articles) < min_news_count:
            logging.debug(f"Insufficient articles for {symbol}: {len(valid_articles)} < {min_news_count}")
            return {
                'symbol': symbol,
                'date': analysis_date,
                'articles_count': len(valid_articles),
                'sentiment_score': 0.0,
                'weighted_sentiment': 0.0,
                'meets_min_news': False,
                'source_breakdown': {},
                'articles_analyzed': []
            }
        
        # Analyze sentiment for each article
        analyzed_articles = []
        total_weighted_sentiment = 0.0
        total_weight = 0.0
        source_breakdown = {}
        
        for article in valid_articles:
            sentiment_data = self._analyze_article_sentiment(article)
            source_weight = self._get_source_weight(article.get('url', ''))
            
            # Track source breakdown
            source = article.get('source', 'unknown')
            if source not in source_breakdown:
                source_breakdown[source] = {'count': 0, 'weight': source_weight, 'avg_sentiment': 0.0}
            source_breakdown[source]['count'] += 1
            source_breakdown[source]['avg_sentiment'] += sentiment_data['sentiment_score']
            
            # Calculate weighted contribution
            weighted_contribution = sentiment_data['sentiment_score'] * source_weight
            total_weighted_sentiment += weighted_contribution
            total_weight += source_weight
            
            analyzed_articles.append({
                'headline': article.get('headline', ''),
                'source': source,
                'url': article.get('url', ''),
                'datetime': article.get('datetime', 0),
                'sentiment_score': sentiment_data['sentiment_score'],
                'source_weight': source_weight,
                'weighted_contribution': weighted_contribution
            })
        
        # Calculate final scores
        avg_sentiment = np.mean([a['sentiment_score'] for a in analyzed_articles])
        weighted_sentiment = total_weighted_sentiment / total_weight if total_weight > 0 else 0.0
        
        # Finalize source breakdown
        for source_data in source_breakdown.values():
            source_data['avg_sentiment'] /= source_data['count']
        
        result = {
            'symbol': symbol,
            'date': analysis_date,
            'articles_count': len(analyzed_articles),
            'sentiment_score': avg_sentiment,
            'weighted_sentiment': weighted_sentiment,
            'meets_min_news': len(analyzed_articles) >= min_news_count,
            'source_breakdown': source_breakdown,
            'articles_analyzed': analyzed_articles
        }
        
        logging.debug(f"{symbol}: {len(analyzed_articles)} articles, sentiment={weighted_sentiment:.3f}")
        return result
    
    def screen_stocks_by_sentiment(
        self, 
        stocks: List[str], 
        analysis_date: str, 
        min_sentiment: float = 0.2,
        max_sentiment: float = 1.0,
        min_news_count: int = 2,
        score_threshold: float = 0.3
    ) -> List[Dict]:
        """
        Screen stocks based on real sentiment analysis
        
        Args:
            stocks: List of stock symbols
            analysis_date: Date for analysis (YYYY-MM-DD)
            min_sentiment: Minimum sentiment threshold
            max_sentiment: Maximum sentiment threshold
            min_news_count: Minimum number of articles required
            score_threshold: Minimum weighted sentiment score to qualify
            
        Returns:
            List of ALL qualified stocks with sentiment data (no limit)
        """
        logging.info(f"Screening {len(stocks)} stocks for {analysis_date}")
        logging.info(f"Sentiment range: {min_sentiment:.2f} to {max_sentiment:.2f}")
        logging.info(f"Min news count: {min_news_count}")
        logging.info(f"Score threshold: {score_threshold:.2f}")
        
        # Analyze sentiment for all stocks
        stock_sentiments = []
        audit_data = []
        
        for i, symbol in enumerate(stocks):
            logging.debug(f"Analyzing {symbol} ({i+1}/{len(stocks)})")
            
            sentiment_data = self.get_stock_sentiment(symbol, analysis_date, min_news_count)
            
            # Check if stock qualifies (using score_threshold instead of min/max range)
            qualifies = (
                sentiment_data['meets_min_news'] and
                sentiment_data['weighted_sentiment'] >= score_threshold
            )
            
            if qualifies:
                stock_sentiments.append({
                    'ticker': symbol,
                    'sentiment': sentiment_data['weighted_sentiment'],
                    'articles_count': sentiment_data['articles_count'],
                    'source_breakdown': sentiment_data['source_breakdown'],
                    'raw_sentiment': sentiment_data['sentiment_score']
                })
            
            # Add to audit log
            audit_data.append({
                'ticker': symbol,
                'date': analysis_date,
                'articles_count': sentiment_data['articles_count'],
                'raw_sentiment': sentiment_data['sentiment_score'],
                'weighted_sentiment': sentiment_data['weighted_sentiment'],
                'meets_min_news': sentiment_data['meets_min_news'],
                'qualifies': qualifies,
                'source_count': len(sentiment_data['source_breakdown'])
            })
        
        # Sort by weighted sentiment (descending) and return ALL qualified stocks
        stock_sentiments.sort(key=lambda x: x['sentiment'], reverse=True)
        qualified_stocks = stock_sentiments  # No top_k limitation!
        
        # Save audit log
        self._save_audit_log(analysis_date, audit_data)
        
        # Print API usage stats
        self.finnhub_pool.print_usage_stats()
        
        logging.info(f"Qualified {len(qualified_stocks)} stocks out of {len(stocks)}")
        for stock in qualified_stocks:
            logging.info(f"  {stock['ticker']}: {stock['sentiment']:.3f} ({stock['articles_count']} articles)")
        
        return qualified_stocks
    
    def _save_audit_log(self, analysis_date: str, audit_data: List[Dict]):
        """Save audit log for transparency"""
        audit_file = self.audit_dir / f"sentiment_audit_{analysis_date}.csv"
        
        try:
            with open(audit_file, 'w', newline='') as f:
                if audit_data:
                    writer = csv.DictWriter(f, fieldnames=audit_data[0].keys())
                    writer.writeheader()
                    writer.writerows(audit_data)
            
            logging.info(f"Audit log saved: {audit_file}")
            
        except Exception as e:
            logging.error(f"Failed to save audit log: {e}")

# Global instance
_sentiment_analyzer = None

def get_sentiment_analyzer() -> RealSentimentAnalyzer:
    """Get the global sentiment analyzer instance"""
    global _sentiment_analyzer
    if _sentiment_analyzer is None:
        _sentiment_analyzer = RealSentimentAnalyzer()
    return _sentiment_analyzer
