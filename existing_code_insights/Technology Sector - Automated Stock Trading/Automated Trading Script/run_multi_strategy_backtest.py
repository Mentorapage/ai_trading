#!/usr/bin/env python3
"""
MULTI-STRATEGY BACKTEST RUNNER
==============================
Run multiple strategies (S01-S20) simultaneously over any date range
with comprehensive logging, reporting, and reconciliation.
"""

import os
import sys
import csv
import argparse
import hashlib
from pathlib import Path
from datetime import datetime, date, time as dt_time
from typing import Dict, List
import pandas as pd
import pandas_market_calendars as mcal

from trading_core import load_stock_universe
from historical_backtest import get_historical_data, run_historical_backtest_with_overnight
from volume_news_analyzer import VolumeNewsAnalyzer

# Strategy definitions (S01-S20)
ALL_STRATEGIES = [
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

def make_trade_id(strategy_id: str, symbol: str, open_time: datetime, close_time: datetime, 
                 entry_price: float, exit_price: float, qty: int) -> str:
    """Generate unique trade ID"""
    basis = f"{strategy_id}|{symbol}|{open_time.strftime('%Y-%m-%d %H:%M:%S')}|{close_time.strftime('%Y-%m-%d %H:%M:%S')}|{entry_price}|{exit_price}|{qty}"
    return hashlib.sha256(basis.encode('utf-8')).hexdigest()[:16]

def label_sentiment(score: float) -> str:
    """Label sentiment score"""
    if score >= 0.05:
        return 'POS'
    elif score <= -0.05:
        return 'NEG'
    return 'NEU'

def run_single_strategy(
    strategy: Dict,
    trading_days: List[date],
    stocks: List[str],
    analyzer: VolumeNewsAnalyzer,
    trade_log_file: Path
) -> Dict:
    """Run a single strategy using the FULL OVERNIGHT HOLDING logic"""
    
    strategy_id = strategy["id"]
    print(f"🌙 Running strategy {strategy_id} with OVERNIGHT HOLDING...")
    
    # Create parameters for the overnight holding backtest
    start_date = trading_days[0]
    end_date = trading_days[-1]
    
    # BUG FIX: Ensure strict date boundaries to prevent overnight carryover
    print(f"🔧 BUG FIX: Enforcing strict date boundaries: {start_date} to {end_date}")
    print(f"🔧 This prevents carrying over positions from before {start_date}")
    
    params = {
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'stop_loss_pct': strategy['stop_pct'],
        'take_profit_pct': strategy['take_pct'],
        'sentiment_min_override': strategy['min_sentiment'],
        'sentiment_max_override': strategy['max_sentiment'],
        'position_size': 1000000,  # $1M per position
        'csv_output': False,  # We'll handle CSV ourselves
        'detailed_output': False  # Suppress detailed output for multi-strategy
    }
    
    # Temporarily redirect the backtest output to capture results
    import io
    import sys
    from contextlib import redirect_stdout
    
    # Capture the backtest results
    captured_output = io.StringIO()
    
    try:
        # Instead of trying to capture results from the interactive function,
        # let's run a single strategy backtest directly and capture its CSV output
        import tempfile
        import os
        
        # Create a temporary CSV file for this strategy
        temp_csv = f"temp_strategy_{strategy_id}.csv"
        
        # Run the FIXED historical backtest (no overnight holding bug)
        print(f"🔧 USING OVERNIGHT-MODE BACKTEST (multi-strategy compatible)")
        
        # Call the FIXED function directly instead of subprocess
        backtest_params = {
            'start_date': params['start_date'],
            'end_date': params['end_date'],
            # Pass full sentiment range so strategies differ by range, not a single threshold
            'sentiment_threshold': params['sentiment_min_override'],  # kept for backward compatibility
            'sentiment_min': params['sentiment_min_override'],
            'sentiment_max': params['sentiment_max_override'],
            'stop_loss_pct': params['stop_loss_pct'],
            'take_profit_pct': params['take_profit_pct'],
            'investment_per_stock': params['position_size']
        }
        
        # Call the overnight-enabled backtest function (returns list of trades)
        backtest_trades = run_historical_backtest_with_overnight(backtest_params)
        
        if backtest_trades:
            # Process returned overnight-mode trades
            import pandas as pd
            try:
                df = pd.DataFrame(backtest_trades)
                trade_count = len(df)
                
                if trade_count > 0:
                    # Calculate performance metrics based on overnight-mode fields
                    total_pnl = df['profit_loss'].sum()
                    wins = df[df['profit_loss'] > 0]
                    win_rate = len(wins) / trade_count * 100
                    avg_holding_minutes = df['holding_minutes'].mean()
                    
                    # Count exit reasons
                    exit_reasons = {"TAKE_PROFIT": 0, "STOP_LOSS": 0, "EOD": 0, "SENTIMENT_EOD_SELL": 0, "SENTIMENT_MORNING_SELL": 0, "BACKTEST_END": 0}
                    for reason in df['exit_reason']:
                        if reason in exit_reasons:
                            exit_reasons[reason] += 1
                    
                    # Write trades to multi-strategy CSV with strategy ID
                    for idx, row in df.iterrows():
                        # Create unique trade ID including row index to prevent duplicates
                        trade_id = make_trade_id(
                            f"{strategy_id}_{idx}", row.get('ticker') or row.get('symbol'), 
                            pd.to_datetime(row['entry_time']), pd.to_datetime(row['exit_time']) if pd.notna(row['exit_time']) else pd.to_datetime(row['entry_time']),
                            row['entry_price'], row['exit_price'], int(row.get('shares', row.get('qty', 0)))
                        )
                        
                        trade_record = [
                            trade_id,
                            row['entry_time'],
                            row['exit_time'],
                            row.get('ticker') or row.get('symbol'),
                            strategy_id,
                            int(row.get('shares', row.get('qty', 0))),
                            row['entry_price'],
                            row['exit_price'],
                            0.0,  # fees_usd
                            row.get('pnl_usd', row.get('profit_loss', 0.0)),
                            row.get('pnl_pct', row.get('profit_loss_pct', 0.0)),
                            row['exit_reason'],
                            float(strategy['stop_pct']),
                            float(strategy['take_pct']),
                            row.get('holding_minutes', 0.0),
                            row.get('sentiment', row.get('sentiment_score', 0.0)),
                            'NEU',
                            ''  # news_headline - not in CSV
                        ]
                        
                        # Append to trade log
                        with open(trade_log_file, 'a', newline='') as f:
                            csv.writer(f).writerow(trade_record)
                        
                else:
                    # No trades found
                    total_pnl = 0
                    win_rate = 0
                    avg_holding_minutes = 0
                    exit_reasons = {"TAKE_PROFIT": 0, "STOP_LOSS": 0, "EOD": 0, "SENTIMENT_EOD_SELL": 0, "SENTIMENT_MORNING_SELL": 0, "BACKTEST_END": 0}
                    
            except Exception as e:
                print(f"   ❌ Error in FIXED backtest: {e}")
                trade_count = 0
                total_pnl = 0
                win_rate = 0
                avg_holding_minutes = 0
                exit_reasons = {"TAKE_PROFIT": 0, "STOP_LOSS": 0, "EOD": 0, "SENTIMENT_EOD_SELL": 0, "SENTIMENT_MORNING_SELL": 0, "BACKTEST_END": 0}
        else:
            # No backtest result
            trade_count = 0
            total_pnl = 0
            win_rate = 0
            avg_holding_minutes = 0
            exit_reasons = {"TAKE_PROFIT": 0, "STOP_LOSS": 0, "EOD": 0, "SENTIMENT_EOD_SELL": 0, "SENTIMENT_MORNING_SELL": 0, "BACKTEST_END": 0}
            total_pnl = 0
            win_rate = 0
            avg_holding_minutes = 0
            exit_reasons = {"TAKE_PROFIT": 0, "STOP_LOSS": 0, "EOD": 0, "SENTIMENT_EOD_SELL": 0, "SENTIMENT_MORNING_SELL": 0, "BACKTEST_END": 0}
    
    except Exception as e:
        print(f"   ❌ Strategy {strategy_id} failed: {e}")
        trade_count = 0
        total_pnl = 0
        win_rate = 0
        avg_holding_minutes = 0
        exit_reasons = {"TAKE_PROFIT": 0, "STOP_LOSS": 0, "EOD": 0, "SENTIMENT_EOD_SELL": 0, "SENTIMENT_MORNING_SELL": 0, "BACKTEST_END": 0}
    
    print(f"   ✅ Completed {strategy_id} — trades: {trade_count}, PnL: ${total_pnl:,.0f}, Avg Hold: {avg_holding_minutes:.0f}min")
    
    return {
        'strategy_id': strategy_id,
        'trade_count': trade_count,
        'total_pnl': total_pnl,
        'win_rate': win_rate,
        'avg_holding_minutes': avg_holding_minutes,
        'exit_reasons': exit_reasons
    }

def generate_summary_reports(trade_log_file: Path, strategy_summary_file: Path, ticker_summary_file: Path):
    """Generate comprehensive summary reports"""
    
    try:
        # Read trade log
        df = pd.read_csv(trade_log_file)
        
        if len(df) == 0:
            print("⚠️  No trades found in log file")
            return
        
        print(f"📊 Generating reports from {len(df)} trades...")
        
        # Strategy summary
        strategy_summary = df.groupby('strategy_id').agg({
            'pnl_usd': ['sum', 'mean', 'count', 'std'],
            'pnl_pct': ['mean', 'std'],
            'holding_minutes': 'mean',
            'exit_reason': lambda x: (x == 'TAKE_PROFIT').sum()
        }).round(4)
        
        # Flatten column names
        strategy_summary.columns = [
            'total_pnl_usd', 'avg_pnl_usd', 'trade_count', 'pnl_std_usd',
            'avg_pnl_pct', 'pnl_std_pct', 'avg_holding_minutes', 'take_profit_count'
        ]
        
        # Add win rate
        strategy_summary['win_rate_pct'] = df.groupby('strategy_id')['pnl_usd'].apply(lambda x: (x > 0).mean() * 100)
        
        # Add stop loss and EOD counts
        strategy_summary['stop_loss_count'] = df.groupby('strategy_id')['exit_reason'].apply(
            lambda x: (x == 'STOP_LOSS').sum()
        )
        strategy_summary['eod_count'] = df.groupby('strategy_id')['exit_reason'].apply(
            lambda x: (x == 'EOD').sum()
        )
        
        # Save strategy summary
        strategy_summary.to_csv(strategy_summary_file)
        
        # Per-ticker summary (aggregated across all strategies)
        ticker_summary = df.groupby('symbol').agg({
            'pnl_usd': ['sum', 'count', 'mean'],
            'pnl_pct': ['mean', 'std'],
            'holding_minutes': 'mean',
            'strategy_id': lambda x: len(set(x))  # Number of unique strategies
        }).round(4)
        
        # Flatten column names
        ticker_summary.columns = [
            'total_pnl_usd', 'trade_count', 'avg_pnl_usd',
            'avg_pnl_pct', 'pnl_std_pct', 'avg_holding_minutes', 'strategy_count'
        ]
        
        # Add win rate per ticker
        ticker_summary['win_rate_pct'] = df.groupby('symbol')['pnl_usd'].apply(lambda x: (x > 0).mean() * 100)
        
        # Save ticker summary
        ticker_summary.to_csv(ticker_summary_file)
        
        print(f"✅ Strategy summary: {strategy_summary_file}")
        print(f"✅ Ticker summary: {ticker_summary_file}")
        
        return strategy_summary, ticker_summary
        
    except Exception as e:
        print(f"❌ Error generating summary reports: {e}")
        return None, None

def perform_reconciliation(trade_log_file: Path, strategy_results: List[Dict]):
    """Perform comprehensive reconciliation checks"""
    
    try:
        # Read trade log
        df = pd.read_csv(trade_log_file)
        
        if len(df) == 0:
            print("⚠️  No trades to reconcile")
            return False
        
        print(f"\n📊 RECONCILIATION CHECKS:")
        print(f"   Total trades in log: {len(df)}")
        
        # Check 1: Total PnL consistency
        total_pnl_trades = df['pnl_usd'].sum()
        total_pnl_strategies = sum(r['total_pnl'] for r in strategy_results)
        
        print(f"   Total PnL (trades): ${total_pnl_trades:,.2f}")
        print(f"   Total PnL (strategies): ${total_pnl_strategies:,.2f}")
        
        pnl_diff = abs(total_pnl_trades - total_pnl_strategies)
        pnl_match = pnl_diff < 0.01
        
        # Check 2: Trade count consistency
        total_trades_log = len(df)
        total_trades_strategies = sum(r['trade_count'] for r in strategy_results)
        
        print(f"   Total trades (log): {total_trades_log}")
        print(f"   Total trades (strategies): {total_trades_strategies}")
        
        trades_match = total_trades_log == total_trades_strategies
        
        # Check 3: No missing trades per strategy
        strategy_counts_log = df['strategy_id'].value_counts().to_dict()
        missing_trades = False
        
        for result in strategy_results:
            strategy_id = result['strategy_id']
            log_count = strategy_counts_log.get(strategy_id, 0)
            result_count = result['trade_count']
            
            if log_count != result_count:
                print(f"   ❌ Strategy {strategy_id}: log={log_count}, result={result_count}")
                missing_trades = True
        
        if not missing_trades:
            print(f"   ✅ All strategy trade counts match")
        
        # Check 4: Unique trade IDs
        unique_ids = df['trade_id'].nunique()
        total_ids = len(df)
        
        print(f"   Unique trade IDs: {unique_ids}/{total_ids}")
        
        ids_unique = unique_ids == total_ids
        
        # Overall status
        all_checks_pass = pnl_match and trades_match and not missing_trades and ids_unique
        
        print(f"\n📈 GRAND TOTAL PnL: ${total_pnl_trades:,.2f}")
        
        if all_checks_pass:
            print(f"   ✅ STATUS: PASS - All reconciliation checks passed")
        else:
            print(f"   ❌ STATUS: FAIL - Reconciliation issues detected")
            if not pnl_match:
                print(f"      • PnL mismatch: ${pnl_diff:.2f}")
            if not trades_match:
                print(f"      • Trade count mismatch")
            if missing_trades:
                print(f"      • Missing trades detected")
            if not ids_unique:
                print(f"      • Duplicate trade IDs found")
        
        return all_checks_pass
        
    except Exception as e:
        print(f"❌ Error during reconciliation: {e}")
        return False

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Multi-Strategy Backtest Runner')
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--strategies', help='Comma-separated strategy IDs (default: ALL)')
    parser.add_argument('--trade-log', required=True, help='Trade log CSV file path')
    parser.add_argument('--strategy-summary', required=True, help='Strategy summary CSV file path')
    parser.add_argument('--ticker-summary', required=True, help='Ticker summary CSV file path')
    
    args = parser.parse_args()
    
    # Parse dates
    start_date = datetime.strptime(args.start, '%Y-%m-%d').date()
    end_date = datetime.strptime(args.end, '%Y-%m-%d').date()
    
    # Parse strategies
    if args.strategies and args.strategies.upper() != "ALL":
        strategy_ids = [s.strip().upper() for s in args.strategies.split(',')]
        selected_strategies = [s for s in ALL_STRATEGIES if s['id'] in strategy_ids]
    else:
        selected_strategies = ALL_STRATEGIES
    
    print(f"🚀 MULTI-STRATEGY BACKTEST")
    print(f"📅 Period: {start_date} to {end_date}")
    print(f"📊 Strategies: {len(selected_strategies)} ({', '.join(s['id'] for s in selected_strategies)})")
    
    # Get trading days
    trading_days = get_trading_days(start_date, end_date)
    print(f"📅 Trading days: {len(trading_days)}")
    
    # Load stock universe
    stocks = load_stock_universe()
    print(f"📈 Stock universe: {len(stocks)} tickers")
    
    # Initialize analyzer
    analyzer = VolumeNewsAnalyzer()
    
    # Prepare trade log file
    trade_log_file = Path(args.trade_log)
    trade_log_file.parent.mkdir(exist_ok=True)
    
    # Initialize CSV with headers
    headers = [
        'trade_id', 'open_time', 'close_time', 'symbol', 'strategy_id', 'qty',
        'entry_price', 'exit_price', 'fees_usd', 'pnl_usd', 'pnl_pct', 'exit_reason',
        'stop_pct', 'take_pct', 'holding_minutes', 'sentiment_score', 'sentiment_label', 'news_headline'
    ]
    
    with open(trade_log_file, 'w', newline='') as f:
        csv.writer(f).writerow(headers)
    
    # Run all strategies
    strategy_results = []
    total_trades = 0
    
    for i, strategy in enumerate(selected_strategies, 1):
        print(f"\n[{i:2d}/{len(selected_strategies)}] Strategy {strategy['id']}: "
              f"-{strategy['stop_pct']}%/+{strategy['take_pct']}%, "
              f"sentiment {strategy['min_sentiment']:.2f}-{strategy['max_sentiment']:.2f}")
        
        try:
            result = run_single_strategy(
                strategy=strategy,
                trading_days=trading_days,
                stocks=stocks,
                analyzer=analyzer,
                trade_log_file=trade_log_file
            )
            
            strategy_results.append(result)
            total_trades += result['trade_count']
            
        except Exception as e:
            print(f"   ❌ Strategy {strategy['id']} failed: {e}")
            # Add error result
            strategy_results.append({
                'strategy_id': strategy['id'],
                'trade_count': 0,
                'total_pnl': 0,
                'win_rate': 0,
                'avg_holding_minutes': 0,
                'exit_reasons': {"TAKE_PROFIT": 0, "STOP_LOSS": 0, "EOD": 0}
            })
    
    print(f"\n📊 EXECUTION COMPLETED")
    print(f"   Total trades logged: {total_trades}")
    
    # Display strategy performance summary
    print(f"\n📈 STRATEGY PERFORMANCE SUMMARY:")
    print("-" * 80)
    print(f"{'Strategy':<10} {'Trades':<8} {'Total P&L':<12} {'Win Rate':<10} {'Avg Hold (min)':<15}")
    print("-" * 80)
    
    for result in strategy_results:
        if result['trade_count'] > 0:
            print(f"{result['strategy_id']:<10} {result['trade_count']:<8} "
                  f"${result['total_pnl']:>10,.0f} {result['win_rate']:>8.1f}% "
                  f"{result['avg_holding_minutes']:>13.0f}")
        else:
            print(f"{result['strategy_id']:<10} {'0':<8} {'$0':>12} {'0.0%':>10} {'0':>15}")
    
    print("-" * 80)
    
    # Generate summary reports
    strategy_summary_file = Path(args.strategy_summary)
    ticker_summary_file = Path(args.ticker_summary)
    
    strategy_summary_file.parent.mkdir(exist_ok=True)
    ticker_summary_file.parent.mkdir(exist_ok=True)
    
    generate_summary_reports(trade_log_file, strategy_summary_file, ticker_summary_file)
    
    # Perform reconciliation
    reconciliation_passed = perform_reconciliation(trade_log_file, strategy_results)
    
    print(f"\n✅ Multi-strategy backtest completed!")
    print(f"📁 Files generated:")
    print(f"   • Trade log: {trade_log_file}")
    print(f"   • Strategy summary: {strategy_summary_file}")
    print(f"   • Ticker summary: {ticker_summary_file}")
    
    # Exit with appropriate code
    sys.exit(0 if reconciliation_passed else 1)

if __name__ == '__main__':
    main()
