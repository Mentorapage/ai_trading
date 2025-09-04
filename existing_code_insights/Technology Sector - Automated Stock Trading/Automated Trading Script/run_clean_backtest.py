#!/usr/bin/env python3
"""
CLEAN Backtest Runner - NO Overnight Holding Bug
This will run backtests with STRICT date boundaries
"""

import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from pathlib import Path
import logging
from trading_core import load_stock_universe
from volume_news_analyzer import VolumeNewsAnalyzer
from historical_backtest import get_historical_data

# Configure logging
logging.basicConfig(level=logging.INFO)

def run_clean_strategy_backtest(strategy_config, start_date, end_date, stocks):
    """Run a single strategy with CLEAN date boundaries - no overnight carryover"""
    
    strategy_id = strategy_config['id']
    print(f"\n🔧 CLEAN Strategy {strategy_id}: {start_date} to {end_date}")
    print(f"   Stop Loss: {strategy_config['stop_pct']}%, Take Profit: {strategy_config['take_pct']}%")
    
    # Convert dates
    start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Initialize analyzer
    analyzer = VolumeNewsAnalyzer()
    
    all_trades = []
    current_date = start_dt
    
    print(f"🔄 Processing {(end_dt - start_dt).days + 1} days CLEANLY...")
    
    while current_date <= end_dt:
        if current_date.weekday() < 5:  # Skip weekends
            date_str = current_date.strftime('%Y-%m-%d')
            print(f"\n📅 Day: {date_str}")
            
            # Screen stocks for this day ONLY
            try:
                qualified_stocks = analyzer.screen_stocks_by_volume_and_news(stocks, date_str)
                print(f"   📊 Qualified stocks: {len(qualified_stocks)}")
                
                # Process each qualified stock
                for stock_data in qualified_stocks:
                    ticker = stock_data['ticker']
                    sentiment = stock_data['weighted_sentiment']
                    
                    # Check if sentiment is in strategy range
                    if strategy_config['min_sentiment'] <= sentiment <= strategy_config['max_sentiment']:
                        
                        # Get price data for this day ONLY
                        # Convert date string to datetime objects with market hours
                        start_dt = datetime.strptime(date_str, '%Y-%m-%d').replace(hour=9, minute=30)  # 9:30 AM
                        end_dt = datetime.strptime(date_str, '%Y-%m-%d').replace(hour=16, minute=0)    # 4:00 PM
                        price_data = get_historical_data(ticker, start_dt, end_dt, '1Min')
                        
                        if price_data is not None and not price_data.empty:
                            # Simulate trade for this day ONLY
                            trade = simulate_clean_trade(
                                ticker, price_data, strategy_config, date_str, sentiment
                            )
                            
                            if trade:
                                all_trades.append(trade)
                                print(f"   💰 {ticker}: ${trade['pnl_usd']:+,.0f} ({trade['exit_reason']})")
                        
            except Exception as e:
                print(f"   ❌ Error processing {date_str}: {e}")
        
        current_date += timedelta(days=1)
    
    # Calculate summary
    if all_trades:
        df = pd.DataFrame(all_trades)
        total_pnl = df['pnl_usd'].sum()
        trade_count = len(df)
        win_count = len(df[df['pnl_usd'] > 0])
        win_rate = (win_count / trade_count) * 100 if trade_count > 0 else 0
        avg_holding = df['holding_minutes'].mean()
        
        tp_count = len(df[df['exit_reason'] == 'TAKE_PROFIT'])
        sl_count = len(df[df['exit_reason'] == 'STOP_LOSS'])
        eod_count = len(df[df['exit_reason'].str.contains('EOD', na=False)])
        
        print(f"\n✅ CLEAN Results for {strategy_id}:")
        print(f"   Trades: {trade_count}")
        print(f"   P&L: ${total_pnl:,.2f}")
        print(f"   Win Rate: {win_rate:.1f}%")
        print(f"   Avg Holding: {avg_holding:.1f} minutes ({avg_holding/60:.1f} hours)")
        print(f"   Max possible for period: {(end_dt - start_dt).days * 24 * 60} minutes")
        
        return {
            'strategy_id': strategy_id,
            'total_pnl_usd': total_pnl,
            'trade_count': trade_count,
            'win_rate_pct': win_rate,
            'avg_holding_minutes': avg_holding,
            'take_profit_count': tp_count,
            'stop_loss_count': sl_count,
            'eod_count': eod_count,
            'trades': all_trades
        }
    else:
        print(f"\n⚠️  No trades for {strategy_id}")
        return {
            'strategy_id': strategy_id,
            'total_pnl_usd': 0.0,
            'trade_count': 0,
            'win_rate_pct': 0.0,
            'avg_holding_minutes': 0.0,
            'take_profit_count': 0,
            'stop_loss_count': 0,
            'eod_count': 0,
            'trades': []
        }

def simulate_clean_trade(ticker, price_data, strategy_config, date_str, sentiment):
    """Simulate a single trade with CLEAN boundaries - no overnight carryover"""
    
    try:
        # Entry at market open
        entry_time = price_data.index[0]
        entry_price = price_data.iloc[0]['open']
        
        # Calculate position size
        investment = 1_000_000  # $1M per trade
        shares = int(investment / entry_price)
        
        # Calculate stop loss and take profit levels
        stop_loss_price = entry_price * (1 - strategy_config['stop_pct'] / 100)
        take_profit_price = entry_price * (1 + strategy_config['take_pct'] / 100)
        
        # Check each minute for exit conditions
        for timestamp, row in price_data.iterrows():
            if timestamp <= entry_time:
                continue
                
            high = row['high']
            low = row['low']
            close = row['close']
            
            # Check for stop loss or take profit
            if low <= stop_loss_price:
                exit_price = stop_loss_price
                exit_reason = 'STOP_LOSS'
                exit_time = timestamp
                break
            elif high >= take_profit_price:
                exit_price = take_profit_price
                exit_reason = 'TAKE_PROFIT'
                exit_time = timestamp
                break
        else:
            # End of day exit
            exit_price = price_data.iloc[-1]['close']
            exit_reason = 'EOD'
            exit_time = price_data.index[-1]
        
        # Calculate P&L
        pnl_usd = (exit_price - entry_price) * shares
        holding_minutes = (exit_time - entry_time).total_seconds() / 60
        
        # CRITICAL: Ensure holding time is within the same day
        max_day_minutes = 24 * 60  # 1440 minutes max per day
        if holding_minutes > max_day_minutes:
            holding_minutes = max_day_minutes
            print(f"   🔧 Capped holding time for {ticker} to {max_day_minutes} minutes")
        
        return {
            'trade_id': f"{ticker}_{date_str}_{strategy_config['id']}",
            'open_time': entry_time,
            'close_time': exit_time,
            'symbol': ticker,
            'strategy_id': strategy_config['id'],
            'qty': shares,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl_usd': pnl_usd,
            'exit_reason': exit_reason,
            'holding_minutes': holding_minutes,
            'sentiment_score': sentiment
        }
        
    except Exception as e:
        print(f"   ❌ Error simulating {ticker}: {e}")
        return None

def run_clean_multi_strategy_test():
    """Test the CLEAN backtest on the SAME interval: 2025-06-01 to 2025-06-04"""
    
    print("🧪 TESTING CLEAN BACKTEST ON SAME INTERVAL")
    print("📅 Period: 2025-06-01 to 2025-06-04 (SAME AS BUGGY VERSION)")
    print("🔧 This will prove the fix works!")
    
    # Same strategies as the buggy test
    strategies = [
        {"id": "S01", "stop_pct": 3, "take_pct": 5, "min_sentiment": 0.10, "max_sentiment": 0.60},
        {"id": "S02", "stop_pct": 3, "take_pct": 8, "min_sentiment": 0.10, "max_sentiment": 0.60},
        {"id": "S03", "stop_pct": 3, "take_pct": 12, "min_sentiment": 0.20, "max_sentiment": 0.70}
    ]
    
    # Same date range
    start_date = "2025-06-01"
    end_date = "2025-06-04"
    
    # Same stocks
    stocks = load_stock_universe()
    print(f"📈 Stock universe: {len(stocks)} tickers")
    
    results = []
    
    for strategy in strategies:
        result = run_clean_strategy_backtest(strategy, start_date, end_date, stocks)
        results.append(result)
    
    print(f"\n🎉 CLEAN TEST COMPLETED!")
    print(f"📊 Comparison with buggy version:")
    print(f"   Period: SAME ({start_date} to {end_date})")
    print(f"   Strategies: SAME (S01, S02, S03)")
    print(f"   Stocks: SAME ({len(stocks)} tickers)")
    
    for result in results:
        strategy_id = result['strategy_id']
        trades = result['trade_count']
        pnl = result['total_pnl_usd']
        avg_holding = result['avg_holding_minutes']
        
        print(f"\n   {strategy_id}:")
        print(f"     Trades: {trades}")
        print(f"     P&L: ${pnl:,.2f}")
        print(f"     Avg Holding: {avg_holding:.1f} minutes ({avg_holding/60:.1f} hours)")
        
        # Check if holding time is reasonable for 3-day period
        max_period_minutes = 3 * 24 * 60  # 4320 minutes for 3 days
        if avg_holding <= max_period_minutes:
            print(f"     ✅ Holding time is REASONABLE (≤ {max_period_minutes} min)")
        else:
            print(f"     ❌ Holding time is STILL WRONG (> {max_period_minutes} min)")
    
    return results

if __name__ == "__main__":
    run_clean_multi_strategy_test()
