#!/usr/bin/env python3
"""
VOLUME + NEWS/SENTIMENT ANALYZER
===============================
Two filters only: Volume AND News/Sentiment (NO ATR, MA20-trend, z-scores)
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional
from pathlib import Path
import csv
import pytz

# Import existing modules
from historical_backtest import get_historical_data
from finnhub_api_pool import get_finnhub_pool
from real_sentiment_analyzer import RealSentimentAnalyzer

class VolumeNewsAnalyzer:
    """Dual-filter analyzer: Volume + News/Sentiment (NO other signals)"""
    
    def __init__(self, audit_dir: str = "audit_logs"):
        """Initialize the volume + news analyzer"""
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(exist_ok=True)
        
        # Initialize Finnhub and sentiment analyzer
        self.finnhub_pool = get_finnhub_pool()
        self.sentiment_analyzer = RealSentimentAnalyzer()
        
        # ET timezone
        self.et_tz = pytz.timezone('America/New_York')
        
        logging.info("Volume + News analyzer initialized - Dual filters: volume AND news/sentiment")
    
    def calculate_volume_eligibility(self, ticker: str, analysis_date: str) -> Dict:
        """Calculate volume eligibility - FIRST filter"""
        try:
            # Get 30 days of data for volume analysis
            end_date = datetime.strptime(analysis_date, '%Y-%m-%d').date()
            start_date = end_date - timedelta(days=40)
            
            daily_data = get_historical_data(
                ticker=ticker,
                start_date=datetime.combine(start_date, datetime.min.time().replace(hour=9, minute=30)),
                end_date=datetime.combine(end_date - timedelta(days=1), datetime.min.time().replace(hour=16)),
                timeframe='1Day'
            )
            
            if len(daily_data) < 20:
                return {
                    'volume_yesterday': 0,
                    'volume_ma20': 0,
                    'passed_volume': False
                }
            
            # Volume metrics
            volume_yesterday = daily_data['volume'].iloc[-1]
            volume_ma20 = daily_data['volume'].rolling(window=20).mean().iloc[-1]
            
            # Volume filter: volume_yesterday > volume_ma20
            passed_volume = volume_yesterday > volume_ma20
            
            return {
                'volume_yesterday': volume_yesterday,
                'volume_ma20': volume_ma20,
                'passed_volume': passed_volume
            }
            
        except Exception as e:
            logging.warning(f"Volume filter failed for {ticker}: {e}")
            return {
                'volume_yesterday': 0,
                'volume_ma20': 0,
                'passed_volume': False
            }
    
    def calculate_news_sentiment_eligibility(
        self, 
        ticker: str, 
        analysis_date: str,
        min_news_count: int = 2,
        min_sentiment: float = 0.1,
        max_sentiment: float = 0.7
    ) -> Dict:
        """Calculate news/sentiment eligibility - SECOND filter with 24-hour window"""
        try:
            # Parse analysis date and set decision time to 09:30 ET
            analysis_dt = datetime.strptime(analysis_date, '%Y-%m-%d')
            decision_time = self.et_tz.localize(analysis_dt.replace(hour=9, minute=30))
            
            # Calculate 24-hour news window: previous day 09:30 ET to current day 09:30 ET
            news_window_start = decision_time - timedelta(days=1)
            news_window_end = decision_time
            
            # Get news within 24-hour window using existing method but with expanded date range
            from_date = news_window_start.strftime('%Y-%m-%d')
            to_date = news_window_end.strftime('%Y-%m-%d')
            
            # Fetch news from Finnhub for the expanded window
            articles = self.finnhub_pool.get_company_news(ticker, from_date, to_date)
            
            if not articles:
                return {
                    'articles_count': 0,
                    'sources_count': 0,
                    'raw_sentiment': 0,
                    'weighted_sentiment': 0,
                    'top_headline': '',
                    'news_window_start': news_window_start.strftime('%Y-%m-%d %H:%M:%S ET'),
                    'news_window_end': news_window_end.strftime('%Y-%m-%d %H:%M:%S ET'),
                    'passed_news': False
                }
            
            # Filter articles within the 24-hour window
            window_start_timestamp = news_window_start.timestamp()
            window_end_timestamp = news_window_end.timestamp()
            
            valid_articles = []
            for article in articles:
                article_time = article.get('datetime', 0)
                if window_start_timestamp <= article_time <= window_end_timestamp:
                    valid_articles.append(article)
            
            if len(valid_articles) < min_news_count:
                return {
                    'articles_count': len(valid_articles),
                    'sources_count': len(set(article.get('source', 'Unknown') for article in valid_articles)) if valid_articles else 0,
                    'raw_sentiment': 0,
                    'weighted_sentiment': 0,
                    'top_headline': (valid_articles[0].get('headline','') if valid_articles else ''),
                    'news_window_start': news_window_start.strftime('%Y-%m-%d %H:%M:%S ET'),
                    'news_window_end': news_window_end.strftime('%Y-%m-%d %H:%M:%S ET'),
                    'passed_news': False
                }
            
            # Analyze sentiment for each article
            total_weighted_sentiment = 0.0
            total_weight = 0.0
            raw_sentiments = []
            
            for article in valid_articles:
                sentiment_data = self.sentiment_analyzer._analyze_article_sentiment(article)
                source_weight = self.sentiment_analyzer._get_source_weight(article.get('url', ''))
                
                raw_sentiments.append(sentiment_data['sentiment_score'])
                
                # Calculate weighted contribution
                weighted_contribution = sentiment_data['sentiment_score'] * source_weight
                total_weighted_sentiment += weighted_contribution
                total_weight += source_weight
            
            # Calculate final metrics
            articles_count = len(valid_articles)
            sources_count = len(set(article.get('source', 'Unknown') for article in valid_articles))
            raw_sentiment = np.mean(raw_sentiments) if raw_sentiments else 0
            weighted_sentiment = total_weighted_sentiment / total_weight if total_weight > 0 else 0
            
            # News/Sentiment filter criteria
            meets_min_news = articles_count >= min_news_count
            meets_sentiment_range = min_sentiment <= weighted_sentiment <= max_sentiment
            
            passed_news = meets_min_news and meets_sentiment_range
            
            return {
                'articles_count': articles_count,
                'sources_count': sources_count,
                'raw_sentiment': raw_sentiment,
                'weighted_sentiment': weighted_sentiment,
                'top_headline': (valid_articles[0].get('headline','') if valid_articles else ''),
                'news_window_start': news_window_start.strftime('%Y-%m-%d %H:%M:%S ET'),
                'news_window_end': news_window_end.strftime('%Y-%m-%d %H:%M:%S ET'),
                'passed_news': passed_news
            }
            
        except Exception as e:
            logging.warning(f"News/sentiment filter failed for {ticker}: {e}")
            return {
                'articles_count': 0,
                'sources_count': 0,
                'raw_sentiment': 0,
                'weighted_sentiment': 0,
                'news_window_start': 'ERROR',
                'news_window_end': 'ERROR',
                'passed_news': False
            }
    
    def screen_stocks_by_volume_and_news(
        self, 
        stocks: List[str], 
        analysis_date: str,
        min_news_count: int = 2,
        min_sentiment: float = 0.1,
        max_sentiment: float = 0.7
    ) -> List[Dict]:
        """Screen stocks using BOTH volume AND news/sentiment filters"""
        
        qualified_stocks = []
        audit_data = []
        
        for ticker in stocks:
            try:
                # FIRST filter: Volume
                volume_data = self.calculate_volume_eligibility(ticker, analysis_date)
                
                # SECOND filter: News/Sentiment
                news_data = self.calculate_news_sentiment_eligibility(
                    ticker, analysis_date, min_news_count, min_sentiment, max_sentiment
                )
                
                # FINAL eligibility: BOTH filters must pass
                passed_all_filters = volume_data['passed_volume'] and news_data['passed_news']
                
                # Combine data
                stock_data = {
                    'ticker': ticker,
                    'date': analysis_date,
                    **volume_data,
                    **news_data,
                    'passed_all_filters': passed_all_filters
                }
                
                # Add to results if passed BOTH filters
                if passed_all_filters:
                    qualified_stocks.append(stock_data)
                
                # Add to audit log
                audit_data.append(stock_data)
                
            except Exception as e:
                logging.error(f"Error screening {ticker}: {e}")
                continue
        
        # Save audit log
        self._save_audit_log(analysis_date, audit_data)
        
        # No sorting needed - just return all that passed BOTH filters
        logging.info(f"Screened {len(stocks)} stocks, {len(qualified_stocks)} qualified (volume AND news)")
        return qualified_stocks
    
    def _save_audit_log(self, analysis_date: str, audit_data: List[Dict]):
        """Save audit log with dual-filter schema including 24-hour news window"""
        audit_file = self.audit_dir / f"volume_news_audit_{analysis_date}.csv"
        
        # Dual-filter audit columns (13 columns) - added news window columns
        audit_columns = [
            'date', 'ticker',
            'volume_yesterday', 'volume_ma20',
            'articles_count', 'sources_count', 'raw_sentiment', 'weighted_sentiment',
            'news_window_start', 'news_window_end',
            'passed_volume', 'passed_news', 'passed_all_filters'
        ]
        
        try:
            with open(audit_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=audit_columns)
                writer.writeheader()
                
                for data in audit_data:
                    # Extract only the columns we want
                    row = {col: data.get(col, '') for col in audit_columns}
                    writer.writerow(row)
                    
        except Exception as e:
            logging.error(f"Failed to save audit log: {e}")
