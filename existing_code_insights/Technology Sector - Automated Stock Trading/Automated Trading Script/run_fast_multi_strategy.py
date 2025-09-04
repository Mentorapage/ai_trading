#!/usr/bin/env python3
"""
FAST MULTI-STRATEGY BATCH RUNNER
================================
Optimized version with shared screening and better progress reporting
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

def get_trading_days(start_date: date, end_date: date) -> List[date]:
    """Get trading days using NYSE calendar"""
    nyse = mcal.get_calendar('NYSE')
    trading_days = nyse.valid_days(start_date=start_date, end_date=end_date)
    return [day.date() if hasattr(day, 'date') else day for day in trading_days]

def screen_all_days_all_ranges(
    volume_news_analyzer: VolumeNewsAnalyzer,
    stocks: List[str],
    trading_days: List[date]
) -> Dict:
    """Pre-screen all days for all possible sentiment ranges to avoid redundant API calls"""
    
    print(f"📊 Pre-screening {len(trading_days)} days for all sentiment ranges...")
    
    # Get all unique sentiment ranges from strategies
    sentiment_ranges = set()
    for strategy in TWENTY_STRATEGIES:
        sentiment_ranges.add((strategy['min_sentiment'], strategy['max_sentiment']))
    
    print(f"🎯 Found {len(sentiment_ranges)} unique sentiment ranges")
    
    daily_screenings = {}
    
    for day in trading_days:
        day_str = day.strftime('%Y-%m-%d')
        print(f"📅 Screening {day_str}...")
        
        daily_screenings[day_str] = {}
        
        for min_sent, max_sent in sentiment_ranges:
            try:
                qualified_stocks = volume_news_analyzer.screen_stocks_by_volume_and_news(
                    stocks=stocks,
                    analysis_date=day_str,
                    min_news_count=2,
                    min_sentiment=min_sent,
                    max_sentiment=max_sent
                )
                
                daily_screenings[day_str][(min_sent, max_sent)] = qualified_stocks
                print(f"  Range {min_sent:.2f}-{max_sent:.2f}: {len(qualified_stocks)} qualified")
                
            except Exception as e:
                print(f"  ❌ Range {min_sent:.2f}-{max_sent:.2f}: Error - {e}")
                daily_screenings[day_str][(min_sent, max_sent)] = []
    
    return daily_screenings

def run_strategy_with_prescreened_data(
    strategy: Dict,
    trading_days: List[date],
    daily_screenings: Dict
) -> Dict:
    """Run a strategy using pre-screened data"""
    
    strategy_id = strategy["id"]
    sentiment_key = (strategy['min_sentiment'], strategy['max_sentiment'])
    
    all_trades = []
    days_with_trades = 0
    
    # Exit reason counters
    closed_take_profit = 0
    closed_stop_loss = 0
    closed_eod = 0
    
    for day in trading_days:
        day_str = day.strftime('%Y-%m-%d')
        
        # Get pre-screened qualified stocks
        qualified_stocks = daily_screenings.get(day_str, {}).get(sentiment_key, [])
        
        if not qualified_stocks:
            continue
        
        day_trades = 0
        
        # Trade ALL qualified stocks
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
                continue
        
        if day_trades > 0:
            days_with_trades += 1
    
    # Calculate performance metrics
    if not all_trades:
        return {
            'strategy_id': strategy['id'],
            'stop_pct': strategy['stop_pct'],
            'take_pct': strategy['take_pct'],
            'min_sentiment': strategy['min_sentiment'],
            'max_sentiment': strategy['max_sentiment'],
            'period_start': trading_days[0].strftime('%Y-%m-%d'),
            'period_end': trading_days[-1].strftime('%Y-%m-%d'),
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
            'days_with_no_trades': len(trading_days),
            'status': 'NO_TRADES'
        }
    
    # Calculate metrics
    total_pnl = sum(trade['pnl'] for trade in all_trades)
    total_investment = len(all_trades) * 1_000_000  # $1M per trade
    cumulative_return_pct = (total_pnl / total_investment * 100) if total_investment > 0 else 0
    
    # Win/Loss rates
    wins = [trade for trade in all_trades if trade['pnl'] > 0]
    losses = [trade for trade in all_trades if trade['pnl'] < 0]
    win_rate = len(wins) / len(all_trades) * 100 if all_trades else 0
    loss_rate = len(losses) / len(all_trades) * 100 if all_trades else 0
    
    # Trade return percentages
    trade_returns = [(trade['pnl'] / 1_000_000 * 100) for trade in all_trades]
    avg_trade_return = np.mean(trade_returns) if trade_returns else 0
    max_trade_gain = max(trade_returns) if trade_returns else 0
    max_trade_loss = min(trade_returns) if trade_returns else 0
    
    return {
        'strategy_id': strategy['id'],
        'stop_pct': strategy['stop_pct'],
        'take_pct': strategy['take_pct'],
        'min_sentiment': strategy['min_sentiment'],
        'max_sentiment': strategy['max_sentiment'],
        'period_start': trading_days[0].strftime('%Y-%m-%d'),
        'period_end': trading_days[-1].strftime('%Y-%m-%d'),
        'trades_count': len(all_trades),
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
        'days_with_no_trades': len(trading_days) - days_with_trades,
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
    
    print(f"✅ Results exported to {output_file}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Fast Multi-Strategy Weekly Batch Runner')
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--out', required=True, help='Output file path')
    
    args = parser.parse_args()
    
    # Parse dates
    start_date = datetime.strptime(args.start, '%Y-%m-%d').date()
    end_date = datetime.strptime(args.end, '%Y-%m-%d').date()
    
    # Load stock universe
    stocks = load_stock_universe()
    
    print(f"🚀 FAST MULTI-STRATEGY BATCH (20 Strategies)")
    print(f"Dual Filters: Volume + News/Sentiment")
    print(f"Period: {start_date} to {end_date}")
    print(f"Stocks: {len(stocks)}")
    print()
    
    # Get trading days
    trading_days = get_trading_days(start_date, end_date)
    print(f"📅 Trading days: {len(trading_days)}")
    
    # Initialize analyzer
    volume_news_analyzer = VolumeNewsAnalyzer()
    
    # Pre-screen all days for all sentiment ranges (OPTIMIZATION)
    daily_screenings = screen_all_days_all_ranges(volume_news_analyzer, stocks, trading_days)
    
    print(f"\n🎯 Running 20 strategies with pre-screened data...")
    
    # Run all 20 strategies using pre-screened data
    all_results = []
    start_time = time.time()
    
    for i, strategy in enumerate(TWENTY_STRATEGIES, 1):
        print(f"[{i:2d}/20] {strategy['id']}: -{strategy['stop_pct']}%/+{strategy['take_pct']}%, sentiment {strategy['min_sentiment']:.2f}-{strategy['max_sentiment']:.2f}")
        
        try:
            result = run_strategy_with_prescreened_data(strategy, trading_days, daily_screenings)
            all_results.append(result)
            
            print(f"         → {result['trades_count']} trades, PnL: ${result['pnl_usd']:,.0f}")
            
        except Exception as e:
            print(f"         → ERROR: {e}")
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
    print(f"\n✅ Fast multi-strategy batch completed in {total_time:.1f} minutes")
    print(f"📁 Results: {args.out}")

if __name__ == "__main__":
    main()
