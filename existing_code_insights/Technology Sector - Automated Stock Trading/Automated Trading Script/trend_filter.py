"""
TREND FILTER MODULE
===================
Implements 20-day moving average price trend filtering
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
import os
from dotenv import load_dotenv

# Load API credentials
load_dotenv(dotenv_path=".env")
api_key = os.getenv("apikey")
secret_key = os.getenv("apisecret")

# Initialize Alpaca historical data client
historical_client = StockHistoricalDataClient(api_key, secret_key)

def get_previous_trading_day(target_date: datetime) -> datetime:
    """
    Get the previous trading day before the target date
    
    Args:
        target_date (datetime): Target date
        
    Returns:
        datetime: Previous trading day
    """
    # Simple implementation - go back 1 day and skip weekends
    # In production, this should use market calendar
    prev_date = target_date - timedelta(days=1)
    
    # Skip weekends (Monday = 0, Sunday = 6)
    while prev_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
        prev_date -= timedelta(days=1)
    
    return prev_date

def get_trading_days_before(end_date: datetime, num_days: int) -> List[datetime]:
    """
    Get a list of trading days before the end date
    
    Args:
        end_date (datetime): End date (exclusive)
        num_days (int): Number of trading days to get
        
    Returns:
        List[datetime]: List of trading days in chronological order
    """
    trading_days = []
    current_date = end_date - timedelta(days=1)
    
    while len(trading_days) < num_days:
        # Skip weekends
        if current_date.weekday() < 5:  # Monday = 0, Friday = 4
            trading_days.append(current_date)
        current_date -= timedelta(days=1)
        
        # Safety check to avoid infinite loop
        if (end_date - current_date).days > 365:
            logging.warning(f"Could not find {num_days} trading days before {end_date}")
            break
    
    return list(reversed(trading_days))  # Return in chronological order

def fetch_daily_bars(symbol: str, start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
    """
    Fetch daily price bars for a symbol
    
    Args:
        symbol (str): Stock ticker
        start_date (datetime): Start date (inclusive)
        end_date (datetime): End date (exclusive)
        
    Returns:
        pd.DataFrame: Daily OHLCV data or None if error
    """
    try:
        # Add buffer to ensure we get enough data
        buffer_start = start_date - timedelta(days=10)
        
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=buffer_start,
            end=end_date
        )
        
        bars = historical_client.get_stock_bars(request)
        
        if not bars.data or symbol not in bars.data:
            logging.debug(f"No daily data available for {symbol}")
            return None
        
        bar_data = bars.data[symbol]
        if not bar_data:
            return None
        
        # Convert to DataFrame
        data_rows = []
        for bar in bar_data:
            data_rows.append({
                'timestamp': bar.timestamp.date(),  # Convert to date for daily data
                'open': float(bar.open),
                'high': float(bar.high),
                'low': float(bar.low),
                'close': float(bar.close),
                'volume': int(bar.volume)
            })
        
        df = pd.DataFrame(data_rows)
        if df.empty:
            return None
        
        # Set date as index
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)
        
        # Filter to requested date range
        start_date_only = start_date.date()
        end_date_only = end_date.date()
        df = df[(df.index >= start_date_only) & (df.index < end_date_only)]
        
        return df if not df.empty else None
        
    except Exception as e:
        logging.error(f"Error fetching daily bars for {symbol}: {e}")
        return None

def compute_moving_average(symbol: str, end_date: datetime, lookback_days: int) -> Tuple[Optional[float], Optional[float]]:
    """
    Compute moving average and yesterday's close for a symbol
    
    Args:
        symbol (str): Stock ticker
        end_date (datetime): Decision date (exclusive for MA calculation)
        lookback_days (int): Number of days for moving average
        
    Returns:
        Tuple[Optional[float], Optional[float]]: (yesterday_close, ma_value) or (None, None) if insufficient data
    """
    try:
        # Get yesterday (previous trading day)
        yesterday = get_previous_trading_day(end_date)
        
        # Get trading days for MA calculation (excluding end_date)
        ma_end_date = end_date  # MA calculation should not include current day
        ma_start_date = ma_end_date - timedelta(days=lookback_days * 2)  # Buffer for weekends
        
        # Fetch daily bars
        daily_data = fetch_daily_bars(symbol, ma_start_date, ma_end_date)
        
        if daily_data is None or len(daily_data) < lookback_days:
            logging.debug(f"Insufficient daily data for {symbol}: got {len(daily_data) if daily_data is not None else 0}, need {lookback_days}")
            return None, None
        
        # Get yesterday's close
        yesterday_date = yesterday.date()
        if yesterday_date not in daily_data.index:
            logging.debug(f"Yesterday's data ({yesterday_date}) not available for {symbol}")
            return None, None
        
        yesterday_close = daily_data.loc[yesterday_date, 'close']
        
        # Calculate MA using the last lookback_days closes (excluding current day)
        # Get the most recent lookback_days bars before end_date
        ma_data = daily_data.tail(lookback_days)
        
        if len(ma_data) < lookback_days:
            logging.debug(f"Insufficient data for MA calculation for {symbol}: got {len(ma_data)}, need {lookback_days}")
            return yesterday_close, None
        
        ma_value = ma_data['close'].mean()
        
        logging.debug(f"Trend data for {symbol}: yesterday_close={yesterday_close:.2f}, MA{lookback_days}={ma_value:.2f}")
        
        return yesterday_close, ma_value
        
    except Exception as e:
        logging.error(f"Error computing moving average for {symbol}: {e}")
        return None, None

def apply_trend_filter(symbols: List[str], decision_date: datetime, trend_config: Dict) -> Dict[str, bool]:
    """
    Apply trend filter to a list of symbols
    
    Args:
        symbols (List[str]): List of stock tickers
        decision_date (datetime): Date for trend analysis
        trend_config (Dict): Trend filter configuration
        
    Returns:
        Dict[str, bool]: Dictionary mapping symbol to pass/fail status
    """
    if not trend_config.get('enabled', False):
        # If trend filter is disabled, all symbols pass
        return {symbol: True for symbol in symbols}
    
    lookback_days = trend_config.get('lookback_days', 20)
    comparator = trend_config.get('comparator', 'yesterday_gt_ma')
    debug_enabled = trend_config.get('debug', False)
    
    results = {}
    
    for symbol in symbols:
        try:
            yesterday_close, ma_value = compute_moving_average(symbol, decision_date, lookback_days)
            
            if yesterday_close is None or ma_value is None:
                # Skip trend filter for this symbol due to insufficient data
                logging.warning(f"Trend filter skipped for {symbol}: insufficient data")
                results[symbol] = True
                continue
            
            # Apply comparator
            if comparator == 'yesterday_gt_ma':
                passed = yesterday_close > ma_value
            elif comparator == 'yesterday_ge_ma':
                passed = yesterday_close >= ma_value
            else:  # 'none' or invalid
                passed = True
            
            results[symbol] = passed
            
            # Debug logging
            if debug_enabled or logging.getLogger().isEnabledFor(logging.DEBUG):
                status = "PASS" if passed else "FAIL"
                logging.debug(f"trend_filter: {symbol} yday_close={yesterday_close:.2f}, ma{lookback_days}={ma_value:.2f}, "
                            f"comparator={comparator}, pass={status}")
            
        except Exception as e:
            logging.error(f"Error applying trend filter to {symbol}: {e}")
            # On error, allow the symbol to pass (conservative approach)
            results[symbol] = True
    
    # Summary logging
    passed_symbols = [s for s, passed in results.items() if passed]
    failed_symbols = [s for s, passed in results.items() if not passed]
    
    if trend_config.get('enabled', False):
        logging.info(f"Trend filter results: {len(passed_symbols)} passed, {len(failed_symbols)} failed")
        if failed_symbols:
            logging.info(f"Trend filter excluded: {failed_symbols}")
    
    return results

def validate_trend_filter_config(config: Dict) -> bool:
    """
    Validate trend filter configuration
    
    Args:
        config (Dict): Trend filter configuration
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not isinstance(config, dict):
        return False
    
    # Check required fields
    if 'enabled' in config and not isinstance(config['enabled'], bool):
        return False
    
    if 'lookback_days' in config:
        if not isinstance(config['lookback_days'], int) or config['lookback_days'] <= 0:
            return False
    
    if 'comparator' in config:
        valid_comparators = ['yesterday_gt_ma', 'yesterday_ge_ma', 'none']
        if config['comparator'] not in valid_comparators:
            return False
    
    return True

