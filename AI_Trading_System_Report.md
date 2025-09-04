# AI Trading System - Comprehensive Report

## 📋 Executive Summary

This is a sophisticated AI-powered automated trading system designed for technology sector stocks. The system combines sentiment analysis from financial news, technical indicators, and risk management to make data-driven trading decisions on the US stock market using the Alpaca Trading API.

## 🎯 System Overview

### Core Functionality
- **Automated Stock Trading**: Executes buy/sell orders based on AI-driven analysis
- **Sentiment Analysis**: Uses NLTK's VADER sentiment analyzer on financial news
- **Risk Management**: Implements stop-loss and take-profit mechanisms
- **Backtesting**: Historical performance testing with realistic market conditions
- **Paper Trading**: Safe testing environment before live trading
- **Real-time Monitoring**: Live market data integration and position tracking

### Target Market
- **Asset Class**: US Technology Sector Stocks
- **Universe**: 14 major tech stocks (AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA, etc.)
- **Trading Hours**: US Market Hours (9:30 AM - 4:00 PM ET)
- **Broker Integration**: Alpaca Markets API

## 🏗️ System Architecture

### Main Components

#### 1. **Main Interface (`main.py`)**
- Unified command-line interface
- Four operation modes:
  - `diagnose`: System health checks
  - `backtest`: Historical testing
  - `live`: Real trading execution
  - `cancel`: Emergency order cancellation

#### 2. **Trading Core (`trading_core.py`)**
- **Sentiment Analysis Engine**
  - Fetches news from Finnhub API
  - Processes articles using NLTK VADER
  - Calculates sentiment scores (range: -1 to +1)
  - Filters stocks based on sentiment threshold
- **Stock Universe Management**
  - Loads predefined technology stock list
  - Validates stock symbols and market data
- **Position Sizing Logic**
  - Calculates optimal share quantities
  - Manages capital allocation per stock

#### 3. **Historical Backtesting (`historical_backtest.py`)**
- **Data Source**: Alpaca historical minute-level data
- **Realism Features**:
  - Slippage simulation ($0.01 per side)
  - Order setup delays (2 seconds)
  - Market hours validation
- **Performance Metrics**:
  - Total P&L and returns
  - Win/loss ratios
  - Average holding times
  - Best/worst trades analysis
- **Export Capabilities**: Excel reports with detailed trade logs

#### 4. **Live Trading (`live_trading.py`)**
- **Real-time Execution**: Market orders with bracket protection
- **Position Management**: Automatic stop-loss and take-profit orders
- **Safety Features**:
  - Paper trading mode (default)
  - Dry-run simulation
  - Maximum position limits
  - Account validation checks
- **Monitoring**: Real-time P&L tracking and notifications

#### 5. **Risk Management (`trade_types.py`)**
- **Order Types**:
  - Market orders for entry
  - Bracket orders (stop-loss + take-profit)
  - Position monitoring and exit logic
- **Safety Mechanisms**:
  - Account balance validation
  - Position size limits
  - Market hours enforcement
  - API connection health checks

## 🔍 Analysis Process

### Pre-Purchase Analysis

#### 1. **News Sentiment Analysis**
```
For each stock in the universe:
1. Fetch recent news articles (last 24-48 hours)
2. Clean and preprocess article text
3. Apply VADER sentiment analysis
4. Calculate weighted sentiment score
5. Filter stocks above sentiment threshold (default: 0.2)
```

#### 2. **Technical Filters (Optional)**
- **Trend Filter**: 20-day moving average comparison
- **Price Action**: Yesterday's close vs. moving average
- **Volume Analysis**: Trading volume validation

#### 3. **News Source Weighting (Optional)**
- **Premium Sources**: Bloomberg (1.30x), Reuters (1.25x), WSJ (1.20x)
- **Standard Sources**: CNBC (1.10x), MarketWatch (1.05x)
- **Lower Weight**: Yahoo Finance (0.90x), Unknown sources (1.00x)

#### 4. **Risk Assessment**
- **Position Sizing**: Based on available capital and risk tolerance
- **Stop-Loss Calculation**: Percentage-based (default: 5%)
- **Take-Profit Target**: Percentage-based (default: 5%)
- **Maximum Positions**: Concurrent position limits (default: 3)

### Decision Matrix

| Criteria | Weight | Threshold | Action |
|----------|--------|-----------|---------|
| Sentiment Score | Primary | ≥ 0.2 | Qualify for trading |
| News Count | Secondary | ≥ 1 article | Minimum data requirement |
| Market Hours | Critical | Open | Enable trading |
| Account Balance | Critical | Sufficient | Allow position sizing |
| Position Limit | Critical | < Max | Allow new positions |

## 📊 Trading Strategy

### Entry Criteria
1. **Sentiment Score** ≥ threshold (configurable, default: 0.2)
2. **Market is Open** during regular trading hours
3. **Sufficient Capital** for position sizing
4. **Position Limit** not exceeded
5. **News Availability** (minimum 1 recent article)

### Position Management
- **Entry**: Market order at current price
- **Stop-Loss**: Automatic order at -5% (configurable)
- **Take-Profit**: Automatic order at +5% (configurable)
- **Time Limit**: End-of-day exit if neither target hit
- **Position Size**: Equal weight allocation across qualified stocks

### Exit Conditions
1. **Stop-Loss Triggered**: -5% loss (or configured percentage)
2. **Take-Profit Hit**: +5% gain (or configured percentage)
3. **Time Limit**: Market close (end-of-day exit)
4. **Manual Override**: User-initiated cancellation

## 🛠️ Configuration Options

### Backtesting Parameters
```bash
python3 historical_backtest.py \
  --start 2024-10-15 \
  --end 2024-10-18 \
  --sentiment 0.3 \
  --stop-loss 3.0 \
  --take-profit 7.0 \
  --investment 5000 \
  --log-level INFO
```

### Live Trading Parameters
```bash
python3 live_trading.py \
  --mode paper \
  --sentiment 0.25 \
  --investment 10000 \
  --max-positions 3 \
  --log-level INFO
```

### Advanced Configuration (`config.yml`)
```yaml
strategy:
  trend_filter:
    enabled: true
    lookback_days: 20
  news_weighting:
    enabled: true
    source_weights:
      bloomberg.com: 1.30
      reuters.com: 1.25
  sentiment:
    min_news_count: 3
    min_sentiment: 0.3
```

## 📈 Performance Metrics

### Sample Backtest Results (2024-10-15 to 2024-10-18)
- **Total Trades**: 30
- **Win Rate**: 40% (12 winning trades)
- **Total Return**: -0.27%
- **Average P&L per Trade**: -$26.98
- **Best Trade**: AVGO (+3.04%, +$301.28)
- **Worst Trade**: TSM (-5.01%, -$495.21)
- **Average Holding Time**: 1,314 minutes

### Risk Metrics
- **Maximum Drawdown**: Limited by stop-loss (5%)
- **Position Concentration**: Equal weight allocation
- **Capital Utilization**: Configurable per-stock investment
- **Diversification**: Multi-stock technology sector focus

## 🔧 System Requirements

### Dependencies
- **Python 3.8+**
- **Core Libraries**: pandas, numpy, nltk, requests
- **Trading APIs**: alpaca-py, alpaca-trade-api
- **Data Sources**: finnhub-python
- **Configuration**: python-dotenv, PyYAML
- **Reporting**: openpyxl, plotly

### API Requirements
- **Alpaca Trading Account**: Paper or live trading access
- **Finnhub API Key**: Free tier available (60 calls/minute)
- **Environment Variables**: Secure credential storage

### System Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp env_example.txt .env
# Edit .env with your API keys

# Run diagnostics
python3 system_diagnose.py

# Test with backtest
python3 historical_backtest.py --start 2024-10-15 --end 2024-10-18
```

## ⚠️ Risk Warnings

### Trading Risks
- **Market Risk**: Stock prices can decline rapidly
- **Sentiment Risk**: News sentiment may not predict price movements
- **Execution Risk**: Slippage and timing delays
- **Technical Risk**: API failures or system downtime
- **Concentration Risk**: Technology sector focus

### Recommended Safety Measures
1. **Start with Paper Trading**: Test thoroughly before live trading
2. **Small Position Sizes**: Limit capital exposure per trade
3. **Stop-Loss Orders**: Always use protective stops
4. **Regular Monitoring**: Check system performance frequently
5. **Diversification**: Consider broader market exposure

## 🚀 Getting Started

### Quick Start Guide
1. **System Check**: Run `python3 main.py diagnose`
2. **Backtest**: Run `python3 main.py backtest --start 2024-10-15 --end 2024-10-18`
3. **Paper Trading**: Run `python3 main.py live --mode paper --dry-run`
4. **Live Trading**: Run `python3 main.py live --mode paper` (when ready)

### Command Reference
```bash
# System diagnostics
python3 main.py diagnose

# Historical backtesting
python3 main.py backtest --start YYYY-MM-DD --end YYYY-MM-DD

# Paper trading (safe)
python3 main.py live --mode paper

# Live trading (real money - use with caution)
python3 main.py live --mode live

# Emergency stop
python3 main.py cancel
```

## 📞 Support & Troubleshooting

### Common Issues
1. **Missing Dependencies**: Run `pip install -r requirements.txt`
2. **API Connection Errors**: Check `.env` file credentials
3. **NLTK Data Missing**: System automatically downloads required data
4. **Market Closed**: System will wait for market open or use historical data

### Log Files
- **Backtest Logs**: `logs/backtest.log`
- **Live Trading Logs**: `logs/live_trading.log`
- **System Diagnostics**: `system_health.json`

### Report Generation
- **Excel Reports**: `reports/backtest_report_YYYYMMDD_HHMMSS.xlsx`
- **Performance Metrics**: Detailed trade-by-trade analysis
- **System Health**: Automated diagnostic reports

---

**Disclaimer**: This system is for educational and research purposes. Past performance does not guarantee future results. Always test thoroughly with paper trading before risking real capital. Consider consulting with a financial advisor before making investment decisions.
