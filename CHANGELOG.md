# CHANGELOG

## [2025-01-21] - Stabilization & Realism Updates

### 🔧 Live Trading Stabilization

**Fixed**: Eliminated Alpaca validation errors (e.g., `take_profit.limit_price must be >= base_price + 0.01`)

**Changes**:
- **Re-quoting**: Fresh market quotes obtained immediately before order submission
- **Price Sanitization**: Automatic adjustment of TP/SL prices to meet Alpaca minimum spread requirements
- **Retry Logic**: Up to 2 automatic retries on price validation failures
- **Decimal Precision**: All prices rounded to exact cents using Decimal for precision
- **Enhanced Logging**: Detailed logging of attempt count, base/TP/SL prices, and final outcomes

**Technical Details**:
- Added `get_fresh_quote()` function in `trade_types.py`
- Added `sanitize_bracket()` function with $0.02 minimum spreads for safety
- Added `_cent()` helper for precise penny rounding
- Updated `bracket_order()` with retry logic and fresh price validation
- Updated `execute_trade()` in `live_trading.py` to use target spreads with real-time re-quoting

### 📊 Backtest Realism Enhancement

**Added**: Realistic execution simulation with slippage and order setup delays

**Changes**:
- **Entry Slippage**: $0.01 per trade entry (against trader)
- **Exit Slippage**: $0.01 per trade exit (against trader)  
- **Setup Delay**: 2-second delay before TP/SL orders become active
- **Conservative P&L**: More realistic profit/loss calculations accounting for execution costs

**Technical Details**:
- Added `DEFAULT_SLIPPAGE = 0.01` and `DEFAULT_SETUP_DELAY_SECONDS = 2` constants
- Updated `simulate_trade_execution()` to apply slippage at entry and exit
- Added setup delay logic - TP/SL levels ignored during delay period
- Updated all P&L calculations to use realistic entry prices
- Enhanced reporting to include realism parameters in Excel output

### 📈 Reporting Improvements

**Enhanced**: Reports now include realism parameters and improved logging

**Changes**:
- Excel reports include slippage and setup delay values
- Console output shows realism settings during backtest
- Enhanced logging for both live and backtest execution
- Improved error messages and attempt tracking

### ✅ Safety & Compatibility

**Maintained**: All existing functionality and user interfaces preserved

**Guarantees**:
- No changes to user-facing prompts or menu flows
- No changes to `main.py` entry points
- No changes to parameter collection (dates, sentiment, capital amounts)
- Backward compatible with existing `.env` configurations
- Paper trading behavior unchanged

### 🧪 Testing Recommendations

**Live Trading**:
- Test with volatile tickers (META, NVDA) using small TP/SL spreads
- Verify no `42210000` validation errors occur
- Confirm retry logic works on price race conditions

**Backtest**:
- Compare results before/after update (expect ~2-4% lower returns due to realism)
- Verify per-stock capital sizing reflected in share counts and P&L
- Check Excel reports include new realism parameters

---

## Files Modified

- `trade_types.py`: Added helper functions, re-quoting, and retry logic
- `live_trading.py`: Updated execute_trade() for fresh quotes
- `historical_backtest.py`: Added slippage, setup delays, and enhanced reporting
- `CHANGELOG.md`: This documentation

## No Breaking Changes

All existing API signatures and user interfaces remain unchanged. Internal enhancements only.




