#!/usr/bin/env python3
"""
FULL BACKTEST WITH COMPLETE TRADE LOGGING
=========================================
Re-runs the entire backtest capturing ALL individual trades.
Logs every single closed trade to CSV/Parquet for complete analysis.
"""

import sys
import os
import argparse
import logging
from datetime import datetime, date, time as dt_time, timedelta
import pandas as pd
import numpy as np
from pathlib import Path
import time
from typing import Dict, List, Optional
import pandas_market_calendars as mcal
import csv
from decimal import Decimal, getcontext
import uuid
import hashlib

# Set high precision for money calculations
getcontext().prec = 28

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

class TradeLogger:
    """Comprehensive trade logging system"""
    
    def __init__(self, logs_dir: str = "logs"):
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(exist_ok=True)
        
        # Trade log files
        self.csv_file = self.logs_dir / "trades_backtest_full.csv"
        self.parquet_file = self.logs_dir / "trades_backtest_full.parquet"
        
        # Initialize CSV file with headers
        self.csv_headers = [
            'trade_id', 'open_time', 'close_time', 'symbol', 'strategy', 'qty',
            'entry_price', 'exit_price', 'fees_usd', 'pnl_usd', 'pnl_pct', 'exit_reason'
        ]
        
        # Clear existing files
        if self.csv_file.exists():
            self.csv_file.unlink()
        if self.parquet_file.exists():
            self.parquet_file.unlink()
        
        # Create CSV with headers
        with open(self.csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(self.csv_headers)
        
        self.trades_logged = 0
        self.trade_ids = set()  # Track for duplicates
        
        print(f"✅ Trade logger initialized: {self.csv_file}")
    
    def log_trade(self, trade_data: Dict):
        """Log a single trade to CSV"""
        
        # Generate deterministic unique trade ID from core fields
        id_basis = (
            f"{trade_data['strategy']}|{trade_data['symbol']}|"
            f"{trade_data['open_time'].strftime('%Y-%m-%d %H:%M:%S')}|"
            f"{trade_data['close_time'].strftime('%Y-%m-%d %H:%M:%S')}|"
            f"{trade_data.get('entry_price')}|{trade_data.get('exit_price')}|{trade_data.get('qty')}"
        )
        trade_id = hashlib.sha256(id_basis.encode('utf-8')).hexdigest()[:16]
        
        # Check for duplicates
        if trade_id in self.trade_ids:
            raise ValueError(f"ERROR: DUPLICATE_TRADE - {trade_id}")
        
        self.trade_ids.add(trade_id)
        
        # Validate required fields
        required_fields = ['symbol', 'strategy', 'open_time', 'close_time', 'entry_price', 'exit_price', 'pnl_usd', 'exit_reason']
        for field in required_fields:
            if field not in trade_data or trade_data[field] is None:
                raise ValueError(f"ERROR: MISSING_FIELD - {field} missing in trade {trade_id}")
        
        # Calculate derived fields
        qty = trade_data.get('qty', 1000000 / trade_data['entry_price'])  # $1M position
        fees_usd = trade_data.get('fees_usd', 0.0)  # Assume no fees unless specified
        # Calculate P&L as percentage of total capital (14M for 14 stocks)
        investment_per_stock = 1_000_000  # $1M per stock
        shares = int(investment_per_stock / trade_data['entry_price'])
        total_capital = 14_000_000  # 14M total capital for 14 stocks
        pnl_pct = ((trade_data['exit_price'] - trade_data['entry_price']) * shares / total_capital) * 100
        
        # Prepare row data
        row_data = [
            trade_id,
            trade_data['open_time'].strftime('%Y-%m-%d %H:%M:%S'),
            trade_data['close_time'].strftime('%Y-%m-%d %H:%M:%S'),
            trade_data['symbol'],
            trade_data['strategy'],
            qty,
            trade_data['entry_price'],
            trade_data['exit_price'],
            fees_usd,
            trade_data['pnl_usd'],
            pnl_pct,
            trade_data['exit_reason']
        ]
        
        # Write to CSV
        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(row_data)
        
        self.trades_logged += 1
        
        if self.trades_logged % 100 == 0:
            print(f"  📝 Logged {self.trades_logged} trades...")
    
    def finalize_logs(self):
        """Finalize logs and create Parquet file"""
        
        print(f"\n📊 FINALIZING TRADE LOGS")
        print(f"   Total trades logged: {self.trades_logged}")
        
        # Load CSV and save as Parquet
        if self.csv_file.exists():
            df = pd.read_csv(self.csv_file)
            df.to_parquet(self.parquet_file, index=False)
            print(f"   ✅ CSV: {self.csv_file}")
            print(f"   ✅ Parquet: {self.parquet_file}")
            
            return df
        else:
            raise ValueError("ERROR: NO_TRADES_LOGGED - CSV file not found")

def get_trading_days(start_date: date, end_date: date) -> List[date]:
    """Get trading days in the specified range"""
    nyse = mcal.get_calendar('NYSE')
    trading_days = nyse.schedule(start_date=start_date, end_date=end_date)
    return [day.date() for day in trading_days.index]

def run_full_backtest_with_logging(start_date: Optional[date] = None, end_date: Optional[date] = None):
    """Run the complete backtest with comprehensive trade logging"""
    
    print("🚀 FULL BACKTEST WITH COMPLETE TRADE LOGGING")
    print("=" * 60)
    if start_date is None:
        start_date = date(2024, 11, 1)
    if end_date is None:
        end_date = date(2025, 8, 31)
    print(f"Period: {start_date} to {end_date}")
    print("Capturing ALL individual trades")
    print()
    
    # Initialize components
    analyzer = VolumeNewsAnalyzer()
    stocks = load_stock_universe()
    trade_logger = TradeLogger()
    
    trading_days = get_trading_days(start_date, end_date)
    
    print(f"📅 Trading days: {len(trading_days)}")
    print(f"📊 Stocks: {len(stocks)}")
    print(f"⚙️  Strategies: {len(TWENTY_STRATEGIES)}")
    print()
    
    total_expected_combinations = len(trading_days) * len(TWENTY_STRATEGIES)
    processed_combinations = 0
    
    # Process each trading day
    for day_idx, trading_day in enumerate(trading_days):
        print(f"\n📅 Processing {trading_day} ({day_idx+1}/{len(trading_days)})")
        
        # Get qualified stocks for this day (pre-screen once)
        try:
            qualified_stocks = analyzer.screen_stocks_by_volume_and_news(
                stocks=stocks,
                analysis_date=trading_day.strftime('%Y-%m-%d'),
                min_news_count=2,
                min_sentiment=0.0,  # Will filter by strategy
                max_sentiment=1.0
            )
        except Exception as e:
            print(f"   ❌ Failed to get qualified stocks: {e}")
            processed_combinations += len(TWENTY_STRATEGIES)
            continue
        
        if not qualified_stocks:
            print(f"   ⚠️  No qualified stocks")
            processed_combinations += len(TWENTY_STRATEGIES)
            continue
        
        print(f"   📊 {len(qualified_stocks)} qualified stocks")
        
        # Process each strategy for this day
        for strategy in TWENTY_STRATEGIES:
            processed_combinations += 1
            progress = (processed_combinations / total_expected_combinations) * 100
            
            print(f"   🔄 {strategy['id']} ({progress:.1f}% complete)")
            
            # Filter qualified stocks by this strategy's sentiment range
            strategy_qualified = []
            for stock in qualified_stocks:
                sentiment = stock.get('weighted_sentiment', 0)
                if strategy['min_sentiment'] <= sentiment <= strategy['max_sentiment']:
                    strategy_qualified.append(stock)
            
            if not strategy_qualified:
                continue
            
            print(f"      📈 {len(strategy_qualified)} stocks for {strategy['id']}")
            
            # Execute trades for each qualified stock
            for stock_info in strategy_qualified:
                ticker = stock_info['ticker']
                
                try:
                    # Get intraday market data
                    historical_data = get_historical_data(
                        ticker, 
                        datetime.combine(trading_day, dt_time(9, 30)), 
                        datetime.combine(trading_day, dt_time(16, 0)),
                        timeframe='1Min'
                    )
                    
                    if historical_data is None or len(historical_data) == 0:
                        continue
                    
                    # Filter to market hours
                    market_data = historical_data.between_time('09:30', '16:00')
                    
                    if market_data is None or len(market_data) == 0:
                        continue
                    
                    # Entry at market open
                    entry_time = market_data.index[0]
                    entry_price = market_data.iloc[0]['close']
                    shares = int(1_000_000 / entry_price)  # $1M position
                    
                    # Execute the trade
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
                        # Log the trade
                        trade_data = {
                            'symbol': ticker,
                            'strategy': strategy['id'],
                            'open_time': trade_result['entry_time'],
                            'close_time': trade_result['exit_time'],
                            'entry_price': trade_result['entry_price'],
                            'exit_price': trade_result['exit_price'],
                            'qty': trade_result['shares'],
                            'pnl_usd': trade_result['pnl'],
                            'exit_reason': trade_result['exit_reason']
                        }
                        
                        trade_logger.log_trade(trade_data)
                
                except Exception as e:
                    print(f"        ❌ {ticker}: {str(e)[:50]}...")
                    continue
    
    # Finalize logging
    df_trades = trade_logger.finalize_logs()
    
    return df_trades

def validate_trade_logs(df_trades, expected_trades: Optional[int] = None, expected_pnl_usd: Optional[str] = None):
    """Validate the complete trade logs (STRICT)"""
    
    print(f"\n🔍 VALIDATING TRADE LOGS")
    print("=" * 30)
    
    # Strict required columns
    required_columns = [
        'trade_id', 'open_time', 'close_time', 'symbol', 'strategy', 'qty',
        'entry_price', 'exit_price', 'fees_usd', 'pnl_usd', 'pnl_pct', 'exit_reason'
    ]
    missing_cols = [c for c in required_columns if c not in df_trades.columns]
    if missing_cols:
        raise ValueError(f"ERROR: MISSING_FIELD - Missing columns: {','.join(missing_cols)}")
    
    # Check for NaNs in required columns
    for col in required_columns:
        nan_count = int(df_trades[col].isna().sum())
        if nan_count > 0:
            raise ValueError(f"ERROR: MISSING_FIELD - {col} has {nan_count} missing values")
    
    print(f"✅ All required fields present and non-null")
    
    # Check trade count (STRICT if provided)
    actual_trades = int(len(df_trades))
    if expected_trades is not None:
        print(f"Expected trades: {expected_trades:,}")
        print(f"Actual trades:   {actual_trades:,}")
        if actual_trades != expected_trades:
            raise ValueError(f"ERROR: TRADE_COUNT_MISMATCH - Expected {expected_trades}, got {actual_trades}")
    else:
        print(f"Actual trades:   {actual_trades:,}")
    
    # Check for duplicate trade_ids (STRICT)
    duplicate_count = int(df_trades['trade_id'].duplicated().sum())
    if duplicate_count > 0:
        raise ValueError(f"ERROR: DUPLICATE_TRADE - Found {duplicate_count} duplicate trade_ids")
    print(f"✅ No duplicate trade_ids")
    
    # Check P&L reconciliation (STRICT)
    # Use Decimal for accurate money math
    total_pnl = Decimal('0')
    for v in df_trades['pnl_usd'].astype(str).tolist():
        total_pnl += Decimal(v)
    tolerance = Decimal("0.01")
    if expected_pnl_usd is not None:
        expected_pnl = Decimal(expected_pnl_usd)
        difference = abs(total_pnl - expected_pnl)
        print(f"Expected P&L: ${expected_pnl:,.2f}")
        print(f"Actual P&L:   ${total_pnl:,.2f}")
        print(f"Difference:   ${difference:,.2f}")
        if difference > tolerance:
            raise ValueError(f"ERROR: INCONSISTENT_TOTALS - P&L diff {difference} > {tolerance}")
        print(f"✅ P&L reconciliation PASSED within ±{tolerance}")
    else:
        print(f"Actual P&L:   ${total_pnl:,.2f}")
    
    return True

def generate_per_ticker_summary(df_trades):
    """Generate per-ticker summary from complete trade logs"""
    
    print(f"\n📊 GENERATING PER-TICKER SUMMARY")
    print("=" * 40)
    
    ticker_summary = []
    
    for ticker in sorted(df_trades['symbol'].unique()):
        ticker_trades = df_trades[df_trades['symbol'] == ticker].copy()
        
        # Basic counts
        total_trades = len(ticker_trades)
        wins = (ticker_trades['pnl_usd'] > 0).sum()
        losses = (ticker_trades['pnl_usd'] <= 0).sum()
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        # Exit reason counts
        tp_count = (ticker_trades['exit_reason'] == 'TAKE_PROFIT').sum()
        sl_count = (ticker_trades['exit_reason'] == 'STOP_LOSS').sum()
        eod_count = (ticker_trades['exit_reason'] == 'EOD').sum()
        
        # P&L metrics
        total_pnl = ticker_trades['pnl_usd'].sum()
        avg_pnl = ticker_trades['pnl_usd'].mean() if total_trades > 0 else 0
        avg_pnl_pct = ticker_trades['pnl_pct'].mean() if total_trades > 0 else 0
        
        ticker_summary.append({
            'symbol': ticker,
            'trades_count': total_trades,
            'wins_count': wins,
            'losses_count': losses,
            'win_rate_%': round(win_rate, 1),
            'tp_count': tp_count,
            'sl_count': sl_count,
            'eod_count': eod_count,
            'total_pnl_$': round(total_pnl, 2),
            'avg_pnl_$': round(avg_pnl, 2),
            'avg_pnl_%': round(avg_pnl_pct, 2)
        })
    
    # Convert to DataFrame and sort by total P&L
    df_summary = pd.DataFrame(ticker_summary)
    df_summary = df_summary.sort_values('total_pnl_$', ascending=False)
    
    # Calculate P&L share percentage
    total_pnl_all = df_summary['total_pnl_$'].sum()
    df_summary['pnl_share_%'] = (df_summary['total_pnl_$'] / total_pnl_all * 100).round(2)
    
    # Add grand total row
    grand_total = {
        'symbol': 'GRAND_TOTAL',
        'trades_count': df_summary['trades_count'].sum(),
        'wins_count': df_summary['wins_count'].sum(),
        'losses_count': df_summary['losses_count'].sum(),
        'win_rate_%': round(df_summary['wins_count'].sum() / df_summary['trades_count'].sum() * 100, 1),
        'tp_count': df_summary['tp_count'].sum(),
        'sl_count': df_summary['sl_count'].sum(),
        'eod_count': df_summary['eod_count'].sum(),
        'total_pnl_$': round(df_summary['total_pnl_$'].sum(), 2),
        'avg_pnl_$': round(df_trades['pnl_usd'].mean(), 2),
        'avg_pnl_%': round(df_trades['pnl_pct'].mean(), 2),
        'pnl_share_%': 100.0
    }
    
    # Add total row
    df_summary = pd.concat([df_summary, pd.DataFrame([grand_total])], ignore_index=True)
    
    return df_summary

def save_results(df_summary):
    """Save per-ticker summary results"""
    
    print(f"\n💾 SAVING RESULTS")
    print("=" * 20)
    
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    
    # Save CSV
    csv_file = reports_dir / "per_ticker_summary_backtest.csv"
    df_summary.to_csv(csv_file, index=False)
    print(f"✅ CSV: {csv_file}")
    
    # Save Markdown
    md_file = reports_dir / "per_ticker_summary_backtest.md"
    with open(md_file, 'w') as f:
        f.write("# PER-TICKER SUMMARY - COMPLETE BACKTEST\n\n")
        f.write(f"**Analysis Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Period:** 2024-11-01 to 2025-08-31\n")
        f.write(f"**Data Source:** Complete individual trade logs (ALL trades captured)\n\n")
        
        f.write("## PERFORMANCE TABLE\n\n")
        f.write("Sorted by total_pnl_$ (descending)\n\n")
        f.write(df_summary.to_markdown(index=False))
    
    print(f"✅ Markdown: {md_file}")
    
    return csv_file, md_file

def display_console_preview(df_summary):
    """Display console preview of top 20 rows"""
    
    print(f"\n📋 CONSOLE PREVIEW - TOP 20 TICKERS")
    print("=" * 50)
    
    preview_df = df_summary.head(20)
    print(preview_df.to_string(index=False))

def main():
    """Main execution function"""
    
    parser = argparse.ArgumentParser(description='Full backtest with complete trade logging')
    parser.add_argument('--start', help='Start date YYYY-MM-DD (default 2024-11-01)')
    parser.add_argument('--end', help='End date YYYY-MM-DD (default 2025-08-31)')
    parser.add_argument('--expected-trades', type=int, help='Expected total trades for strict validation')
    parser.add_argument('--expected-pnl', type=str, help='Expected total P&L in USD (e.g., 1964340.37)')
    args = parser.parse_args()
    
    try:
        # Parse dates if provided
        start_date = datetime.strptime(args.start, '%Y-%m-%d').date() if args.start else None
        end_date = datetime.strptime(args.end, '%Y-%m-%d').date() if args.end else None
        
        # Step 1: Run full backtest with logging
        df_trades = run_full_backtest_with_logging(start_date=start_date, end_date=end_date)
        
        # Step 2: Validate trade logs
        validation_passed = validate_trade_logs(df_trades, expected_trades=args.expected_trades, expected_pnl_usd=args.expected_pnl)
        
        # Step 3: Generate per-ticker summary
        df_summary = generate_per_ticker_summary(df_trades)
        
        # Step 4: Display console preview
        display_console_preview(df_summary)
        
        # Step 5: Save results
        csv_file, md_file = save_results(df_summary)
        
        # Step 6: Final status
        if validation_passed:
            print(f"\n✅ STATUS: PASS")
            print(f"📁 Trade logs: logs/trades_backtest_full.csv, logs/trades_backtest_full.parquet")
            print(f"📁 Summary: {csv_file}, {md_file}")
        else:
            print(f"\n❌ STATUS: FAIL - Validation errors occurred")
        
    except Exception as e:
        error_code = str(e).split(':')[0] if ':' in str(e) else "UNEXPECTED_ERROR"
        print(f"\n❌ STATUS: FAIL — {error_code}: {e}")
        raise

if __name__ == "__main__":
    main()
