#!/usr/bin/env python3
"""
VOLUME-ONLY BATCH RUNNER
========================
Single filter: volume_yesterday > volume_ma20 (NO other signals)
"""

import sys
import os
import argparse
import logging
from datetime import datetime, date, time as dt_time
import pandas as pd
import numpy as np
from pathlib import Path
import time
from typing import Dict, List, Optional
import pandas_market_calendars as mcal

# Import existing modules
from volume_only_analyzer import VolumeOnlyAnalyzer
from historical_backtest import get_historical_data
from run_real_strategy_batch import simulate_intraday_trade
from trading_core import load_stock_universe
import bootstrap_nltk  # noqa

# Single strategy configuration (volume-only)
VOLUME_ONLY_STRATEGY = {
    "id": "VOL01", 
    "name": "Volume Only", 
    "stop_pct": 5, 
    "take_pct": 10,
    "description": "Trade if volume_yesterday > volume_ma20"
}

def setup_logging(log_level: str, console_minimal: bool = False):
    """Setup logging configuration"""
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    if console_minimal:
        logging.basicConfig(
            level=level,
            format='%(message)s',
            handlers=[logging.StreamHandler()]
        )
    else:
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('volume_only_batch.log'),
                logging.StreamHandler()
            ]
        )

def get_trading_days(start_date: date, end_date: date) -> List[date]:
    """Get trading days using NYSE calendar"""
    nyse = mcal.get_calendar('NYSE')
    trading_days = nyse.valid_days(start_date=start_date, end_date=end_date)
    return [day.date() if hasattr(day, 'date') else day for day in trading_days]

def run_volume_only_strategy(
    strategy: Dict,
    start_date: date,
    end_date: date,
    stocks: List[str],
    console_minimal: bool = False
) -> Dict:
    """Run the single volume-only strategy"""
    
    strategy_id = strategy["id"]
    
    if console_minimal:
        print(f"Running strategy {strategy_id}: Volume Only (yesterday > MA20)")
    
    # Initialize volume-only analyzer
    volume_analyzer = VolumeOnlyAnalyzer()
    
    # Get trading days
    trading_days = get_trading_days(start_date, end_date)
    
    all_trades = []
    daily_pnl = []
    eod_forced_closes = 0
    days_with_trades = 0
    
    for day in trading_days:
        try:
            # Screen stocks using ONLY volume filter
            qualified_stocks = volume_analyzer.screen_stocks_by_volume_only(
                stocks=stocks,
                analysis_date=day.strftime('%Y-%m-%d')
            )
            
            day_trades = 0
            day_pnl = 0
            
            # Trade ALL qualified stocks (no limits)
            for stock_data in qualified_stocks:
                ticker = stock_data['ticker']
                
                try:
                    # Get intraday market data
                    market_data = get_historical_data(
                        ticker=ticker,
                        start_date=datetime.combine(day, dt_time(9, 30)),
                        end_date=datetime.combine(day, dt_time(16, 0)),
                        timeframe='1Min'
                    )
                    
                    if len(market_data) == 0:
                        continue
                    
                    # Entry at market open
                    entry_price = market_data['open'].iloc[0]
                    entry_time = market_data.index[0]
                    shares = int(1_000_000 / entry_price)  # $1M investment
                    
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
                        day_pnl += trade_result['pnl']
                        day_trades += 1
                        
                        if trade_result['exit_reason'] == 'EOD':
                            eod_forced_closes += 1
                
                except Exception as e:
                    logging.warning(f"Error trading {ticker} on {day}: {e}")
                    continue
            
            daily_pnl.append(day_pnl)
            
            if day_trades > 0:
                days_with_trades += 1
            
            if console_minimal:
                print(f"date={day.strftime('%Y-%m-%d')}, passed={len(qualified_stocks)}, traded={day_trades}")
                
        except Exception as e:
            if not console_minimal:
                logging.error(f"Error processing day {day}: {e}")
            daily_pnl.append(0)
            continue
    
    # Calculate performance metrics
    results = calculate_volume_only_performance(
        all_trades, daily_pnl, strategy, eod_forced_closes, 
        days_with_trades, len(trading_days),
        start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
    )
    
    if console_minimal:
        print(f"Strategy {strategy_id} finished (PnL=${results['total_pnl_usd']:,.2f}, Return={results['cumulative_return_pct']*100:+.2f}%)")
    
    return results

def calculate_volume_only_performance(
    trades: List[Dict], 
    daily_pnl: List[float], 
    strategy: Dict, 
    eod_forced_closes: int,
    days_with_trades: int,
    total_trading_days: int,
    start_date: str,
    end_date: str
) -> Dict:
    """Calculate performance metrics for volume-only strategy"""
    
    if not trades:
        return {
            'strategy_id': strategy['id'],
            'period_start': start_date,
            'period_end': end_date,
            'decision_time_et': '09:30:00 EDT',
            'total_pnl_usd': 0,
            'cumulative_return_pct': 0,
            'trades_count': 0,
            'win_rate_pct': 0,
            'forced_closes': 0,
            'days_with_trades': 0,
            'days_with_no_trades': total_trading_days,
            'status': 'NO_TRADES'
        }
    
    # Calculate metrics
    total_pnl = sum(trade['pnl'] for trade in trades)
    total_investment = len(trades) * 1_000_000  # $1M per trade
    cumulative_return_pct = total_pnl / total_investment if total_investment > 0 else 0
    
    wins = [trade for trade in trades if trade['pnl'] > 0]
    win_rate = len(wins) / len(trades) * 100 if trades else 0
    
    return {
        'strategy_id': strategy['id'],
        'period_start': start_date,
        'period_end': end_date,
        'decision_time_et': '09:30:00 EDT',
        'total_pnl_usd': total_pnl,
        'cumulative_return_pct': cumulative_return_pct,
        'trades_count': len(trades),
        'win_rate_pct': win_rate,
        'forced_closes': eod_forced_closes,
        'days_with_trades': days_with_trades,
        'days_with_no_trades': total_trading_days - days_with_trades,
        'status': 'OK'
    }

def export_volume_only_results(results: List[Dict], output_file: str):
    """Export ultra-minimal results to Excel/CSV"""
    df = pd.DataFrame(results)
    
    # Ultra-minimal column order (NO ATR, trend, news, sentiment, etc.)
    column_order = [
        'strategy_id', 'period_start', 'period_end', 'decision_time_et',
        'total_pnl_usd', 'cumulative_return_pct', 'trades_count', 'win_rate_pct',
        'forced_closes', 'days_with_trades', 'days_with_no_trades', 'status'
    ]
    
    # Reorder columns
    df = df.reindex(columns=column_order)
    
    # Export to Excel and CSV
    if output_file.endswith('.xlsx'):
        df.to_excel(output_file, index=False)
        csv_file = output_file.replace('.xlsx', '.csv')
        df.to_csv(csv_file, index=False)
    else:
        df.to_csv(output_file, index=False)
    
    logging.info(f"Results exported to {output_file}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Volume-Only Strategy Batch Runner (Single Filter)')
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--out', required=True, help='Output file path')
    parser.add_argument('--log-level', default='INFO', help='Logging level')
    parser.add_argument('--console-minimal', action='store_true', help='Minimal console output')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level, args.console_minimal)
    
    # Parse dates
    start_date = datetime.strptime(args.start, '%Y-%m-%d').date()
    end_date = datetime.strptime(args.end, '%Y-%m-%d').date()
    
    # Load stock universe
    stocks = load_stock_universe()
    
    print(f"🚀 VOLUME-ONLY STRATEGY (Single Filter)")
    print(f"Filter: volume_yesterday > volume_ma20")
    print(f"Period: {start_date} to {end_date}")
    print(f"Stocks: {len(stocks)}")
    print()
    
    # Run the single volume-only strategy
    try:
        result = run_volume_only_strategy(
            strategy=VOLUME_ONLY_STRATEGY,
            start_date=start_date,
            end_date=end_date,
            stocks=stocks,
            console_minimal=args.console_minimal
        )
        
        # Export results
        export_volume_only_results([result], args.out)
        
        print(f"✅ Volume-only batch completed. Results: {args.out}")
        
    except Exception as e:
        logging.error(f"Volume-only strategy failed: {e}")

if __name__ == "__main__":
    main()
