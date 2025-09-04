#!/usr/bin/env python3
"""
SIMPLIFIED STRATEGY BATCH RUNNER
===============================
Volume + News/Sentiment filters ONLY (no ATR, no MA20/trend, no top_k)
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
from simplified_sentiment_analyzer import SimplifiedSentimentAnalyzer
from historical_backtest import get_historical_data
from run_real_strategy_batch import simulate_intraday_trade
from trading_core import load_stock_universe
import bootstrap_nltk  # noqa

# Simplified strategy configurations (Volume + News/Sentiment only)
SIMPLIFIED_STRATEGIES = [
    {"id": "S01", "min_news_count": 2, "min_sentiment": 0.1, "max_sentiment": 0.7, "score_threshold": None, "volume_multiplier_min": 1.2, "volume_z_min": 0.5, "stop_pct": 3, "take_pct": 5},
    {"id": "S02", "min_news_count": 2, "min_sentiment": 0.2, "max_sentiment": 0.8, "score_threshold": None, "volume_multiplier_min": 1.5, "volume_z_min": 0.8, "stop_pct": 5, "take_pct": 7},
    {"id": "S03", "min_news_count": 3, "min_sentiment": 0.3, "max_sentiment": 0.9, "score_threshold": 0.4, "volume_multiplier_min": 1.0, "volume_z_min": 0.3, "stop_pct": 4, "take_pct": 6},
    {"id": "S04", "min_news_count": 1, "min_sentiment": 0.0, "max_sentiment": 1.0, "score_threshold": 0.5, "volume_multiplier_min": 2.0, "volume_z_min": 1.0, "stop_pct": 6, "take_pct": 8},
    {"id": "S05", "min_news_count": 2, "min_sentiment": 0.15, "max_sentiment": 0.85, "score_threshold": 0.35, "volume_multiplier_min": 1.3, "volume_z_min": 0.6, "stop_pct": 5, "take_pct": 10}
]

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
                logging.FileHandler('simplified_batch.log'),
                logging.StreamHandler()
            ]
        )

def get_trading_days(start_date: date, end_date: date) -> List[date]:
    """Get trading days using NYSE calendar"""
    nyse = mcal.get_calendar('NYSE')
    trading_days = nyse.valid_days(start_date=start_date, end_date=end_date)
    return [day.date() if hasattr(day, 'date') else day for day in trading_days]

def run_simplified_strategy(
    strategy: Dict,
    start_date: date,
    end_date: date,
    stocks: List[str],
    console_minimal: bool = False
) -> Dict:
    """Run a single simplified strategy"""
    
    strategy_id = strategy["id"]
    
    if console_minimal:
        print(f"Running strategy {strategy_id}: News({strategy['min_news_count']}+, {strategy['min_sentiment']}-{strategy['max_sentiment']}) + Volume({strategy['volume_multiplier_min']}x/{strategy['volume_z_min']}z)")
    
    # Initialize sentiment analyzer with strategy config
    sentiment_analyzer = SimplifiedSentimentAnalyzer()
    sentiment_analyzer.min_news_count = strategy['min_news_count']
    sentiment_analyzer.min_sentiment = strategy['min_sentiment']
    sentiment_analyzer.max_sentiment = strategy['max_sentiment']
    sentiment_analyzer.volume_multiplier_min = strategy['volume_multiplier_min']
    sentiment_analyzer.volume_z_min = strategy['volume_z_min']
    
    # Get trading days
    trading_days = get_trading_days(start_date, end_date)
    
    all_trades = []
    daily_pnl = []
    eod_forced_closes = 0
    daily_qualified_counts = []
    days_with_trades = 0
    
    for day in trading_days:
        try:
            # Screen stocks using simplified filters
            qualified_stocks = sentiment_analyzer.screen_stocks_by_filters(
                stocks=stocks,
                analysis_date=day.strftime('%Y-%m-%d'),
                score_threshold=strategy.get('score_threshold')
            )
            
            daily_qualified_counts.append(len(qualified_stocks))
            day_trades = 0
            day_pnl = 0
            
            # Trade ALL qualified stocks (no top_k limit)
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
                print(f"date={day.strftime('%Y-%m-%d')}, qualified={len(qualified_stocks)}, traded={day_trades}")
                
        except Exception as e:
            if not console_minimal:
                logging.error(f"Error processing day {day}: {e}")
            daily_pnl.append(0)
            daily_qualified_counts.append(0)
            continue
    
    # Calculate performance metrics
    results = calculate_simplified_performance(
        all_trades, daily_pnl, strategy, eod_forced_closes, 
        daily_qualified_counts, days_with_trades, len(trading_days),
        start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
    )
    
    if console_minimal:
        print(f"Strategy {strategy_id} finished (PnL=${results['total_pnl_usd']:,.2f}, Return={results['cumulative_return_pct']*100:+.2f}%)")
    
    return results

def calculate_simplified_performance(
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
    """Calculate performance metrics for simplified strategy"""
    
    if not trades:
        avg_qualified = sum(daily_qualified_counts) / len(daily_qualified_counts) if daily_qualified_counts else 0
        return {
            'strategy_id': strategy['id'],
            'period_start': start_date,
            'period_end': end_date,
            'decision_time_et': '09:30:00 EDT',
            'min_news_count': strategy['min_news_count'],
            'min_sentiment': strategy['min_sentiment'],
            'max_sentiment': strategy['max_sentiment'],
            'score_threshold': strategy.get('score_threshold'),
            'volume_multiplier_min': strategy['volume_multiplier_min'],
            'volume_z_min': strategy['volume_z_min'],
            'total_pnl_usd': 0,
            'cumulative_return_pct': 0,
            'trades_count': 0,
            'win_rate_pct': 0,
            'avg_pnl_per_trade_usd': 0,
            'profit_factor': 0,
            'max_drawdown_pct': 0,
            'sharpe_ratio': 0,
            'forced_closes': 0,
            'avg_qualified_per_day': avg_qualified,
            'days_with_no_trade': total_trading_days - days_with_trades,
            'status': 'NO_TRADES'
        }
    
    # Calculate metrics
    total_pnl = sum(trade['pnl'] for trade in trades)
    total_investment = len(trades) * 1_000_000  # $1M per trade
    cumulative_return_pct = total_pnl / total_investment if total_investment > 0 else 0
    
    wins = [trade for trade in trades if trade['pnl'] > 0]
    losses = [trade for trade in trades if trade['pnl'] <= 0]
    
    win_rate = len(wins) / len(trades) * 100 if trades else 0
    avg_pnl_per_trade = total_pnl / len(trades) if trades else 0
    
    # Profit factor
    gross_profit = sum(trade['pnl'] for trade in wins) if wins else 0
    gross_loss = abs(sum(trade['pnl'] for trade in losses)) if losses else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0)
    
    # Max drawdown
    cumulative_pnl = 0
    peak = 0
    max_drawdown = 0
    
    for pnl in daily_pnl:
        cumulative_pnl += pnl
        if cumulative_pnl > peak:
            peak = cumulative_pnl
        drawdown = (peak - cumulative_pnl) / total_investment * 100 if total_investment > 0 else 0
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    
    # Sharpe ratio (simplified)
    if len(daily_pnl) > 1:
        daily_returns = [pnl / 1_000_000 for pnl in daily_pnl]  # Normalize by daily investment
        avg_return = np.mean(daily_returns)
        std_return = np.std(daily_returns)
        sharpe_ratio = (avg_return / std_return * np.sqrt(252)) if std_return > 0 else 0
    else:
        sharpe_ratio = 0
    
    avg_qualified = sum(daily_qualified_counts) / len(daily_qualified_counts) if daily_qualified_counts else 0
    
    return {
        'strategy_id': strategy['id'],
        'period_start': start_date,
        'period_end': end_date,
        'decision_time_et': '09:30:00 EDT',
        'min_news_count': strategy['min_news_count'],
        'min_sentiment': strategy['min_sentiment'],
        'max_sentiment': strategy['max_sentiment'],
        'score_threshold': strategy.get('score_threshold'),
        'volume_multiplier_min': strategy['volume_multiplier_min'],
        'volume_z_min': strategy['volume_z_min'],
        'total_pnl_usd': total_pnl,
        'cumulative_return_pct': cumulative_return_pct,
        'trades_count': len(trades),
        'win_rate_pct': win_rate,
        'avg_pnl_per_trade_usd': avg_pnl_per_trade,
        'profit_factor': profit_factor,
        'max_drawdown_pct': max_drawdown,
        'sharpe_ratio': sharpe_ratio,
        'forced_closes': eod_forced_closes,
        'avg_qualified_per_day': avg_qualified,
        'days_with_no_trade': total_trading_days - days_with_trades,
        'status': 'OK'
    }

def export_simplified_results(results: List[Dict], output_file: str):
    """Export simplified results to Excel/CSV"""
    df = pd.DataFrame(results)
    
    # Column order for simplified results
    column_order = [
        'strategy_id', 'period_start', 'period_end', 'decision_time_et',
        'min_news_count', 'min_sentiment', 'max_sentiment', 'score_threshold',
        'volume_multiplier_min', 'volume_z_min',
        'total_pnl_usd', 'cumulative_return_pct', 'trades_count', 'win_rate_pct',
        'avg_pnl_per_trade_usd', 'profit_factor', 'max_drawdown_pct', 'sharpe_ratio',
        'forced_closes', 'avg_qualified_per_day', 'days_with_no_trade', 'status'
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
    parser = argparse.ArgumentParser(description='Simplified Strategy Batch Runner (Volume + News/Sentiment only)')
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
    
    print(f"🚀 SIMPLIFIED STRATEGY BATCH (Volume + News/Sentiment Only)")
    print(f"Period: {start_date} to {end_date}")
    print(f"Strategies: {len(SIMPLIFIED_STRATEGIES)}")
    print(f"Stocks: {len(stocks)}")
    print()
    
    # Run all strategies
    all_results = []
    
    for i, strategy in enumerate(SIMPLIFIED_STRATEGIES, 1):
        try:
            result = run_simplified_strategy(
                strategy=strategy,
                start_date=start_date,
                end_date=end_date,
                stocks=stocks,
                console_minimal=args.console_minimal
            )
            all_results.append(result)
            
        except Exception as e:
            logging.error(f"Strategy {strategy['id']} failed: {e}")
            continue
    
    # Export results
    export_simplified_results(all_results, args.out)
    
    print(f"✅ Batch completed. Results: {args.out}")

if __name__ == "__main__":
    main()
