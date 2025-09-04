#!/usr/bin/env python3
"""
COMPREHENSIVE PER-TICKER ANALYSIS
==================================
Runs a fresh backtest to collect individual trade data and generate
comprehensive per-ticker performance analysis across all strategies.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import logging
import sys
import os
from typing import Dict, List, Optional
import json

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import bootstrap_nltk
import certifi
os.environ.setdefault("SSL_CERT_FILE", certifi.where())

from trading_core import load_stock_universe
from historical_backtest import get_historical_data
from volume_news_analyzer import VolumeNewsAnalyzer
import pandas_market_calendars as mcal

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('ticker_analysis.log')
        ]
    )

def get_trading_days(start_date, end_date):
    """Get list of trading days in the specified range"""
    nyse = mcal.get_calendar('NYSE')
    trading_days = nyse.schedule(start_date=start_date, end_date=end_date)
    return [day.date() for day in trading_days.index]

def simulate_intraday_trade_detailed(
    ticker: str,
    entry_price: float,
    entry_time: datetime,
    shares: int,
    market_data: pd.DataFrame,
    stop_loss_pct: float,
    take_profit_pct: float,
    strategy_id: str
) -> Optional[Dict]:
    """Enhanced version of simulate_intraday_trade with detailed tracking"""
    
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
                'trade_id': f"{strategy_id}_{ticker}_{entry_time.strftime('%Y%m%d_%H%M%S')}",
                'symbol': ticker,
                'strategy': strategy_id,
                'open_time': entry_time,
                'close_time': timestamp,
                'entry_price': entry_price,
                'exit_price': current_price,
                'shares': shares,
                'pnl_usd': pnl,
                'pnl_pct': (current_price - entry_price) / entry_price * 100,
                'exit_reason': 'STOP_LOSS',
                'holding_minutes': (timestamp - entry_time).total_seconds() / 60
            }
        
        # Check for take profit
        if current_price >= take_profit_price:
            pnl = (current_price - entry_price) * shares
            return {
                'trade_id': f"{strategy_id}_{ticker}_{entry_time.strftime('%Y%m%d_%H%M%S')}",
                'symbol': ticker,
                'strategy': strategy_id,
                'open_time': entry_time,
                'close_time': timestamp,
                'entry_price': entry_price,
                'exit_price': current_price,
                'shares': shares,
                'pnl_usd': pnl,
                'pnl_pct': (current_price - entry_price) / entry_price * 100,
                'exit_reason': 'TAKE_PROFIT',
                'holding_minutes': (timestamp - entry_time).total_seconds() / 60
            }
    
    # If we reach here, force close at EOD
    eod_price = market_data.iloc[-1]['close']
    eod_time = market_data.index[-1]
    
    pnl = (eod_price - entry_price) * shares
    return {
        'trade_id': f"{strategy_id}_{ticker}_{entry_time.strftime('%Y%m%d_%H%M%S')}",
        'symbol': ticker,
        'strategy': strategy_id,
        'open_time': entry_time,
        'close_time': eod_time,
        'entry_price': entry_price,
        'exit_price': eod_price,
        'shares': shares,
        'pnl_usd': pnl,
        'pnl_pct': (eod_price - entry_price) / entry_price * 100,
        'exit_reason': 'EOD',
        'holding_minutes': (eod_time - entry_time).total_seconds() / 60
    }

def run_comprehensive_backtest():
    """Run comprehensive backtest to collect individual trade data"""
    
    print("🚀 COMPREHENSIVE TICKER ANALYSIS")
    print("=" * 60)
    print("Running fresh backtest to collect individual trade data")
    print()
    
    # Define test period (shorter for faster execution)
    start_date = datetime(2024, 12, 1)
    end_date = datetime(2024, 12, 31)  # December 2024 for testing
    
    print(f"📅 ANALYSIS PERIOD: {start_date.date()} to {end_date.date()}")
    
    # Strategy configurations
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
        {"id": "S10", "stop_pct": 3, "take_pct": 6, "min_sentiment": 0.20, "max_sentiment": 0.70}
    ]
    
    # Load stock universe
    stocks = load_stock_universe()
    print(f"📊 STOCK UNIVERSE: {len(stocks)} stocks")
    
    # Initialize analyzer
    analyzer = VolumeNewsAnalyzer()
    
    # Get trading days
    trading_days = get_trading_days(start_date, end_date)
    print(f"📈 TRADING DAYS: {len(trading_days)} days")
    
    # Collect all trades
    all_trades = []
    
    for day_idx, trading_day in enumerate(trading_days):
        print(f"\n📅 Processing {trading_day} ({day_idx+1}/{len(trading_days)})")
        
        # Process each strategy for this day
        for strategy in strategies:
            print(f"  🔄 Strategy {strategy['id']}")
            
            try:
                # Get qualified stocks using the analyzer's method
                qualified_stocks = analyzer.screen_stocks_by_volume_and_news(
                    stocks=stocks,
                    analysis_date=trading_day.strftime('%Y-%m-%d'),
                    min_news_count=2,
                    min_sentiment=strategy['min_sentiment'],
                    max_sentiment=strategy['max_sentiment']
                )
                
                if not qualified_stocks:
                    print(f"    ⚠️  No qualified stocks")
                    continue
                
                print(f"    📊 {len(qualified_stocks)} qualified stocks")
                
                # Execute trades for qualified stocks
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
                        entry_price = market_data.iloc[0]['close']
                        shares = int(1_000_000 / entry_price)  # $1M position
                        
                        # Execute the trade
                        trade_result = simulate_intraday_trade_detailed(
                            ticker=ticker,
                            entry_price=entry_price,
                            entry_time=entry_time,
                            shares=shares,
                            market_data=market_data,
                            stop_loss_pct=strategy['stop_pct'],
                            take_profit_pct=strategy['take_pct'],
                            strategy_id=strategy['id']
                        )
                        
                        if trade_result:
                            all_trades.append(trade_result)
                            print(f"      ✅ {ticker}: ${trade_result['pnl_usd']:.0f} ({trade_result['exit_reason']})")
                        
                    except Exception as e:
                        print(f"      ❌ {ticker}: {str(e)[:50]}...")
                        continue
                        
            except Exception as e:
                print(f"    ❌ Strategy failed: {str(e)[:50]}...")
                continue
    
    print(f"\n✅ COLLECTED {len(all_trades)} INDIVIDUAL TRADES")
    return all_trades

def analyze_ticker_performance(trades_data):
    """Analyze performance by ticker across all strategies"""
    
    print("\n📊 ANALYZING TICKER PERFORMANCE")
    print("=" * 50)
    
    if not trades_data:
        print("❌ No trades to analyze")
        return None, None
    
    # Convert to DataFrame
    df = pd.DataFrame(trades_data)
    
    print(f"📈 Total trades: {len(df):,}")
    print(f"📅 Date range: {df['open_time'].min().date()} to {df['open_time'].max().date()}")
    print(f"🎯 Unique tickers: {df['symbol'].nunique()}")
    print(f"⚙️ Strategies: {df['strategy'].nunique()}")
    
    # Per-ticker summary
    ticker_summary = []
    
    for ticker in sorted(df['symbol'].unique()):
        ticker_trades = df[df['symbol'] == ticker]
        
        # Overall ticker metrics
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
        avg_pnl = ticker_trades['pnl_usd'].mean()
        avg_pnl_pct = ticker_trades['pnl_pct'].mean()
        
        # Strategy participation
        strategies_traded = ticker_trades['strategy'].nunique()
        
        ticker_summary.append({
            'symbol': ticker,
            'total_trades': total_trades,
            'strategies_traded': strategies_traded,
            'wins': wins,
            'losses': losses,
            'win_rate_%': round(win_rate, 1),
            'tp_count': tp_count,
            'sl_count': sl_count,
            'eod_count': eod_count,
            'total_pnl_$': round(total_pnl, 2),
            'avg_pnl_$': round(avg_pnl, 2),
            'avg_pnl_%': round(avg_pnl_pct, 2)
        })
    
    # Per-ticker-strategy breakdown
    strategy_breakdown = []
    
    for ticker in sorted(df['symbol'].unique()):
        for strategy in sorted(df['strategy'].unique()):
            strategy_trades = df[(df['symbol'] == ticker) & (df['strategy'] == strategy)]
            
            if len(strategy_trades) == 0:
                continue
                
            trades_count = len(strategy_trades)
            wins = (strategy_trades['pnl_usd'] > 0).sum()
            win_rate = (wins / trades_count * 100) if trades_count > 0 else 0
            total_pnl = strategy_trades['pnl_usd'].sum()
            avg_pnl = strategy_trades['pnl_usd'].mean()
            
            strategy_breakdown.append({
                'symbol': ticker,
                'strategy': strategy,
                'trades': trades_count,
                'wins': wins,
                'win_rate_%': round(win_rate, 1),
                'total_pnl_$': round(total_pnl, 2),
                'avg_pnl_$': round(avg_pnl, 2)
            })
    
    return pd.DataFrame(ticker_summary), pd.DataFrame(strategy_breakdown)

def save_comprehensive_results(df_ticker_summary, df_strategy_breakdown, trades_data):
    """Save comprehensive analysis results"""
    
    print("\n💾 SAVING COMPREHENSIVE RESULTS")
    print("=" * 40)
    
    # Create reports directory
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save ticker summary
    ticker_file = reports_dir / f"ticker_performance_summary_{timestamp}.csv"
    df_ticker_summary.to_csv(ticker_file, index=False)
    print(f"✅ Ticker summary: {ticker_file}")
    
    # Save strategy breakdown
    breakdown_file = reports_dir / f"ticker_strategy_breakdown_{timestamp}.csv"
    df_strategy_breakdown.to_csv(breakdown_file, index=False)
    print(f"✅ Strategy breakdown: {breakdown_file}")
    
    # Save raw trades
    trades_file = reports_dir / f"individual_trades_{timestamp}.csv"
    pd.DataFrame(trades_data).to_csv(trades_file, index=False)
    print(f"✅ Individual trades: {trades_file}")
    
    # Create Excel workbook with multiple sheets
    excel_file = reports_dir / f"comprehensive_ticker_analysis_{timestamp}.xlsx"
    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
        df_ticker_summary.to_excel(writer, sheet_name='Ticker Summary', index=False)
        df_strategy_breakdown.to_excel(writer, sheet_name='Strategy Breakdown', index=False)
        pd.DataFrame(trades_data).to_excel(writer, sheet_name='Individual Trades', index=False)
    
    print(f"✅ Excel workbook: {excel_file}")
    
    # Generate markdown report
    md_file = reports_dir / f"ticker_analysis_report_{timestamp}.md"
    with open(md_file, 'w') as f:
        f.write("# COMPREHENSIVE TICKER ANALYSIS REPORT\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Period:** December 2024 (Test Period)\n")
        f.write(f"**Total Trades:** {len(trades_data):,}\n\n")
        
        f.write("## TICKER PERFORMANCE SUMMARY\n\n")
        f.write(df_ticker_summary.to_markdown(index=False))
        
        f.write("\n\n## TOP PERFORMERS\n\n")
        top_performers = df_ticker_summary.nlargest(5, 'total_pnl_$')
        for _, row in top_performers.iterrows():
            f.write(f"- **{row['symbol']}**: ${row['total_pnl_$']:,.2f} ({row['total_trades']} trades, {row['win_rate_%']:.1f}% win rate)\n")
        
        f.write(f"\n\n## STRATEGY PARTICIPATION\n\n")
        f.write("Showing how many strategies each ticker participated in:\n\n")
        participation = df_ticker_summary[['symbol', 'strategies_traded', 'total_trades']].sort_values('strategies_traded', ascending=False)
        f.write(participation.to_markdown(index=False))
    
    print(f"✅ Markdown report: {md_file}")
    
    return excel_file

def display_results(df_ticker_summary, df_strategy_breakdown):
    """Display key results in console"""
    
    print("\n📋 TICKER PERFORMANCE SUMMARY")
    print("=" * 60)
    print(df_ticker_summary.to_string(index=False))
    
    print(f"\n🏆 TOP 5 PERFORMERS BY TOTAL P&L:")
    top_5 = df_ticker_summary.nlargest(5, 'total_pnl_$')
    for i, (_, row) in enumerate(top_5.iterrows(), 1):
        print(f"  {i}. {row['symbol']}: ${row['total_pnl_$']:,.2f} ({row['total_trades']} trades)")
    
    print(f"\n📊 STRATEGY PARTICIPATION:")
    participation = df_ticker_summary.groupby('strategies_traded').size()
    for strategies, count in participation.items():
        print(f"  {count} tickers traded in {strategies} strategies")
    
    print(f"\n🎯 OVERALL STATISTICS:")
    total_trades = df_ticker_summary['total_trades'].sum()
    total_pnl = df_ticker_summary['total_pnl_$'].sum()
    overall_win_rate = (df_ticker_summary['wins'].sum() / total_trades * 100) if total_trades > 0 else 0
    
    print(f"  • Total trades: {total_trades:,}")
    print(f"  • Total P&L: ${total_pnl:,.2f}")
    print(f"  • Overall win rate: {overall_win_rate:.1f}%")
    print(f"  • Average P&L per trade: ${total_pnl/total_trades:.2f}")

def main():
    """Main execution function"""
    
    setup_logging()
    
    try:
        # Step 1: Run comprehensive backtest
        trades_data = run_comprehensive_backtest()
        
        if not trades_data:
            print("❌ No trades collected. Check system configuration.")
            return
        
        # Step 2: Analyze ticker performance
        df_ticker_summary, df_strategy_breakdown = analyze_ticker_performance(trades_data)
        
        if df_ticker_summary is None:
            print("❌ Analysis failed.")
            return
        
        # Step 3: Display results
        display_results(df_ticker_summary, df_strategy_breakdown)
        
        # Step 4: Save comprehensive results
        excel_file = save_comprehensive_results(df_ticker_summary, df_strategy_breakdown, trades_data)
        
        print(f"\n✅ ANALYSIS COMPLETE")
        print(f"📁 Results saved in reports/ directory")
        print(f"📊 Main file: {excel_file}")
        
    except KeyboardInterrupt:
        print(f"\n⚠️  Analysis interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logging.error(f"Analysis failed: {e}")

if __name__ == "__main__":
    main()
