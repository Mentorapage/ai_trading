# Trading System - Quick Start Guide

## 🚀 Getting Started

### 1. System Health Check (ALWAYS RUN FIRST)

Before running any trading operations, diagnose your system:

```bash
python3 system_diagnose.py
```

This will check:
- ✅ Python dependencies
- ✅ API credentials (.env file)
- ✅ Configuration files
- ✅ External service connectivity
- ✅ File permissions

**If any checks fail, fix them before proceeding!**

### 2. Setup Your Environment

1. **Copy the environment template:**
   ```bash
   cp env_example.txt .env
   ```

2. **Edit `.env` with your API keys:**
   ```bash
   # Required: Alpaca Trading API
   apikey=YOUR_ALPACA_API_KEY
   apisecret=YOUR_ALPACA_SECRET_KEY
   
   # Required: Finnhub News API
   FINNHUB_KEYS=your_key_1,your_key_2
   ```

3. **Get API Keys:**
   - **Alpaca (Trading):** https://app.alpaca.markets/paper/dashboard/overview
   - **Finnhub (News):** https://finnhub.io/register

### 3. Copy Safe Configuration

```bash
cp config.default.yml config.yml
```

This ensures all advanced features are OFF by default.

---

## 📊 Running Historical Backtests

Test your strategies on historical data:

### Basic Backtest
```bash
python3 historical_backtest.py --start 2024-10-15 --end 2024-10-18 --log-level INFO
```

### Advanced Backtest
```bash
python3 historical_backtest.py \
  --start 2024-12-01 \
  --end 2024-12-05 \
  --sentiment 0.3 \
  --stop-loss 3 \
  --take-profit 5 \
  --investment 5000 \
  --log-level DEBUG
```

### What You'll See:
```
🚀 STARTING HISTORICAL BACKTEST
📅 Period: 2024-10-15 to 2024-10-18
📊 Sentiment Threshold: 0.2
🛡️  Stop Loss: 5.0%
💰 Take Profit: 5.0%

📅 Processing 2024-10-15...
   ✅ 15 stocks qualified: ['AAPL', 'MSFT', 'GOOGL', ...]
   📊 AAPL: 50 shares @ $150.25 → $152.10 (TAKE_PROFIT) = +$92.50
   📊 MSFT: 25 shares @ $380.50 → $375.20 (STOP_LOSS) = -$132.50

🏁 HISTORICAL BACKTEST COMPLETED
📁 Check the reports/ directory for Excel/CSV output
```

---

## 🔴 Running Live Trading (Paper Mode)

**ALWAYS start with paper trading!**

### Paper Trading (Safe)
```bash
python3 live_trading.py --mode paper --log-level INFO
```

### Dry Run (No Orders)
```bash
python3 live_trading.py --mode paper --dry-run --log-level DEBUG
```

### What You'll See:
```
🚀 LIVE TRADING SYSTEM
📊 Mode: PAPER
📊 Sentiment Threshold: 0.2
💼 Investment per Stock: $10,000
🎯 Max Positions: 3

✅ Connected to Alpaca PAPER account
💰 Account Value: $100,000.00
💵 Buying Power: $100,000.00

📅 Market is currently OPEN
⏰ Market hours: 9:30 AM - 4:00 PM ET

🔄 Starting trading session...
```

### Live Trading (Real Money - CAUTION!)
```bash
python3 live_trading.py --mode live --log-level INFO
```
**⚠️ This uses REAL money! Only use after thorough paper testing.**

---

## 🛠️ Common Issues & Solutions

### Issue: "No module named 'trading_core'"
**Solution:**
```bash
# Make sure you're in the correct directory
cd "existing_code_insights/Technology Sector - Automated Stock Trading/Automated Trading Script"
python3 system_diagnose.py
```

### Issue: "Alpaca API connection failed"
**Solution:**
1. Check your `.env` file has valid `apikey` and `apisecret`
2. Verify keys are for the correct mode (paper vs live)
3. Run diagnostics: `python3 system_diagnose.py`

### Issue: "No Finnhub API keys found"
**Solution:**
1. Get a free API key from https://finnhub.io/register
2. Add to `.env`: `FINNHUB_KEYS=your_key_here`
3. For better rate limits, use multiple keys: `FINNHUB_KEYS=key1,key2,key3`

### Issue: "Market is currently CLOSED"
**Solution:**
- Market hours: 9:30 AM - 4:00 PM ET (Monday-Friday)
- Run a backtest instead: `python3 historical_backtest.py --start 2024-10-15 --end 2024-10-18`
- Or use `--dry-run` to test the pipeline

### Issue: Terminal commands hang/freeze
**Solution:**
1. Check if you have too many cache files: `ls -la cache_finnhub/ | wc -l`
2. Clear cache if needed: `rm -rf cache_finnhub/*`
3. Run diagnostics: `python3 system_diagnose.py`

---

## 📁 Output Files

### Backtest Reports
- `reports/backtest_report_YYYYMMDD_HHMMSS.xlsx` - Detailed Excel report
- `reports/backtest_report_YYYYMMDD_HHMMSS.csv` - CSV fallback

### Log Files
- `logs/backtest.log` - Backtest detailed logs
- `logs/live_trading.log` - Live trading logs
- `logs/app.log` - General application logs

### Diagnostic Reports
- `system_health.json` - Machine-readable health status
- `diagnostics_report.md` - Human-readable diagnostic report

---

## 🔧 Advanced Configuration

### Enable Advanced Features (Optional)
Edit `config.yml`:
```yaml
strategy:
  trend_filter:
    enabled: true    # Enable trend filtering
  news_weighting:
    enabled: true    # Enable source-weighted sentiment
```

### Adjust Trading Parameters
```yaml
strategy:
  sentiment:
    min_news_count: 3        # Require more news articles
    min_sentiment: 0.3       # Higher sentiment threshold
  trading:
    investment_per_stock: 5000  # Smaller position sizes
    stop_loss_pct: 3.0         # Tighter stop loss
```

---

## 🆘 Emergency Commands

### Cancel All Orders & Positions
```bash
python3 cancel_all.py
```

### System Health Check
```bash
python3 system_diagnose.py
```

### View Recent Logs
```bash
tail -f logs/live_trading.log
```

---

## 📞 Support

If you encounter issues:

1. **Run diagnostics first:** `python3 system_diagnose.py`
2. **Check the logs:** `logs/` directory
3. **Verify your setup:** Compare with `env_example.txt` and `config.default.yml`
4. **Start simple:** Use paper trading and short backtests first

**Remember: Always test with paper trading before using real money!**
