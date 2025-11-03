#!/usr/bin/env python3
"""
DECISION ENGINE WITH HARD GATES
===============================
Enforces strict gating for trading decisions:
- Articles >= 2 required for any OPEN decision
- Volume vs 20-DMA must be computed and available
- All missing data results in SKIP
"""

import logging
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict, Any
import pytz
from dataclasses import dataclass

@dataclass
class TradingGates:
    """Hard gates that must pass for any OPEN decision"""
    has_sufficient_articles: bool = False
    articles_count: int = 0
    sentiment_in_range: bool = False
    sentiment_score: float = 0.0
    volume_data_available: bool = False
    volume_vs_avg: Optional[float] = None
    volume_above_avg: bool = False
    current_price: float = 0.0
    no_existing_position: bool = False
    under_position_limit: bool = False
    
    def all_gates_pass(self) -> bool:
        """Check if all required gates pass for OPEN decision"""
        return (
            self.has_sufficient_articles and
            self.sentiment_in_range and
            self.volume_data_available and
            self.volume_above_avg and
            self.no_existing_position and
            self.under_position_limit
        )
    
    def get_failure_reasons(self) -> list:
        """Get list of failed gate reasons"""
        reasons = []
        if not self.has_sufficient_articles:
            reasons.append(f"insufficient articles ({self.articles_count} < 2)")
        if not self.sentiment_in_range:
            reasons.append(f"sentiment below 0.1 ({self.sentiment_score:.3f})")
        if not self.volume_data_available:
            reasons.append("volume data unavailable")
        elif not self.volume_above_avg:
            reasons.append(f"volume below 20-DMA ({self.volume_vs_avg:.2f}x)")
        if not self.no_existing_position:
            reasons.append("already have position")
        if not self.under_position_limit:
            reasons.append("max positions reached")
        return reasons

class DecisionEngine:
    """Enforces hard gates for trading decisions"""
    
    def __init__(self, trader, sentiment_analyzer=None):
        self.trader = trader
        self.sentiment_analyzer = sentiment_analyzer
        self.et_tz = pytz.timezone('America/New_York')
        self.logger = logging.getLogger(__name__)
        
        # Hard gate parameters
        self.MIN_ARTICLES = 2
        self.SENTIMENT_MIN = 0.1  # On -1 to +1 scale (slightly positive)
        self.SENTIMENT_MAX = 1.0
        
        # API key rotation state
        self.current_key_index = 0  # Track which Finnhub key to use next
    
    def get_sentiment_data(self, ticker: str, date_str: str) -> Tuple[int, float]:
        """Get sentiment data with REAL NLTK VADER sentiment analysis and API key rotation"""
        try:
            import os
            import requests
            from datetime import datetime, timedelta
            import pytz
            from nltk.sentiment import SentimentIntensityAnalyzer
            import nltk
            
            # Download VADER lexicon if not already present
            try:
                nltk.data.find('sentiment/vader_lexicon.zip')
            except LookupError:
                self.logger.info("Downloading VADER lexicon for sentiment analysis...")
                nltk.download('vader_lexicon', quiet=True)
            
            # Initialize VADER sentiment analyzer
            sia = SentimentIntensityAnalyzer()
            
            # Get Finnhub API keys from environment
            finnhub_keys = os.getenv('FINNHUB_KEYS', '').split(',')
            finnhub_keys = [key.strip() for key in finnhub_keys if key.strip()]  # Clean and filter empty keys
            
            if not finnhub_keys:
                self.logger.error(f"No Finnhub API keys configured for {ticker}")
                return 0, 0.0
            
            # Calculate 24-hour news window (use date format YYYY-MM-DD)
            et_tz = pytz.timezone('America/New_York')
            today = datetime.now(et_tz)
            
            # Use yesterday and today dates in YYYY-MM-DD format
            yesterday = today - timedelta(days=1)
            from_date = yesterday.strftime('%Y-%m-%d')
            to_date = today.strftime('%Y-%m-%d')
            
            # Fetch news from Finnhub with API key rotation
            url = f"https://finnhub.io/api/v1/company-news"
            
            # Try all available API keys (round-robin rotation)
            num_keys = len(finnhub_keys)
            for attempt in range(num_keys):
                # Get current key using round-robin
                api_key = finnhub_keys[self.current_key_index]
                key_number = self.current_key_index + 1
                
                self.logger.debug(f"Trying Finnhub API key #{key_number}/{num_keys} for {ticker}")
                
                params = {
                    'symbol': ticker,
                    'from': from_date,
                    'to': to_date,
                    'token': api_key
                }
                
                try:
                    response = requests.get(url, params=params, timeout=10)
                    
                    if response.status_code == 200:
                        # SUCCESS! Process the articles
                        articles = response.json()
                        
                        self.logger.info(f"✅ Finnhub API key #{key_number} SUCCESS for {ticker}")
                        
                        if not articles or len(articles) == 0:
                            self.logger.info(f"No news articles found for {ticker} in 24h window")
                            return 0, 0.0
                        
                        article_count = len(articles)
                        
                        # REAL SENTIMENT ANALYSIS using NLTK VADER
                        sentiment_scores = []
                        for article in articles:
                            # Analyze headline and summary
                            headline = article.get('headline', '')
                            summary = article.get('summary', '')
                            
                            # Combine headline and summary (headline weighted more heavily)
                            text = f"{headline} {headline} {summary}"  # Headline counted twice for more weight
                            
                            if text.strip():
                                # Get compound sentiment score (-1 to +1)
                                sentiment = sia.polarity_scores(text)
                                compound_score = sentiment['compound']
                                sentiment_scores.append(compound_score)
                                
                                self.logger.debug(f"{ticker} article sentiment: {compound_score:.3f} - {headline[:50]}...")
                        
                        # Calculate average sentiment
                        if sentiment_scores:
                            # Average compound score (-1 to +1)
                            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
                            
                            # Return RAW compound score (no normalization)
                            # -1.0 = very negative, 0.0 = neutral, +1.0 = very positive
                            
                            self.logger.info(f"REAL SENTIMENT for {ticker}: {article_count} articles, "
                                           f"compound: {avg_sentiment:.3f} (using key #{key_number})")
                            
                            return article_count, avg_sentiment
                        else:
                            self.logger.warning(f"No valid text in articles for {ticker}")
                            return article_count, 0.0
                    
                    elif response.status_code == 429:
                        # RATE LIMITED - Try next key
                        self.logger.warning(f"⚠️ Finnhub API key #{key_number} RATE LIMITED for {ticker}")
                        # Move to next key for next attempt
                        self.current_key_index = (self.current_key_index + 1) % num_keys
                        continue
                    
                    elif response.status_code in [401, 403]:
                        # UNAUTHORIZED/FORBIDDEN - Key is invalid, try next
                        self.logger.error(f"❌ Finnhub API key #{key_number} INVALID/EXPIRED for {ticker}")
                        # Move to next key for next attempt
                        self.current_key_index = (self.current_key_index + 1) % num_keys
                        continue
                    
                    else:
                        # OTHER ERROR - Try next key
                        self.logger.error(f"❌ Finnhub API key #{key_number} error {response.status_code} for {ticker}")
                        # Move to next key for next attempt
                        self.current_key_index = (self.current_key_index + 1) % num_keys
                        continue
                
                except requests.Timeout:
                    self.logger.warning(f"⏱️ Finnhub API key #{key_number} TIMEOUT for {ticker}")
                    # Move to next key for next attempt
                    self.current_key_index = (self.current_key_index + 1) % num_keys
                    continue
                
                except Exception as e:
                    self.logger.error(f"❌ Finnhub API key #{key_number} exception for {ticker}: {e}")
                    # Move to next key for next attempt
                    self.current_key_index = (self.current_key_index + 1) % num_keys
                    continue
            
            # If we get here, ALL keys failed
            self.logger.error(f"🚨 ALL {num_keys} Finnhub API keys FAILED for {ticker}")
            return 0, 0.0
            
        except Exception as e:
            self.logger.error(f"Critical error getting sentiment for {ticker}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return 0, 0.0
    
    def get_volume_data(self, ticker: str) -> Tuple[bool, Optional[float]]:
        """Get volume vs 20-day average with proper error handling"""
        try:
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame
            from datetime import datetime, timedelta
            import os
            
            # Use Alpaca for volume data
            api_key = os.getenv("apikey")
            secret_key = os.getenv("apisecret")
            
            if not api_key or not secret_key:
                self.logger.error(f"No Alpaca API credentials for volume data")
                return False, None
            
            # Initialize Alpaca data client
            data_client = StockHistoricalDataClient(api_key, secret_key)
            
            # Get last 25 trading days (to calculate 20-day MA)
            end_date = datetime.now(self.et_tz).date()
            start_date = end_date - timedelta(days=35)  # Extra days for weekends/holidays
            
            # Request daily bars
            request = StockBarsRequest(
                symbol_or_symbols=[ticker],
                timeframe=TimeFrame.Day,
                start=start_date,
                end=end_date
            )
            
            bars = data_client.get_stock_bars(request)
            
            if ticker in bars.df.index.get_level_values('symbol'):
                ticker_data = bars.df.xs(ticker, level='symbol')
                
                if len(ticker_data) >= 20:
                    # Calculate 20-day volume average (excluding today)
                    volumes = ticker_data['volume'].iloc[-21:-1]  # Last 20 days excluding today
                    vol_20dma = volumes.mean()
                    
                    # Get today's volume (if available)
                    today_volume = ticker_data['volume'].iloc[-1] if len(ticker_data) > 20 else None
                    
                    if today_volume and vol_20dma:
                        volume_ratio = today_volume / vol_20dma
                        self.logger.info(f"{ticker} volume: today={today_volume:,.0f}, 20DMA={vol_20dma:,.0f}, ratio={volume_ratio:.2f}")
                        return True, volume_ratio
                    else:
                        self.logger.warning(f"Insufficient volume data for {ticker}")
                        return False, None
                else:
                    self.logger.warning(f"Not enough historical data for {ticker} (need 20 days, got {len(ticker_data)})")
                    return False, None
            else:
                self.logger.error(f"No volume data found for {ticker}")
                return False, None
            
        except Exception as e:
            self.logger.error(f"Error getting volume data for {ticker}: {e}")
            return False, None
    
    def evaluate_gates(self, ticker: str, current_positions: list) -> TradingGates:
        """Evaluate all trading gates for a ticker"""
        gates = TradingGates()
        
        # Get current price (for context only, not gating)
        gates.current_price = self.trader.get_current_price(ticker) or 0.0
        
        # Gate 1: Position checks
        gates.no_existing_position = not any(pos.symbol == ticker for pos in current_positions)
        gates.under_position_limit = len(current_positions) < self.trader.max_positions
        
        # Gate 2: Sentiment analysis (articles >= 2, sentiment >= 0.1 on -1 to +1 scale)
        today_str = datetime.now(self.et_tz).strftime('%Y-%m-%d')
        gates.articles_count, gates.sentiment_score = self.get_sentiment_data(ticker, today_str)
        gates.has_sufficient_articles = gates.articles_count >= self.MIN_ARTICLES
        gates.sentiment_in_range = self.SENTIMENT_MIN <= gates.sentiment_score <= self.SENTIMENT_MAX
        
        # Gate 3: Volume analysis
        gates.volume_data_available, gates.volume_vs_avg = self.get_volume_data(ticker)
        if gates.volume_data_available and gates.volume_vs_avg:
            gates.volume_above_avg = gates.volume_vs_avg > 1.0
        
        return gates
    
    def make_decision(self, ticker: str, current_positions: list) -> Tuple[str, str, TradingGates]:
        """Make trading decision with hard gates enforcement"""
        gates = self.evaluate_gates(ticker, current_positions)
        
        # Check if already have position
        if not gates.no_existing_position:
            return 'keep_overnight', 'Already in position, will reassess at close', gates
        
        # Apply hard gates for OPEN decision
        if gates.all_gates_pass():
            return 'open_new', f'All gates passed: {gates.articles_count} articles, sentiment {gates.sentiment_score:.3f}, volume {gates.volume_vs_avg:.2f}x avg', gates
        else:
            # Build detailed failure reason
            failure_reasons = gates.get_failure_reasons()
            reason = f"Gates failed: {', '.join(failure_reasons)}"
            return 'skip', reason, gates
    
    def execute_decision(self, ticker: str, decision: str, gates: TradingGates) -> Tuple[bool, str, Optional[str]]:
        """Execute the trading decision and return success, message, order_id"""
        if decision != 'open_new':
            return True, f"No action required for {decision}", None
        
        # Double-check gates before execution
        if not gates.all_gates_pass():
            return False, f"Gates failed at execution: {', '.join(gates.get_failure_reasons())}", None
        
        try:
            # Calculate position size and shares
            shares = self.trader.calculate_shares(ticker, self.trader.position_size)
            if shares == 0:
                return False, "Cannot calculate shares", None
            
            # Execute buy order using existing trader logic
            success = self.trader.place_buy_order(ticker)
            
            if success:
                # Get the order ID from the trader's active positions
                order_id = self.trader.active_positions.get(ticker, {}).get('order_id', 'UNKNOWN')
                return True, f"Order placed: {shares} shares @ ${gates.current_price:.2f}", str(order_id)
            else:
                return False, "Order placement failed", None
                
        except Exception as e:
            self.logger.error(f"Error executing order for {ticker}: {e}")
            return False, f"Execution error: {str(e)[:50]}...", None

def main():
    """Test the decision engine"""
    from simple_trader import SimpleTrader
    
    trader = SimpleTrader()
    engine = DecisionEngine(trader)
    
    # Test gates for a sample ticker
    ticker = 'AAPL'
    current_positions = trader.trading_client.get_all_positions()
    
    gates = engine.evaluate_gates(ticker, current_positions)
    decision, reason, _ = engine.make_decision(ticker, current_positions)
    
    print(f"Ticker: {ticker}")
    print(f"Decision: {decision}")
    print(f"Reason: {reason}")
    print(f"Gates: {gates}")

if __name__ == "__main__":
    main()
