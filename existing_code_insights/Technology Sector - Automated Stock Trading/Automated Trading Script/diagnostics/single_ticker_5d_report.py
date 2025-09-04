#!/usr/bin/env python3
"""
Single Ticker 5-Day Diagnostic Report
Creates comprehensive Excel report with all signals for one ticker over last 5 trading days
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time as dt_time
import pytz
from pathlib import Path
import pandas_market_calendars as mcal
from dotenv import load_dotenv

# Add parent directory to path to import existing modules
sys.path.append(str(Path(__file__).parent.parent))

# Import existing modules (no modifications)
from finnhub_api_pool import get_finnhub_pool
from real_sentiment_analyzer import RealSentimentAnalyzer
from historical_backtest import get_historical_data
from trading_core import load_stock_universe
import bootstrap_nltk  # noqa

# Load environment
load_dotenv()

class SingleTickerReporter:
    def __init__(self):
        self.et_tz = pytz.timezone('America/New_York')
        self.finnhub_pool = get_finnhub_pool()
        self.sentiment_analyzer = RealSentimentAnalyzer()
        
    def get_last_5_trading_days(self):
        """Get last 5 NYSE trading days"""
        nyse = mcal.get_calendar('NYSE')
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)  # Look back 30 days to find 5 trading days
        
        trading_days = nyse.valid_days(start_date=start_date, end_date=end_date)
        
        # Get last 5 trading days
        last_5_days = trading_days[-5:].date
        return [day.date() if hasattr(day, 'date') else day for day in last_5_days]
    
    def calculate_ma20_and_slope(self, ticker: str, current_date: datetime.date):
        """Calculate MA20 and slope using data strictly prior to current_date"""
        try:
            # Get 30 days of data prior to current_date to ensure we have enough for MA20
            end_date = current_date - timedelta(days=1)  # Yesterday
            start_date = end_date - timedelta(days=40)   # Go back further to ensure 20+ trading days
            
            # Get daily data from Alpaca
            daily_data = get_historical_data(
                ticker=ticker,
                start_date=datetime.combine(start_date, dt_time(9, 30)),
                end_date=datetime.combine(end_date, dt_time(16, 0)),
                timeframe='1Day'
            )
            
            if len(daily_data) < 20:
                return None, None, None
            
            # Calculate MA20
            daily_data['ma20'] = daily_data['close'].rolling(window=20).mean()
            
            # Get yesterday's values
            yesterday_close = daily_data['close'].iloc[-1]
            ma20_close = daily_data['ma20'].iloc[-1]
            
            # Calculate slope (MA20 today vs MA20 yesterday)
            if len(daily_data) >= 21:
                ma20_slope_pos = daily_data['ma20'].iloc[-1] > daily_data['ma20'].iloc[-2]
            else:
                ma20_slope_pos = False
                
            return yesterday_close, ma20_close, ma20_slope_pos
            
        except Exception as e:
            print(f"Error calculating MA20 for {ticker}: {e}")
            return None, None, None
    
    def calculate_volume_metrics(self, ticker: str, current_date: datetime.date):
        """Calculate volume z-score and ATR"""
        try:
            # Get 30 days of data for volume analysis
            end_date = current_date - timedelta(days=1)  # Yesterday
            start_date = end_date - timedelta(days=40)
            
            daily_data = get_historical_data(
                ticker=ticker,
                start_date=datetime.combine(start_date, dt_time(9, 30)),
                end_date=datetime.combine(end_date, dt_time(16, 0)),
                timeframe='1Day'
            )
            
            if len(daily_data) < 20:
                return None, None, None, None
            
            # Volume metrics
            volume_yesterday = daily_data['volume'].iloc[-1]
            volume_ma20 = daily_data['volume'].rolling(window=20).mean().iloc[-1]
            volume_std20 = daily_data['volume'].rolling(window=20).std().iloc[-1]
            volume_zscore = (volume_yesterday - volume_ma20) / volume_std20 if volume_std20 > 0 else 0
            
            # ATR calculation
            daily_data['high_low'] = daily_data['high'] - daily_data['low']
            daily_data['high_close'] = abs(daily_data['high'] - daily_data['close'].shift(1))
            daily_data['low_close'] = abs(daily_data['low'] - daily_data['close'].shift(1))
            daily_data['true_range'] = daily_data[['high_low', 'high_close', 'low_close']].max(axis=1)
            
            if len(daily_data) >= 14:
                atr14 = daily_data['true_range'].rolling(window=14).mean().iloc[-1]
                atr14_pct = (atr14 / daily_data['close'].iloc[-1]) * 100 if daily_data['close'].iloc[-1] > 0 else 0
            else:
                atr14_pct = 0
                
            return volume_yesterday, volume_ma20, volume_zscore, atr14_pct
            
        except Exception as e:
            print(f"Error calculating volume metrics for {ticker}: {e}")
            return None, None, None, None
    
    def get_sentiment_analysis(self, ticker: str, analysis_date: datetime.date):
        """Get sentiment analysis for a specific date"""
        try:
            # Screen stocks using existing sentiment analyzer
            qualified_stocks = self.sentiment_analyzer.screen_stocks_by_sentiment(
                stocks=[ticker],
                analysis_date=analysis_date.strftime('%Y-%m-%d'),
                min_news_count=2,
                score_threshold=0.35  # Use a standard threshold
            )
            
            if qualified_stocks:
                stock_data = qualified_stocks[0]
                return {
                    'articles_count': stock_data.get('news_count', 0),
                    'sources_count': stock_data.get('source_count', 0),
                    'raw_sentiment': stock_data.get('raw_sentiment', 0.0),
                    'weighted_sentiment': stock_data.get('sentiment', 0.0),
                    'meets_min_news': stock_data.get('meets_min_news', False),
                    'meets_sentiment_range': stock_data.get('sentiment', 0.0) >= 0.35,
                    'score_threshold': 0.35,
                    'passed_all_filters': stock_data.get('qualifies', False)
                }
            else:
                return {
                    'articles_count': 0,
                    'sources_count': 0,
                    'raw_sentiment': 0.0,
                    'weighted_sentiment': 0.0,
                    'meets_min_news': False,
                    'meets_sentiment_range': False,
                    'score_threshold': 0.35,
                    'passed_all_filters': False
                }
                
        except Exception as e:
            print(f"Error getting sentiment for {ticker}: {e}")
            return {
                'articles_count': 0,
                'sources_count': 0,
                'raw_sentiment': 0.0,
                'weighted_sentiment': 0.0,
                'meets_min_news': False,
                'meets_sentiment_range': False,
                'score_threshold': 0.35,
                'passed_all_filters': False
            }
    
    def get_intraday_data(self, ticker: str, trading_days: list):
        """Get 30-minute intraday data for all trading days"""
        intraday_data = []
        
        for day in trading_days:
            try:
                # Get minute bars for the day
                start_datetime = datetime.combine(day, dt_time(9, 30))
                end_datetime = datetime.combine(day, dt_time(16, 0))
                
                minute_data = get_historical_data(
                    ticker=ticker,
                    start_date=start_datetime,
                    end_date=end_datetime,
                    timeframe='1Min'
                )
                
                if len(minute_data) == 0:
                    continue
                
                # Ensure timezone is ET
                if minute_data.index.tz is None:
                    minute_data.index = minute_data.index.tz_localize('America/New_York')
                elif minute_data.index.tz != self.et_tz:
                    minute_data.index = minute_data.index.tz_convert('America/New_York')
                
                # Filter to market hours (09:30-16:00 ET)
                market_start = minute_data.index.normalize() + pd.Timedelta(hours=9, minutes=30)
                market_end = minute_data.index.normalize() + pd.Timedelta(hours=16)
                
                market_data = minute_data[(minute_data.index >= market_start) & (minute_data.index <= market_end)]
                
                if len(market_data) == 0:
                    continue
                
                # Resample to 30-minute buckets
                thirty_min_data = market_data.resample('30Min').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum'
                }).dropna()
                
                # Add to results
                for timestamp, row in thirty_min_data.iterrows():
                    intraday_data.append({
                        'date': day.strftime('%Y-%m-%d'),
                        'timestamp_et': timestamp.strftime('%Y-%m-%d %H:%M:%S %Z'),
                        'ticker': ticker,
                        'open': row['open'],
                        'high': row['high'],
                        'low': row['low'],
                        'close': row['close'],
                        'volume': row['volume']
                    })
                    
            except Exception as e:
                print(f"Error getting intraday data for {ticker} on {day}: {e}")
                continue
        
        return intraday_data
    
    def generate_report(self, ticker: str):
        """Generate the complete Excel report"""
        print(f"Ticker chosen: {ticker}")
        
        # Get last 5 trading days
        trading_days = self.get_last_5_trading_days()
        print(f"Processed days: {', '.join([day.strftime('%Y-%m-%d') for day in trading_days])}")
        
        # Daily analysis data
        daily_data = []
        
        for day in trading_days:
            # Calculate technical indicators
            yesterday_close, ma20_close, ma20_slope_pos = self.calculate_ma20_and_slope(ticker, day)
            volume_yesterday, volume_ma20, volume_zscore, atr14_pct = self.calculate_volume_metrics(ticker, day)
            
            # Trend analysis
            trend_ok = False
            if yesterday_close is not None and ma20_close is not None and ma20_slope_pos is not None:
                trend_ok = yesterday_close > ma20_close and ma20_slope_pos
            
            # Sentiment analysis
            sentiment_data = self.get_sentiment_analysis(ticker, day)
            
            # Decision time (09:30 ET)
            decision_time_et = datetime.combine(day, dt_time(9, 30))
            decision_time_et = self.et_tz.localize(decision_time_et)
            
            daily_data.append({
                'date': day.strftime('%Y-%m-%d'),
                'decision_time_et': decision_time_et.strftime('%Y-%m-%d %H:%M:%S %Z'),
                'ticker': ticker,
                'yesterday_close': yesterday_close,
                'ma20_close': ma20_close,
                'ma20_slope_pos': ma20_slope_pos,
                'trend_ok': trend_ok,
                'volume_yesterday': volume_yesterday,
                'volume_ma20': volume_ma20,
                'volume_zscore': volume_zscore,
                'atr14_pct': atr14_pct,
                'articles_count': sentiment_data['articles_count'],
                'sources_count': sentiment_data['sources_count'],
                'raw_sentiment': sentiment_data['raw_sentiment'],
                'weighted_sentiment': sentiment_data['weighted_sentiment'],
                'meets_min_news': sentiment_data['meets_min_news'],
                'meets_sentiment_range': sentiment_data['meets_sentiment_range'],
                'score_threshold': sentiment_data['score_threshold'],
                'passed_all_filters': sentiment_data['passed_all_filters']
            })
        
        # Get intraday data
        intraday_data = self.get_intraday_data(ticker, trading_days)
        
        # Create Excel file
        output_file = f"single_stock_5d_report_{ticker}.xlsx"
        
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # Daily Analysis sheet
            daily_df = pd.DataFrame(daily_data)
            daily_df.to_excel(writer, sheet_name='Daily_Analysis', index=False)
            
            # Intraday 30min sheet
            intraday_df = pd.DataFrame(intraday_data)
            intraday_df.to_excel(writer, sheet_name='Intraday_30min', index=False)
        
        print(f"Wrote: {output_file}")
        return output_file

def main():
    """Main function"""
    try:
        # Load stock universe and get first ticker
        stocks = load_stock_universe()
        if not stocks:
            print("Error: No stocks found in universe")
            return
        
        ticker = stocks[0]  # First ticker from universe
        
        # Generate report
        reporter = SingleTickerReporter()
        output_file = reporter.generate_report(ticker)
        
        return output_file
        
    except Exception as e:
        print(f"Error generating report: {e}")
        return None

if __name__ == "__main__":
    main()
