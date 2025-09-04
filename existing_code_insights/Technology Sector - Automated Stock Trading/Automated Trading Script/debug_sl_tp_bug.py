#!/usr/bin/env python3
"""
Debug Script: Trace SL/TP Parameter Bug
"""

import pandas as pd
import numpy as np
from datetime import datetime, time
import random

def simulate_trade_debug(entry_price: float, stop_loss_pct: float, take_profit_pct: float, strategy_id: str):
    """Debug version of trade simulation to trace SL/TP usage"""
    
    # Calculate levels
    stop_loss_price = entry_price * (1 - stop_loss_pct / 100)
    take_profit_price = entry_price * (1 + take_profit_pct / 100)
    
    print(f"Strategy {strategy_id}:")
    print(f"  Entry: ${entry_price:.2f}")
    print(f"  SL {stop_loss_pct}% → ${stop_loss_price:.2f}")
    print(f"  TP {take_profit_pct}% → ${take_profit_price:.2f}")
    
    # Simulate some price movement
    price_moves = [
        entry_price * 0.97,  # -3% (should hit SL for most strategies)
        entry_price * 1.08,  # +8% (should hit TP for most strategies)
        entry_price * 1.02   # +2% (EOD exit)
    ]
    
    for i, price in enumerate(price_moves):
        if price <= stop_loss_price:
            return_pct = (price - entry_price) / entry_price * 100
            print(f"  → SL HIT at ${price:.2f} ({return_pct:+.2f}%)")
            return return_pct, 'STOP_LOSS'
        elif price >= take_profit_price:
            return_pct = (price - entry_price) / entry_price * 100
            print(f"  → TP HIT at ${price:.2f} ({return_pct:+.2f}%)")
            return return_pct, 'TAKE_PROFIT'
    
    # EOD exit
    final_price = price_moves[-1]
    return_pct = (final_price - entry_price) / entry_price * 100
    print(f"  → EOD EXIT at ${final_price:.2f} ({return_pct:+.2f}%)")
    return return_pct, 'EOD'

def main():
    print("🔍 DEBUGGING SL/TP PARAMETER BUG")
    print("=" * 60)
    
    # Test the strategies that should have different results but don't
    identical_strategies = [
        {"id": "02", "stop_pct": 5, "take_pct": 5},
        {"id": "04", "stop_pct": 7, "take_pct": 7},
        {"id": "06", "stop_pct": 10, "take_pct": 20},
        {"id": "08", "stop_pct": 7, "take_pct": 10},
        {"id": "10", "stop_pct": 6, "take_pct": 10},
    ]
    
    entry_price = 100.0
    
    print("🧪 TESTING IDENTICAL STRATEGIES WITH DIFFERENT SL/TP:")
    print()
    
    results = []
    
    for strategy in identical_strategies:
        return_pct, exit_reason = simulate_trade_debug(
            entry_price, 
            strategy['stop_pct'], 
            strategy['take_pct'], 
            strategy['id']
        )
        results.append({
            'strategy_id': strategy['id'],
            'stop_pct': strategy['stop_pct'],
            'take_pct': strategy['take_pct'],
            'return_pct': return_pct,
            'exit_reason': exit_reason
        })
        print()
    
    print("📊 EXPECTED RESULTS:")
    for result in results:
        print(f"Strategy {result['strategy_id']}: {result['return_pct']:+.2f}% ({result['exit_reason']})")
    
    print()
    print("🚨 ACTUAL RESULTS FROM BACKTEST:")
    print("ALL 5 strategies: +14.28% (IDENTICAL!)")
    print()
    print("💡 CONCLUSION:")
    print("The SL/TP logic SHOULD produce different results.")
    print("The fact that they're identical suggests:")
    print("1. SL/TP parameters are not being passed correctly")
    print("2. OR there's a bug in the trade simulation loop")
    print("3. OR all trades are exiting via EOD with the same return")
    
    # Let's check what +14.28% corresponds to
    target_return = 0.142824
    print(f"\\n🔍 REVERSE ENGINEERING +14.28% RETURN:")
    print(f"If entry = $100, exit = ${100 * (1 + target_return):.2f}")
    print("This suggests all trades are exiting at the same price level!")

if __name__ == "__main__":
    main()
