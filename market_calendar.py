#!/usr/bin/env python3
"""
MARKET CALENDAR MODULE
======================
Handles NYSE market calendar with America/New_York timezone.
Determines market open/close times for any given date.
"""

import pytz
from datetime import datetime, date, time as dt_time
from typing import Tuple, Optional
import logging
from alpaca.trading.client import TradingClient
import os
from dotenv import load_dotenv

load_dotenv()

class MarketCalendar:
    """NYSE market calendar handler with EST/EDT timezone support"""
    
    def __init__(self):
        """Initialize market calendar"""
        self.et_tz = pytz.timezone('America/New_York')
        self.logger = logging.getLogger(__name__)
        
        # Initialize Alpaca client for calendar data
        api_key = os.getenv("apikey")
        secret_key = os.getenv("apisecret")
        
        if api_key and secret_key:
            self.trading_client = TradingClient(api_key, secret_key, paper=True)
        else:
            self.trading_client = None
            self.logger.warning("No Alpaca credentials - using fallback calendar")
    
    def is_market_day(self, target_date: date) -> bool:
        """Check if given date is a trading day"""
        try:
            if self.trading_client:
                calendar = self.trading_client.get_calendar()
                for session in calendar:
                    if session.date == target_date:
                        return True
                return False
            else:
                # Fallback: exclude weekends
                return target_date.weekday() < 5
                
        except Exception as e:
            self.logger.error(f"Error checking market day for {target_date}: {e}")
            # Fallback: exclude weekends
            return target_date.weekday() < 5
    
    def get_market_hours(self, target_date: date) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Get market open and close times for a given date in EST/EDT"""
        try:
            if self.trading_client:
                calendar = self.trading_client.get_calendar()
                for session in calendar:
                    if session.date == target_date:
                        # Convert to EST/EDT timezone
                        market_open = datetime.combine(target_date, session.open.time()).replace(tzinfo=self.et_tz)
                        market_close = datetime.combine(target_date, session.close.time()).replace(tzinfo=self.et_tz)
                        return market_open, market_close
                
                return None, None
            else:
                # Fallback: standard market hours
                if target_date.weekday() < 5:  # Monday-Friday
                    market_open = datetime.combine(target_date, dt_time(9, 30)).replace(tzinfo=self.et_tz)
                    market_close = datetime.combine(target_date, dt_time(16, 0)).replace(tzinfo=self.et_tz)
                    return market_open, market_close
                else:
                    return None, None
                    
        except Exception as e:
            self.logger.error(f"Error getting market hours for {target_date}: {e}")
            return None, None
    
    def get_market_status(self, target_date: date) -> dict:
        """Get comprehensive market status for a date"""
        is_trading_day = self.is_market_day(target_date)
        market_open, market_close = self.get_market_hours(target_date)
        
        status = {
            'date': target_date.isoformat(),
            'is_trading_day': is_trading_day,
            'market_open': market_open.isoformat() if market_open else None,
            'market_close': market_close.isoformat() if market_close else None,
            'timezone': 'America/New_York'
        }
        
        if not is_trading_day:
            if target_date.weekday() == 5:  # Saturday
                status['reason'] = 'Weekend (Saturday)'
            elif target_date.weekday() == 6:  # Sunday
                status['reason'] = 'Weekend (Sunday)'
            else:
                status['reason'] = 'Market Holiday'
        
        return status
    
    def get_batch_windows(self, target_date: date) -> Tuple[Optional[datetime], Optional[datetime], Optional[datetime], Optional[datetime]]:
        """Get morning and evening batch windows for notifications"""
        market_open, market_close = self.get_market_hours(target_date)
        
        if not market_open or not market_close:
            return None, None, None, None
        
        # Morning batch: open + 0..5 minutes
        morning_start = market_open
        morning_end = market_open.replace(minute=market_open.minute + 5)
        
        # Evening batch: close - 5..0 minutes or close + 0..5 minutes
        evening_start = market_close.replace(minute=market_close.minute - 5)
        evening_end = market_close.replace(minute=market_close.minute + 5)
        
        return morning_start, morning_end, evening_start, evening_end
    
    def format_est_time(self, dt: datetime) -> str:
        """Format datetime as EST/EDT time string"""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=self.et_tz)
        elif dt.tzinfo != self.et_tz:
            dt = dt.astimezone(self.et_tz)
        
        return dt.strftime('%H:%M EST')
    
    def get_current_est_time(self) -> datetime:
        """Get current time in EST/EDT"""
        return datetime.now(self.et_tz)

def main():
    """Test the market calendar"""
    calendar = MarketCalendar()
    
    # Test with today
    today = date.today()
    status = calendar.get_market_status(today)
    
    print("Market Calendar Test")
    print("=" * 40)
    print(f"Date: {status['date']}")
    print(f"Trading Day: {status['is_trading_day']}")
    
    if status['is_trading_day']:
        print(f"Market Open: {status['market_open']}")
        print(f"Market Close: {status['market_close']}")
        
        # Test batch windows
        morning_start, morning_end, evening_start, evening_end = calendar.get_batch_windows(today)
        print(f"Morning Batch: {calendar.format_est_time(morning_start)} - {calendar.format_est_time(morning_end)}")
        print(f"Evening Batch: {calendar.format_est_time(evening_start)} - {calendar.format_est_time(evening_end)}")
    else:
        print(f"Reason: {status.get('reason', 'Unknown')}")
    
    print(f"Current EST Time: {calendar.format_est_time(calendar.get_current_est_time())}")

if __name__ == "__main__":
    main()

