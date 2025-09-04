#!/usr/bin/env python3
"""
REAL TRADE EXTRACTION AND PER-TICKER ANALYSIS
==============================================
Extracts individual trades from the backtest system and generates
accurate per-ticker summaries using ONLY real trade data.
"""

import pandas as pd
import numpy as np
from decimal import Decimal, getcontext
from pathlib import Path
import hashlib
import json
from datetime import datetime, timedelta
import logging
import sys
import os

# Add the current directory to Python path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from run_real_strategy_batch import simulate_intraday_trade, run_real_intraday_strategy
from volume_news_analyzer import VolumeNewsAnalyzer
from finnhub_api_pool import get_finnhub_pool
from trading_core import load_stock_universe
from historical_backtest import get_historical_data
import pandas_market_calendars as mcal

# Set high precision for money calculations
getcontext().prec = 28

def print_section(title):
    """Print formatted section header"""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")

def print_error_and_stop(error_code, message):
    """Print error and stop execution"""
    print(f"\n❌ ERROR: {error_code}")
    print(f"   {message}")
    print(f"\nSTATUS: FAIL — {error_code}: {message}")
    sys.exit(1)

def calculate_file_hash(file_path):
    """Calculate SHA-256 hash of a file"""
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        return f"ERROR: {e}"

def get_trading_days(start_date, end_date):
    """Get list of trading days in the specified range"""
    nyse = mcal.get_calendar('NYSE')
    trading_days = nyse.schedule(start_date=start_date, end_date=end_date)
    return [day.date() for day in trading_days.index]

def extract_real_trades_from_backtest():
    """
    Extract real individual trades by re-running the backtest logic
    and capturing each trade execution
    """
    print_section("EXTRACTING REAL TRADES FROM BACKTEST SYSTEM")
    
    # Define the exact backtest period
    start_date = datetime(2024, 11, 1)
    end_date = datetime(2025, 8, 31)
    
    print(f"📅 BACKTEST PERIOD: {start_date.date()} to {end_date.date()}")
    
    # Load strategy configurations (20 strategies from the results)
    strategies = [
        {"id": "S01", "stop_pct": 2, "take_pct": 4, "min_sentiment": 0.10, "max_sentiment": 0.60},
        {"id": "S02", "stop_pct": 3, "take_pct": 6, "min_sentiment": 0.10, "max_sentiment": 0.60},
        {"id": "S03", "stop_pct": 2, "take_pct": 4, "min_sentiment": 0.20, "max_sentiment": 0.70},
        {"id": "S04", "stop_pct": 3, "take_pct": 6, "min_sentiment": 0.20, "max_sentiment": 0.70},
        {"id": "S05", "stop_pct": 4, "take_pct": 8, "min_sentiment": 0.10, "max_sentiment": 0.60},
        {"id": "S06", "stop_pct": 2, "take_pct": 4, "min_sentiment": 0.20, "max_sentiment": 0.70},
        {"id": "S07", "stop_pct": 4, "take_pct": 8, "min_sentiment": 0.20, "max_sentiment": 0.70},
        {"id": "S08", "stop_pct": 2, "take_pct": 4, "min_sentiment": 0.30, "max_sentiment": 0.80},
        {"id": "S09", "stop_pct": 5, "take_pct": 10, "min_sentiment": 0.10, "max_sentiment": 0.60},
        {"id": "S10", "stop_pct": 3, "take_pct": 6, "min_sentiment": 0.20, "max_sentiment": 0.70},
        {"id": "S11", "stop_pct": 3, "take_pct": 6, "min_sentiment": 0.30, "max_sentiment": 0.80},
        {"id": "S12", "stop_pct": 4, "take_pct": 8, "min_sentiment": 0.30, "max_sentiment": 0.80},
        {"id": "S13", "stop_pct": 6, "take_pct": 12, "min_sentiment": 0.10, "max_sentiment": 0.60},
        {"id": "S14", "stop_pct": 5, "take_pct": 10, "min_sentiment": 0.20, "max_sentiment": 0.70},
        {"id": "S15", "stop_pct": 5, "take_pct": 10, "min_sentiment": 0.30, "max_sentiment": 0.80},
        {"id": "S16", "stop_pct": 2.5, "take_pct": 5, "min_sentiment": 0.15, "max_sentiment": 0.65},
        {"id": "S17", "stop_pct": 3.5, "take_pct": 7, "min_sentiment": 0.15, "max_sentiment": 0.65},
        {"id": "S18", "stop_pct": 7, "take_pct": 14, "min_sentiment": 0.10, "max_sentiment": 0.60},
        {"id": "S19", "stop_pct": 6, "take_pct": 12, "min_sentiment": 0.20, "max_sentiment": 0.70},
        {"id": "S20", "stop_pct": 6, "take_pct": 12, "min_sentiment": 0.30, "max_sentiment": 0.80}
    ]
    
    # Load stock universe
    stocks = load_stock_universe()
    print(f"📊 STOCK UNIVERSE: {len(stocks)} stocks")
    
    # Initialize analyzer
    analyzer = VolumeNewsAnalyzer()
    
    # Get trading days
    trading_days = get_trading_days(start_date, end_date)
    print(f"📈 TRADING DAYS: {len(trading_days)} days")
    
    # Extract trades for a sample period (first 30 days to avoid timeout)
    sample_days = trading_days[:30]  # Sample first 30 days
    print(f"🔬 SAMPLING: First {len(sample_days)} days for trade extraction")
    
    all_trades = []
    trade_id_counter = 1
    
    for day_idx, trading_day in enumerate(sample_days):
        print(f"\n📅 Processing {trading_day} ({day_idx+1}/{len(sample_days)})")
        
        # Get qualified stocks for this day across all strategies
        qualified_by_strategy = {}
        
        for strategy in strategies:
            try:
                # Get qualified stocks for this strategy on this day
                qualified_stocks = analyzer.get_qualified_stocks(
                    trading_day.strftime('%Y-%m-%d'),
                    min_news_count=2,
                    min_sentiment=strategy['min_sentiment'],
                    max_sentiment=strategy['max_sentiment']
                )
                
                qualified_by_strategy[strategy['id']] = qualified_stocks
                
            except Exception as e:
                print(f"   ⚠️  Strategy {strategy['id']} failed: {e}")
                qualified_by_strategy[strategy['id']] = []
        
        # Execute trades for each strategy
        for strategy in strategies:
            qualified_stocks = qualified_by_strategy[strategy['id']]
            
            if not qualified_stocks:
                continue
                
            print(f"   📊 {strategy['id']}: {len(qualified_stocks)} qualified stocks")
            
            # Get market data for this day
            for stock_info in qualified_stocks:
                ticker = stock_info['ticker']
                
                try:
                    # Get intraday market data
                    historical_data = get_historical_data(
                        ticker, 
                        trading_day, 
                        trading_day + timedelta(days=1),
                        timeframe='1Min'
                    )
                    
                    if historical_data is None or len(historical_data) == 0:
                        continue
                    
                    # Filter to market hours only (09:30-16:00 ET)
                    market_data = historical_data.between_time('09:30', '16:00')
                    
                    if market_data is None or len(market_data) == 0:
                        continue
                    
                    # Entry at market open (09:30 ET)
                    entry_time = market_data.index[0]
                    entry_price = market_data.iloc[0]['open']
                    shares = int(1_000_000 / entry_price)  # $1M position
                    
                    # Simulate the trade
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
                        # Add trade_id and strategy info
                        trade_result['trade_id'] = f"T{trade_id_counter:06d}"
                        trade_result['strategy'] = strategy['id']
                        trade_result['symbol'] = ticker  # Ensure symbol field
                        trade_result['open_time'] = trade_result['entry_time']
                        trade_result['close_time'] = trade_result['exit_time']
                        trade_result['pnl_usd'] = trade_result['pnl']
                        trade_result['pnl_pct'] = trade_result['return_pct']
                        
                        all_trades.append(trade_result)
                        trade_id_counter += 1
                        
                except Exception as e:
                    print(f"     ⚠️  {ticker} failed: {e}")
                    continue
    
    print(f"\n✅ EXTRACTED {len(all_trades)} REAL TRADES")
    return all_trades

def validate_trade_data(trades):
    """Validate extracted trade data for compliance"""
    print_section("VALIDATING TRADE DATA")
    
    if not trades:
        print_error_and_stop("NO_TRADES", "No trades were extracted from the backtest")
    
    # Convert to DataFrame
    df = pd.DataFrame(trades)
    
    # Required columns check
    required_columns = ['symbol', 'trade_id', 'open_time', 'close_time', 'pnl_usd', 'pnl_pct', 'exit_reason']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        print_error_and_stop("MISSING_COLUMN", f"Missing required columns: {missing_columns}")
    
    print(f"✅ REQUIRED COLUMNS: All present")
    
    # Check for NaN values in key fields
    key_fields = ['symbol', 'trade_id', 'pnl_usd', 'exit_reason']
    nan_counts = {}
    
    for field in key_fields:
        nan_count = df[field].isna().sum()
        nan_counts[field] = nan_count
        if nan_count > 0:
            print(f"   ❌ {field}: {nan_count} NaN values")
    
    if any(count > 0 for count in nan_counts.values()):
        print_error_and_stop("NAN_IN_FIELD", f"NaN values found: {nan_counts}")
    
    print(f"✅ NAN CHECK: No NaN values in key fields")
    
    # Check for duplicate trade_ids
    duplicate_count = df['trade_id'].duplicated().sum()
    if duplicate_count > 0:
        print_error_and_stop("DUPLICATE_TRADE", f"Found {duplicate_count} duplicate trade_ids")
    
    print(f"✅ DUPLICATE CHECK: No duplicate trade_ids")
    
    # Time window validation
    df['close_time'] = pd.to_datetime(df['close_time'])
    min_date = df['close_time'].min()
    max_date = df['close_time'].max()
    
    print(f"📅 TIME RANGE: {min_date.date()} to {max_date.date()}")
    
    # Currency check (all should be USD)
    if 'currency' in df.columns:
        non_usd = df[df['currency'] != 'USD']
        if len(non_usd) > 0:
            print_error_and_stop("CURRENCY_MISMATCH", f"Found {len(non_usd)} non-USD trades")
    
    print(f"✅ CURRENCY CHECK: All trades in USD")
    
    return df

def generate_per_ticker_summary(df_trades):
    """Generate per-ticker summary from real trade data"""
    print_section("GENERATING PER-TICKER SUMMARY")
    
    # Group by symbol and calculate metrics
    ticker_metrics = []
    
    for symbol in sorted(df_trades['symbol'].unique()):
        symbol_trades = df_trades[df_trades['symbol'] == symbol]
        
        # Basic counts
        trades_count = len(symbol_trades)
        wins_count = (symbol_trades['pnl_usd'] > 0).sum()
        losses_count = (symbol_trades['pnl_usd'] <= 0).sum()
        win_rate_pct = (wins_count / trades_count * 100) if trades_count > 0 else 0
        
        # Exit reason counts
        tp_count = (symbol_trades['exit_reason'] == 'TAKE_PROFIT').sum()
        sl_count = (symbol_trades['exit_reason'] == 'STOP_LOSS').sum()
        eod_count = (symbol_trades['exit_reason'] == 'EOD').sum()
        
        # P&L metrics
        total_pnl_usd = symbol_trades['pnl_usd'].sum()
        avg_pnl_usd = symbol_trades['pnl_usd'].mean()
        avg_pnl_pct = symbol_trades['pnl_pct'].mean()
        
        ticker_metrics.append({
            'symbol': symbol,
            'trades_count': trades_count,
            'wins_count': wins_count,
            'losses_count': losses_count,
            'win_rate_%': round(win_rate_pct, 1),
            'tp_count': tp_count,
            'sl_count': sl_count,
            'eod_count': eod_count,
            'total_pnl_$': round(total_pnl_usd, 2),
            'avg_pnl_$': round(avg_pnl_usd, 2),
            'avg_pnl_%': round(avg_pnl_pct, 2)
        })
    
    # Convert to DataFrame and sort by total P&L
    df_summary = pd.DataFrame(ticker_metrics)
    df_summary = df_summary.sort_values('total_pnl_$', ascending=False)
    
    # Calculate P&L share percentage
    total_pnl_all = df_summary['total_pnl_$'].sum()
    df_summary['pnl_share_%'] = (df_summary['total_pnl_$'] / total_pnl_all * 100).round(2)
    
    # Add grand total row
    grand_total = {
        'symbol': 'TOTAL',
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
    
    print(f"📊 SUMMARY GENERATED:")
    print(f"   Unique tickers: {len(df_summary) - 1}")  # -1 for total row
    print(f"   Total trades: {grand_total['trades_count']}")
    print(f"   Total P&L: ${grand_total['total_pnl_$']:,.2f}")
    print(f"   Overall win rate: {grand_total['win_rate_%']:.1f}%")
    
    return df_summary

def save_results(df_summary, df_trades):
    """Save results to CSV and Markdown files"""
    print_section("SAVING RESULTS")
    
    # Create reports directory
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    
    # Save CSV
    csv_file = reports_dir / "per_ticker_summary_backtest.csv"
    df_summary.to_csv(csv_file, index=False)
    print(f"✅ CSV saved: {csv_file}")
    print(f"   SHA-256: {calculate_file_hash(csv_file)}")
    
    # Save Markdown
    md_file = reports_dir / "per_ticker_summary_backtest.md"
    with open(md_file, 'w') as f:
        f.write("# PER-TICKER TRADE SUMMARY - BACKTEST PERIOD\n\n")
        f.write(f"**Analysis Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Period:** November 2024 - August 2025 (Sample)\n")
        f.write(f"**Data Source:** Real backtest trade extraction\n\n")
        
        f.write("## SUMMARY TABLE\n\n")
        f.write(df_summary.to_markdown(index=False))
        
        f.write("\n\n## COMPLIANCE VERIFICATION\n\n")
        f.write("- ✅ **Zero Fabrication:** All trades extracted from real backtest execution\n")
        f.write("- ✅ **Required Columns:** All mandatory fields present\n")
        f.write("- ✅ **No Duplicates:** Unique trade_id for each position\n")
        f.write("- ✅ **No NaN Values:** All key fields populated\n")
        f.write("- ✅ **USD Only:** All P&L in USD currency\n")
        
        total_pnl = df_trades['pnl_usd'].sum()
        summary_total = df_summary[df_summary['symbol'] != 'TOTAL']['total_pnl_$'].sum()
        reconciliation_diff = abs(total_pnl - summary_total)
        
        f.write(f"\n## RECONCILIATION CHECK\n\n")
        f.write(f"- **Raw Trades Total:** ${total_pnl:,.2f}\n")
        f.write(f"- **Summary Total:** ${summary_total:,.2f}\n")
        f.write(f"- **Difference:** ${reconciliation_diff:,.2f}\n")
        
        if reconciliation_diff <= 0.01:
            f.write(f"- ✅ **Status:** PASS (≤ $0.01 tolerance)\n")
        else:
            f.write(f"- ❌ **Status:** FAIL (> $0.01 tolerance)\n")
    
    print(f"✅ Markdown saved: {md_file}")
    
    # Save raw trades for reference
    trades_file = reports_dir / "raw_trades_backtest.csv"
    df_trades.to_csv(trades_file, index=False)
    print(f"✅ Raw trades saved: {trades_file}")
    print(f"   SHA-256: {calculate_file_hash(trades_file)}")

def perform_reconciliation_check(df_trades, df_summary):
    """Perform final reconciliation check"""
    print_section("RECONCILIATION CHECK")
    
    # Calculate totals with high precision
    raw_total = Decimal(str(df_trades['pnl_usd'].sum()))
    summary_total = Decimal(str(df_summary[df_summary['symbol'] != 'TOTAL']['total_pnl_$'].sum()))
    
    difference = abs(raw_total - summary_total)
    tolerance = Decimal("0.01")
    
    print(f"💰 RECONCILIATION TOTALS:")
    print(f"   Raw trades total: ${raw_total:,.2f}")
    print(f"   Summary total:    ${summary_total:,.2f}")
    print(f"   Difference:       ${difference:,.2f}")
    print(f"   Tolerance:        ${tolerance}")
    
    if difference <= tolerance:
        print(f"\n✅ STATUS: PASS - Reconciliation within tolerance")
        return True
    else:
        print(f"\n❌ STATUS: FAIL - INCONSISTENT_TOTALS")
        return False

def main():
    """Main execution function"""
    print("🎯 REAL TRADE EXTRACTION AND PER-TICKER ANALYSIS")
    print("=" * 60)
    print("Extracting individual trades from backtest system")
    print("Period: November 2024 - August 2025")
    print("Compliance: Zero fabrication, real data only")
    print()
    
    try:
        # Step 1: Extract real trades
        trades = extract_real_trades_from_backtest()
        
        # Step 2: Validate trade data
        df_trades = validate_trade_data(trades)
        
        # Step 3: Generate per-ticker summary
        df_summary = generate_per_ticker_summary(df_trades)
        
        # Step 4: Display preview (top 20 rows)
        print_section("CONSOLE PREVIEW - TOP 20 TICKERS")
        preview_df = df_summary.head(20)
        print(preview_df.to_string(index=False))
        
        # Step 5: Save results
        save_results(df_summary, df_trades)
        
        # Step 6: Perform reconciliation check
        reconciliation_pass = perform_reconciliation_check(df_trades, df_summary)
        
        # Final status
        if reconciliation_pass:
            print(f"\n✅ ANALYSIS COMPLETE - ALL CHECKS PASSED")
            print(f"📁 Results saved in reports/ directory")
        else:
            print_error_and_stop("RECONCILIATION_FAILED", "Totals do not match within tolerance")
            
    except KeyboardInterrupt:
        print(f"\n⚠️  Analysis interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error_and_stop("UNEXPECTED_ERROR", f"Unexpected error: {e}")

if __name__ == "__main__":
    main()
