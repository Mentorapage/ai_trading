#!/usr/bin/env python3
"""
CONCURRENT EXPOSURE ANALYZER
============================
Analyzes actual capital requirements based on maximum concurrent positions
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from pathlib import Path
import json

def analyze_concurrent_exposure():
    """Analyze the extended backtest to determine real capital requirements"""
    
    print("🔍 ANALYZING CONCURRENT EXPOSURE FROM EXTENDED BACKTEST")
    print("=" * 70)
    
    # Read the extended results
    results_file = "extended_strategies_2024-11-10_to_2025-08-20.xlsx"
    
    try:
        df = pd.read_excel(results_file, sheet_name='Strategies')
        print(f"✅ Loaded results from {results_file}")
    except Exception as e:
        print(f"❌ Error loading results: {e}")
        return
    
    # Find the best performing strategy (S02)
    best_strategy = df.loc[df['pnl_usd'].idxmax()]
    strategy_id = best_strategy['strategy_id']
    
    print(f"\n📊 ANALYZING BEST STRATEGY: {strategy_id}")
    print(f"Original metrics:")
    print(f"  Total trades: {best_strategy['trades_count']:,}")
    print(f"  Total P&L: ${best_strategy['pnl_usd']:,.2f}")
    print(f"  Return %: {best_strategy['pnl_pct']:.4f}%")
    
    # Since we don't have individual trade logs, we need to estimate concurrent exposure
    # from the audit logs and daily qualified stocks
    
    print(f"\n🔍 ESTIMATING CONCURRENT EXPOSURE...")
    
    # Load audit logs to understand daily qualified stocks
    audit_dir = Path("audit_logs")
    
    if not audit_dir.exists():
        print("❌ Audit logs directory not found")
        return
    
    # Get all audit files
    audit_files = list(audit_dir.glob("volume_news_audit_*.csv"))
    
    if not audit_files:
        print("❌ No audit files found")
        return
    
    print(f"📁 Found {len(audit_files)} audit files")
    
    # Analyze daily qualified stocks to estimate concurrent positions
    daily_qualified = []
    max_concurrent = 0
    
    for audit_file in sorted(audit_files):
        try:
            audit_df = pd.read_csv(audit_file)
            date_str = audit_file.stem.split('_')[-1]  # Extract date from filename
            
            # Count qualified stocks for this date
            qualified_count = len(audit_df[audit_df['passed_all_filters'] == True])
            daily_qualified.append({
                'date': date_str,
                'qualified_count': qualified_count
            })
            
            if qualified_count > max_concurrent:
                max_concurrent = qualified_count
                
        except Exception as e:
            print(f"⚠️ Error reading {audit_file}: {e}")
            continue
    
    print(f"\n📈 CONCURRENT EXPOSURE ANALYSIS:")
    print(f"  Days analyzed: {len(daily_qualified)}")
    print(f"  Maximum concurrent positions: {max_concurrent}")
    print(f"  Average daily positions: {np.mean([d['qualified_count'] for d in daily_qualified]):.1f}")
    
    # Calculate real capital requirements
    position_size = 1_000_000  # $1M per position
    required_capital = max_concurrent * position_size
    
    print(f"\n💰 CAPITAL REQUIREMENTS:")
    print(f"  Position size: ${position_size:,}")
    print(f"  Max concurrent positions: {max_concurrent}")
    print(f"  Required capital base: ${required_capital:,}")
    
    # Recalculate performance metrics
    total_profit = best_strategy['pnl_usd']
    final_balance = required_capital + total_profit
    total_return_pct = (total_profit / required_capital) * 100
    
    # Calculate annualized return (CAGR) for 9+ months
    start_date = datetime.strptime("2024-11-10", "%Y-%m-%d")
    end_date = datetime.strptime("2025-08-20", "%Y-%m-%d")
    days_elapsed = (end_date - start_date).days
    years_elapsed = days_elapsed / 365.25
    
    cagr = ((final_balance / required_capital) ** (1 / years_elapsed) - 1) * 100
    
    # Average profit per trade
    avg_profit_per_trade = total_profit / best_strategy['trades_count']
    avg_return_per_trade = (avg_profit_per_trade / position_size) * 100
    
    print(f"\n📊 CORRECTED PERFORMANCE METRICS:")
    print(f"  Required capital base: ${required_capital:,}")
    print(f"  Total profit: ${total_profit:,.2f}")
    print(f"  Final balance: ${final_balance:,.2f}")
    print(f"  Total return: {total_return_pct:.2f}%")
    print(f"  Annualized return (CAGR): {cagr:.2f}%")
    print(f"  Average profit per trade: ${avg_profit_per_trade:,.2f}")
    print(f"  Average return per trade: {avg_return_per_trade:.4f}%")
    print(f"  Test period: {days_elapsed} days ({years_elapsed:.2f} years)")
    
    # Create equity curve simulation
    print(f"\n📈 CREATING EQUITY CURVE...")
    
    # Simulate equity curve based on daily P&L
    # Since we don't have exact daily P&L, we'll distribute the total P&L
    # across trading days proportionally to qualified stocks
    
    trading_days = [d for d in daily_qualified if d['qualified_count'] > 0]
    total_qualified = sum(d['qualified_count'] for d in trading_days)
    
    equity_curve = []
    running_balance = required_capital
    
    for day_data in daily_qualified:
        if day_data['qualified_count'] > 0:
            # Proportional P&L for this day
            day_proportion = day_data['qualified_count'] / total_qualified
            day_pnl = total_profit * day_proportion
        else:
            day_pnl = 0
        
        running_balance += day_pnl
        equity_curve.append({
            'date': day_data['date'],
            'balance': running_balance,
            'daily_pnl': day_pnl
        })
    
    # Create equity curve plot
    dates = [datetime.strptime(d['date'], '%Y-%m-%d') for d in equity_curve]
    balances = [d['balance'] for d in equity_curve]
    
    plt.figure(figsize=(12, 8))
    plt.plot(dates, balances, linewidth=2, color='blue')
    plt.axhline(y=required_capital, color='red', linestyle='--', alpha=0.7, label='Initial Capital')
    plt.title(f'Equity Curve - Strategy {strategy_id}\n(Corrected for Concurrent Exposure)', fontsize=14)
    plt.xlabel('Date')
    plt.ylabel('Account Balance ($)')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # Format y-axis as currency
    plt.gca().yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
    
    # Save plot
    plt.savefig('equity_curve_corrected.png', dpi=300, bbox_inches='tight')
    print(f"💾 Equity curve saved as: equity_curve_corrected.png")
    
    # Calculate additional risk metrics
    daily_returns = []
    for i in range(1, len(equity_curve)):
        prev_balance = equity_curve[i-1]['balance']
        curr_balance = equity_curve[i]['balance']
        daily_return = (curr_balance - prev_balance) / prev_balance
        daily_returns.append(daily_return)
    
    # Risk metrics
    if daily_returns:
        volatility = np.std(daily_returns) * np.sqrt(252)  # Annualized volatility
        sharpe_ratio = (cagr / 100) / volatility if volatility > 0 else 0
        
        # Max drawdown
        peak = required_capital
        max_drawdown = 0
        for balance in balances:
            if balance > peak:
                peak = balance
            drawdown = (peak - balance) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        max_drawdown_pct = max_drawdown * 100
    else:
        volatility = 0
        sharpe_ratio = 0
        max_drawdown_pct = 0
    
    print(f"\n📊 RISK METRICS:")
    print(f"  Annualized volatility: {volatility:.2f}%")
    print(f"  Sharpe ratio: {sharpe_ratio:.2f}")
    print(f"  Maximum drawdown: {max_drawdown_pct:.2f}%")
    
    # Save corrected metrics to JSON
    corrected_metrics = {
        'strategy_id': strategy_id,
        'analysis_date': datetime.now().isoformat(),
        'capital_requirements': {
            'max_concurrent_positions': max_concurrent,
            'position_size_usd': position_size,
            'required_capital_base': required_capital
        },
        'performance_metrics': {
            'total_profit_usd': total_profit,
            'final_balance_usd': final_balance,
            'total_return_pct': total_return_pct,
            'annualized_return_cagr_pct': cagr,
            'avg_profit_per_trade_usd': avg_profit_per_trade,
            'avg_return_per_trade_pct': avg_return_per_trade,
            'test_period_days': days_elapsed,
            'test_period_years': years_elapsed
        },
        'risk_metrics': {
            'annualized_volatility_pct': volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown_pct': max_drawdown_pct
        },
        'original_metrics': {
            'total_trades': int(best_strategy['trades_count']),
            'original_return_pct': float(best_strategy['pnl_pct']),
            'turnover_based_calculation': best_strategy['trades_count'] * position_size
        }
    }
    
    with open('corrected_performance_metrics.json', 'w') as f:
        json.dump(corrected_metrics, f, indent=2)
    
    print(f"\n💾 Corrected metrics saved to: corrected_performance_metrics.json")
    
    print(f"\n🎯 SUMMARY:")
    print(f"  ❌ INCORRECT (Turnover-based): {best_strategy['pnl_pct']:.4f}% return")
    print(f"  ✅ CORRECT (Exposure-based): {total_return_pct:.2f}% return")
    print(f"  📈 Annualized (CAGR): {cagr:.2f}%")
    print(f"  🎲 Sharpe Ratio: {sharpe_ratio:.2f}")
    
    return corrected_metrics

if __name__ == "__main__":
    analyze_concurrent_exposure()
