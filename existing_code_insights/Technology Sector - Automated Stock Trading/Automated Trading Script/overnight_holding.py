#!/usr/bin/env python3
"""
SENTIMENT-RANGE OVERNIGHT HOLDING MODULE
=======================================
Implements sentiment-range rules for overnight position holding
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple
import pytz

# Import existing modules
from config_loader import config
from real_sentiment_analyzer import RealSentimentAnalyzer
from finnhub_api_pool import get_finnhub_pool

class OvernightHoldingManager:
    """Manages sentiment-range overnight holding decisions"""
    
    def __init__(self):
        """Initialize the overnight holding manager"""
        self.config = config
        self.sentiment_analyzer = RealSentimentAnalyzer()
        self.finnhub_pool = get_finnhub_pool()
        self.et_tz = pytz.timezone('America/New_York')
        
        # Load configuration
        self.enabled = self.config.get('strategy.overnight_holding.enabled', True)
        self.sentiment_min = self.config.get('strategy.overnight_holding.sentiment_range_min', 0.2)
        self.sentiment_max = self.config.get('strategy.overnight_holding.sentiment_range_max', 0.6)
        self.lookback_hours = self.config.get('strategy.overnight_holding.lookback_hours', 24)
        
        logging.info(f"Overnight holding initialized: enabled={self.enabled}, "
                    f"range=[{self.sentiment_min}, {self.sentiment_max}], "
                    f"lookback={self.lookback_hours}h")
    
    def get_sentiment_for_holding_decision(self, ticker: str, check_time: datetime) -> Optional[float]:
        """
        Get sentiment score for overnight holding decision
        
        Args:
            ticker: Stock ticker symbol
            check_time: Time to check sentiment (end of lookback window)
            
        Returns:
            Sentiment score or None if no news available
        """
        try:
            # Calculate lookback window
            window_start = check_time - timedelta(hours=self.lookback_hours)
            
            # Convert to date strings for API
            from_date = window_start.strftime('%Y-%m-%d')
            to_date = check_time.strftime('%Y-%m-%d')
            
            # Fetch news articles
            articles = self.finnhub_pool.get_company_news(ticker, from_date, to_date)
            
            if not articles:
                logging.debug(f"No news found for {ticker} in {self.lookback_hours}h window")
                return None
            
            # Filter articles within the exact time window
            window_start_timestamp = window_start.timestamp()
            check_time_timestamp = check_time.timestamp()
            
            valid_articles = []
            for article in articles:
                article_time = article.get('datetime', 0)
                if window_start_timestamp <= article_time <= check_time_timestamp:
                    valid_articles.append(article)
            
            if not valid_articles:
                logging.debug(f"No articles in exact time window for {ticker}")
                return None
            
            # Calculate weighted sentiment
            total_weighted_sentiment = 0.0
            total_weight = 0.0
            
            for article in valid_articles:
                sentiment_data = self.sentiment_analyzer._analyze_article_sentiment(article)
                source_weight = self.sentiment_analyzer._get_source_weight(article.get('url', ''))
                
                weighted_contribution = sentiment_data['sentiment_score'] * source_weight
                total_weighted_sentiment += weighted_contribution
                total_weight += source_weight
            
            if total_weight == 0:
                return None
            
            final_sentiment = total_weighted_sentiment / total_weight
            
            logging.debug(f"{ticker} sentiment for holding decision: {final_sentiment:.4f} "
                         f"({len(valid_articles)} articles)")
            
            return final_sentiment
            
        except Exception as e:
            logging.error(f"Error getting sentiment for {ticker}: {e}")
            return None
    
    def should_hold_overnight_eod(self, ticker: str, check_time: datetime) -> bool:
        """
        End-of-day holding decision for existing position
        
        Args:
            ticker: Stock ticker symbol
            check_time: End-of-day check time (post-close)
            
        Returns:
            True if should HOLD overnight, False if should SELL MOC
        """
        if not self.enabled:
            return False  # Default to selling if overnight holding disabled
        
        sentiment = self.get_sentiment_for_holding_decision(ticker, check_time)
        
        # No-news rule: if no news, HOLD
        if sentiment is None:
            logging.info(f"EOD {ticker}: No news -> HOLD overnight")
            return True
        
        # Sentiment range rule
        in_range = self.sentiment_min <= sentiment <= self.sentiment_max
        
        if in_range:
            logging.info(f"EOD {ticker}: Sentiment {sentiment:.4f} in range [{self.sentiment_min}, {self.sentiment_max}] -> HOLD overnight")
            return True
        else:
            logging.info(f"EOD {ticker}: Sentiment {sentiment:.4f} outside range [{self.sentiment_min}, {self.sentiment_max}] -> SELL MOC")
            return False
    
    def should_hold_overnight_morning(self, ticker: str, check_time: datetime) -> bool:
        """
        Morning holding decision for existing position
        
        Args:
            ticker: Stock ticker symbol
            check_time: Morning check time (pre-open/at-open)
            
        Returns:
            True if should HOLD, False if should SELL at open
        """
        if not self.enabled:
            return False  # Default to selling if overnight holding disabled
        
        sentiment = self.get_sentiment_for_holding_decision(ticker, check_time)
        
        # No-news rule: if no news, HOLD
        if sentiment is None:
            logging.info(f"Morning {ticker}: No news -> HOLD")
            return True
        
        # Sentiment range rule
        in_range = self.sentiment_min <= sentiment <= self.sentiment_max
        
        if in_range:
            logging.info(f"Morning {ticker}: Sentiment {sentiment:.4f} in range [{self.sentiment_min}, {self.sentiment_max}] -> HOLD")
            return True
        else:
            logging.info(f"Morning {ticker}: Sentiment {sentiment:.4f} outside range [{self.sentiment_min}, {self.sentiment_max}] -> SELL at open")
            return False
    
    def should_buy_morning(self, ticker: str, check_time: datetime) -> bool:
        """
        Morning buy decision for new position
        
        Args:
            ticker: Stock ticker symbol
            check_time: Morning check time (pre-open/at-open)
            
        Returns:
            True if should BUY at open, False if NO TRADE
        """
        if not self.enabled:
            return False  # Use existing logic if overnight holding disabled
        
        sentiment = self.get_sentiment_for_holding_decision(ticker, check_time)
        
        # No-news rule: if no news, NO TRADE
        if sentiment is None:
            logging.info(f"Morning {ticker}: No news -> NO TRADE")
            return False
        
        # Sentiment range rule
        in_range = self.sentiment_min <= sentiment <= self.sentiment_max
        
        if in_range:
            logging.info(f"Morning {ticker}: Sentiment {sentiment:.4f} in range [{self.sentiment_min}, {self.sentiment_max}] -> BUY at open")
            return True
        else:
            logging.info(f"Morning {ticker}: Sentiment {sentiment:.4f} outside range [{self.sentiment_min}, {self.sentiment_max}] -> NO TRADE")
            return False

# Global instance
_overnight_manager = None

def get_overnight_manager() -> OvernightHoldingManager:
    """Get the global overnight holding manager instance"""
    global _overnight_manager
    if _overnight_manager is None:
        _overnight_manager = OvernightHoldingManager()
    return _overnight_manager

