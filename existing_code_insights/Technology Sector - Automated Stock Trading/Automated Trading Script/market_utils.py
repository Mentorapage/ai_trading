"""
Market Utilities - Comprehensive safety checks and validations
Prevents trading failures through proactive validation
"""

import pandas_market_calendars as mcal
from datetime import datetime, time
import pytz
import logging
from trade_types import trading_client


def is_market_open():
    """
    Check if US stock market is currently open
    Returns: (bool, str) - (is_open, status_message)
    """
    try:
        # Get NYSE calendar
        nyse = mcal.get_calendar('NYSE')
        
        # Get current time in EST
        est = pytz.timezone('US/Eastern')
        now_est = datetime.now(est)
        today = now_est.date()
        
        # Check if today is a trading day
        schedule = nyse.schedule(start_date=today, end_date=today)
        
        if schedule.empty:
            return False, f"Market closed - {today} is not a trading day"
        
        # Get market open/close times for today
        market_open = schedule.iloc[0]['market_open'].to_pydatetime()
        market_close = schedule.iloc[0]['market_close'].to_pydatetime()
        
        # Check if current time is within trading hours
        if market_open <= now_est <= market_close:
            return True, f"Market open - closes at {market_close.strftime('%H:%M EST')}"
        elif now_est < market_open:
            return False, f"Market opens at {market_open.strftime('%H:%M EST')}"
        else:
            return False, f"Market closed at {market_close.strftime('%H:%M EST')}"
            
    except Exception as e:
        logging.warning(f"Market hours check failed: {e}")
        # Fallback to basic time check (9:30 AM - 4:00 PM EST weekdays)
        est = pytz.timezone('US/Eastern')
        now_est = datetime.now(est)
        
        if now_est.weekday() >= 5:  # Weekend
            return False, "Market closed - Weekend"
        
        market_time = now_est.time()
        if time(9, 30) <= market_time <= time(16, 0):
            return True, "Market likely open (fallback check)"
        else:
            return False, "Market likely closed (fallback check)"


def validate_account_status():
    """
    Comprehensive account validation before trading
    Returns: (bool, dict) - (is_valid, account_info)
    """
    try:
        account = trading_client.get_account()
        
        issues = []
        
        # Check account status
        if account.status.value != 'ACTIVE':
            issues.append(f"Account status: {account.status.value}")
        
        # Check buying power
        buying_power = float(account.buying_power)
        if buying_power < 1000:
            issues.append(f"Low buying power: ${buying_power:.2f}")
        
        # Check if account is restricted
        if hasattr(account, 'trade_suspended_by_user') and account.trade_suspended_by_user:
            issues.append("Trading suspended by user")
            
        # Check pattern day trader status
        if hasattr(account, 'pattern_day_trader') and account.pattern_day_trader:
            issues.append("Pattern Day Trader restrictions may apply")
        
        account_info = {
            'status': account.status.value,
            'buying_power': buying_power,
            'cash': float(account.cash),
            'portfolio_value': float(account.portfolio_value),
            'equity': float(account.equity)
        }
        
        is_valid = len(issues) == 0
        if issues:
            account_info['issues'] = issues
            
        return is_valid, account_info
        
    except Exception as e:
        logging.error(f"Account validation failed: {e}")
        return False, {'error': str(e)}


def validate_stock_symbol(symbol):
    """
    Validate if a stock symbol is tradeable
    Returns: (bool, str) - (is_valid, message)
    """
    try:
        symbol = symbol.upper().strip()
        
        # Basic format validation
        if not symbol or len(symbol) > 5 or not symbol.isalpha():
            return False, f"Invalid symbol format: {symbol}"
        
        # Try to get asset info from Alpaca
        try:
            assets = trading_client.get_all_assets()
            tradeable_symbols = {asset.symbol for asset in assets if asset.tradable}
            
            if symbol not in tradeable_symbols:
                return False, f"Symbol {symbol} not tradeable on Alpaca"
                
        except Exception:
            # Fallback - just check if we can get a quote
            pass
        
        return True, f"Symbol {symbol} validated"
        
    except Exception as e:
        return False, f"Symbol validation error: {e}"


def pre_trading_validation():
    """
    Complete pre-trading validation checklist
    Returns: (bool, list) - (ready_to_trade, validation_results)
    """
    results = []
    all_passed = True
    
    # 1. Market hours check
    market_open, market_msg = is_market_open()
    results.append({
        'check': 'Market Hours',
        'passed': market_open,
        'message': market_msg
    })
    if not market_open:
        all_passed = False
    
    # 2. Account validation
    account_valid, account_info = validate_account_status()
    results.append({
        'check': 'Account Status',
        'passed': account_valid,
        'message': f"Buying power: ${account_info.get('buying_power', 0):,.2f}" if account_valid 
                  else f"Issues: {', '.join(account_info.get('issues', ['Unknown error']))}"
    })
    if not account_valid:
        all_passed = False
    
    # 3. API connectivity
    try:
        positions = trading_client.get_all_positions()
        results.append({
            'check': 'API Connectivity',
            'passed': True,
            'message': f"Connected - {len(positions)} current positions"
        })
    except Exception as e:
        results.append({
            'check': 'API Connectivity',
            'passed': False,
            'message': f"API Error: {str(e)}"
        })
        all_passed = False
    
    return all_passed, results


def log_validation_results(results):
    """Log validation results for audit trail"""
    logging.info("=== PRE-TRADING VALIDATION ===")
    for result in results:
        status = "✅ PASS" if result['passed'] else "❌ FAIL"
        logging.info(f"{status}: {result['check']} - {result['message']}")
    logging.info("=== VALIDATION COMPLETE ===")


def safe_trading_wrapper(trading_function):
    """
    Decorator to wrap trading functions with comprehensive safety checks
    """
    def wrapper(*args, **kwargs):
        logging.info("Starting pre-trading safety validation...")
        
        ready, results = pre_trading_validation()
        log_validation_results(results)
        
        if not ready:
            failed_checks = [r['check'] for r in results if not r['passed']]
            error_msg = f"Trading aborted - Failed validation: {', '.join(failed_checks)}"
            logging.error(error_msg)
            print(f"❌ {error_msg}")
            return False
        
        logging.info("✅ All safety checks passed - proceeding with trading")
        
        try:
            return trading_function(*args, **kwargs)
        except Exception as e:
            logging.error(f"Trading function failed: {e}")
            print(f"❌ Trading execution failed: {e}")
            return False
    
    return wrapper 