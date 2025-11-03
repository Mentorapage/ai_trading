#!/usr/bin/env python3
"""
TELEGRAM NOTIFICATION SYSTEM
=============================
Handles all Telegram messaging for the autonomous daily trader
with idempotency, retry logic, and structured reporting.
"""

import os
import time
import json
import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import requests
from dotenv import load_dotenv
import pytz

# Load environment variables
load_dotenv()

@dataclass
class StockDecision:
    """Represents a trading decision for a stock"""
    ticker: str
    decision: str  # 'keep_overnight', 'open_new', 'skip', 'close'
    reason: str
    sentiment_score: float
    article_count: int
    volume_vs_avg: Optional[float]
    current_price: float
    position_status: str
    constraints: List[str]

@dataclass
class IntradayEvent:
    """Represents an intraday trading event"""
    event_id: str  # Unique identifier to prevent duplicates
    ticker: str
    event_type: str  # 'entry', 'fill', 'stop_loss', 'take_profit', 'reject', 'cancel', 'error'
    details: Dict[str, Any]
    timestamp: datetime

@dataclass
class DayOutcome:
    """Represents end-of-day outcome for a stock"""
    ticker: str
    outcome: str  # 'never_opened', 'kept_overnight', 'closed'
    reason: str
    pnl: Optional[float]
    position_status: str
    sentiment_score: float

class TelegramNotifier:
    """Handles all Telegram notifications with idempotency and retry logic"""
    
    def __init__(self):
        """Initialize Telegram notifier"""
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        if not self.bot_token or not self.chat_id:
            raise ValueError("Missing Telegram credentials. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        
        self.et_tz = pytz.timezone('America/New_York')
        
        # State tracking for idempotency
        self.state_file = "telegram_state.json"
        self.state = self._load_state()
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Watchlist - the 14 stocks from simple_trader.py
        self.WATCHLIST = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA',  # Original 5
            'NVDA', 'META', 'NFLX', 'AMD', 'CRM',      # Additional 5
            'ADBE', 'PYPL', 'INTC', 'ORCL'             # Additional 4 (total 14)
        ]
        
        self.logger.info("Telegram Notifier initialized")
        self.logger.info(f"Watchlist: {self.WATCHLIST}")
    
    def _load_state(self) -> Dict:
        """Load state from file for idempotency"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.warning(f"Could not load state file: {e}")
        
        return {
            'sent_messages': {},
            'last_morning_date': None,
            'last_evening_date': None,
            'intraday_events': {}
        }
    
    def _save_state(self):
        """Save state to file"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Could not save state file: {e}")
    
    def _send_telegram_message(self, message: str, retry_count: int = 3) -> bool:
        """Send message to Telegram with retry logic"""
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
        # Split long messages if needed (Telegram limit is 4096 characters)
        if len(message) > 4000:
            parts = [message[i:i+4000] for i in range(0, len(message), 4000)]
            for i, part in enumerate(parts):
                if i > 0:
                    part = f"(continued {i+1}/{len(parts)})\n" + part
                if not self._send_single_message(url, part, retry_count):
                    return False
            return True
        else:
            return self._send_single_message(url, message, retry_count)
    
    def _send_single_message(self, url: str, message: str, retry_count: int) -> bool:
        """Send a single message with retry logic"""
        for attempt in range(retry_count):
            try:
                payload = {
                    'chat_id': self.chat_id,
                    'text': message,
                    'parse_mode': 'Markdown'
                }
                
                response = requests.post(url, json=payload, timeout=10)
                
                if response.status_code == 200:
                    return True
                elif response.status_code == 429:  # Rate limited
                    retry_after = response.json().get('parameters', {}).get('retry_after', 1)
                    self.logger.warning(f"Rate limited, waiting {retry_after} seconds")
                    time.sleep(retry_after)
                else:
                    self.logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                    
            except Exception as e:
                self.logger.error(f"Telegram send error (attempt {attempt + 1}): {e}")
                if attempt < retry_count - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
        
        return False
    
    def send_morning_decisions(self, decisions: List[StockDecision]) -> bool:
        """Send exactly 14 morning decision messages (one per stock)"""
        today_str = datetime.now(self.et_tz).strftime('%Y-%m-%d')
        
        # Check if already sent today
        if self.state.get('last_morning_date') == today_str:
            self.logger.info("Morning messages already sent today")
            return True
        
        success_count = 0
        
        # Ensure we have decisions for all 14 stocks
        decision_dict = {d.ticker: d for d in decisions}
        
        for ticker in self.WATCHLIST:
            decision = decision_dict.get(ticker)
            
            if not decision:
                # Create default decision if missing
                decision = StockDecision(
                    ticker=ticker,
                    decision='skip',
                    reason='No analysis available',
                    sentiment_score=0.0,
                    article_count=0,
                    volume_vs_avg=None,
                    current_price=0.0,
                    position_status='no_position',
                    constraints=['analysis_failed']
                )
            
            message = self._format_morning_message(decision, today_str)
            
            if self._send_telegram_message(message):
                success_count += 1
                self.logger.info(f"Sent morning decision for {ticker}")
            else:
                self.logger.error(f"Failed to send morning decision for {ticker}")
        
        if success_count == 14:
            self.state['last_morning_date'] = today_str
            self._save_state()
            self.logger.info("All 14 morning messages sent successfully")
            return True
        else:
            self.logger.error(f"Only sent {success_count}/14 morning messages")
            return False
    
    def _format_morning_message(self, decision: StockDecision, date_str: str) -> str:
        """Format morning decision message for a single stock"""
        # Header with phase and date
        header = f"🌅 **OPEN** - {date_str}\n"
        header += f"**{decision.ticker}**\n\n"
        
        # Decision
        decision_emoji = {
            'keep_overnight': '🔄',
            'open_new': '🟢',
            'skip': '⏸️',
            'close': '🔴'
        }.get(decision.decision, '❓')
        
        message = header
        message += f"{decision_emoji} **Decision:** {decision.decision.replace('_', ' ').title()}\n\n"
        
        # Why (plain English reasoning)
        message += f"**Why:** {decision.reason}\n\n"
        
        # Key indicators
        message += "**Key Indicators:**\n"
        message += f"• Sentiment: {decision.sentiment_score:.3f} ({decision.article_count} articles)\n"
        
        if decision.volume_vs_avg is not None:
            volume_status = "above" if decision.volume_vs_avg > 1.0 else "below"
            message += f"• Volume: {volume_status} 20-day avg ({decision.volume_vs_avg:.2f}x)\n"
        else:
            message += f"• Volume: data unavailable\n"
        
        message += f"• Price: ${decision.current_price:.2f}\n"
        message += f"• Position: {decision.position_status.replace('_', ' ')}\n"
        
        # Constraints if any
        if decision.constraints:
            message += f"• Constraints: {', '.join(decision.constraints)}\n"
        
        return message
    
    def send_intraday_event(self, event: IntradayEvent) -> bool:
        """Send intraday event notification (with deduplication)"""
        # Check if already sent this event
        if event.event_id in self.state.get('intraday_events', {}):
            self.logger.debug(f"Event {event.event_id} already sent")
            return True
        
        message = self._format_intraday_message(event)
        
        if self._send_telegram_message(message):
            # Mark as sent
            if 'intraday_events' not in self.state:
                self.state['intraday_events'] = {}
            self.state['intraday_events'][event.event_id] = event.timestamp.isoformat()
            self._save_state()
            
            self.logger.info(f"Sent intraday event: {event.event_type} for {event.ticker}")
            return True
        else:
            self.logger.error(f"Failed to send intraday event: {event.event_type} for {event.ticker}")
            return False
    
    def _format_intraday_message(self, event: IntradayEvent) -> str:
        """Format intraday event message"""
        timestamp = event.timestamp.strftime('%H:%M ET')
        
        # Event type emoji
        event_emojis = {
            'entry': '🟢',
            'fill': '✅',
            'stop_loss': '🛑',
            'take_profit': '🎯',
            'reject': '❌',
            'cancel': '🚫',
            'error': '⚠️'
        }
        
        emoji = event_emojis.get(event.event_type, '📊')
        
        message = f"📈 **INTRADAY** - {timestamp}\n"
        message += f"{emoji} **{event.ticker}** - {event.event_type.replace('_', ' ').title()}\n\n"
        
        # Event-specific details
        if event.event_type in ['entry', 'fill']:
            qty = event.details.get('qty', 0)
            price = event.details.get('price', 0.0)
            investment = event.details.get('investment', 0.0)
            sl_price = event.details.get('sl_price', 0.0)
            tp_price = event.details.get('tp_price', 0.0)
            order_id = event.details.get('order_id', 'N/A')
            message += f"• Quantity: {qty} shares\n"
            message += f"• Avg Fill Price: ${price:.2f}\n"
            message += f"• Investment: ${investment:,.0f}\n"
            message += f"• Stop Loss: ${sl_price:.2f} (-10%)\n"
            message += f"• Take Profit: ${tp_price:.2f} (+5%)\n"
            message += f"• Order ID: {order_id}\n"
            
        elif event.event_type in ['stop_loss', 'take_profit']:
            trigger_price = event.details.get('trigger_price', 0.0)
            pnl = event.details.get('pnl', 0.0)
            message += f"• Trigger Price: ${trigger_price:.2f}\n"
            message += f"• P&L: ${pnl:+,.0f}\n"
            
        elif event.event_type in ['reject', 'cancel', 'error']:
            reason = event.details.get('reason', 'Unknown')
            message += f"• Reason: {reason}\n"
        
        # Add reason/tag
        reason = event.details.get('reason', event.event_type.replace('_', ' '))
        message += f"\n**Reason:** {reason}"
        
        return message
    
    def send_evening_outcomes(self, outcomes: List[DayOutcome]) -> bool:
        """Send exactly 14 evening outcome messages (one per stock)"""
        today_str = datetime.now(self.et_tz).strftime('%Y-%m-%d')
        
        # Check if already sent today
        if self.state.get('last_evening_date') == today_str:
            self.logger.info("Evening messages already sent today")
            return True
        
        success_count = 0
        
        # Ensure we have outcomes for all 14 stocks
        outcome_dict = {o.ticker: o for o in outcomes}
        
        for ticker in self.WATCHLIST:
            outcome = outcome_dict.get(ticker)
            
            if not outcome:
                # Create default outcome if missing
                outcome = DayOutcome(
                    ticker=ticker,
                    outcome='never_opened',
                    reason='No trading activity',
                    pnl=None,
                    position_status='no_position',
                    sentiment_score=0.0
                )
            
            message = self._format_evening_message(outcome, today_str)
            
            if self._send_telegram_message(message):
                success_count += 1
                self.logger.info(f"Sent evening outcome for {ticker}")
            else:
                self.logger.error(f"Failed to send evening outcome for {ticker}")
        
        if success_count == 14:
            self.state['last_evening_date'] = today_str
            self._save_state()
            self.logger.info("All 14 evening messages sent successfully")
            return True
        else:
            self.logger.error(f"Only sent {success_count}/14 evening messages")
            return False
    
    def _format_evening_message(self, outcome: DayOutcome, date_str: str) -> str:
        """Format evening outcome message for a single stock"""
        # Header with phase and date
        header = f"🌆 **CLOSE** - {date_str}\n"
        header += f"**{outcome.ticker}**\n\n"
        
        # Outcome
        outcome_emoji = {
            'never_opened': '⏸️',
            'kept_overnight': '🌙',
            'closed': '🔚'
        }.get(outcome.outcome, '❓')
        
        message = header
        message += f"{outcome_emoji} **Outcome:** {outcome.outcome.replace('_', ' ').title()}\n\n"
        
        # Rationale
        message += f"**Rationale:** {outcome.reason}\n\n"
        
        # Key context
        message += "**Context:**\n"
        message += f"• Sentiment: {outcome.sentiment_score:.3f}\n"
        message += f"• Position: {outcome.position_status.replace('_', ' ')}\n"
        
        if outcome.pnl is not None:
            pnl_emoji = "📈" if outcome.pnl >= 0 else "📉"
            message += f"• Day P&L: {pnl_emoji} ${outcome.pnl:+,.0f}\n"
        
        return message
    
    def cleanup_old_events(self, days_to_keep: int = 7):
        """Clean up old intraday events to prevent state file bloat"""
        if 'intraday_events' not in self.state:
            return
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        events_to_remove = []
        for event_id, timestamp_str in self.state['intraday_events'].items():
            try:
                event_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                if event_time < cutoff_date:
                    events_to_remove.append(event_id)
            except:
                events_to_remove.append(event_id)  # Remove invalid entries
        
        for event_id in events_to_remove:
            del self.state['intraday_events'][event_id]
        
        if events_to_remove:
            self._save_state()
            self.logger.info(f"Cleaned up {len(events_to_remove)} old intraday events")
    
    def reset_daily_state(self):
        """Reset daily state (for testing or manual reset)"""
        today_str = datetime.now(self.et_tz).strftime('%Y-%m-%d')
        
        # Only reset if it's a new day
        if (self.state.get('last_morning_date') != today_str or 
            self.state.get('last_evening_date') != today_str):
            
            self.state['last_morning_date'] = None
            self.state['last_evening_date'] = None
            self.state['intraday_events'] = {}
            self._save_state()
            self.logger.info("Daily state reset")
    
    def get_status(self) -> Dict:
        """Get current notification status"""
        today_str = datetime.now(self.et_tz).strftime('%Y-%m-%d')
        
        return {
            'morning_sent': self.state.get('last_morning_date') == today_str,
            'evening_sent': self.state.get('last_evening_date') == today_str,
            'intraday_events_today': len([
                event_id for event_id, timestamp_str in self.state.get('intraday_events', {}).items()
                if timestamp_str.startswith(today_str)
            ]),
            'watchlist_size': len(self.WATCHLIST),
            'telegram_configured': bool(self.bot_token and self.chat_id)
        }

def main():
    """Test the Telegram notifier"""
    try:
        notifier = TelegramNotifier()
        
        # Test message
        test_message = f"🤖 Telegram Notifier Test\n\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nStatus: Ready for autonomous trading"
        
        if notifier._send_telegram_message(test_message):
            print("✅ Telegram test message sent successfully")
            print(f"Status: {notifier.get_status()}")
        else:
            print("❌ Failed to send test message")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()

