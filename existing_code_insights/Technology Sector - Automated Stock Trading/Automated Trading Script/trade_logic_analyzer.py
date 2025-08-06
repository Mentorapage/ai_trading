#!/usr/bin/env python3
"""
Trade Logic Analyzer - Detailed Analysis of Backtesting Trade Outcome Logic
Explains exactly how profits/losses are determined in the backtesting system
"""

import random
from typing import Dict, Tuple
from datetime import datetime

class TradeLogicAnalyzer:
    """
    Analyzes and demonstrates the trade outcome determination logic
    """
    
    def __init__(self):
        self.examples = []
        
    def display_banner(self):
        """Display analysis banner"""
        print("🔍" + "=" * 78 + "🔍")
        print("    TRADE LOGIC ANALYZER - BACKTESTING OUTCOME DETERMINATION")
        print("=" * 80)
        print("📊 Detailed Analysis of How Profits/Losses Are Calculated")
        print("🎯 Explanation of Take-Profit vs Stop-Loss Logic")
        print("📈 Current Implementation vs Best Practices")
        print("=" * 80)
        
    def analyze_current_logic(self):
        """Analyze the current trade outcome determination logic"""
        
        print("\n🔍 CURRENT BACKTESTING LOGIC ANALYSIS:")
        print("=" * 60)
        
        print("\n📊 1. PRICE DATA STRUCTURE:")
        print("   • Uses single daily OHLC (Open, High, Low, Close) bars")
        print("   • Each day gets ONE price bar with 4 values:")
        print("     - Open: Entry price (simulated)")
        print("     - High: Daily high (Open * 1.01 to 1.03)")
        print("     - Low: Daily low (Open * 0.97 to 0.99)")
        print("     - Close: Exit price if no TP/SL hit (Open * 0.99 to 1.01)")
        
        print("\n🎯 2. TRADE OUTCOME DETERMINATION:")
        print("   Current logic in simulate_trade_execution():")
        print("   ```python")
        print("   if high >= tp_price:")
        print("       outcome = 'take_profit'")
        print("   elif low <= sl_price:")
        print("       outcome = 'stop_loss'")
        print("   else:")
        print("       outcome = 'market_close'")
        print("   ```")
        
        print("\n⚠️  CRITICAL ISSUE WITH CURRENT LOGIC:")
        print("   • Uses IF-ELIF structure - checks TP first, then SL")
        print("   • If BOTH TP and SL are reached in same bar:")
        print("     → Always assumes TP was hit first")
        print("     → This creates unrealistic bias toward profits")
        print("   • Does NOT consider price sequence or timing within the bar")
        
        print("\n❌ PROBLEMS:")
        print("   1. Unrealistic win rate (100% in recent test)")
        print("   2. No consideration of which level was hit first")
        print("   3. No intraday price movement simulation")
        print("   4. Assumes instant fills at exact TP/SL prices")
        print("   5. No realistic execution delays or slippage")
        
    def demonstrate_current_logic_examples(self):
        """Show examples of how current logic works"""
        
        print(f"\n📋 CURRENT LOGIC EXAMPLES:")
        print("=" * 60)
        
        examples = [
            {
                'name': 'Scenario 1: Only TP Hit',
                'entry_price': 100.00,
                'take_profit': 1.00,  # TP at $101.00
                'stop_loss': 2.00,    # SL at $98.00
                'price_data': {'open': 100.00, 'high': 101.50, 'low': 99.50, 'close': 100.80},
                'expected': 'take_profit'
            },
            {
                'name': 'Scenario 2: Only SL Hit',
                'entry_price': 100.00,
                'take_profit': 1.00,  # TP at $101.00
                'stop_loss': 2.00,    # SL at $98.00
                'price_data': {'open': 100.00, 'high': 100.50, 'low': 97.00, 'close': 99.20},
                'expected': 'stop_loss'
            },
            {
                'name': 'Scenario 3: BOTH TP and SL Hit (PROBLEM CASE)',
                'entry_price': 100.00,
                'take_profit': 1.00,  # TP at $101.00
                'stop_loss': 2.00,    # SL at $98.00
                'price_data': {'open': 100.00, 'high': 102.00, 'low': 97.00, 'close': 100.50},
                'expected_current': 'take_profit (BIASED)',
                'reality': 'Could be either - depends on sequence'
            },
            {
                'name': 'Scenario 4: Neither Hit',
                'entry_price': 100.00,
                'take_profit': 1.00,  # TP at $101.00
                'stop_loss': 2.00,    # SL at $98.00
                'price_data': {'open': 100.00, 'high': 100.80, 'low': 98.50, 'close': 100.20},
                'expected': 'market_close'
            }
        ]
        
        for i, example in enumerate(examples, 1):
            print(f"\n{i}️⃣  {example['name']}:")
            print(f"   Entry Price: ${example['entry_price']:.2f}")
            print(f"   Take Profit: ${example['entry_price'] + example['take_profit']:.2f}")
            print(f"   Stop Loss:   ${example['entry_price'] - example['stop_loss']:.2f}")
            print(f"   Price Data:  Open=${example['price_data']['open']:.2f}, "
                  f"High=${example['price_data']['high']:.2f}, "
                  f"Low=${example['price_data']['low']:.2f}, "
                  f"Close=${example['price_data']['close']:.2f}")
            
            # Simulate current logic
            result = self.simulate_current_logic(
                example['entry_price'], 
                example['take_profit'], 
                example['stop_loss'], 
                example['price_data']
            )
            
            if 'expected_current' in example:
                print(f"   Current Result: {result} ⚠️")
                print(f"   Reality: {example['reality']}")
            else:
                print(f"   Result: {result} ✅")
    
    def simulate_current_logic(self, entry_price: float, take_profit: float, 
                              stop_loss: float, price_data: Dict) -> str:
        """Simulate the current backtesting logic exactly as implemented"""
        tp_price = round(entry_price + take_profit, 2)
        sl_price = round(entry_price - stop_loss, 2)
        
        high = price_data['high']
        low = price_data['low']
        
        # Current logic (problematic)
        if high >= tp_price:
            return 'take_profit'
        elif low <= sl_price:
            return 'stop_loss'
        else:
            return 'market_close'
    
    def explain_improved_logic(self):
        """Explain how the logic should be improved"""
        
        print(f"\n🚀 IMPROVED TRADE LOGIC RECOMMENDATIONS:")
        print("=" * 60)
        
        print("\n1️⃣  PRIORITY-BASED DETERMINATION:")
        print("   When both TP and SL are hit in same bar:")
        print("   • Check distance from entry to each level")
        print("   • Assume closer level is hit first")
        print("   • More realistic than always choosing TP")
        
        print("\n2️⃣  PROBABILISTIC APPROACH:")
        print("   When both levels hit:")
        print("   • 50/50 random chance between TP and SL")
        print("   • Or weight based on distance from entry")
        print("   • Removes artificial profit bias")
        
        print("\n3️⃣  INTRADAY SIMULATION:")
        print("   • Simulate multiple price points within each bar")
        print("   • Use random walk or realistic price movements")
        print("   • Check TP/SL at each simulated tick")
        
        print("\n4️⃣  REALISTIC EXECUTION:")
        print("   • Add slippage (1-3 ticks away from exact level)")
        print("   • Simulate execution delays")
        print("   • Account for bid-ask spreads")
        
        print("\n📊 RECOMMENDED IMPLEMENTATION:")
        print("   ```python")
        print("   def improved_trade_execution(entry, tp_amt, sl_amt, ohlc):")
        print("       tp_price = entry + tp_amt")
        print("       sl_price = entry - sl_amt")
        print("       ")
        print("       high, low = ohlc['high'], ohlc['low']")
        print("       ")
        print("       # Check if both levels hit")
        print("       tp_hit = high >= tp_price")
        print("       sl_hit = low <= sl_price")
        print("       ")
        print("       if tp_hit and sl_hit:")
        print("           # Determine which was hit first")
        print("           tp_distance = tp_price - entry")
        print("           sl_distance = entry - sl_price")
        print("           ")
        print("           if tp_distance <= sl_distance:")
        print("               return 'take_profit'")
        print("           else:")
        print("               return 'stop_loss'")
        print("       elif tp_hit:")
        print("           return 'take_profit'")
        print("       elif sl_hit:")
        print("           return 'stop_loss'")
        print("       else:")
        print("           return 'market_close'")
        print("   ```")
    
    def demonstrate_improved_logic(self):
        """Demonstrate improved logic with examples"""
        
        print(f"\n🧪 IMPROVED LOGIC DEMONSTRATION:")
        print("=" * 60)
        
        # Test case where both TP and SL are hit
        entry_price = 100.00
        take_profit = 1.50  # TP at $101.50
        stop_loss = 2.00    # SL at $98.00
        price_data = {'open': 100.00, 'high': 102.00, 'low': 97.50, 'close': 100.50}
        
        print(f"\n📊 TEST CASE - Both Levels Hit:")
        print(f"   Entry: ${entry_price:.2f}")
        print(f"   Take Profit: ${entry_price + take_profit:.2f} (distance: ${take_profit:.2f})")
        print(f"   Stop Loss: ${entry_price - stop_loss:.2f} (distance: ${stop_loss:.2f})")
        print(f"   Price Range: ${price_data['low']:.2f} - ${price_data['high']:.2f}")
        
        # Current (biased) logic
        current_result = self.simulate_current_logic(entry_price, take_profit, stop_loss, price_data)
        print(f"\n   Current Logic Result: {current_result} ⚠️ (always TP when both hit)")
        
        # Improved logic
        improved_result = self.simulate_improved_logic(entry_price, take_profit, stop_loss, price_data)
        print(f"   Improved Logic Result: {improved_result} ✅ (closer level wins)")
        
        # Distance-based explanation
        tp_distance = take_profit
        sl_distance = stop_loss
        print(f"\n   📏 Distance Analysis:")
        print(f"   • TP Distance: ${tp_distance:.2f}")
        print(f"   • SL Distance: ${sl_distance:.2f}")
        print(f"   • Closer Level: {'Take Profit' if tp_distance <= sl_distance else 'Stop Loss'}")
        print(f"   • Logic: Closer level likely hit first")
    
    def simulate_improved_logic(self, entry_price: float, take_profit: float, 
                               stop_loss: float, price_data: Dict) -> str:
        """Simulate improved trade logic that considers distance"""
        tp_price = round(entry_price + take_profit, 2)
        sl_price = round(entry_price - stop_loss, 2)
        
        high = price_data['high']
        low = price_data['low']
        
        tp_hit = high >= tp_price
        sl_hit = low <= sl_price
        
        if tp_hit and sl_hit:
            # Both hit - determine which was closer (likely hit first)
            tp_distance = take_profit
            sl_distance = stop_loss
            
            if tp_distance <= sl_distance:
                return 'take_profit (closer level)'
            else:
                return 'stop_loss (closer level)'
        elif tp_hit:
            return 'take_profit'
        elif sl_hit:
            return 'stop_loss'
        else:
            return 'market_close'
    
    def calculate_bias_impact(self):
        """Calculate the impact of the current biased logic"""
        
        print(f"\n📈 BIAS IMPACT ANALYSIS:")
        print("=" * 60)
        
        print("\n🎯 Current System Results:")
        print("   • Win Rate: 100% (44/44 trades)")
        print("   • Total Profit: +$946.40")
        print("   • This is UNREALISTIC for any trading strategy")
        
        print("\n⚠️  Why 100% Win Rate is Impossible:")
        print("   1. Market volatility ensures some SL hits")
        print("   2. News sentiment isn't perfectly predictive")
        print("   3. Real trading has slippage and execution delays")
        print("   4. High-frequency moves can hit both levels")
        
        print("\n📊 Realistic Expectations:")
        print("   • Good strategies: 55-65% win rate")
        print("   • Excellent strategies: 65-75% win rate")
        print("   • 100% win rate: Indicates flawed backtesting")
        
        print("\n🔧 Impact of Fixing the Logic:")
        print("   • Win rate would likely drop to 60-70%")
        print("   • Some trades would show losses")
        print("   • Results would be more realistic and trustworthy")
        print("   • Better strategy validation and risk assessment")
    
    def run_complete_analysis(self):
        """Run the complete trade logic analysis"""
        self.display_banner()
        self.analyze_current_logic()
        self.demonstrate_current_logic_examples()
        self.explain_improved_logic()
        self.demonstrate_improved_logic()
        self.calculate_bias_impact()
        
        print(f"\n🎯 SUMMARY:")
        print("=" * 60)
        print("❌ Current Logic: Biased toward profits (IF TP, ELIF SL)")
        print("✅ Improved Logic: Distance-based or probabilistic determination")
        print("📊 Impact: More realistic win rates and better strategy validation")
        print("🚀 Recommendation: Implement improved logic for accurate backtesting")

def main():
    """Main execution function"""
    analyzer = TradeLogicAnalyzer()
    analyzer.run_complete_analysis()

if __name__ == "__main__":
    main() 