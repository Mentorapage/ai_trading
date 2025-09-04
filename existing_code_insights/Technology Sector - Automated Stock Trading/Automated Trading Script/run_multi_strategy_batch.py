#!/usr/bin/env python3
"""
MULTI-STRATEGY BATCH RUNNER (20 Strategies)
===========================================
Dual filters: Volume AND News/Sentiment for 20 distinct strategies
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
from volume_news_analyzer import VolumeNewsAnalyzer
from historical_backtest import get_historical_data
from run_real_strategy_batch import simulate_intraday_trade
from trading_core import load_stock_universe
import bootstrap_nltk  # noqa

# 20 Strategy configurations (exact as specified)
TWENTY_STRATEGIES = [
    {"id": "S01", "stop_pct": 3, "take_pct": 5, "min_sentiment": 0.10, "max_sentiment": 0.60},
    {"id": "S02", "stop_pct": 3, "take_pct": 8, "min_sentiment": 0.10, "max_sentiment": 0.60},
    {"id": "S03", "stop_pct": 3, "take_pct": 12, "min_sentiment": 0.20, "max_sentiment": 0.70},
    {"id": "S04", "stop_pct": 3, "take_pct": 20, "min_sentiment": 0.20, "max_sentiment": 0.70},
    {"id": "S05", "stop_pct": 5, "take_pct": 5, "min_sentiment": 0.10, "max_sentiment": 0.60},
    {"id": "S06", "stop_pct": 5, "take_pct": 8, "min_sentiment": 0.20, "max_sentiment": 0.70},
    {"id": "S07", "stop_pct": 5, "take_pct": 12, "min_sentiment": 0.20, "max_sentiment": 0.70},
    {"id": "S08", "stop_pct": 5, "take_pct": 20, "min_sentiment": 0.30, "max_sentiment": 0.80},
    {"id": "S09", "stop_pct": 7, "take_pct": 5, "min_sentiment": 0.10, "max_sentiment": 0.60},
    {"id": "S10", "stop_pct": 7, "take_pct": 8, "min_sentiment": 0.20, "max_sentiment": 0.70},
    {"id": "S11", "stop_pct": 7, "take_pct": 12, "min_sentiment": 0.30, "max_sentiment": 0.80},
    {"id": "S12", "stop_pct": 7, "take_pct": 20, "min_sentiment": 0.30, "max_sentiment": 0.80},
    {"id": "S13", "stop_pct": 10, "take_pct": 5, "min_sentiment": 0.10, "max_sentiment": 0.60},
    {"id": "S14", "stop_pct": 10, "take_pct": 8, "min_sentiment": 0.20, "max_sentiment": 0.70},
    {"id": "S15", "stop_pct": 10, "take_pct": 12, "min_sentiment": 0.30, "max_sentiment": 0.80},
    {"id": "S16", "stop_pct": 10, "take_pct": 20, "min_sentiment": 0.15, "max_sentiment": 0.65},
    {"id": "S17", "stop_pct": 4, "take_pct": 6, "min_sentiment": 0.15, "max_sentiment": 0.65},
    {"id": "S18", "stop_pct": 6, "take_pct": 9, "min_sentiment": 0.10, "max_sentiment": 0.60},
    {"id": "S19", "stop_pct": 8, "take_pct": 15, "min_sentiment": 0.20, "max_sentiment": 0.70},
    {"id": "S20", "stop_pct": 12, "take_pct": 20, "min_sentiment": 0.30, "max_sentiment": 0.80},
]

def setup_logging(log_level: str, console_progress: bool = False):
    """Setup logging configuration"""
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    if console_progress:
        # Minimal progress logging
        logging.basicConfig(
            level=level,
            format='[%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler('multi_strategy_batch.log'),
                logging.StreamHandler()
            ]
        )
    else:
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('multi_strategy_batch.log'),
                logging.StreamHandler()
            ]
        )

def get_trading_days(start_date: date, end_date: date) -> List[date]:
    """Get trading days using NYSE calendar"""
    nyse = mcal.get_calendar('NYSE')
    trading_days = nyse.valid_days(start_date=start_date, end_date=end_date)
    return [day.date() if hasattr(day, 'date') else day for day in trading_days]

def run_single_strategy(
    strategy: Dict,
    start_date: date,
    end_date: date,
    stocks: List[str],
    volume_news_analyzer: VolumeNewsAnalyzer,
    console_progress: bool = False
) -> Dict:
    """Run a single strategy with dual-filter logic"""
    
    strategy_id = strategy["id"]
    
    # Get trading days
    trading_days = get_trading_days(start_date, end_date)
    
    all_trades = []
    daily_pnl = []
    days_with_trades = 0
    
    # Exit reason counters
    closed_take_profit = 0
    closed_stop_loss = 0
    closed_eod = 0
    
    for day in trading_days:
        try:
            # Screen stocks using BOTH volume AND news/sentiment filters
            qualified_stocks = volume_news_analyzer.screen_stocks_by_volume_and_news(
                stocks=stocks,
                analysis_date=day.strftime('%Y-%m-%d'),
                min_news_count=2,  # Fixed requirement
                min_sentiment=strategy['min_sentiment'],
                max_sentiment=strategy['max_sentiment']
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
                    
                    # Entry at market open (09:30 ET)
                    entry_price = market_data['open'].iloc[0]
                    entry_time = market_data.index[0]
                    shares = int(1_000_000 / entry_price)  # $1M investment
                    
                    if shares == 0:
                        continue
                    
                    # Simulate intraday trade with SL/TP/EOD
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
                        
                        # Count exit reasons
                        exit_reason = trade_result['exit_reason']
                        if exit_reason == 'TAKE_PROFIT':
                            closed_take_profit += 1
                        elif exit_reason == 'STOP_LOSS':
                            closed_stop_loss += 1
                        elif exit_reason == 'EOD':
                            closed_eod += 1
                
                except Exception as e:
                    if not console_progress:
                        logging.warning(f"Error trading {ticker} on {day}: {e}")
                    continue
            
            daily_pnl.append(day_pnl)
            
            if day_trades > 0:
                days_with_trades += 1
                
        except Exception as e:
            if not console_progress:
                logging.error(f"Error processing day {day} for {strategy_id}: {e}")
            daily_pnl.append(0)
            continue
    
    # Calculate performance metrics
    results = calculate_strategy_performance(
        all_trades, daily_pnl, strategy, 
        closed_take_profit, closed_stop_loss, closed_eod,
        days_with_trades, len(trading_days),
        start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
    )
    
    return results

def calculate_strategy_performance(
    trades: List[Dict], 
    daily_pnl: List[float], 
    strategy: Dict, 
    closed_take_profit: int,
    closed_stop_loss: int,
    closed_eod: int,
    days_with_trades: int,
    total_trading_days: int,
    start_date: str,
    end_date: str
) -> Dict:
    """Calculate comprehensive performance metrics"""
    
    if not trades:
        return {
            'strategy_id': strategy['id'],
            'stop_pct': strategy['stop_pct'],
            'take_pct': strategy['take_pct'],
            'min_sentiment': strategy['min_sentiment'],
            'max_sentiment': strategy['max_sentiment'],
            'period_start': start_date,
            'period_end': end_date,
            'trades_count': 0,
            'pnl_usd': 0,
            'pnl_pct': 0,
            'win_rate_pct': 0,
            'loss_rate_pct': 0,
            'closed_take_profit': 0,
            'closed_stop_loss': 0,
            'closed_eod': 0,
            'avg_trade_return_pct': 0,
            'max_trade_gain_pct': 0,
            'max_trade_loss_pct': 0,
            'days_with_trades': 0,
            'days_with_no_trades': total_trading_days,
            'status': 'NO_TRADES'
        }
    
    # Calculate metrics
    total_pnl = sum(trade['pnl'] for trade in trades)
    total_investment = len(trades) * 1_000_000  # $1M per trade
    cumulative_return_pct = (total_pnl / total_investment * 100) if total_investment > 0 else 0
    
    # Win/Loss rates
    wins = [trade for trade in trades if trade['pnl'] > 0]
    losses = [trade for trade in trades if trade['pnl'] < 0]
    win_rate = len(wins) / len(trades) * 100 if trades else 0
    loss_rate = len(losses) / len(trades) * 100 if trades else 0
    
    # Trade return percentages
    trade_returns = [(trade['pnl'] / 1_000_000 * 100) for trade in trades]
    avg_trade_return = np.mean(trade_returns) if trade_returns else 0
    max_trade_gain = max(trade_returns) if trade_returns else 0
    max_trade_loss = min(trade_returns) if trade_returns else 0
    
    return {
        'strategy_id': strategy['id'],
        'stop_pct': strategy['stop_pct'],
        'take_pct': strategy['take_pct'],
        'min_sentiment': strategy['min_sentiment'],
        'max_sentiment': strategy['max_sentiment'],
        'period_start': start_date,
        'period_end': end_date,
        'trades_count': len(trades),
        'pnl_usd': total_pnl,
        'pnl_pct': cumulative_return_pct,
        'win_rate_pct': win_rate,
        'loss_rate_pct': loss_rate,
        'closed_take_profit': closed_take_profit,
        'closed_stop_loss': closed_stop_loss,
        'closed_eod': closed_eod,
        'avg_trade_return_pct': avg_trade_return,
        'max_trade_gain_pct': max_trade_gain,
        'max_trade_loss_pct': max_trade_loss,
        'days_with_trades': days_with_trades,
        'days_with_no_trades': total_trading_days - days_with_trades,
        'status': 'OK'
    }

def export_weekly_results(results: List[Dict], output_file: str, stocks: List[str]):
    """Export weekly results to Excel with exact schema"""
    
    # Create DataFrame with exact column order
    df = pd.DataFrame(results)
    
    column_order = [
        'strategy_id', 'stop_pct', 'take_pct', 'min_sentiment', 'max_sentiment',
        'period_start', 'period_end',
        'trades_count', 'pnl_usd', 'pnl_pct',
        'win_rate_pct', 'loss_rate_pct',
        'closed_take_profit', 'closed_stop_loss', 'closed_eod',
        'avg_trade_return_pct', 'max_trade_gain_pct', 'max_trade_loss_pct',
        'days_with_trades', 'days_with_no_trades', 'status'
    ]
    
    # Reorder columns
    df = df.reindex(columns=column_order)
    
    # Create Excel with multiple sheets
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # Main strategies sheet
        df.to_excel(writer, sheet_name='Strategies', index=False)
        
        # Metadata sheet
        metadata = pd.DataFrame([{
            'generated_at_et': datetime.now().strftime('%Y-%m-%d %H:%M:%S ET'),
            'universe_size': len(stocks),
            'notes': 'Dual filters: Volume (yesterday > MA20) AND News/Sentiment (≥2 articles, weighted sentiment in range)'
        }])
        metadata.to_excel(writer, sheet_name='Metadata', index=False)
    
    # Also create CSV
    csv_file = output_file.replace('.xlsx', '.csv')
    df.to_csv(csv_file, index=False)
    
    logging.info(f"Weekly results exported to {output_file}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Multi-Strategy Weekly Batch Runner (20 Strategies)')
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--out', required=True, help='Output file path')
    parser.add_argument('--log-level', default='INFO', help='Logging level')
    parser.add_argument('--console-progress', action='store_true', help='Progress-only console output')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level, args.console_progress)
    
    # Parse dates
    start_date = datetime.strptime(args.start, '%Y-%m-%d').date()
    end_date = datetime.strptime(args.end, '%Y-%m-%d').date()
    
    # Load stock universe
    stocks = load_stock_universe()
    
    print(f"🚀 WEEKLY MULTI-STRATEGY BATCH (20 Strategies)")
    print(f"Dual Filters: Volume + News/Sentiment")
    print(f"Period: {start_date} to {end_date}")
    print(f"Stocks: {len(stocks)}")
    print()
    
    # Initialize dual-filter analyzer (shared across all strategies)
    volume_news_analyzer = VolumeNewsAnalyzer()
    
    # Run all 20 strategies
    all_results = []
    start_time = time.time()
    
    for i, strategy in enumerate(TWENTY_STRATEGIES, 1):
        strategy_start_time = time.time()
        
        if args.console_progress:
            elapsed_min = (time.time() - start_time) / 60
            if i == 1 or elapsed_min >= 5 * ((i-1) // 5):  # Progress every ~5 minutes
                print(f"[INFO] Weekly batch progress: {i-1}/20 strategies done; running {strategy['id']} (-{strategy['stop_pct']}%/+{strategy['take_pct']}%, sentiment {strategy['min_sentiment']:.2f}–{strategy['max_sentiment']:.2f}) ...")
        
        try:
            result = run_single_strategy(
                strategy=strategy,
                start_date=start_date,
                end_date=end_date,
                stocks=stocks,
                volume_news_analyzer=volume_news_analyzer,
                console_progress=args.console_progress
            )
            
            all_results.append(result)
            
            if not args.console_progress:
                strategy_time = (time.time() - strategy_start_time) / 60
                logging.info(f"Strategy {strategy['id']} completed in {strategy_time:.1f} min - PnL: ${result['pnl_usd']:,.2f}")
            
        except Exception as e:
            logging.error(f"Strategy {strategy['id']} failed: {e}")
            # Add error result
            error_result = {
                'strategy_id': strategy['id'],
                'stop_pct': strategy['stop_pct'],
                'take_pct': strategy['take_pct'],
                'min_sentiment': strategy['min_sentiment'],
                'max_sentiment': strategy['max_sentiment'],
                'period_start': start_date.strftime('%Y-%m-%d'),
                'period_end': end_date.strftime('%Y-%m-%d'),
                'trades_count': 0,
                'pnl_usd': 0,
                'pnl_pct': 0,
                'win_rate_pct': 0,
                'loss_rate_pct': 0,
                'closed_take_profit': 0,
                'closed_stop_loss': 0,
                'closed_eod': 0,
                'avg_trade_return_pct': 0,
                'max_trade_gain_pct': 0,
                'max_trade_loss_pct': 0,
                'days_with_trades': 0,
                'days_with_no_trades': 0,
                'status': f'ERROR: {str(e)[:50]}'
            }
            all_results.append(error_result)
    
    # Export results
    export_weekly_results(all_results, args.out, stocks)
    
    total_time = (time.time() - start_time) / 60
    print(f"✅ Weekly multi-strategy batch completed in {total_time:.1f} minutes")
    print(f"📁 Results: {args.out}")

if __name__ == "__main__":
    main()
