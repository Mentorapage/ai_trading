#!/usr/bin/env python3
"""
REAL STRATEGY BATCH RUNNER - NO MOCK DATA
==========================================
Runs intraday strategies with 100% real data from Finnhub + Alpaca APIs
"""

import argparse
import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time
import logging
from pathlib import Path
import traceback
from typing import Dict, List, Tuple, Optional
import time as time_module
import csv

# Add current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Import trading modules
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import bootstrap_nltk  # noqa
import os, certifi
os.environ.setdefault("SSL_CERT_FILE", certifi.where())

from trading_core import validate_environment, load_stock_universe
from historical_backtest import get_historical_data
from real_sentiment_analyzer import get_sentiment_analyzer
from finnhub_api_pool import get_finnhub_pool

# Strategy configurations (exactly 20 as specified) - Updated with score_threshold
STRATEGIES = [
    {"id": "01", "score_threshold": 0.35, "trend": "ON", "stop_pct": 3, "take_pct": 5, "note": "conservative"},
    {"id": "02", "score_threshold": 0.40, "trend": "ON", "stop_pct": 5, "take_pct": 5, "note": "baseline"},
    {"id": "03", "score_threshold": 0.35, "trend": "ON", "stop_pct": 5, "take_pct": 7, "note": "mild trend"},
    {"id": "04", "score_threshold": 0.40, "trend": "ON", "stop_pct": 7, "take_pct": 7, "note": "wider stops"},
    {"id": "05", "score_threshold": 0.35, "trend": "ON", "stop_pct": 10, "take_pct": 15, "note": "semi-aggressive"},
    {"id": "06", "score_threshold": 0.40, "trend": "ON", "stop_pct": 10, "take_pct": 20, "note": "aggressive"},
    {"id": "07", "score_threshold": 0.35, "trend": "OFF", "stop_pct": 5, "take_pct": 5, "note": "no trend filter"},
    {"id": "08", "score_threshold": 0.40, "trend": "OFF", "stop_pct": 7, "take_pct": 10, "note": "no trend, looser TP"},
    {"id": "09", "score_threshold": 0.35, "trend": "ON", "stop_pct": 4, "take_pct": 8, "note": "asym SL/TP"},
    {"id": "10", "score_threshold": 0.40, "trend": "ON", "stop_pct": 6, "take_pct": 10, "note": "asym SL/TP"},
    {"id": "11", "score_threshold": 0.45, "trend": "ON", "stop_pct": 3, "take_pct": 3, "note": "tight + strict"},
    {"id": "12", "score_threshold": 0.50, "trend": "ON", "stop_pct": 5, "take_pct": 5, "note": "baseline + strict"},
    {"id": "13", "score_threshold": 0.45, "trend": "ON", "stop_pct": 7, "take_pct": 5, "note": "protective"},
    {"id": "14", "score_threshold": 0.50, "trend": "ON", "stop_pct": 10, "take_pct": 10, "note": "wide both"},
    {"id": "15", "score_threshold": 0.45, "trend": "OFF", "stop_pct": 3, "take_pct": 5, "note": "no trend, tight"},
    {"id": "16", "score_threshold": 0.50, "trend": "OFF", "stop_pct": 5, "take_pct": 7, "note": "no trend"},
    {"id": "17", "score_threshold": 0.30, "trend": "ON", "stop_pct": 8, "take_pct": 12, "note": "mid-aggressive"},
    {"id": "18", "score_threshold": 0.35, "trend": "ON", "stop_pct": 6, "take_pct": 12, "note": "asym growth"},
    {"id": "19", "score_threshold": 0.30, "trend": "OFF", "stop_pct": 10, "take_pct": 20, "note": "aggressive no trend"},
    {"id": "20", "score_threshold": 0.35, "trend": "ON", "stop_pct": 10, "take_pct": 20, "note": "aggressive with trend"},
]

def setup_logging(log_level: str, console_minimal: bool = False):
    """Setup logging configuration"""
    if console_minimal:
        # Minimal console output - only our progress messages
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        # Suppress other loggers
        logging.getLogger('trading_core').setLevel(logging.WARNING)
        logging.getLogger('historical_backtest').setLevel(logging.WARNING)
        logging.getLogger('real_sentiment_analyzer').setLevel(logging.WARNING)
        logging.getLogger('finnhub_api_pool').setLevel(logging.WARNING)
    else:
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

def get_trading_days(start_date: datetime, end_date: datetime) -> List[datetime]:
    """Get list of US trading days between start and end dates"""
    import pandas_market_calendars as mcal
    
    # Get NYSE calendar
    nyse = mcal.get_calendar('NYSE')
    
    # Get trading days
    trading_days = nyse.schedule(start_date=start_date, end_date=end_date)
    
    return [day.date() for day in trading_days.index]

def apply_trend_filter_real(qualified_stocks: List[Dict], analysis_date: str) -> List[Dict]:
    """Apply trend filter using real Alpaca historical data"""
    try:
        from trend_filter import apply_trend_filter
        return apply_trend_filter(qualified_stocks, analysis_date)
    except ImportError:
        logging.warning("Trend filter module not available, skipping trend filtering")
        return qualified_stocks
    except Exception as e:
        logging.warning(f"Trend filter failed: {e}, continuing without trend filtering")
        return qualified_stocks

def simulate_intraday_trade(
    ticker: str,
    entry_price: float,
    entry_time: datetime,
    shares: int,
    market_data: pd.DataFrame,
    stop_loss_pct: float,
    take_profit_pct: float
) -> Optional[Dict]:
    """Simulate an intraday trade with EOD force close"""
    
    # Calculate stop loss and take profit levels
    stop_loss_price = entry_price * (1 - stop_loss_pct / 100)
    take_profit_price = entry_price * (1 + take_profit_pct / 100)
    
    # Track the trade through the day
    for i, (timestamp, row) in enumerate(market_data.iterrows()):
        current_price = row['close']
        
        # Check for stop loss
        if current_price <= stop_loss_price:
            pnl = (current_price - entry_price) * shares
            return {
                'ticker': ticker,
                'entry_time': entry_time,
                'exit_time': timestamp,
                'entry_price': entry_price,
                'exit_price': current_price,
                'shares': shares,
                'pnl': pnl,
                'return_pct': (current_price - entry_price) / entry_price * 100,
                'exit_reason': 'STOP_LOSS',
                'holding_minutes': (timestamp - entry_time).total_seconds() / 60
            }
        
        # Check for take profit
        if current_price >= take_profit_price:
            pnl = (current_price - entry_price) * shares
            return {
                'ticker': ticker,
                'entry_time': entry_time,
                'exit_time': timestamp,
                'entry_price': entry_price,
                'exit_price': current_price,
                'shares': shares,
                'pnl': pnl,
                'return_pct': (current_price - entry_price) / entry_price * 100,
                'exit_reason': 'TAKE_PROFIT',
                'holding_minutes': (timestamp - entry_time).total_seconds() / 60
            }
    
    # If we reach here, force close at EOD (15:59:59 ET)
    eod_price = market_data.iloc[-1]['close']
    eod_time = market_data.index[-1]
    
    pnl = (eod_price - entry_price) * shares
    return {
        'ticker': ticker,
        'entry_time': entry_time,
        'exit_time': eod_time,
        'entry_price': entry_price,
        'exit_price': eod_price,
        'shares': shares,
        'pnl': pnl,
        'return_pct': (eod_price - entry_price) / entry_price * 100,
        'exit_reason': 'EOD',
        'holding_minutes': (eod_time - entry_time).total_seconds() / 60
    }

def assert_no_mock_data(qualified_stocks: List[Dict], stocks: List[str]):
    """Assert that no mock data is being used"""
    # Check that we're not just using the first N stocks from the list
    if qualified_stocks:
        qualified_tickers = [stock['ticker'] for stock in qualified_stocks]
        first_n_stocks = stocks[:len(qualified_tickers)]
        
        if qualified_tickers == first_n_stocks:
            raise AssertionError(
                f"MOCK DATA DETECTED: Qualified stocks {qualified_tickers} "
                f"match first {len(qualified_tickers)} stocks from list. "
                f"This indicates mock stock selection is being used!"
            )
    
    # Check that stocks have sentiment scores
    for stock in qualified_stocks:
        if 'sentiment' not in stock or stock['sentiment'] == 0.0:
            logging.warning(f"Stock {stock['ticker']} has zero sentiment - may indicate mock data")

def run_real_intraday_strategy(
    strategy: Dict,
    start_date: datetime,
    end_date: datetime,
    stocks: List[str],
    console_minimal: bool = False
) -> Dict:
    """Run a single intraday strategy with 100% real data"""
    
    strategy_id = strategy["id"]
    
    if console_minimal:
        print(f"Running strategy {strategy_id}/20: S{strategy_id} ({strategy['trend']}, stop={strategy['stop_pct']}%, take={strategy['take_pct']}%, threshold={strategy['score_threshold']})")
    
    # Get trading days
    trading_days = get_trading_days(start_date, end_date)
    
    # Initialize results tracking
    all_trades = []
    daily_pnl = []
    eod_forced_closes = 0
    daily_qualified_counts = []
    days_with_trades = 0
    
    # Get sentiment analyzer
    sentiment_analyzer = get_sentiment_analyzer()
    
    # Process each trading day
    for day in trading_days:
        day_trades = 0
        day_pnl = 0
        
        try:
            # REAL sentiment analysis screening - NO MOCK DATA, NO TOP_K LIMIT
            qualified_stocks = sentiment_analyzer.screen_stocks_by_sentiment(
                stocks=stocks,
                analysis_date=day.strftime('%Y-%m-%d'),
                min_sentiment=0.0,  # Not used anymore
                max_sentiment=1.0,  # Not used anymore
                min_news_count=2,  # Hard requirement
                score_threshold=float(strategy['score_threshold'])
            )
            
            # Assert no mock data is being used
            assert_no_mock_data(qualified_stocks, stocks)
            
            # Apply trend filter if enabled (using real Alpaca data)
            if strategy['trend'] == 'ON':
                qualified_stocks = apply_trend_filter_real(qualified_stocks, day.strftime('%Y-%m-%d'))
            
            if console_minimal:
                print(f"date={day.strftime('%Y-%m-%d')}, qualified={len(qualified_stocks)}, traded={day_trades}")
            
            # Simulate trades for qualified stocks
            for stock_data in qualified_stocks:
                ticker = stock_data['ticker']
                
                try:
                    # Get REAL intraday data from Alpaca
                    historical_data = get_historical_data(
                        ticker, 
                        day, 
                        day + timedelta(days=1),
                        timeframe='1Min'
                    )
                    
                    if historical_data is None or len(historical_data) == 0:
                        continue
                    
                    # Filter to market hours only (09:30-16:00 ET)
                    market_data = historical_data.between_time('09:30', '16:00')
                    
                    if len(market_data) == 0:
                        continue
                    
                    # Entry at 09:30 ET (or first available price after)
                    entry_price = market_data.iloc[0]['close']
                    entry_time = market_data.index[0]
                    
                    # Calculate position size
                    investment = 1_000_000  # $1M per stock as specified
                    shares = int(investment / entry_price)
                    
                    if shares == 0:
                        continue
                    
                    # Simulate intraday trade with EOD force close
                    trade_result = simulate_intraday_trade(
                        ticker=ticker,
                        entry_price=entry_price,
                        entry_time=entry_time,
                        shares=shares,
                        market_data=market_data,
                        stop_loss_pct=strategy['stop_pct'],
                        take_profit_pct=strategy['take_pct']
                    )
                    
                    if trade_result:
                        all_trades.append(trade_result)
                        day_trades += 1
                        day_pnl += trade_result['pnl']
                        
                        if trade_result['exit_reason'] == 'EOD':
                            eod_forced_closes += 1
                
                except Exception as e:
                    if not console_minimal:
                        logging.warning(f"Error processing {ticker} on {day}: {e}")
                    continue
            
            daily_pnl.append(day_pnl)
            daily_qualified_counts.append(len(qualified_stocks))
            
            if day_trades > 0:
                days_with_trades += 1
        
        except Exception as e:
            if not console_minimal:
                logging.error(f"Error processing day {day}: {e}")
            daily_pnl.append(0)
            continue
    
    # Calculate performance metrics
    results = calculate_strategy_performance(
        all_trades, daily_pnl, strategy, eod_forced_closes, 
        daily_qualified_counts, days_with_trades, len(trading_days),
        start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
    )
    
    if console_minimal:
        print(f"Strategy {strategy_id} finished (PnL=${results['total_pnl_usd']:,.2f}, Sharpe={results['sharpe_ratio']:.3f})")
    
    return results

def calculate_strategy_performance(
    trades: List[Dict], 
    daily_pnl: List[float], 
    strategy: Dict, 
    eod_forced_closes: int,
    daily_qualified_counts: List[int],
    days_with_trades: int,
    total_trading_days: int,
    start_date: str,
    end_date: str
) -> Dict:
    """Calculate comprehensive performance metrics for a strategy"""
    
    if not trades:
        avg_qualified = sum(daily_qualified_counts) / len(daily_qualified_counts) if daily_qualified_counts else 0
        return {
            'strategy_id': strategy['id'],
            'start_date': start_date,
            'end_date': end_date,
            'score_threshold': strategy['score_threshold'],
            'min_news_count': 2,
            'trend_filter': strategy['trend'],
            'stop_pct': strategy['stop_pct'],
            'take_pct': strategy['take_pct'],
            'qualified_count': avg_qualified,
            'days_with_trades': days_with_trades,
            'days_with_no_trades': total_trading_days - days_with_trades,
            'investment_per_stock_usd': 1_000_000,
            'hold_policy': 'EOD',
            'total_pnl_usd': 0,
            'cumulative_return_pct': 0,
            'trades_count': 0,
            'win_rate_pct': 0,
            'avg_pnl_per_trade_usd': 0,
            'profit_factor': 0,
            'max_drawdown_pct': 0,
            'sharpe_ratio': 0,
            'eod_forced_closes': 0,
            'status': 'OK'
        }
    
    # Basic metrics
    total_pnl = sum(trade['pnl'] for trade in trades)
    total_trades = len(trades)
    winning_trades = [trade for trade in trades if trade['pnl'] > 0]
    losing_trades = [trade for trade in trades if trade['pnl'] < 0]
    
    win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0
    avg_pnl_per_trade = total_pnl / total_trades if total_trades > 0 else 0
    
    # Profit factor
    gross_profit = sum(trade['pnl'] for trade in winning_trades)
    gross_loss = abs(sum(trade['pnl'] for trade in losing_trades))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0
    
    # Cumulative return (assuming total capital deployed)
    total_capital_deployed = sum(abs(trade['entry_price'] * trade['shares']) for trade in trades)
    cumulative_return_pct = (total_pnl / total_capital_deployed * 100) if total_capital_deployed > 0 else 0
    
    # Maximum drawdown
    cumulative_pnl = np.cumsum([trade['pnl'] for trade in trades])
    running_max = np.maximum.accumulate(cumulative_pnl)
    drawdown = (cumulative_pnl - running_max) / running_max * 100
    max_drawdown_pct = abs(np.min(drawdown)) if len(drawdown) > 0 else 0
    
    # Sharpe ratio (using daily returns)
    if len(daily_pnl) > 1:
        daily_returns = np.array(daily_pnl)
        if np.std(daily_returns) > 0:
            sharpe_ratio = np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(252)  # Annualized
        else:
            sharpe_ratio = 0
    else:
        sharpe_ratio = 0
    
    avg_qualified = sum(daily_qualified_counts) / len(daily_qualified_counts) if daily_qualified_counts else 0
    
    return {
        'strategy_id': strategy['id'],
        'start_date': start_date,
        'end_date': end_date,
        'score_threshold': strategy['score_threshold'],
        'min_news_count': 2,
        'trend_filter': strategy['trend'],
        'stop_pct': strategy['stop_pct'],
        'take_pct': strategy['take_pct'],
        'qualified_count': avg_qualified,
        'days_with_trades': days_with_trades,
        'days_with_no_trades': total_trading_days - days_with_trades,
        'investment_per_stock_usd': 1_000_000,
        'hold_policy': 'EOD',
        'total_pnl_usd': total_pnl,
        'cumulative_return_pct': cumulative_return_pct,
        'trades_count': total_trades,
        'win_rate_pct': win_rate,
        'avg_pnl_per_trade_usd': avg_pnl_per_trade,
        'profit_factor': profit_factor,
        'max_drawdown_pct': max_drawdown_pct,
        'sharpe_ratio': sharpe_ratio,
        'eod_forced_closes': eod_forced_closes,
        'status': 'OK'
    }

def export_results(results: List[Dict], output_file: str):
    """Export results to Excel or CSV file"""
    
    df = pd.DataFrame(results)
    
    # Ensure columns are in the specified order (updated for new format)
    column_order = [
        'strategy_id', 'start_date', 'end_date', 'score_threshold',
        'min_news_count', 'trend_filter', 'stop_pct', 'take_pct', 
        'qualified_count', 'days_with_trades', 'days_with_no_trades',
        'investment_per_stock_usd', 'hold_policy', 'total_pnl_usd',
        'cumulative_return_pct', 'trades_count', 'win_rate_pct',
        'avg_pnl_per_trade_usd', 'profit_factor', 'max_drawdown_pct',
        'sharpe_ratio', 'eod_forced_closes', 'status'
    ]
    
    df = df[column_order]
    
    # Export to file
    if output_file.endswith('.xlsx'):
        try:
            df.to_excel(output_file, index=False)
        except ImportError:
            # Fallback to CSV if openpyxl not available
            csv_file = output_file.replace('.xlsx', '.csv')
            df.to_csv(csv_file, index=False)
            print(f"Excel not available, saved as CSV: {csv_file}")
    else:
        df.to_csv(output_file, index=False)
    
    print(f"Results saved to: {output_file}")

def main():
    """Main batch runner function"""
    parser = argparse.ArgumentParser(
        description='Run 20 intraday trading strategies with 100% REAL data (no mock)',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--out', required=True, help='Output file path (.xlsx or .csv)')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'])
    parser.add_argument('--console-minimal', action='store_true', help='Minimal console output')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level, args.console_minimal)
    
    # Parse dates
    try:
        start_date = datetime.strptime(args.start, '%Y-%m-%d')
        end_date = datetime.strptime(args.end, '%Y-%m-%d')
    except ValueError as e:
        print(f"Error parsing dates: {e}")
        sys.exit(1)
    
    try:
        # Validate environment
        validate_environment()
        
        # Load stock universe
        stocks = load_stock_universe()
        
        # Initialize Finnhub pool
        finnhub_pool = get_finnhub_pool()
        
        if args.console_minimal:
            print(f"🚀 REAL DATA BATCH RUN: {len(STRATEGIES)} strategies from {args.start} to {args.end}")
            print(f"📊 Using {len(stocks)} stocks with REAL Finnhub sentiment analysis")
            finnhub_pool.print_usage_stats()
        
        # Run all strategies
        all_results = []
        
        for i, strategy in enumerate(STRATEGIES, 1):
            try:
                result = run_real_intraday_strategy(
                    strategy=strategy,
                    start_date=start_date,
                    end_date=end_date,
                    stocks=stocks,
                    console_minimal=args.console_minimal
                )
                all_results.append(result)
                
            except Exception as e:
                error_result = {
                    'strategy_id': strategy['id'],
                    'start_date': args.start,
                    'end_date': args.end,
                    'sentiment_min': strategy['sent_min'],
                    'sentiment_max': strategy['sent_max'],
                    'min_news_count': 2,
                    'trend_filter': strategy['trend'],
                    'stop_pct': strategy['stop_pct'],
                    'take_pct': strategy['take_pct'],
                    'top_k': strategy['top_k'],
                    'investment_per_stock_usd': 1_000_000,
                    'hold_policy': 'EOD',
                    'total_pnl_usd': 0,
                    'cumulative_return_pct': 0,
                    'trades_count': 0,
                    'win_rate_pct': 0,
                    'avg_pnl_per_trade_usd': 0,
                    'profit_factor': 0,
                    'max_drawdown_pct': 0,
                    'sharpe_ratio': 0,
                    'eod_forced_closes': 0,
                    'status': f'ERROR:{str(e)[:50]}'
                }
                all_results.append(error_result)
                
                if args.console_minimal:
                    print(f"Strategy {strategy['id']} failed: {str(e)[:50]}")
                else:
                    logging.error(f"Strategy {strategy['id']} failed: {e}")
        
        # Export results
        export_results(all_results, args.out)
        
        # Final API usage stats
        if args.console_minimal:
            print("\n🔑 FINAL API USAGE STATS:")
            finnhub_pool.print_usage_stats()
            
            successful = len([r for r in all_results if r['status'] == 'OK'])
            print(f"\n✅ Batch completed: {successful}/{len(STRATEGIES)} strategies successful")
            print(f"📁 Audit logs saved in: audit_logs/")
        
    except Exception as e:
        print(f"Fatal error: {e}")
        if not args.console_minimal:
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
