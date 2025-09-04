#!/usr/bin/env python3
"""
FULL STRATEGY RESULTS EXCEL GENERATOR
=====================================
Re-run S01-S20 backtest for 2024-11-11 → 2025-08-20 and create comprehensive Excel report
with BOTH strategy configuration parameters AND trading results in one table.

Expected outputs:
- Trade count: ~13,444 (baseline total)
- Total PnL: $1,964,340.37 ± 0.01
- Excel file: reports/strategies_S01-S20_results.xlsx
"""

import os
import sys
import csv
import argparse
import hashlib
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, date, time as dt_time
from typing import Dict, List
import pandas_market_calendars as mcal
import logging
import time

# Import existing modules
from trading_core import load_stock_universe
from historical_backtest import get_historical_data
from run_real_strategy_batch import simulate_intraday_trade
from volume_news_analyzer import VolumeNewsAnalyzer

# S01-S20 Strategy definitions (exact baseline configurations)
STRATEGIES: List[Dict] = [
    {"id": "S01", "stop_pct": 3, "take_pct": 5,  "min_sentiment": 0.10, "max_sentiment": 0.60},
    {"id": "S02", "stop_pct": 3, "take_pct": 8,  "min_sentiment": 0.10, "max_sentiment": 0.60},
    {"id": "S03", "stop_pct": 3, "take_pct": 12, "min_sentiment": 0.20, "max_sentiment": 0.70},
    {"id": "S04", "stop_pct": 3, "take_pct": 20, "min_sentiment": 0.20, "max_sentiment": 0.70},
    {"id": "S05", "stop_pct": 5, "take_pct": 5,  "min_sentiment": 0.10, "max_sentiment": 0.60},
    {"id": "S06", "stop_pct": 5, "take_pct": 8,  "min_sentiment": 0.20, "max_sentiment": 0.70},
    {"id": "S07", "stop_pct": 5, "take_pct": 12, "min_sentiment": 0.20, "max_sentiment": 0.70},
    {"id": "S08", "stop_pct": 5, "take_pct": 20, "min_sentiment": 0.30, "max_sentiment": 0.80},
    {"id": "S09", "stop_pct": 7, "take_pct": 5,  "min_sentiment": 0.10, "max_sentiment": 0.60},
    {"id": "S10", "stop_pct": 7, "take_pct": 8,  "min_sentiment": 0.20, "max_sentiment": 0.70},
    {"id": "S11", "stop_pct": 7, "take_pct": 12, "min_sentiment": 0.30, "max_sentiment": 0.80},
    {"id": "S12", "stop_pct": 7, "take_pct": 20, "min_sentiment": 0.30, "max_sentiment": 0.80},
    {"id": "S13", "stop_pct": 10, "take_pct": 5,  "min_sentiment": 0.10, "max_sentiment": 0.60},
    {"id": "S14", "stop_pct": 10, "take_pct": 8,  "min_sentiment": 0.20, "max_sentiment": 0.70},
    {"id": "S15", "stop_pct": 10, "take_pct": 12, "min_sentiment": 0.30, "max_sentiment": 0.80},
    {"id": "S16", "stop_pct": 10, "take_pct": 20, "min_sentiment": 0.15, "max_sentiment": 0.65},
    {"id": "S17", "stop_pct": 4,  "take_pct": 6,  "min_sentiment": 0.15, "max_sentiment": 0.65},
    {"id": "S18", "stop_pct": 6,  "take_pct": 9,  "min_sentiment": 0.10, "max_sentiment": 0.60},
    {"id": "S19", "stop_pct": 8,  "take_pct": 15, "min_sentiment": 0.20, "max_sentiment": 0.70},
    {"id": "S20", "stop_pct": 12, "take_pct": 20, "min_sentiment": 0.30, "max_sentiment": 0.80},
]

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('strategy_results_excel.log'),
            logging.StreamHandler()
        ]
    )

def get_trading_days(start_d: date, end_d: date):
    """Get trading days using NYSE calendar"""
    nyse = mcal.get_calendar('NYSE')
    days = nyse.valid_days(start_date=start_d, end_date=end_d)
    return [d.date() if hasattr(d, 'date') else d for d in days]

def run_strategy_backtest(strategy: Dict, start_date: date, end_date: date, stocks: List[str], analyzer: VolumeNewsAnalyzer) -> Dict:
    """Run backtest for a single strategy and return comprehensive results with live progress logging"""
    
    strategy_id = strategy["id"]
    print(f"\n🔄 Running strategy {strategy_id} (SL: {strategy['stop_pct']}%, TP: {strategy['take_pct']}%, Sentiment: {strategy['min_sentiment']:.2f}-{strategy['max_sentiment']:.2f})", flush=True)
    
    trading_days = get_trading_days(start_date, end_date)
    all_trades = []
    per_ticker_pnl: Dict[str, float] = {}
    trades_so_far = 0
    pnl_so_far = 0.0
    
    # Exit reason counters
    tp_count = 0
    sl_count = 0
    eod_count = 0
    
    for day_idx, day in enumerate(trading_days, 1):
        # Per-day progress logging
        print(f"   🗓️  {strategy_id} — Day {day_idx}/{len(trading_days)}: {day}", flush=True)
        
        day_str = day.strftime('%Y-%m-%d')
        
        try:
            # Screen stocks using volume and news filters
            qualified_stocks = analyzer.screen_stocks_by_volume_and_news(
                stocks=stocks,
                analysis_date=day_str,
                min_news_count=2,
                min_sentiment=strategy['min_sentiment'],
                max_sentiment=strategy['max_sentiment']
            )
            
            # Process each qualified stock
            for stock_data in qualified_stocks:
                ticker = stock_data['ticker']
                
                try:
                    # Get intraday market data (09:30-16:00 ET)
                    market_data = get_historical_data(
                        ticker=ticker,
                        start_date=datetime.combine(day, dt_time(9, 30)),
                        end_date=datetime.combine(day, dt_time(16, 0)),
                        timeframe='1Min'
                    )
                    
                    if market_data is None or len(market_data) == 0:
                        continue
                    
                    # Filter to market hours
                    market_data = market_data.between_time('09:30', '16:00')
                    if len(market_data) == 0:
                        continue
                    
                    # Entry at market open
                    entry_time = market_data.index[0]
                    entry_price = float(market_data.iloc[0]['close'])
                    shares = int(1_000_000 / entry_price)  # $1M position size
                    
                    if shares <= 0:
                        continue
                    
                    # Simulate intraday trade
                    trade_result = simulate_intraday_trade(
                        ticker=ticker,
                        entry_price=entry_price,
                        entry_time=entry_time,
                        shares=shares,
                        market_data=market_data,
                        stop_loss_pct=float(strategy['stop_pct']),
                        take_profit_pct=float(strategy['take_pct'])
                    )
                    
                    if trade_result:
                        # Add strategy info to trade result
                        trade_result['strategy_id'] = strategy_id
                        trade_result['date'] = day_str
                        trade_result['sentiment_score'] = float(stock_data.get('weighted_sentiment', 0.0))
                        
                        all_trades.append(trade_result)
                        trades_so_far += 1
                        pnl_so_far += trade_result.get('pnl', 0.0)
                        per_ticker_pnl[ticker] = per_ticker_pnl.get(ticker, 0.0) + trade_result.get('pnl', 0.0)
                        # Periodic progress logging every 50 trades
                        if trades_so_far % 10 == 0:
                            print(f"   ▶ {strategy_id}: Processed {trades_so_far} trades — partial PnL: ${pnl_so_far:,.2f}", flush=True)
                        
                        # Count exit reasons
                        exit_reason = trade_result['exit_reason']
                        if exit_reason == 'TAKE_PROFIT':
                            tp_count += 1
                        elif exit_reason == 'STOP_LOSS':
                            sl_count += 1
                        elif exit_reason == 'EOD':
                            eod_count += 1
                
                except Exception as e:
                    continue  # Skip individual ticker errors
        
        except Exception as e:
            continue  # Skip individual day errors
    
    # Calculate comprehensive metrics
    if not all_trades:
        return {
            'strategy_id': strategy_id,
            'stop_pct': strategy['stop_pct'],
            'take_pct': strategy['take_pct'],
            'in_sentiment': strategy['min_sentiment'],
            'max_sentiment': strategy['max_sentiment'],
            'trades_count': 0,
            'wins_count': 0,
            'losses_count': 0,
            'win_rate_%': 0.0,
            'tp_count': 0,
            'sl_count': 0,
            'eod_count': 0,
            'total_pnl_$': 0.0,
            'avg_pnl_$': 0.0,
            'avg_pnl_%': 0.0,
            'capital_base': 0.0,
            'return_%': 0.0,
            # Extra for reconciliation (not written to Excel table)
            'per_ticker_pnl': per_ticker_pnl
        }
    
    # Calculate metrics
    total_trades = len(all_trades)
    total_pnl = sum(trade['pnl'] for trade in all_trades)
    wins = [trade for trade in all_trades if trade['pnl'] > 0]
    losses = [trade for trade in all_trades if trade['pnl'] < 0]
    wins_count = len(wins)
    losses_count = len(losses)
    win_rate = (wins_count / total_trades * 100) if total_trades > 0 else 0
    
    avg_pnl_dollar = total_pnl / total_trades if total_trades > 0 else 0
    capital_base = total_trades * 1_000_000  # $1M per trade
    # Calculate P&L as percentage of total capital (14M for 14 stocks)
    total_capital = 14_000_000  # 14M total capital for 14 stocks
    avg_pnl_pct = (avg_pnl_dollar / total_capital * 100) if total_trades > 0 else 0
    return_pct = (total_pnl / total_capital * 100)
    
    # Final per-strategy completion line
    print(f"   ✅ Completed {strategy_id} — total trades: {total_trades}, PnL: ${total_pnl:,.2f}, Win Rate: {win_rate:.1f}%", flush=True)
    
    return {
        'strategy_id': strategy_id,
        'stop_pct': strategy['stop_pct'],
        'take_pct': strategy['take_pct'],
        'in_sentiment': strategy['min_sentiment'],
        'max_sentiment': strategy['max_sentiment'],
        'trades_count': total_trades,
        'wins_count': wins_count,
        'losses_count': losses_count,
        'win_rate_%': win_rate,
        'tp_count': tp_count,
        'sl_count': sl_count,
        'eod_count': eod_count,
        'total_pnl_$': total_pnl,
        'avg_pnl_$': avg_pnl_dollar,
        'avg_pnl_%': avg_pnl_pct,
        'capital_base': capital_base,
        'return_%': return_pct,
        # Extra for reconciliation (not written to Excel table)
        'per_ticker_pnl': per_ticker_pnl
    }

def create_excel_report(results: List[Dict], output_path: str):
    """Create comprehensive Excel report with strategy configs and results"""
    
    # Create DataFrame
    df = pd.DataFrame(results)
    
    # Define column order (configs first, then results)
    column_order = [
        'strategy_id', 'stop_pct', 'take_pct', 'in_sentiment', 'max_sentiment',
        'trades_count', 'wins_count', 'losses_count', 'win_rate_%',
        'tp_count', 'sl_count', 'eod_count',
        'total_pnl_$', 'avg_pnl_$', 'avg_pnl_%', 'capital_base', 'return_%'
    ]
    
    # Reorder columns
    df = df.reindex(columns=column_order)
    
    # Calculate grand totals
    grand_total = {
        'strategy_id': 'GRAND_TOTAL',
        'stop_pct': '',
        'take_pct': '',
        'in_sentiment': '',
        'max_sentiment': '',
        'trades_count': df['trades_count'].sum(),
        'wins_count': df['wins_count'].sum(),
        'losses_count': df['losses_count'].sum(),
        'win_rate_%': (df['wins_count'].sum() / df['trades_count'].sum() * 100) if df['trades_count'].sum() > 0 else 0,
        'tp_count': df['tp_count'].sum(),
        'sl_count': df['sl_count'].sum(),
        'eod_count': df['eod_count'].sum(),
        'total_pnl_$': df['total_pnl_$'].sum(),
        'avg_pnl_$': df['total_pnl_$'].sum() / df['trades_count'].sum() if df['trades_count'].sum() > 0 else 0,
        'avg_pnl_%': (df['total_pnl_$'].sum() / 14_000_000 * 100),
        'capital_base': df['capital_base'].sum(),
        'return_%': (df['total_pnl_$'].sum() / 14_000_000 * 100)
    }
    
    # Add grand total row
    grand_total_df = pd.DataFrame([grand_total])
    df_with_total = pd.concat([df, grand_total_df], ignore_index=True)
    
    # Create Excel file
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        # Main results sheet
        df_with_total.to_excel(writer, sheet_name='Strategy_Results', index=False)
        
        # Metadata sheet
        metadata = pd.DataFrame([{
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'period': '2024-11-11 to 2025-08-20',
            'total_strategies': len(STRATEGIES),
            'expected_trade_count': '~13,444',
            'expected_total_pnl': '$1,964,340.37',
            'notes': 'S01-S20 baseline strategies with volume + news/sentiment filters'
        }])
        metadata.to_excel(writer, sheet_name='Metadata', index=False)
    
    print(f"📊 Excel report created: {output_path}")
    return grand_total

def validate_results(grand_total: Dict, results: List[Dict]) -> str:
    """Validate results against expected values and reconciliation rules"""
    total_trades = grand_total['trades_count']
    total_pnl = grand_total['total_pnl_$']
    
    # Expected values
    expected_trades = 13444
    expected_pnl = 1964340.37
    
    errors = []
    
    # Trade count check (exact match expected)
    if total_trades != expected_trades:
        errors.append("TRADE_COUNT_MISMATCH")
    
    # PnL check (±0.01 tolerance)
    if abs(total_pnl - expected_pnl) > 0.01:
        errors.append("INCONSISTENT_TOTALS")
    
    # Reconciliation: sum by strategies vs sum by tickers vs global
    # Sum by strategies is simply total_pnl
    # Sum by tickers: aggregate per_ticker_pnl across strategies
    per_ticker_global: Dict[str, float] = {}
    for r in results:
        per_ticker = r.get('per_ticker_pnl', {}) or {}
        for ticker, pnl in per_ticker.items():
            per_ticker_global[ticker] = per_ticker_global.get(ticker, 0.0) + float(pnl)
    sum_by_tickers = sum(per_ticker_global.values()) if per_ticker_global else 0.0
    
    if abs(sum_by_tickers - total_pnl) > 0.01:
        errors.append("RECONCILIATION_FAIL")
    
    if errors:
        return f"FAIL — {', '.join(errors)}"
    return "PASS"

def main():
    """Main execution function"""
    setup_logging()
    
    print("🚀 FULL STRATEGY RESULTS EXCEL GENERATOR")
    print("=" * 60)
    print("Period: 2024-11-11 → 2025-08-20")
    print("Strategies: S01–S20 (20 baseline strategies)")
    print("Output: reports/strategies_S01-S20_results.xlsx")
    print()
    
    # Setup
    start_date = date(2024, 11, 11)
    end_date = date(2025, 8, 20)
    
    # Create reports directory
    reports_dir = Path('reports')
    reports_dir.mkdir(exist_ok=True)
    output_path = reports_dir / 'strategies_S01-S20_results.xlsx'
    
    # Load stock universe and initialize analyzer
    stocks = load_stock_universe()
    analyzer = VolumeNewsAnalyzer()
    
    print(f"📈 Stock universe: {len(stocks)} tickers")
    print(f"📅 Trading period: {start_date} to {end_date}")
    print()
    
    # Run backtest for all strategies
    all_results = []
    start_time = time.time()
    
    for i, strategy in enumerate(STRATEGIES, 1):
        print(f"🔄 Running strategy {i}/20: {strategy['id']}")
        
        try:
            result = run_strategy_backtest(strategy, start_date, end_date, stocks, analyzer)
            all_results.append(result)
            
        except Exception as e:
            print(f"❌ Strategy {strategy['id']} failed: {e}")
            # Add error result
            error_result = {
                'strategy_id': strategy['id'],
                'stop_pct': strategy['stop_pct'],
                'take_pct': strategy['take_pct'],
                'min_sentiment': strategy['min_sentiment'],
                'max_sentiment': strategy['max_sentiment'],
                'trades_count': 0,
                'wins_count': 0,
                'losses_count': 0,
                'win_rate_%': 0.0,
                'tp_count': 0,
                'sl_count': 0,
                'eod_count': 0,
                'total_pnl_$': 0.0,
                'avg_pnl_$': 0.0,
                'avg_pnl_%': 0.0,
                'capital_base': 0.0,
                'return_%': 0.0
            }
            all_results.append(error_result)
    
    # Create Excel report
    grand_total = create_excel_report(all_results, output_path)
    
    # Validate results
    status = validate_results(grand_total, all_results)
    
    # Final output
    total_time = (time.time() - start_time) / 60
    print("\n" + "=" * 60)
    print("📊 FINAL RESULTS SUMMARY")
    print("=" * 60)
    print(f"TOTAL_TRADES: {grand_total['trades_count']:,}")
    print(f"GRAND_TOTAL_PNL: ${grand_total['total_pnl_$']:,.2f}")
    print(f"CAPITAL_BASE: ${grand_total['capital_base']:,.2f}")
    print(f"RETURN_%: {grand_total['return_%']:.4f}%")
    print(f"STATUS: {status}")
    print(f"EXECUTION_TIME: {total_time:.1f} minutes")
    print(f"OUTPUT_FILE: {output_path}")
    print("=" * 60)

if __name__ == '__main__':
    main()


