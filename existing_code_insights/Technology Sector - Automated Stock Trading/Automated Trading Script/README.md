# Dual Mode Trading System

A comprehensive automated trading system with both live trading and historical backtesting capabilities.

## 🚀 Features

### Live Trading Mode
- **Real-time sentiment analysis** using Finnhub news API and NLTK VADER
- **Automated bracket orders** with stop loss and take profit levels
- **Scheduled execution** with user-defined start times
- **Automatic position closure** after specified holding period
- **Alpaca Paper Trading** integration for safe testing

### Historical Backtest Mode
- **Real historical price data** using Yahoo Finance (yfinance)
- **Minute-level trade simulation** (2-minute intervals)
- **Realistic TP/SL execution logic** with sophisticated candle analysis
- **Comprehensive Excel reports** with trade-by-trade details
- **Performance metrics** including win rate, P&L, and holding times

## 📁 File Structure

```
├── main.py                    # Main entry point with dual-mode selection
├── trading_core.py           # Shared utilities (sentiment, screening, etc.)
├── live_trading.py           # Live trading execution module
├── historical_backtest.py    # Historical backtesting module
├── trade_types.py            # Alpaca API order management
├── cancel_all.py             # Position and order cleanup
├── technology_tickers.csv    # Stock universe (14 tech stocks)
├── .env                      # API credentials (Alpaca & Finnhub)
└── trading.log              # Trading activity log
```

## 🛠️ Setup

### 1. Install Dependencies
```bash
pip install yfinance openpyxl pandas nltk finnhub-python alpaca-trade-api
```

### 2. Configure API Keys
Create a `.env` file with:
```
# Alpaca API (Paper Trading)
apikey=YOUR_ALPACA_API_KEY
apisecret=YOUR_ALPACA_SECRET_KEY

# Finnhub API
finnhubkey=YOUR_FINNHUB_API_KEY
```

### 3. Download NLTK Data
```bash
python3 -c "import nltk; nltk.download('vader_lexicon')"
```

## 🔄 Usage

### Run the System
```bash
python3 main.py
```

### Mode 1: Live Trading
1. Select option `1` from the main menu
2. Confirm live trading start
3. Configure parameters:
   - **Start time** (HH:MM format)
   - **Maximum holding time** (minutes)
   - **Sentiment range** (min/max scores)
   - **Stop Loss** (dollar amount)
   - **Take Profit** (dollar amount)
4. System will:
   - Wait until start time
   - Analyze sentiment for all stocks
   - Place bracket orders for qualifying stocks
   - Automatically close positions after holding period

### Mode 2: Historical Backtest
1. Select option `2` from the main menu
2. Configure parameters:
   - **Date range** (YYYY-MM-DD format)
   - **Sentiment threshold** (0.0 to 1.0)
   - **Stop Loss percentage**
   - **Take Profit percentage**
3. System will:
   - Process each trading day in the range
   - Fetch real historical news and price data
   - Simulate realistic trade execution
   - Generate detailed Excel report

## 📊 Trading Logic

### Sentiment Analysis
- Fetches daily company news from Finnhub API
- Analyzes sentiment using NLTK VADER lexicon
- Calculates compound sentiment score (-1 to 1)
- Averages top 10 articles per stock

### Trade Execution
**Live Mode:**
- Uses Alpaca bracket orders with SL/TP levels
- Concurrent execution for multiple stocks
- Equal position sizing across qualified stocks

**Backtest Mode:**
- 2-minute price data from Yahoo Finance
- Sophisticated candle analysis for TP/SL determination
- Considers realistic execution within candle ranges

### Position Management
- **Live:** Broker manages SL/TP, system force-closes after holding time
- **Backtest:** Simulates each minute to determine exit reason and timing

## 📈 Stock Universe
14 Technology stocks:
NVDA, MSFT, AAPL, AMZN, GOOGL, META, AVGO, TSM, TSLA, ORCL, ADBE, CSCO, INTU, QCOM

## ⚠️ Important Notes

### Safety Features
- **Paper trading only** - No real money at risk
- **Environment validation** - Checks API keys and connections
- **Error handling** - Graceful degradation on failures
- **Logging** - Comprehensive activity logging

### Limitations
- **News data** may be limited for historical dates
- **Minute data** availability varies by date range
- **Rate limiting** applies to API calls (1-second delays)
- **Market hours** not enforced (assumes user responsibility)

## 🚨 Risk Disclaimer
This system is designed for **educational and testing purposes only**. It uses Alpaca's paper trading environment with simulated funds. Always thoroughly test any trading strategy before considering real money implementation.

## 📧 Support
Check the trading.log file for detailed execution logs and error messages.
