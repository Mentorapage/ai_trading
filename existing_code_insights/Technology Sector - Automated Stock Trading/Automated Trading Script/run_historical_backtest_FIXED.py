#!/usr/bin/env python3
"""
COMPLETELY FIXED Historical Backtest - NO OVERNIGHT HOLDING BUG
This replaces the buggy run_historical_backtest_with_overnight function
"""

import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import logging
from trading_core import load_stock_universe
from volume_news_analyzer import VolumeNewsAnalyzer
from historical_backtest import get_historical_data

def run_historical_backtest_with_overnight_FIXED(params):
    """
    COMPLETELY FIXED Historical backtest - NO OVERNIGHT HOLDING BUG
    - Uses proper datetime objects for minute-level data
    - No fabricated trades from before backtest period  
    - Correct holding time calculations
    - No overnight position carryover
    
    Args:
        params (dict): Backtest parameters from user input
    """
    try:
        print("\n" + "=" * 60)
        print("   📊 FIXED HISTORICAL BACKTEST (NO OVERNIGHT BUG)")
        print("=" * 60)
        
        # Extract parameters
        start_date = params['start_date']
        end_date = params['end_date']
        sentiment_threshold = params.get('sentiment_threshold', 0.2)
        # New: allow full sentiment range per strategy
        sentiment_min = params.get('sentiment_min', sentiment_threshold)
        sentiment_max = params.get('sentiment_max', 1.0)
        stop_loss_pct = params['stop_loss_pct']
        take_profit_pct = params['take_profit_pct']
        investment_per_stock = params['investment_per_stock']
        
        print(f"📋 BACKTEST PARAMETERS:")
        print(f"📅 Date range: {start_date} to {end_date}")
        print(f"📊 Sentiment filter: [{sentiment_min:.2f}, {sentiment_max:.2f}] (min/max)")
        print(f"🛡️  Stop Loss: {stop_loss_pct:.1f}%")
        print(f"💰 Take Profit: {take_profit_pct:.1f}%")
        print(f"💼 Investment per Stock: ${investment_per_stock:,.0f}")
        
        # Load stock universe
        stocks = load_stock_universe()
        print(f"✅ Loaded {len(stocks)} stocks from universe")
        
        # Initialize analyzer
        analyzer = VolumeNewsAnalyzer()
        
        # Convert dates to date objects for iteration
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        all_trades = []
        current_date = start_dt
        
        print(f"🔄 Processing {(end_dt - start_dt).days + 1} days with FIXED logic...")
        print(f"🔧 NO OVERNIGHT CARRYOVER - Each day is independent!")
        
        while current_date <= end_dt:
            if current_date.weekday() < 5:  # Skip weekends
                date_str = current_date.strftime('%Y-%m-%d')
                
                try:
                    # Screen stocks for this day ONLY
                    # Pass strategy-specific sentiment range to analyzer so selection differs per strategy
                    qualified_stocks = analyzer.screen_stocks_by_volume_and_news(
                        stocks, date_str, min_news_count=2, min_sentiment=sentiment_min, max_sentiment=sentiment_max
                    )
                    
                    if qualified_stocks:
                        print(f"\n📅 {date_str}: {len(qualified_stocks)} qualified stocks")
                        
                        # Process each qualified stock
                        for stock_data in qualified_stocks:
                            ticker = stock_data['ticker']
                            sentiment = stock_data['weighted_sentiment']
                            
                            # Check if sentiment is within strategy-specific range
                            if sentiment_min <= sentiment <= sentiment_max:
                                
                                # Get MINUTE-LEVEL price data for this day ONLY
                                # CRITICAL FIX: Use datetime objects with market hours
                                start_dt_market = datetime.strptime(date_str, '%Y-%m-%d').replace(hour=9, minute=30)
                                end_dt_market = datetime.strptime(date_str, '%Y-%m-%d').replace(hour=16, minute=0)
                                price_data = get_historical_data(ticker, start_dt_market, end_dt_market, '1Min')
                                
                                if price_data is not None and not price_data.empty:
                                    # Simulate trade for this day ONLY
                                    trade = simulate_trade_FIXED(
                                        ticker, price_data, date_str, sentiment,
                                        stop_loss_pct, take_profit_pct, investment_per_stock
                                    )
                                    
                                    if trade:
                                        all_trades.append(trade)
                                        print(f"   💰 {ticker}: ${trade['pnl_usd']:+,.0f} ({trade['holding_minutes']:.0f}min, {trade['exit_reason']})")
                    
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
            
            # Count exit reasons
            tp_count = len(df[df['exit_reason'] == 'TAKE_PROFIT'])
            sl_count = len(df[df['exit_reason'] == 'STOP_LOSS'])
            eod_count = len(df[df['exit_reason'] == 'EOD'])
            
            print(f"\n✅ FIXED BACKTEST RESULTS:")
            print(f"   Trades: {trade_count}")
            print(f"   P&L: ${total_pnl:,.2f}")
            print(f"   Win Rate: {win_rate:.1f}%")
            print(f"   Avg Holding: {avg_holding:.1f} minutes ({avg_holding/60:.1f} hours)")
            print(f"   Exit reasons: TP={tp_count}, SL={sl_count}, EOD={eod_count}")
            
            # Verify holding time is reasonable
            max_period_minutes = (end_dt - start_dt).days * 24 * 60
            if avg_holding <= 450:  # Max 7.5 hours per day
                print(f"   ✅ HOLDING TIME IS CORRECT (≤ 450 min per day)")
            else:
                print(f"   ❌ HOLDING TIME IS STILL WRONG (> 450 min per day)")
            
            # Save results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"backtest_report_FIXED_{timestamp}.xlsx"
            
            try:
                df.to_excel(filename, index=False)
                print(f"💾 FIXED results saved to: {filename}")
            except Exception as e:
                csv_filename = f"backtest_report_FIXED_{timestamp}.csv"
                df.to_csv(csv_filename, index=False)
                print(f"💾 FIXED CSV saved to: {csv_filename}")
            
            return {
                'trades': all_trades,
                'summary': {
                    'total_trades': trade_count,
                    'total_pnl': total_pnl,
                    'win_rate': win_rate,
                    'avg_holding_minutes': avg_holding
                }
            }
        else:
            print(f"\n⚠️  No trades found in FIXED backtest")
            return {
                'trades': [],
                'summary': {
                    'total_trades': 0,
                    'total_pnl': 0.0,
                    'win_rate': 0.0,
                    'avg_holding_minutes': 0.0
                }
            }
            
    except Exception as e:
        print(f"❌ Error in FIXED backtest: {e}")
        import traceback
        traceback.print_exc()
        return None

def simulate_trade_FIXED(ticker, price_data, date_str, sentiment, stop_loss_pct, take_profit_pct, investment_per_stock):
    """
    FIXED trade simulation with correct holding time calculation
    """
    try:
        if price_data is None or price_data.empty:
            return None
            
        # Entry at market open (first available bar)
        entry_time = price_data.index[0]
        entry_price = price_data.iloc[0]['open']
        
        # Calculate position size
        shares = int(investment_per_stock / entry_price)
        
        # Calculate stop loss and take profit levels
        stop_loss_price = entry_price * (1 - stop_loss_pct / 100)
        take_profit_price = entry_price * (1 + take_profit_pct / 100)
        
        # Check each minute for exit conditions
        exit_time = None
        exit_price = None
        exit_reason = None
        
        for timestamp, row in price_data.iterrows():
            if timestamp <= entry_time:
                continue
                
            high = row['high']
            low = row['low']
            
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
        
        if exit_time is None:
            # End of day exit
            exit_price = price_data.iloc[-1]['close']
            exit_reason = 'EOD'
            exit_time = price_data.index[-1]
        
        # Calculate P&L and holding time
        pnl_usd = (exit_price - entry_price) * shares
        holding_minutes = (exit_time - entry_time).total_seconds() / 60
        
        # Calculate P&L percentage against the capital deployed in this position
        position_capital = entry_price * shares if shares > 0 else investment_per_stock
        pnl_pct = (pnl_usd / position_capital) * 100 if position_capital else 0.0
        
        return {
            'trade_id': f"{ticker}_{date_str}_FIXED",
            'open_time': entry_time,
            'close_time': exit_time,
            'symbol': ticker,
            'qty': shares,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl_usd': pnl_usd,
            'pnl_pct': pnl_pct,
            'exit_reason': exit_reason,
            'holding_minutes': holding_minutes,
            'sentiment_score': sentiment
        }
        
    except Exception as e:
        print(f"   ❌ Error simulating {ticker}: {e}")
        return None
