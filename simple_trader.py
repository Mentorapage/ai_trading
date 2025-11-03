#!/usr/bin/env python3
"""
SIMPLE REAL-TIME TRADER
=======================
Minimal automated trading system with Alpaca API integration.
Features:
- Real-time market data connection
- Automated buy/sell order execution
- Basic stop-loss and take-profit controls
- Simple trade logging
"""

import os
import time
import logging
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import pytz
from dotenv import load_dotenv

# Alpaca API imports
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, StopLossRequest, TakeProfitRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest

# Load environment variables
load_dotenv()

class SimpleTrader:
    """Minimal real-time trading system"""
    
    def __init__(self):
        """Initialize the trading system"""
        # Load API credentials
        self.api_key = os.getenv("apikey")
        self.secret_key = os.getenv("apisecret")
        
        if not self.api_key or not self.secret_key:
            raise ValueError("Missing Alpaca API credentials. Check your .env file.")
        
        # Initialize Alpaca clients (paper trading mode)
        self.trading_client = TradingClient(self.api_key, self.secret_key, paper=True)
        self.data_client = StockHistoricalDataClient(self.api_key, self.secret_key)
        
        # Trading parameters - Expanded to 14 stocks for 1/14 allocation
        self.target_stocks = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA',  # Original 5
            'NVDA', 'META', 'NFLX', 'AMD', 'CRM',      # Additional 5
            'ADBE', 'PYPL', 'INTC', 'ORCL'             # Additional 4 (total 14)
        ]
        
        # Dynamic position sizing based on account balance
        self.position_size = self.calculate_dynamic_position_size()
        self.stop_loss_pct = 10.0   # 10% stop loss
        self.take_profit_pct = 5.0  # 5% take profit
        self.max_positions = 14     # Maximum concurrent positions (all 14 stocks)
        
        # Timezone
        self.et_tz = pytz.timezone('America/New_York')
        
        # Active positions tracking
        self.active_positions = {}
        
        # Setup logging
        self.setup_logging()
        
        logging.info("Simple Trader initialized")
        logging.info(f"Target stocks: {self.target_stocks}")
        logging.info(f"Position size: ${self.position_size:,}")
        logging.info(f"Stop loss: {self.stop_loss_pct}%")
        logging.info(f"Take profit: {self.take_profit_pct}%")
    
    def setup_logging(self):
        """Setup logging configuration"""
        # Create logs directory
        os.makedirs('logs', exist_ok=True)
        
        # Configure logging
        log_filename = f"logs/simple_trader_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filename),
                logging.StreamHandler()  # Console output
            ]
        )
        
        logging.info(f"Logging initialized. Log file: {log_filename}")
    
    def calculate_dynamic_position_size(self):
        """Calculate position size based on account balance (85% / 14 stocks)"""
        try:
            # Get account information
            account = self.trading_client.get_account()
            portfolio_value = float(account.portfolio_value)
            
            # Calculate 85% of portfolio value
            investable_amount = portfolio_value * 0.85
            
            # Divide by 14 stocks
            position_size = investable_amount / 14
            
            logging.info(f"Dynamic position sizing calculated:")
            logging.info(f"  Portfolio Value: ${portfolio_value:,.2f}")
            logging.info(f"  Investable Amount (85%): ${investable_amount:,.2f}")
            logging.info(f"  Position Size per Stock: ${position_size:,.2f}")
            
            # Minimum position size of $100 to avoid very small trades
            return max(position_size, 100.0)
            
        except Exception as e:
            logging.error(f"Error calculating dynamic position size: {e}")
            logging.info("Falling back to default position size of $1000")
            return 1000.0  # Fallback to $1000 per position
    
    def is_market_open(self):
        """Check if the market is currently open"""
        try:
            calendar = self.trading_client.get_calendar()
            now_et = datetime.now(self.et_tz)
            current_date = now_et.date()
            
            # Find today's market session
            for session in calendar:
                if session.date == current_date:
                    market_open = datetime.combine(current_date, session.open.time()).replace(tzinfo=self.et_tz)
                    market_close = datetime.combine(current_date, session.close.time()).replace(tzinfo=self.et_tz)
                    
                    if market_open <= now_et <= market_close:
                        return True, f"Market open until {market_close.strftime('%H:%M ET')}"
                    elif now_et < market_open:
                        return False, f"Market opens at {market_open.strftime('%H:%M ET')}"
                    else:
                        return False, "Market closed for today"
            
            return False, "Market closed - no session today"
            
        except Exception as e:
            logging.warning(f"Could not check market status: {e}")
            return True, "Market status unknown - proceeding"
    
    def get_current_price(self, symbol):
        """Get current price for a symbol"""
        try:
            request = StockLatestQuoteRequest(symbol_or_symbols=[symbol])
            latest_quote = self.data_client.get_stock_latest_quote(request)
            
            if symbol in latest_quote:
                bid = float(latest_quote[symbol].bid_price)
                ask = float(latest_quote[symbol].ask_price)
                current_price = (bid + ask) / 2  # Mid price
                return current_price
            else:
                logging.error(f"No quote data for {symbol}")
                return None
                
        except Exception as e:
            logging.error(f"Error getting price for {symbol}: {e}")
            return None
    
    def calculate_shares(self, symbol, investment_amount):
        """Calculate number of shares to buy"""
        current_price = self.get_current_price(symbol)
        if current_price is None:
            return 0
        
        shares = int(investment_amount / current_price)
        return max(1, shares)  # At least 1 share
    
    def place_buy_order(self, symbol):
        """Place a buy order with stop-loss and take-profit"""
        try:
            # Get current price
            current_price = self.get_current_price(symbol)
            if current_price is None:
                logging.error(f"Cannot get price for {symbol}, skipping buy order")
                return False
            
            # Calculate shares
            shares = self.calculate_shares(symbol, self.position_size)
            if shares == 0:
                logging.error(f"Cannot calculate shares for {symbol}")
                return False
            
            # Calculate stop-loss and take-profit prices
            stop_price = current_price * (1 - self.stop_loss_pct / 100)
            take_profit_price = current_price * (1 + self.take_profit_pct / 100)
            
            # Create bracket order (buy with stop-loss and take-profit)
            market_order_data = MarketOrderRequest(
                symbol=symbol,
                qty=shares,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
                order_class=OrderClass.BRACKET,
                stop_loss=StopLossRequest(stop_price=Decimal(str(round(stop_price, 2)))),
                take_profit=TakeProfitRequest(limit_price=Decimal(str(round(take_profit_price, 2))))
            )
            
            # Submit order
            order = self.trading_client.submit_order(order_data=market_order_data)
            
            # Log the trade
            logging.info(f"BUY ORDER PLACED: {symbol}")
            logging.info(f"  Shares: {shares}")
            logging.info(f"  Estimated Price: ${current_price:.2f}")
            logging.info(f"  Investment: ${shares * current_price:.2f}")
            logging.info(f"  Stop Loss: ${stop_price:.2f} ({self.stop_loss_pct}%)")
            logging.info(f"  Take Profit: ${take_profit_price:.2f} ({self.take_profit_pct}%)")
            logging.info(f"  Order ID: {order.id}")
            
            # Track the position
            self.active_positions[symbol] = {
                'order_id': order.id,
                'shares': shares,
                'entry_price': current_price,
                'stop_price': stop_price,
                'take_profit_price': take_profit_price,
                'entry_time': datetime.now()
            }
            
            return True
            
        except Exception as e:
            logging.error(f"Error placing buy order for {symbol}: {e}")
            return False
    
    def check_positions(self):
        """Check status of active positions"""
        try:
            # Get current positions from Alpaca
            positions = self.trading_client.get_all_positions()
            
            # Update our tracking
            current_symbols = {pos.symbol for pos in positions}
            
            # Remove positions that are no longer active
            symbols_to_remove = []
            for symbol in self.active_positions:
                if symbol not in current_symbols:
                    logging.info(f"Position closed: {symbol}")
                    symbols_to_remove.append(symbol)
            
            for symbol in symbols_to_remove:
                del self.active_positions[symbol]
            
            # Log current positions
            if positions:
                logging.info(f"Active positions: {len(positions)}")
                for pos in positions:
                    current_price = self.get_current_price(pos.symbol)
                    pnl = float(pos.unrealized_pl) if pos.unrealized_pl else 0
                    pnl_pct = (pnl / (float(pos.qty) * float(pos.avg_entry_price))) * 100 if pos.avg_entry_price else 0
                    
                    logging.info(f"  {pos.symbol}: {pos.qty} shares @ ${pos.avg_entry_price}, "
                               f"Current: ${current_price:.2f}, PnL: ${pnl:.2f} ({pnl_pct:.1f}%)")
            
        except Exception as e:
            logging.error(f"Error checking positions: {e}")
    
    def should_buy_stock(self, symbol):
        """Simple logic to determine if we should buy a stock"""
        # Simple example: buy if we don't already have a position
        # In a real system, this would include your trading logic
        
        if symbol in self.active_positions:
            return False, "Already have position"
        
        if len(self.active_positions) >= self.max_positions:
            return False, "Maximum positions reached"
        
        # Get current price to ensure it's reasonable
        current_price = self.get_current_price(symbol)
        if current_price is None:
            return False, "Cannot get current price"
        
        if current_price < 10:  # Avoid penny stocks
            return False, "Price too low"
        
        if current_price > 500:  # Avoid very expensive stocks for this example
            return False, "Price too high"
        
        # Simple buy signal (in real system, add your trading logic here)
        return True, "Buy signal triggered"
    
    def trading_loop(self):
        """Main trading loop"""
        logging.info("Starting trading loop...")
        
        while True:
            try:
                # Check if market is open
                market_open, status_msg = self.is_market_open()
                
                if not market_open:
                    logging.info(f"Market status: {status_msg}")
                    time.sleep(300)  # Wait 5 minutes before checking again
                    continue
                
                logging.info(f"Market status: {status_msg}")
                
                # Check existing positions
                self.check_positions()
                
                # Look for new trading opportunities
                for symbol in self.target_stocks:
                    should_buy, reason = self.should_buy_stock(symbol)
                    
                    if should_buy:
                        logging.info(f"Buy signal for {symbol}: {reason}")
                        success = self.place_buy_order(symbol)
                        
                        if success:
                            logging.info(f"Successfully placed buy order for {symbol}")
                        else:
                            logging.error(f"Failed to place buy order for {symbol}")
                    else:
                        logging.debug(f"No buy signal for {symbol}: {reason}")
                
                # Wait before next iteration
                logging.info("Waiting 60 seconds before next check...")
                time.sleep(60)  # Check every minute
                
            except KeyboardInterrupt:
                logging.info("Trading loop interrupted by user")
                break
            except Exception as e:
                logging.error(f"Error in trading loop: {e}")
                time.sleep(30)  # Wait 30 seconds before retrying
    
    def get_account_info(self):
        """Get account information"""
        try:
            account = self.trading_client.get_account()
            portfolio_value = float(account.portfolio_value)
            investable_amount = portfolio_value * 0.85
            position_size_per_stock = investable_amount / 14
            
            logging.info("=== ACCOUNT INFO ===")
            logging.info(f"Account ID: {account.id}")
            logging.info(f"Cash: ${float(account.cash):,.2f}")
            logging.info(f"Portfolio Value: ${portfolio_value:,.2f}")
            logging.info(f"Buying Power: ${float(account.buying_power):,.2f}")
            logging.info(f"Status: {account.status}")
            logging.info("=== POSITION SIZING ===")
            logging.info(f"Investable Amount (85%): ${investable_amount:,.2f}")
            logging.info(f"Target Stocks: {len(self.target_stocks)} stocks")
            logging.info(f"Position Size per Stock: ${position_size_per_stock:,.2f}")
            logging.info(f"Current Position Size Setting: ${self.position_size:,.2f}")
            logging.info("=====================")
            
            return account
            
        except Exception as e:
            logging.error(f"Error getting account info: {e}")
            return None
    
    def cancel_all_orders(self):
        """Cancel all open orders and close all positions"""
        try:
            logging.info("Cancelling all orders and closing all positions...")
            
            # Cancel all orders
            orders = self.trading_client.get_orders()
            for order in orders:
                try:
                    self.trading_client.cancel_order_by_id(order.id)
                    logging.info(f"Cancelled order: {order.id} for {order.symbol}")
                except Exception as e:
                    logging.error(f"Error cancelling order {order.id}: {e}")
            
            # Close all positions
            positions = self.trading_client.get_all_positions()
            for position in positions:
                try:
                    self.trading_client.close_position(position.symbol)
                    logging.info(f"Closed position: {position.symbol}")
                except Exception as e:
                    logging.error(f"Error closing position {position.symbol}: {e}")
            
            # Clear our tracking
            self.active_positions.clear()
            
            logging.info("All orders cancelled and positions closed")
            
        except Exception as e:
            logging.error(f"Error in cancel_all_orders: {e}")

def main():
    """Main function"""
    print("=== SIMPLE REAL-TIME TRADER ===")
    print("This is a minimal automated trading system.")
    print("It will connect to Alpaca API and execute trades in paper mode.")
    print("Press Ctrl+C to stop the system.")
    print("================================")
    
    try:
        # Initialize trader
        trader = SimpleTrader()
        
        # Get account info
        trader.get_account_info()
        
        # Start trading
        trader.trading_loop()
        
    except KeyboardInterrupt:
        print("\nShutting down trader...")
        if 'trader' in locals():
            trader.cancel_all_orders()
        print("Trader stopped.")
    except Exception as e:
        print(f"Error: {e}")
        logging.error(f"Fatal error: {e}")

if __name__ == "__main__":
    main()


