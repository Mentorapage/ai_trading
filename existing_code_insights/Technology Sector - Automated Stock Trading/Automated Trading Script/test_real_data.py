#!/usr/bin/env python3
from run_clean_backtest import run_clean_strategy_backtest
from trading_core import load_stock_universe

# Test on December 2024 - real historical data
strategies = [
    {"id": "S01", "stop_pct": 3, "take_pct": 5, "min_sentiment": 0.10, "max_sentiment": 0.60},
    {"id": "S02", "stop_pct": 3, "take_pct": 8, "min_sentiment": 0.10, "max_sentiment": 0.60},
    {"id": "S03", "stop_pct": 3, "take_pct": 12, "min_sentiment": 0.20, "max_sentiment": 0.70}
]

stocks = load_stock_universe()
start_date = "2024-12-18"
end_date = "2024-12-20"

print(f"🧪 TESTING CLEAN BACKTEST ON REAL HISTORICAL DATA")
print(f"📅 Period: {start_date} to {end_date} (HAS REAL PRICE DATA)")

for strategy in strategies:
    result = run_clean_strategy_backtest(strategy, start_date, end_date, stocks)
    strategy_id = result["strategy_id"]
    trades = result["trade_count"]
    pnl = result["total_pnl_usd"]
    avg_holding = result["avg_holding_minutes"]
    
    print(f"\n{strategy_id}: {trades} trades, ${pnl:,.2f} P&L, {avg_holding:.1f} min avg holding")
    
    # Check if holding time is reasonable for 3-day period
    max_period_minutes = 3 * 24 * 60  # 4320 minutes for 3 days
    if avg_holding <= max_period_minutes:
        print(f"   ✅ Holding time is REASONABLE (≤ {max_period_minutes} min)")
    else:
        print(f"   ❌ Holding time is WRONG (> {max_period_minutes} min)")