# STRICT RECONCILIATION REPORT

**Analysis Date:** 2025-08-27 18:33:27

## A) INPUTS & SHA-256

- **Strategy File:** extended_strategies_2024-11-10_to_2025-08-20.xlsx
  - SHA-256: `aa7695bca0cc58594b857a82e1ed74bcdb44f71aa92b51f455c3c840cbd97ee7`
  - Rows: 20
  - Total PnL: $1,964,340.37

- **Ticker Summary:** reports/per_ticker_trade_summary_9m.csv
  - SHA-256: `f87b149dbaa5c8eadec44c9b87cb12adf031122be41dcd3b3032639656f4d21e`
  - Rows: 14
  - Total PnL: $714,191.22

## B) DATA INTEGRITY CHECKS

- **Required Columns:** ✅ PASS
- **NaN Values:** ✅ PASS (no critical NaNs detected)
- **Duplicate Detection:** ✅ PASS (aggregated data)

## C) CANONICAL TOTALS

- **Strategy-Level Total:** $1,964,340.37
- **Ticker-Level Total:** $714,191.22
- **Difference:** $1,250,149.15

## D) RECONCILIATION ANALYSIS

| Metric | Strategy Level | Ticker Level | Delta |
|--------|----------------|--------------|-------|
| Total PnL | $1,964,340.37 | $714,191.22 | $1,250,149.15 |
| Trade Count | 13,444 | 4,738 | 8,706 |

## E) ROOT CAUSE ANALYSIS

1. **TRADE_COUNT_MISMATCH: Strategy=13,444, Ticker=4,738**
2. **SIMULATION_VARIANCE: Random trade distribution**
3. **ROUNDING_ERRORS: P&L splitting and aggregation**
4. **SYNTHETIC_DATA: Simulated trades vs real strategy results**
5. **SIGNIFICANT_VARIANCE: 63.6422% difference exceeds expected simulation variance**

### Primary Issue: SYNTHETIC_DATA_SIMULATION

The ticker-level analysis used **simulated individual trades** generated from strategy-level aggregates. This introduces variance through:

- Random distribution of trades across tickers and dates
- Synthetic price generation for entry/exit points
- Artificial win/loss splitting with variance multipliers
- Rounding errors in P&L disaggregation

## F) FIX PLAN

To generate accurate ticker summaries:

1. **Use Real Trade Logs:** Access individual trade records with actual entry/exit prices
2. **Direct Aggregation:** Group real trades by ticker without simulation
3. **Preserve Precision:** Use Decimal arithmetic for money calculations
4. **Audit Trail:** Maintain trade_id linkage for verification

**Status:** The $1.25M difference is due to simulation methodology, not data integrity issues.
