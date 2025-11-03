#!/usr/bin/env python3
"""
ALPACA BALANCE CHECKER & POSITION CALCULATOR
============================================
This script connects to your Alpaca account, checks your balance,
and calculates the investment amount per stock based on your requirements:
- Uses 85% of total account balance
- Divides by 14 stocks for equal allocation
"""

import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

# Load environment variables
load_dotenv()

class BalanceChecker:
    """Check Alpaca account balance and calculate position sizes"""
    
    def __init__(self):
        """Initialize the balance checker"""
        # Load API credentials
        self.api_key = os.getenv("apikey")
        self.secret_key = os.getenv("apisecret")
        
        if not self.api_key or not self.secret_key:
            raise ValueError("Missing Alpaca API credentials. Please check your .env file.")
        
        # Initialize Alpaca client (paper trading mode)
        self.trading_client = TradingClient(self.api_key, self.secret_key, paper=True)
        
        # Trading parameters
        self.allocation_percentage = 0.85  # Use 85% of balance
        self.number_of_stocks = 14         # Divide by 14 stocks
        
        # Setup logging
        self.setup_logging()
        
        logging.info("Balance Checker initialized")
    
    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler()  # Console output
            ]
        )
    
    def get_account_balance(self):
        """Get comprehensive account information"""
        try:
            account = self.trading_client.get_account()
            
            account_info = {
                "account_id": account.id,
                "cash": float(account.cash),
                "portfolio_value": float(account.portfolio_value),
                "buying_power": float(account.buying_power),
                "equity": float(account.equity),
                "status": account.status,
                "day_trade_count": getattr(account, 'day_trade_count', 0),
                "pattern_day_trader": getattr(account, 'pattern_day_trader', False)
            }
            
            return account_info
            
        except Exception as e:
            logging.error(f"Error getting account information: {e}")
            return None
    
    def calculate_position_size(self, account_info):
        """Calculate position size per stock"""
        if not account_info:
            return None
        
        # Use portfolio value as the base for calculation
        total_balance = account_info["portfolio_value"]
        
        # Calculate 85% of balance
        investable_amount = total_balance * self.allocation_percentage
        
        # Divide by number of stocks
        position_size_per_stock = investable_amount / self.number_of_stocks
        
        calculation_info = {
            "total_balance": total_balance,
            "allocation_percentage": self.allocation_percentage * 100,
            "investable_amount": investable_amount,
            "number_of_stocks": self.number_of_stocks,
            "position_size_per_stock": position_size_per_stock
        }
        
        return calculation_info
    
    def display_results(self, account_info, calculation_info):
        """Display account balance and calculated position sizes"""
        print("=" * 60)
        print("🏦 ALPACA ACCOUNT BALANCE & POSITION CALCULATOR")
        print("=" * 60)
        
        if not account_info:
            print("❌ Could not retrieve account information")
            return
        
        # Account Information
        print("\n📊 ACCOUNT INFORMATION:")
        print(f"Account ID: {account_info['account_id']}")
        print(f"Account Status: {account_info['status']}")
        print(f"Cash Available: ${account_info['cash']:,.2f}")
        print(f"Portfolio Value: ${account_info['portfolio_value']:,.2f}")
        print(f"Buying Power: ${account_info['buying_power']:,.2f}")
        print(f"Total Equity: ${account_info['equity']:,.2f}")
        print(f"Day Trade Count: {account_info['day_trade_count']}")
        print(f"Pattern Day Trader: {account_info['pattern_day_trader']}")
        
        if not calculation_info:
            print("❌ Could not calculate position sizes")
            return
        
        # Position Size Calculation
        print("\n💰 POSITION SIZE CALCULATION:")
        print(f"Total Portfolio Value: ${calculation_info['total_balance']:,.2f}")
        print(f"Allocation Percentage: {calculation_info['allocation_percentage']:.1f}%")
        print(f"Investable Amount: ${calculation_info['investable_amount']:,.2f}")
        print(f"Number of Stocks: {calculation_info['number_of_stocks']}")
        print(f"Position Size per Stock: ${calculation_info['position_size_per_stock']:,.2f}")
        
        # Risk Information
        print("\n⚠️  RISK INFORMATION:")
        cash_available = account_info['cash']
        total_investment_needed = calculation_info['investable_amount']
        
        if cash_available >= total_investment_needed:
            print(f"✅ Sufficient cash available for full allocation")
            print(f"   Cash Available: ${cash_available:,.2f}")
            print(f"   Total Investment: ${total_investment_needed:,.2f}")
            print(f"   Remaining Cash: ${cash_available - total_investment_needed:,.2f}")
        else:
            print(f"⚠️  Limited cash for full allocation")
            print(f"   Cash Available: ${cash_available:,.2f}")
            print(f"   Total Investment Needed: ${total_investment_needed:,.2f}")
            print(f"   Shortfall: ${total_investment_needed - cash_available:,.2f}")
            
            # Calculate maximum possible positions
            max_positions = int(cash_available / calculation_info['position_size_per_stock'])
            print(f"   Maximum Full Positions: {max_positions} stocks")
        
        print("\n" + "=" * 60)
    
    def save_config(self, calculation_info):
        """Save the calculated position size to a config file"""
        if not calculation_info:
            return False
        
        try:
            config_content = f"""# Auto-generated trading configuration
# Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

# Account Balance Information
TOTAL_BALANCE = {calculation_info['total_balance']:.2f}
ALLOCATION_PERCENTAGE = {calculation_info['allocation_percentage'] / 100:.2f}
INVESTABLE_AMOUNT = {calculation_info['investable_amount']:.2f}

# Position Sizing
NUMBER_OF_STOCKS = {calculation_info['number_of_stocks']}
POSITION_SIZE_PER_STOCK = {calculation_info['position_size_per_stock']:.2f}

# For use in trading scripts:
# position_size = {calculation_info['position_size_per_stock']:.2f}
"""
            
            with open('trading_config.py', 'w') as f:
                f.write(config_content)
            
            logging.info("Trading configuration saved to trading_config.py")
            return True
            
        except Exception as e:
            logging.error(f"Error saving configuration: {e}")
            return False
    
    def run_check(self):
        """Run the complete balance check and calculation"""
        try:
            print("Connecting to Alpaca API...")
            
            # Get account information
            account_info = self.get_account_balance()
            
            if not account_info:
                print("❌ Failed to retrieve account information")
                return False
            
            # Calculate position sizes
            calculation_info = self.calculate_position_size(account_info)
            
            # Display results
            self.display_results(account_info, calculation_info)
            
            # Save configuration
            if calculation_info:
                self.save_config(calculation_info)
                print(f"\n💾 Configuration saved to trading_config.py")
                print(f"   Use this in your trading scripts:")
                print(f"   position_size = {calculation_info['position_size_per_stock']:.2f}")
            
            return True
            
        except Exception as e:
            logging.error(f"Error in balance check: {e}")
            print(f"❌ Error: {e}")
            return False

def main():
    """Main function"""
    try:
        checker = BalanceChecker()
        success = checker.run_check()
        
        if success:
            print("\n✅ Balance check completed successfully!")
        else:
            print("\n❌ Balance check failed!")
            return 1
        
        return 0
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        return 1

if __name__ == "__main__":
    import sys
    exit_code = main()
    sys.exit(exit_code)
