#!/usr/bin/env python3
"""
AUTONOMOUS DAILY TRADER
=======================
Runs every market day without manual intervention:
- Morning: assess all 14 stocks and make decisions
- Intraday: monitor positions and report events
- Evening: decide overnight positions and summarize
- Repeat daily until manually stopped

Uses existing trading logic without inventing new strategies.
"""

import os
import sys
import time
import json
import logging
import signal
import threading
from datetime import datetime, timedelta, time as dt_time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import pytz
from dotenv import load_dotenv

# Import existing system components
from simple_trader import SimpleTrader
from balance_checker import BalanceChecker
from telegram_notifier import TelegramNotifier, StockDecision, IntradayEvent, DayOutcome

# Load environment variables
load_dotenv()

class AutonomousDailyTrader:
    """Autonomous trading system that runs daily market sessions"""
    
    def __init__(self):
        """Initialize the autonomous trader"""
        self.et_tz = pytz.timezone('America/New_York')
        
        # Initialize components
        self.trader = SimpleTrader()
        self.balance_checker = BalanceChecker()
        self.telegram = TelegramNotifier()
        
        # Control flags
        self.running = True
        self.stop_requested = False
        
        # State tracking
        self.state_file = "autonomous_trader_state.json"
        self.state = self._load_state()
        
        # Trading parameters from existing logic
        self.WATCHLIST = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA',  # Original 5
            'NVDA', 'META', 'NFLX', 'AMD', 'CRM',      # Additional 5
            'ADBE', 'PYPL', 'INTC', 'ORCL'             # Additional 4 (total 14)
        ]
        
        # Use existing logic parameters
        self.SENTIMENT_MIN = 0.1  # On -1 to +1 scale (slightly positive)
        self.SENTIMENT_MAX = 1.0  # Maximum positive sentiment
        self.MIN_ARTICLES = 2     # Minimum news articles required
        self.PRICE_MIN = 10.0     # From simple_trader.py
        self.PRICE_MAX = 500.0    # From simple_trader.py
        
        # Setup logging
        self._setup_logging()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info("Autonomous Daily Trader initialized")
        self.logger.info(f"Watchlist: {self.WATCHLIST}")
        
    def _setup_logging(self):
        """Setup comprehensive logging"""
        log_filename = f"logs/autonomous_trader_{datetime.now().strftime('%Y%m%d')}.log"
        os.makedirs('logs', exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filename),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
    
    def _load_state(self) -> Dict:
        """Load persistent state"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logging.warning(f"Could not load state: {e}")
        
        return {
            'last_trading_date': None,
            'positions': {},
            'daily_stats': {},
            'phase': 'waiting'  # waiting, morning, intraday, evening
        }
    
    def _save_state(self):
        """Save persistent state"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Could not save state: {e}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.stop_requested = True
        self.running = False
    
    def is_market_day(self, date_obj: datetime) -> Tuple[bool, Optional[datetime], Optional[datetime]]:
        """Check if given date is a market day and get market hours"""
        try:
            # Get market calendar from Alpaca
            calendar = self.trader.trading_client.get_calendar()
            
            target_date = date_obj.date()
            
            for session in calendar:
                if session.date == target_date:
                    market_open = datetime.combine(target_date, session.open.time()).replace(tzinfo=self.et_tz)
                    market_close = datetime.combine(target_date, session.close.time()).replace(tzinfo=self.et_tz)
                    return True, market_open, market_close
            
            return False, None, None
            
        except Exception as e:
            self.logger.error(f"Error checking market calendar: {e}")
            return False, None, None
    
    def wait_for_market_open(self) -> Tuple[datetime, datetime]:
        """Wait for the next market open and return open/close times"""
        while self.running:
            now = datetime.now(self.et_tz)
            
            # Check today first
            is_market_day, market_open, market_close = self.is_market_day(now)
            
            if is_market_day and now < market_open:
                # Market opens today, wait for it
                wait_seconds = (market_open - now).total_seconds()
                self.logger.info(f"Market opens today at {market_open.strftime('%H:%M ET')} (in {wait_seconds/60:.0f} minutes)")
                
                # Wait in chunks to allow for shutdown
                while wait_seconds > 0 and self.running:
                    sleep_time = min(60, wait_seconds)  # Check every minute
                    time.sleep(sleep_time)
                    wait_seconds -= sleep_time
                
                return market_open, market_close
                
            elif is_market_day and market_open <= now <= market_close:
                # Market is already open today
                self.logger.info(f"Market is already open (closes at {market_close.strftime('%H:%M ET')})")
                return market_open, market_close
                
            else:
                # Find next market day
                # Send Telegram notification about market being closed
                today_date = now.strftime('%A, %B %d, %Y')
                self.logger.info(f"Today ({today_date}) is not a trading day")
                
                # Send notification to user
                try:
                    import requests
                    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
                    chat_id = os.getenv("TELEGRAM_CHAT_ID")
                    
                    if bot_token and chat_id:
                        message = (
                            f"📅 **Market Closed**\n\n"
                            f"Today is **{today_date}**\n"
                            f"The market is closed (weekend/holiday).\n\n"
                            f"🔍 Searching for next trading day...\n"
                            f"⏰ Bot is running and will automatically trade when market opens."
                        )
                        
                        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                        requests.post(url, json={'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown'}, timeout=10)
                        self.logger.info("Sent market closed notification to Telegram")
                except Exception as e:
                    self.logger.error(f"Failed to send market closed notification: {e}")
                
                next_day = now + timedelta(days=1)
                for i in range(7):  # Check next 7 days
                    check_date = next_day + timedelta(days=i)
                    is_next_market_day, next_open, next_close = self.is_market_day(check_date)
                    
                    if is_next_market_day:
                        wait_seconds = (next_open - now).total_seconds()
                        wait_hours = wait_seconds / 3600
                        self.logger.info(f"Next market day: {next_open.strftime('%Y-%m-%d %H:%M ET')} (in {wait_hours:.1f} hours)")
                        
                        # Send update with next trading day
                        try:
                            if bot_token and chat_id:
                                next_day_str = next_open.strftime('%A, %B %d at %I:%M %p %Z')
                                message = (
                                    f"📅 **Next Trading Day**\n\n"
                                    f"Market opens: **{next_day_str}**\n"
                                    f"⏰ Time until open: **{int(wait_hours)} hours {int((wait_hours % 1) * 60)} minutes**\n\n"
                                    f"✅ Bot will automatically send morning decisions when market opens.\n"
                                    f"💤 Sleeping until then..."
                                )
                                
                                requests.post(url, json={'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown'}, timeout=10)
                                self.logger.info("Sent next trading day notification to Telegram")
                        except Exception as e:
                            self.logger.error(f"Failed to send next trading day notification: {e}")
                        
                        # Wait in chunks
                        while wait_seconds > 0 and self.running:
                            sleep_time = min(300, wait_seconds)  # Check every 5 minutes
                            time.sleep(sleep_time)
                            wait_seconds -= sleep_time
                            
                            # Re-check in case of early close or schedule changes
                            now = datetime.now(self.et_tz)
                            wait_seconds = (next_open - now).total_seconds()
                        
                        return next_open, next_close
                
                # If we get here, no market days found in next 7 days
                self.logger.error("No market days found in next 7 days")
                time.sleep(3600)  # Wait 1 hour and try again
    
    def assess_stock_for_morning(self, ticker: str) -> StockDecision:
        """Assess a single stock for morning decision using hard gates"""
        try:
            # Get current positions
            current_positions = self.trader.trading_client.get_all_positions()
            
            # Use decision engine with hard gates
            from decision_engine import DecisionEngine
            engine = DecisionEngine(self.trader)
            
            decision, reason, gates = engine.make_decision(ticker, current_positions)
            
            # Determine position status
            has_position = not gates.no_existing_position
            position_status = 'has_position' if has_position else 'no_position'
            
            # Build constraints list
            constraints = []
            if not gates.all_gates_pass():
                constraints = gates.get_failure_reasons()
            
            return StockDecision(
                ticker=ticker,
                decision=decision,
                reason=reason,
                sentiment_score=gates.sentiment_score,
                article_count=gates.articles_count,
                volume_vs_avg=gates.volume_vs_avg,
                current_price=gates.current_price,
                position_status=position_status,
                constraints=constraints
            )
                
        except Exception as e:
            self.logger.error(f"Error assessing {ticker}: {e}")
            return StockDecision(
                ticker=ticker,
                decision='skip',
                reason=f'Assessment error: {str(e)[:50]}...',
                sentiment_score=0.0,
                article_count=0,
                volume_vs_avg=None,
                current_price=0.0,
                position_status='error',
                constraints=['assessment_error']
            )
    
    def execute_morning_routine(self) -> bool:
        """Execute morning routine: assess all stocks and send decisions"""
        try:
            self.logger.info("🌅 Starting morning routine")
            self.state['phase'] = 'morning'
            self._save_state()
            
            # Get account info for context
            account_info = self.balance_checker.get_account_balance()
            if account_info:
                self.logger.info(f"Account balance: ${account_info['portfolio_value']:,.2f}")
            
            # Assess all 14 stocks and execute orders
            decisions = []
            order_attempts = []
            
            for ticker in self.WATCHLIST:
                decision = self.assess_stock_for_morning(ticker)
                decisions.append(decision)
                self.logger.info(f"{ticker}: {decision.decision} - {decision.reason}")
                
                # Execute order if decision is OPEN
                if decision.decision == 'open_new':
                    from decision_engine import DecisionEngine
                    engine = DecisionEngine(self.trader)
                    current_positions = self.trader.trading_client.get_all_positions()
                    
                    # Re-evaluate gates at execution time
                    _, _, gates = engine.make_decision(ticker, current_positions)
                    success, message, order_id = engine.execute_decision(ticker, decision.decision, gates)
                    
                    order_attempt = {
                        'ticker': ticker,
                        'decision': decision.decision,
                        'success': success,
                        'message': message,
                        'order_id': order_id,
                        'timestamp': datetime.now(self.et_tz).isoformat()
                    }
                    order_attempts.append(order_attempt)
                    
                    if success and order_id:
                        # Get order details for SL/TP calculation
                        try:
                            # Get the filled order details
                            order = self.trader.trading_client.get_order_by_id(order_id)
                            fill_price = float(order.filled_avg_price) if order.filled_avg_price else gates.current_price
                            qty = int(order.filled_qty) if order.filled_qty else 0
                            investment = fill_price * qty
                            
                            # Calculate SL/TP levels
                            sl_price = fill_price * 0.90  # -10%
                            tp_price = fill_price * 1.05  # +5%
                            
                        except Exception as e:
                            self.logger.warning(f"Could not get order details for {ticker}: {e}")
                            fill_price = gates.current_price
                            qty = 0
                            investment = 0.0
                            sl_price = fill_price * 0.90
                            tp_price = fill_price * 1.05
                        
                        # Send intraday notification for successful order
                        from telegram_notifier import IntradayEvent
                        event = IntradayEvent(
                            event_id=f"entry_{ticker}_{order_id}",
                            ticker=ticker,
                            event_type='entry',
                            details={
                                'order_id': order_id,
                                'qty': qty,
                                'price': fill_price,
                                'investment': investment,
                                'sl_price': sl_price,
                                'tp_price': tp_price,
                                'reason': 'Morning decision executed'
                            },
                            timestamp=datetime.now(self.et_tz)
                        )
                        self.telegram.send_intraday_event(event)
                    elif not success:
                        # Send rejection notification
                        from telegram_notifier import IntradayEvent
                        event = IntradayEvent(
                            event_id=f"reject_{ticker}_{datetime.now().timestamp()}",
                            ticker=ticker,
                            event_type='reject',
                            details={
                                'reason': message
                            },
                            timestamp=datetime.now(self.et_tz)
                        )
                        self.telegram.send_intraday_event(event)
            
            # Log all order attempts
            self.logger.info(f"Order attempts today: {len(order_attempts)}")
            for attempt in order_attempts:
                self.logger.info(f"  {attempt['ticker']}: {attempt['success']} - {attempt['message']}")
            
            # Save order attempts to state
            self.state['order_attempts'] = order_attempts
            self._save_state()
            
            # Send Telegram notifications (exactly 14 messages)
            success = self.telegram.send_morning_decisions(decisions)
            
            if success:
                self.logger.info("✅ Morning routine completed successfully")
                return True
            else:
                self.logger.error("❌ Morning routine failed - Telegram notifications incomplete")
                return False
                
        except Exception as e:
            self.logger.error(f"Morning routine error: {e}")
            return False
    
    def monitor_intraday_activity(self, market_close: datetime) -> bool:
        """Monitor trading activity during market hours"""
        try:
            self.logger.info("📈 Starting intraday monitoring")
            self.state['phase'] = 'intraday'
            self._save_state()
            
            last_position_check = datetime.now(self.et_tz)
            last_order_check = datetime.now(self.et_tz)
            
            while self.running and datetime.now(self.et_tz) < market_close:
                try:
                    # Check for new fills/position changes every 30 seconds
                    if (datetime.now(self.et_tz) - last_position_check).total_seconds() > 30:
                        self._check_position_changes()
                        last_position_check = datetime.now(self.et_tz)
                    
                    # Check for order status changes every 15 seconds
                    if (datetime.now(self.et_tz) - last_order_check).total_seconds() > 15:
                        self._check_order_status()
                        last_order_check = datetime.now(self.et_tz)
                    
                    time.sleep(5)  # Main loop sleep
                    
                except Exception as e:
                    self.logger.error(f"Intraday monitoring error: {e}")
                    time.sleep(30)  # Wait longer on error
            
            self.logger.info("📊 Intraday monitoring completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Intraday monitoring failed: {e}")
            return False
    
    def _check_position_changes(self):
        """Check for position changes and send notifications"""
        try:
            current_positions = self.trader.trading_client.get_all_positions()
            
            # Track position changes
            current_tickers = {pos.symbol for pos in current_positions}
            previous_tickers = set(self.state.get('positions', {}).keys())
            
            # New positions (entries/fills)
            new_positions = current_tickers - previous_tickers
            for ticker in new_positions:
                pos = next(p for p in current_positions if p.symbol == ticker)
                event = IntradayEvent(
                    event_id=f"entry_{ticker}_{datetime.now().timestamp()}",
                    ticker=ticker,
                    event_type='entry',
                    details={
                        'qty': int(pos.qty),
                        'price': float(pos.avg_entry_price),
                        'investment': float(pos.qty) * float(pos.avg_entry_price),
                        'reason': 'position opened'
                    },
                    timestamp=datetime.now(self.et_tz)
                )
                self.telegram.send_intraday_event(event)
            
            # Closed positions
            closed_positions = previous_tickers - current_tickers
            for ticker in closed_positions:
                # Determine if it was stop loss, take profit, or manual close
                # This would require order history analysis for precise detection
                event = IntradayEvent(
                    event_id=f"close_{ticker}_{datetime.now().timestamp()}",
                    ticker=ticker,
                    event_type='fill',  # Generic close
                    details={
                        'reason': 'position closed'
                    },
                    timestamp=datetime.now(self.et_tz)
                )
                self.telegram.send_intraday_event(event)
            
            # Update state
            self.state['positions'] = {
                pos.symbol: {
                    'qty': float(pos.qty),
                    'avg_entry_price': float(pos.avg_entry_price),
                    'market_value': float(pos.market_value),
                    'unrealized_pl': float(pos.unrealized_pl) if pos.unrealized_pl else 0.0
                }
                for pos in current_positions
            }
            self._save_state()
            
        except Exception as e:
            self.logger.error(f"Error checking position changes: {e}")
    
    def _check_order_status(self):
        """Check for order status changes (rejections, cancellations)"""
        try:
            # Get recent orders
            orders = self.trader.trading_client.get_orders()
            
            for order in orders:
                if order.status in ['rejected', 'canceled']:
                    event_id = f"order_{order.status}_{order.id}"
                    
                    # Check if we already notified about this
                    if event_id not in self.state.get('notified_orders', set()):
                        event = IntradayEvent(
                            event_id=event_id,
                            ticker=order.symbol,
                            event_type='reject' if order.status == 'rejected' else 'cancel',
                            details={
                                'order_id': order.id,
                                'reason': f"order {order.status}"
                            },
                            timestamp=datetime.now(self.et_tz)
                        )
                        self.telegram.send_intraday_event(event)
                        
                        # Mark as notified
                        if 'notified_orders' not in self.state:
                            self.state['notified_orders'] = []
                        self.state['notified_orders'].append(event_id)
                        self._save_state()
            
        except Exception as e:
            self.logger.error(f"Error checking order status: {e}")
    
    def execute_evening_routine(self) -> bool:
        """Execute evening routine at 3:50 PM: decide overnight positions and summarize
        
        Note: Runs 10 minutes before market close to allow time for sell orders
        to execute before 4:00 PM close.
        """
        try:
            self.state['phase'] = 'evening'
            self._save_state()
            
            # Get current positions
            current_positions = self.trader.trading_client.get_all_positions()
            position_dict = {pos.symbol: pos for pos in current_positions}
            
            # Create outcomes for all 14 stocks
            outcomes = []
            for ticker in self.WATCHLIST:
                outcome = self._assess_stock_for_evening(ticker, position_dict.get(ticker))
                outcomes.append(outcome)
                self.logger.info(f"{ticker}: {outcome.outcome} - {outcome.reason}")
            
            # Send Telegram notifications (exactly 14 messages)
            success = self.telegram.send_evening_outcomes(outcomes)
            
            if success:
                self.logger.info("✅ Evening routine completed successfully")
                return True
            else:
                self.logger.error("❌ Evening routine failed - Telegram notifications incomplete")
                return False
                
        except Exception as e:
            self.logger.error(f"Evening routine error: {e}")
            return False
    
    def _assess_stock_for_evening(self, ticker: str, position) -> DayOutcome:
        """Assess a single stock for evening outcome with REAL sentiment re-check"""
        try:
            if not position:
                # No position in this stock
                return DayOutcome(
                    ticker=ticker,
                    outcome='never_opened',
                    reason='No trading activity today',
                    pnl=None,
                    position_status='no_position',
                    sentiment_score=0.0
                )
            
            # Calculate P&L
            pnl = float(position.unrealized_pl) if position.unrealized_pl else 0.0
            
            # REAL SENTIMENT RE-CHECK at market close
            from decision_engine import DecisionEngine
            engine = DecisionEngine(self.trader)
            today_str = datetime.now(self.et_tz).strftime('%Y-%m-%d')
            article_count, sentiment_score = engine.get_sentiment_data(ticker, today_str)
            
            self.logger.info(f"{ticker} evening sentiment: {sentiment_score:.3f} ({article_count} articles), P&L: ${pnl:+,.0f}")
            
            # Decision logic: Keep overnight if sentiment >= 0.1 (on -1 to +1 scale)
            # Close if sentiment drops below 0.1 (same threshold as morning entry)
            should_close = sentiment_score < 0.1
            
            if should_close:
                # ACTUALLY CLOSE THE POSITION with real sell order
                close_success = self._close_position_now(ticker, position)
                
                if close_success:
                    reason = f'Sentiment dropped below 0.1 ({sentiment_score:.3f}), closed position, P&L: ${pnl:+,.0f}'
                    
                    return DayOutcome(
                        ticker=ticker,
                        outcome='closed',
                        reason=reason,
                        pnl=pnl,
                        position_status='closed',
                        sentiment_score=sentiment_score
                    )
                else:
                    # Close order failed
                    return DayOutcome(
                        ticker=ticker,
                        outcome='kept_overnight',
                        reason=f'Failed to close position, keeping overnight (P&L: ${pnl:+,.0f})',
                        pnl=pnl,
                        position_status='close_failed_keeping',
                        sentiment_score=sentiment_score
                    )
            else:
                # Keep overnight - sentiment still positive (>= 0.1 on -1 to +1 scale)
                return DayOutcome(
                    ticker=ticker,
                    outcome='kept_overnight',
                    reason=f'Sentiment positive ({sentiment_score:.3f} >= 0.1), holding overnight, P&L: ${pnl:+,.0f}',
                    pnl=pnl,
                    position_status='holding_overnight',
                    sentiment_score=sentiment_score
                )
                
        except Exception as e:
            self.logger.error(f"Error assessing {ticker} for evening: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return DayOutcome(
                ticker=ticker,
                outcome='never_opened',
                reason=f'Assessment error: {str(e)[:50]}...',
                pnl=None,
                position_status='error',
                sentiment_score=0.0
            )
    
    def _close_position_now(self, ticker: str, position) -> bool:
        """ACTUALLY close a position by placing a market sell order"""
        try:
            from alpaca.trading.requests import MarketOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce
            
            qty = int(float(position.qty))
            
            if qty <= 0:
                self.logger.error(f"Invalid quantity for {ticker}: {qty}")
                return False
            
            self.logger.info(f"Placing REAL SELL order for {ticker}: {qty} shares")
            
            # Create market sell order
            market_order_data = MarketOrderRequest(
                symbol=ticker,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY
            )
            
            # Submit the sell order
            order = self.trader.trading_client.submit_order(order_data=market_order_data)
            
            self.logger.info(f"✅ REAL SELL order placed for {ticker}: Order ID {order.id}")
            
            # Send intraday notification for the close
            event = IntradayEvent(
                event_id=f"close_{ticker}_{order.id}",
                ticker=ticker,
                event_type='fill',
                details={
                    'order_id': order.id,
                    'qty': qty,
                    'reason': 'Evening close decision'
                },
                timestamp=datetime.now(self.et_tz)
            )
            self.telegram.send_intraday_event(event)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error closing position for {ticker}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    def run_daily_loop(self):
        """Main daily loop - runs until manually stopped"""
        self.logger.info("🚀 Starting autonomous daily trader")
        
        while self.running:
            try:
                # Wait for market open
                if self.stop_requested:
                    break
                
                market_open, market_close = self.wait_for_market_open()
                
                if not self.running:
                    break
                
                today_str = market_open.strftime('%Y-%m-%d')
                self.logger.info(f"📅 Trading day: {today_str}")
                
                # Check if we already processed today
                if self.state.get('last_trading_date') == today_str:
                    self.logger.info("Already processed today, waiting for next trading day")
                    # Wait until next day
                    tomorrow = datetime.now(self.et_tz) + timedelta(days=1)
                    tomorrow_start = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
                    wait_seconds = (tomorrow_start - datetime.now(self.et_tz)).total_seconds()
                    
                    while wait_seconds > 0 and self.running:
                        sleep_time = min(300, wait_seconds)
                        time.sleep(sleep_time)
                        wait_seconds -= sleep_time
                    continue
                
                # Execute morning routine
                if not self.execute_morning_routine():
                    self.logger.error("Morning routine failed, skipping day")
                    continue
                
                # Monitor intraday activity
                if not self.monitor_intraday_activity(market_close):
                    self.logger.error("Intraday monitoring failed")
                
                # Wait for evening routine time (3:50 PM - 10 minutes before close)
                evening_routine_time = market_close - timedelta(minutes=10)
                now = datetime.now(self.et_tz)
                if now < evening_routine_time:
                    wait_seconds = (evening_routine_time - now).total_seconds()
                    self.logger.info(f"Waiting for evening routine at {evening_routine_time.strftime('%H:%M ET')} "
                                   f"(in {wait_seconds/60:.0f} minutes)")
                    
                    while wait_seconds > 0 and self.running:
                        sleep_time = min(60, wait_seconds)
                        time.sleep(sleep_time)
                        wait_seconds -= sleep_time
                        now = datetime.now(self.et_tz)
                        wait_seconds = (evening_routine_time - now).total_seconds()
                
                # Execute evening routine (at 3:50 PM ET, 10 minutes before close)
                self.logger.info(f"🌆 Starting evening routine at {datetime.now(self.et_tz).strftime('%H:%M:%S ET')}")
                if not self.execute_evening_routine():
                    self.logger.error("Evening routine failed")
                
                # Mark day as completed
                self.state['last_trading_date'] = today_str
                self.state['phase'] = 'waiting'
                self._save_state()
                
                self.logger.info(f"✅ Trading day {today_str} completed")
                
                # Clean up old data
                self.telegram.cleanup_old_events()
                
            except Exception as e:
                self.logger.error(f"Daily loop error: {e}")
                time.sleep(300)  # Wait 5 minutes before retrying
        
        self.logger.info("🛑 Autonomous daily trader stopped")
    
    def stop(self):
        """Stop the autonomous trader gracefully"""
        self.logger.info("Stop requested...")
        self.stop_requested = True
        self.running = False

def main():
    """Main entry point"""
    try:
        trader = AutonomousDailyTrader()
        
        print("🤖 Autonomous Daily Trader")
        print("=" * 50)
        print("Starting autonomous trading loop...")
        print("Press Ctrl+C to stop gracefully")
        print("=" * 50)
        
        trader.run_daily_loop()
        
    except KeyboardInterrupt:
        print("\n🛑 Shutdown requested by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        logging.error(f"Fatal error: {e}")
    finally:
        print("👋 Autonomous trader stopped")

if __name__ == "__main__":
    main()
