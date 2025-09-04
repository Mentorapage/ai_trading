#!/usr/bin/env python3
"""
SIMPLIFIED SENTIMENT ANALYZER
============================
Volume + News/Sentiment filters ONLY (no ATR, no MA20/trend)
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
from historical_backtest import get_historical_data

class SimplifiedSentimentAnalyzer:
    """Simplified sentiment analysis with Volume + News/Sentiment filters only"""
    
    def __init__(self, audit_dir: str = "audit_logs"):
        """Initialize the simplified sentiment analyzer"""
        self.finnhub_pool = get_finnhub_pool()
        self.vader = SentimentIntensityAnalyzer()
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(exist_ok=True)
        
        # Load configuration
        self.volume_multiplier_min = config.get('strategy', {}).get('volume', {}).get('volume_multiplier_min', 1.2)
        self.volume_z_min = config.get('strategy', {}).get('volume', {}).get('volume_z_min', 0.5)
        self.min_news_count = config.get('strategy', {}).get('news', {}).get('min_news_count', 2)
        self.min_sentiment = config.get('strategy', {}).get('news', {}).get('min_sentiment', 0.1)
        self.max_sentiment = config.get('strategy', {}).get('news', {}).get('max_sentiment', 0.7)
        
        # Source weights for sentiment analysis
        self.source_weights = {
            'Reuters': 1.0,
            'Bloomberg': 1.0,
            'MarketWatch': 0.8,
            'Yahoo': 0.7,
            'SeekingAlpha': 0.6,
            'Benzinga': 0.5
        }
        
        logging.info(f"Simplified analyzer initialized - Volume: {self.volume_multiplier_min}x/{self.volume_z_min}z, News: {self.min_news_count}+ articles, Sentiment: {self.min_sentiment}-{self.max_sentiment}")
    
    def calculate_volume_filter(self, ticker: str, analysis_date: str) -> Dict:
        """Calculate volume metrics and filter"""
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
                    'volume_zscore': 0,
                    'volume_filter_pass': False
                }
            
            # Volume metrics
            volume_yesterday = daily_data['volume'].iloc[-1]
            volume_ma20 = daily_data['volume'].rolling(window=20).mean().iloc[-1]
            volume_std20 = daily_data['volume'].rolling(window=20).std().iloc[-1]
            volume_zscore = (volume_yesterday - volume_ma20) / volume_std20 if volume_std20 > 0 else 0
            
            # Volume filter logic
            volume_filter_pass = (
                volume_yesterday >= self.volume_multiplier_min * volume_ma20 or
                volume_zscore >= self.volume_z_min
            )
            
            return {
                'volume_yesterday': volume_yesterday,
                'volume_ma20': volume_ma20,
                'volume_zscore': volume_zscore,
                'volume_filter_pass': volume_filter_pass
            }
            
        except Exception as e:
            logging.warning(f"Volume filter failed for {ticker}: {e}")
            return {
                'volume_yesterday': 0,
                'volume_ma20': 0,
                'volume_zscore': 0,
                'volume_filter_pass': False
            }
    
    def get_news_and_sentiment(self, ticker: str, analysis_date: str) -> Dict:
        """Get news and calculate sentiment (no caching for real-time accuracy)"""
        try:
            # Parse analysis date and set cutoff to 09:30 ET
            analysis_dt = datetime.strptime(analysis_date, '%Y-%m-%d')
            cutoff_time = analysis_dt.replace(hour=9, minute=30, second=0, microsecond=0)
            
            # Get news from Finnhub
            news_data = self.finnhub_pool.get_company_news(
                symbol=ticker,
                from_date=(analysis_dt - timedelta(days=1)).strftime('%Y-%m-%d'),
                to_date=analysis_date
            )
            
            if not news_data:
                return {
                    'articles_count': 0,
                    'sources_count': 0,
                    'raw_sentiment': 0.0,
                    'weighted_sentiment': 0.0,
                    'meets_min_news': False,
                    'meets_sentiment_range': False
                }
            
            # Filter articles by cutoff time and deduplicate
            valid_articles = []
            seen_titles = set()
            
            for article in news_data:
                if not isinstance(article, dict):
                    continue
                    
                # Check publication time
                pub_time = article.get('datetime', 0)
                if pub_time:
                    pub_dt = datetime.fromtimestamp(pub_time)
                    if pub_dt > cutoff_time:
                        continue
                
                # Deduplicate by title
                title = article.get('headline', '').strip()
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    valid_articles.append(article)
            
            if not valid_articles:
                return {
                    'articles_count': 0,
                    'sources_count': 0,
                    'raw_sentiment': 0.0,
                    'weighted_sentiment': 0.0,
                    'meets_min_news': False,
                    'meets_sentiment_range': False
                }
            
            # Calculate sentiment
            sentiments = []
            sources = set()
            
            for article in valid_articles:
                title = article.get('headline', '')
                summary = article.get('summary', '')
                source = article.get('source', 'Unknown')
                
                sources.add(source)
                
                # Combine title and summary for sentiment analysis
                text = f"{title} {summary}".strip()
                if text:
                    sentiment_scores = self.vader.polarity_scores(text)
                    compound_score = sentiment_scores['compound']
                    
                    # Normalize to 0-1 range
                    normalized_score = (compound_score + 1) / 2
                    sentiments.append((normalized_score, source))
            
            if not sentiments:
                return {
                    'articles_count': len(valid_articles),
                    'sources_count': len(sources),
                    'raw_sentiment': 0.0,
                    'weighted_sentiment': 0.0,
                    'meets_min_news': False,
                    'meets_sentiment_range': False
                }
            
            # Calculate raw sentiment (simple average)
            raw_sentiment = sum(score for score, _ in sentiments) / len(sentiments)
            
            # Calculate weighted sentiment
            weighted_sum = 0
            weight_sum = 0
            
            for score, source in sentiments:
                weight = self.source_weights.get(source, 0.3)  # Default weight for unknown sources
                weighted_sum += score * weight
                weight_sum += weight
            
            weighted_sentiment = weighted_sum / weight_sum if weight_sum > 0 else raw_sentiment
            
            # Check filters
            meets_min_news = len(valid_articles) >= self.min_news_count
            meets_sentiment_range = self.min_sentiment <= weighted_sentiment <= self.max_sentiment
            
            return {
                'articles_count': len(valid_articles),
                'sources_count': len(sources),
                'raw_sentiment': raw_sentiment,
                'weighted_sentiment': weighted_sentiment,
                'meets_min_news': meets_min_news,
                'meets_sentiment_range': meets_sentiment_range
            }
            
        except Exception as e:
            logging.warning(f"News/sentiment analysis failed for {ticker}: {e}")
            return {
                'articles_count': 0,
                'sources_count': 0,
                'raw_sentiment': 0.0,
                'weighted_sentiment': 0.0,
                'meets_min_news': False,
                'meets_sentiment_range': False
            }
    
    def screen_stocks_by_filters(
        self, 
        stocks: List[str], 
        analysis_date: str,
        score_threshold: Optional[float] = None
    ) -> List[Dict]:
        """Screen stocks using Volume + News/Sentiment filters only"""
        
        qualified_stocks = []
        audit_data = []
        
        for ticker in stocks:
            try:
                # Volume filter
                volume_data = self.calculate_volume_filter(ticker, analysis_date)
                
                # News/sentiment filter
                news_data = self.get_news_and_sentiment(ticker, analysis_date)
                
                # Apply score threshold if specified
                news_filter_pass = news_data['meets_min_news'] and news_data['meets_sentiment_range']
                if score_threshold is not None:
                    news_filter_pass = news_filter_pass and news_data['weighted_sentiment'] >= score_threshold
                
                # Final decision: Volume AND News filters
                passed_all_filters = volume_data['volume_filter_pass'] and news_filter_pass
                
                # Combine data
                stock_data = {
                    'ticker': ticker,
                    'date': analysis_date,
                    **volume_data,
                    **news_data,
                    'score_threshold': score_threshold,
                    'passed_all_filters': passed_all_filters
                }
                
                # Add to results if passed
                if passed_all_filters:
                    qualified_stocks.append(stock_data)
                
                # Add to audit log
                audit_data.append(stock_data)
                
            except Exception as e:
                logging.error(f"Error screening {ticker}: {e}")
                continue
        
        # Save audit log
        self._save_audit_log(analysis_date, audit_data)
        
        # Sort by weighted sentiment (descending) - no top_k limit
        qualified_stocks.sort(key=lambda x: x['weighted_sentiment'], reverse=True)
        
        logging.info(f"Screened {len(stocks)} stocks, {len(qualified_stocks)} qualified")
        return qualified_stocks
    
    def _save_audit_log(self, analysis_date: str, audit_data: List[Dict]):
        """Save audit log with simplified schema"""
        audit_file = self.audit_dir / f"simplified_audit_{analysis_date}.csv"
        
        # Define simplified audit columns
        audit_columns = [
            'date', 'ticker',
            'volume_yesterday', 'volume_ma20', 'volume_zscore',
            'articles_count', 'sources_count', 'raw_sentiment', 'weighted_sentiment',
            'meets_min_news', 'meets_sentiment_range', 'score_threshold',
            'passed_all_filters'
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
