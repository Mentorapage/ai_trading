#!/usr/bin/env python3
"""
Run EXACTLY 20 baseline strategies (S01–S20) over 2024-11-11 → 2025-08-20
and log every trade with the required fields.

Outputs:
- logs/trades_S01-S20_2024-11-11_2025-08-20.csv
- logs/trades_S01-S20_2024-11-11_2025-08-20.parquet

Each row fields:
trade_id, open_time, close_time, symbol, strategy_id, qty, entry_price, exit_price,
fees_usd, pnl_usd, pnl_pct, exit_reason, stop_pct, take_pct, sentiment_score, sentiment_label, news_headline
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
from historical_backtest import get_historical_data
from run_real_strategy_batch import simulate_intraday_trade
from volume_news_analyzer import VolumeNewsAnalyzer


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


def get_trading_days(start_d: date, end_d: date):
    nyse = mcal.get_calendar('NYSE')
    days = nyse.valid_days(start_date=start_d, end_date=end_d)
    return [d.date() if hasattr(d, 'date') else d for d in days]


def make_trade_id(strategy_id: str, symbol: str, open_time: datetime, close_time: datetime, entry_price: float, exit_price: float, qty: int) -> str:
    basis = f"{strategy_id}|{symbol}|{open_time.strftime('%Y-%m-%d %H:%M:%S')}|{close_time.strftime('%Y-%m-%d %H:%M:%S')}|{entry_price}|{exit_price}|{qty}"
    return hashlib.sha256(basis.encode('utf-8')).hexdigest()[:16]


def label_sentiment(score: float) -> str:
    if score >= 0.05:
        return 'POS'
    if score <= -0.05:
        return 'NEG'
    return 'NEU'


def main():
    parser = argparse.ArgumentParser(description='Run S01–S20 backtest for a date range and append trades')
    parser.add_argument('--start', help='Start date YYYY-MM-DD (default 2024-11-11)')
    parser.add_argument('--end', help='End date YYYY-MM-DD (default 2025-08-20)')
    parser.add_argument('--out', help='Output CSV path (default logs/trades_S01-S20_2024-11-11_2025-08-20.csv)')
    args = parser.parse_args()
    logs_dir = Path('logs')
    logs_dir.mkdir(exist_ok=True)
    default_csv = 'trades_S01-S20_2024-11-11_2025-08-20.csv'
    csv_path = logs_dir / (args.out if args.out else default_csv)
    parquet_path = Path(str(csv_path).replace('.csv', '.parquet'))

    # Prepare CSV
    initialize = not csv_path.exists()

    headers = [
        'trade_id','open_time','close_time','symbol','strategy_id','qty',
        'entry_price','exit_price','fees_usd','pnl_usd','pnl_pct','exit_reason',
        'stop_pct','take_pct','sentiment_score','sentiment_label','news_headline'
    ]
    if initialize:
        with open(csv_path, 'w', newline='') as f:
            csv.writer(f).writerow(headers)

    # Setup
    analyzer = VolumeNewsAnalyzer()
    stocks = load_stock_universe()
    start_date = datetime.strptime(args.start, '%Y-%m-%d').date() if args.start else date(2024,11,11)
    end_date = datetime.strptime(args.end, '%Y-%m-%d').date() if args.end else date(2025,8,20)
    trading_days = get_trading_days(start_date, end_date)

    total_logged = 0
    print(f"🚀 S01–S20 run: {len(STRATEGIES)} strategies, {len(trading_days)} days, {len(stocks)} tickers", flush=True)

    for idx, day in enumerate(trading_days, 1):
        day_str = day.strftime('%Y-%m-%d')
        print(f"📅 {day_str} ({idx}/{len(trading_days)})", flush=True)

        # Pre-screen ONCE for the day with BROAD range, then filter per strategy in-memory
        try:
            day_screen = analyzer.screen_stocks_by_volume_and_news(
                stocks=stocks,
                analysis_date=day_str,
                min_news_count=2,
                min_sentiment=0.0,
                max_sentiment=1.0
            )
        except Exception as e:
            print(f"   ❌ day pre-screen failed: {e}", flush=True)
            continue

        by_ticker = {s['ticker']: s for s in day_screen}
        print(f"   ✅ pre-screen qualified={len(by_ticker)}", flush=True)

        for strategy in STRATEGIES:
            # Filter by strategy sentiment window
            strategy_qualified = []
            try:
                for s in day_screen:
                    sent = float(s.get('weighted_sentiment', 0.0))
                    if s.get('articles_count', 0) >= 2 and float(strategy['min_sentiment']) <= sent <= float(strategy['max_sentiment']):
                        strategy_qualified.append(s)
            except Exception as e:
                print(f"   ⚠️  strategy {strategy['id']} filter failed: {e}", flush=True)
                continue

            if not strategy_qualified:
                continue

            print(f"   ▶ {strategy['id']}: {len(strategy_qualified)} stocks", flush=True)

            for stock in strategy_qualified:
                ticker = stock['ticker']
                try:
                    # Market data 09:30–16:00 ET
                    md = get_historical_data(
                        ticker=ticker,
                        start_date=datetime.combine(day, dt_time(9,30)),
                        end_date=datetime.combine(day, dt_time(16,0)),
                        timeframe='1Min'
                    )
                    if md is None or len(md) == 0:
                        continue

                    md = md.between_time('09:30','16:00')
                    if len(md) == 0:
                        continue

                    entry_time = md.index[0]
                    entry_price = float(md.iloc[0]['close'])
                    shares = int(1_000_000 / entry_price)
                    if shares <= 0:
                        continue

                    tr = simulate_intraday_trade(
                        ticker=ticker,
                        entry_price=entry_price,
                        entry_time=entry_time,
                        shares=shares,
                        market_data=md,
                        stop_loss_pct=float(strategy['stop_pct']),
                        take_profit_pct=float(strategy['take_pct'])
                    )
                    if not tr:
                        continue

                    exit_time = tr['exit_time']
                    exit_price = float(tr['exit_price'])
                    pnl_usd = float(tr['pnl'])
                    # Calculate P&L as percentage of total capital (14M for 14 stocks)
                    investment_per_stock = 1_000_000  # $1M per stock
                    shares = int(investment_per_stock / entry_price)
                    total_capital = 14_000_000  # 14M total capital for 14 stocks
                    pnl_pct = (exit_price - entry_price) * shares / total_capital * 100.0
                    trade_id = make_trade_id(strategy['id'], ticker, entry_time, exit_time, entry_price, exit_price, int(tr['shares']))
                    headline = stock.get('top_headline','')
                    sent_score = float(stock.get('weighted_sentiment', 0.0))
                    sent_label = label_sentiment(sent_score)

                    row = [
                        trade_id,
                        entry_time.strftime('%Y-%m-%d %H:%M:%S'),
                        exit_time.strftime('%Y-%m-%d %H:%M:%S'),
                        ticker,
                        strategy['id'],
                        int(tr['shares']),
                        entry_price,
                        exit_price,
                        0.0,
                        pnl_usd,
                        pnl_pct,
                        tr['exit_reason'],
                        float(strategy['stop_pct']),
                        float(strategy['take_pct']),
                        sent_score,
                        sent_label,
                        headline
                    ]

                    with open(csv_path, 'a', newline='') as f:
                        csv.writer(f).writerow(row)
                    total_logged += 1
                    if total_logged % 100 == 0:
                        print(f"   📝 Logged {total_logged} trades...", flush=True)

                except Exception as e:
                    # Continue on errors per ticker
                    continue

    print(f"\n📊 FINALIZING", flush=True)
    print(f"   Total trades logged: {total_logged}", flush=True)
    # Save Parquet
    try:
        df = pd.read_csv(csv_path)
        df.to_parquet(parquet_path, index=False)
        print(f"   ✅ CSV: {csv_path}")
        print(f"   ✅ Parquet: {parquet_path}")
    except Exception as e:
        print(f"   ⚠️  Parquet save failed: {e}")

if __name__ == '__main__':
    main()


