"""
EXPORT ANALYSIS
===============
Generate comprehensive daily analysis table for backtesting period
"""

import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import os
from typing import Dict, List, Tuple, Any
import time

# Import our modules
from config_loader import config
from trading_core import validate_environment, load_stock_universe, get_sentiment
from trend_filter import apply_trend_filter, compute_moving_average, get_previous_trading_day
from news_weighting import apply_news_weighting
import finnhub
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=".env")
finn_api_key = os.getenv("finnhubkey")

# Initialize Finnhub client
finnhub_client = finnhub.Client(api_key=finn_api_key)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def get_trading_days(start_date: str, end_date: str) -> List[datetime]:
    """Get list of trading days between start and end dates"""
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    
    trading_days = []
    current_date = start_dt
    
    while current_date <= end_dt:
        # Skip weekends (Monday = 0, Sunday = 6)
        if current_date.weekday() < 5:
            trading_days.append(current_date)
        current_date += timedelta(days=1)
    
    return trading_days

def analyze_stock_day(symbol: str, analysis_date: datetime, 
                     sentiment_min: float, sentiment_max: float,
                     capital_per_stock: float) -> Dict[str, Any]:
    """
    Perform complete analysis for one stock on one day
    
    Returns:
        Dict with all analysis results
    """
    # Set decision time to market open (9:30 AM ET)
    decision_time = analysis_date.replace(hour=9, minute=30)
    date_str = analysis_date.strftime('%Y-%m-%d')
    
    # Initialize result dictionary
    result = {
        'Date': date_str,
        'Symbol': symbol,
        'Yesterday_Close': None,
        'MA20': None,
        'Trend_Filter_Result': 'N/A',
        'Num_News_Articles': 0,
        'Weighted_Sentiment_Score': 0.0,
        'Qualified': 'No',
        'Trade_Size': 0,
        'Stop_Loss_Pct': 5.0,
        'Take_Profit_Pct': 5.0,
        'Final_Trade_Action': 'Skip'
    }
    
    try:
        # 1. Get trend analysis (MA20 and yesterday close)
        yesterday_close, ma20 = compute_moving_average(symbol, analysis_date, 20)
        
        if yesterday_close is not None:
            result['Yesterday_Close'] = round(yesterday_close, 2)
        if ma20 is not None:
            result['MA20'] = round(ma20, 2)
        
        # 2. Apply trend filter
        trend_config = {
            'enabled': True,  # Always analyze trend for the table
            'lookback_days': 20,
            'comparator': 'yesterday_gt_ma'
        }
        
        trend_results = apply_trend_filter([symbol], analysis_date, trend_config)
        trend_passed = trend_results.get(symbol, False)
        result['Trend_Filter_Result'] = 'Pass' if trend_passed else 'Fail'
        
        # 3. Get news and sentiment analysis
        try:
            # Fetch news for the date
            all_articles = finnhub_client.company_news(symbol, _from=date_str, to=date_str)
            
            if all_articles:
                # Filter articles by decision time
                valid_articles = []
                for article in all_articles:
                    published_time = datetime.fromtimestamp(article['datetime'])
                    if published_time <= decision_time:
                        valid_articles.append(article)
                
                result['Num_News_Articles'] = len(valid_articles)
                
                if valid_articles:
                    # Get sentiment with source weighting
                    sentiment_score = get_sentiment(symbol, date_str, decision_time)
                    result['Weighted_Sentiment_Score'] = round(sentiment_score, 4)
                else:
                    result['Weighted_Sentiment_Score'] = 0.0
            else:
                result['Num_News_Articles'] = 0
                result['Weighted_Sentiment_Score'] = 0.0
                
        except Exception as e:
            logging.warning(f"Error getting news for {symbol} on {date_str}: {e}")
            result['Num_News_Articles'] = 0
            result['Weighted_Sentiment_Score'] = 0.0
        
        # 4. Determine qualification
        sentiment_qualified = (sentiment_min <= result['Weighted_Sentiment_Score'] <= sentiment_max)
        
        # For this analysis, we'll show both trend and sentiment results
        # but only qualify if both pass (when trend filter would be enabled)
        if trend_passed and sentiment_qualified:
            result['Qualified'] = 'Yes'
            result['Trade_Size'] = capital_per_stock
            result['Final_Trade_Action'] = 'Buy'
        else:
            result['Qualified'] = 'No'
            result['Trade_Size'] = 0
            result['Final_Trade_Action'] = 'Skip'
        
        # Add rate limiting
        time.sleep(0.5)
        
    except Exception as e:
        logging.error(f"Error analyzing {symbol} on {date_str}: {e}")
    
    return result

def generate_analysis_table(start_date: str, end_date: str, 
                          sentiment_min: float = 0.1, sentiment_max: float = 0.6,
                          capital_per_stock: float = 1000000) -> pd.DataFrame:
    """
    Generate comprehensive analysis table for the specified period
    """
    print(f"🔄 Generating analysis table from {start_date} to {end_date}")
    print(f"📊 Parameters: Sentiment [{sentiment_min:.1f}, {sentiment_max:.1f}], Capital: ${capital_per_stock:,.0f}")
    
    # Get trading days and stock universe
    trading_days = get_trading_days(start_date, end_date)
    stocks = load_stock_universe()
    
    print(f"📅 Processing {len(trading_days)} trading days")
    print(f"📈 Analyzing {len(stocks)} stocks")
    print(f"🔢 Total combinations: {len(trading_days) * len(stocks)}")
    
    # Collect all analysis results
    all_results = []
    
    for i, analysis_date in enumerate(trading_days):
        date_str = analysis_date.strftime('%Y-%m-%d')
        print(f"\n📅 Processing {date_str} ({i+1}/{len(trading_days)})")
        
        day_results = []
        for j, symbol in enumerate(stocks):
            print(f"   📊 {symbol} ({j+1}/{len(stocks)})", end=' ')
            
            result = analyze_stock_day(
                symbol, analysis_date, sentiment_min, sentiment_max, capital_per_stock
            )
            
            all_results.append(result)
            day_results.append(result)
            
            # Show quick status
            status = "✅" if result['Qualified'] == 'Yes' else "❌"
            print(f"{status}")
        
        # Show daily summary
        qualified_count = sum(1 for r in day_results if r['Qualified'] == 'Yes')
        print(f"   📊 Daily summary: {qualified_count}/{len(stocks)} stocks qualified")
    
    # Convert to DataFrame
    df = pd.DataFrame(all_results)
    
    # Ensure proper column order
    column_order = [
        'Date', 'Symbol', 'Yesterday_Close', 'MA20', 'Trend_Filter_Result',
        'Num_News_Articles', 'Weighted_Sentiment_Score', 'Qualified',
        'Trade_Size', 'Stop_Loss_Pct', 'Take_Profit_Pct', 'Final_Trade_Action'
    ]
    
    df = df[column_order]
    
    print(f"\n✅ Analysis complete: {len(df)} total records")
    return df

def export_to_csv(df: pd.DataFrame, filename: str):
    """Export DataFrame to CSV"""
    df.to_csv(filename, index=False)
    print(f"💾 Exported CSV: {filename}")

def export_to_html(df: pd.DataFrame, filename: str):
    """Export DataFrame to interactive HTML table with styling"""
    
    # Create HTML with styling and interactivity
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>October 2024 Trading Analysis</title>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            text-align: center;
            margin-bottom: 30px;
        }}
        .summary {{
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .filters {{
            margin-bottom: 20px;
        }}
        .filters input, .filters select {{
            margin: 5px;
            padding: 5px;
            border: 1px solid #ddd;
            border-radius: 3px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: #4CAF50;
            color: white;
            cursor: pointer;
            user-select: none;
        }}
        th:hover {{
            background-color: #45a049;
        }}
        tr:nth-child(even) {{
            background-color: #f2f2f2;
        }}
        .qualified-yes {{
            background-color: #d4edda !important;
        }}
        .trend-fail {{
            background-color: #f8d7da !important;
        }}
        .sentiment-good {{
            background-color: #d1ecf1 !important;
        }}
        .number {{
            text-align: right;
        }}
        .center {{
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 October 2024 Trading Analysis</h1>
        
        <div class="summary">
            <h3>📋 Analysis Summary</h3>
            <p><strong>Period:</strong> October 1-31, 2024</p>
            <p><strong>Stocks Analyzed:</strong> 14 technology stocks</p>
            <p><strong>Trading Rules:</strong></p>
            <ul>
                <li>Capital per stock: $1,000,000</li>
                <li>Sentiment filter: 0.1 ≤ weighted_sentiment ≤ 0.6</li>
                <li>Trend filter: Yesterday close > MA20</li>
                <li>Stop Loss: 5% | Take Profit: 5%</li>
            </ul>
        </div>
        
        <div class="filters">
            <h3>🔍 Filters</h3>
            <input type="text" id="symbolFilter" placeholder="Filter by symbol..." onkeyup="filterTable()">
            <input type="date" id="dateFilter" onchange="filterTable()">
            <select id="qualifiedFilter" onchange="filterTable()">
                <option value="">All Qualified Status</option>
                <option value="Yes">Qualified Only</option>
                <option value="No">Not Qualified Only</option>
            </select>
            <select id="trendFilter" onchange="filterTable()">
                <option value="">All Trend Results</option>
                <option value="Pass">Trend Pass Only</option>
                <option value="Fail">Trend Fail Only</option>
            </select>
        </div>
        
        <div style="overflow-x: auto;">
            <table id="analysisTable">
                <thead>
                    <tr>
"""
    
    # Add table headers
    for col in df.columns:
        html_content += f'                        <th onclick="sortTable({list(df.columns).index(col)})">{col.replace("_", " ")}</th>\n'
    
    html_content += """                    </tr>
                </thead>
                <tbody>
"""
    
    # Add table rows with conditional formatting
    for _, row in df.iterrows():
        row_class = ""
        
        # Apply conditional formatting
        if row['Qualified'] == 'Yes':
            row_class = "qualified-yes"
        elif row['Trend_Filter_Result'] == 'Fail':
            row_class = "trend-fail"
        elif 0.1 <= row['Weighted_Sentiment_Score'] <= 0.6:
            row_class = "sentiment-good"
        
        html_content += f'                    <tr class="{row_class}">\n'
        
        for col in df.columns:
            value = row[col]
            cell_class = ""
            
            # Format numbers
            if col in ['Yesterday_Close', 'MA20']:
                if pd.notna(value):
                    value = f"${value:.2f}"
                    cell_class = "number"
                else:
                    value = "N/A"
            elif col == 'Weighted_Sentiment_Score':
                value = f"{value:.4f}"
                cell_class = "number"
            elif col == 'Trade_Size':
                if value > 0:
                    value = f"${value:,.0f}"
                else:
                    value = "$0"
                cell_class = "number"
            elif col in ['Stop_Loss_Pct', 'Take_Profit_Pct']:
                value = f"{value:.1f}%"
                cell_class = "number"
            elif col in ['Qualified', 'Final_Trade_Action', 'Trend_Filter_Result']:
                cell_class = "center"
            
            html_content += f'                        <td class="{cell_class}">{value}</td>\n'
        
        html_content += '                    </tr>\n'
    
    # Add JavaScript for interactivity
    html_content += """                </tbody>
            </table>
        </div>
    </div>

    <script>
        function sortTable(columnIndex) {
            var table = document.getElementById("analysisTable");
            var rows = Array.from(table.rows).slice(1);
            var ascending = table.getAttribute("data-sort-dir") !== "asc";
            
            rows.sort(function(a, b) {
                var aVal = a.cells[columnIndex].textContent.trim();
                var bVal = b.cells[columnIndex].textContent.trim();
                
                // Try to parse as numbers
                var aNum = parseFloat(aVal.replace(/[$,%]/g, ''));
                var bNum = parseFloat(bVal.replace(/[$,%]/g, ''));
                
                if (!isNaN(aNum) && !isNaN(bNum)) {
                    return ascending ? aNum - bNum : bNum - aNum;
                }
                
                // String comparison
                return ascending ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
            });
            
            // Remove existing rows
            while(table.rows.length > 1) {
                table.deleteRow(1);
            }
            
            // Add sorted rows
            rows.forEach(function(row) {
                table.appendChild(row);
            });
            
            table.setAttribute("data-sort-dir", ascending ? "asc" : "desc");
        }
        
        function filterTable() {
            var symbolFilter = document.getElementById("symbolFilter").value.toUpperCase();
            var dateFilter = document.getElementById("dateFilter").value;
            var qualifiedFilter = document.getElementById("qualifiedFilter").value;
            var trendFilter = document.getElementById("trendFilter").value;
            
            var table = document.getElementById("analysisTable");
            var rows = table.getElementsByTagName("tr");
            
            for (var i = 1; i < rows.length; i++) {
                var row = rows[i];
                var cells = row.getElementsByTagName("td");
                var show = true;
                
                // Symbol filter
                if (symbolFilter && !cells[1].textContent.toUpperCase().includes(symbolFilter)) {
                    show = false;
                }
                
                // Date filter
                if (dateFilter && !cells[0].textContent.includes(dateFilter)) {
                    show = false;
                }
                
                // Qualified filter
                if (qualifiedFilter && cells[7].textContent !== qualifiedFilter) {
                    show = false;
                }
                
                // Trend filter
                if (trendFilter && cells[4].textContent !== trendFilter) {
                    show = false;
                }
                
                row.style.display = show ? "" : "none";
            }
        }
    </script>
</body>
</html>"""
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"💾 Exported HTML: {filename}")

def print_summary_stats(df: pd.DataFrame):
    """Print summary statistics"""
    print("\n" + "=" * 60)
    print("📊 ANALYSIS SUMMARY STATISTICS")
    print("=" * 60)
    
    total_records = len(df)
    qualified_records = len(df[df['Qualified'] == 'Yes'])
    
    print(f"📋 Total Records: {total_records:,}")
    print(f"✅ Qualified Trades: {qualified_records:,} ({qualified_records/total_records*100:.1f}%)")
    print(f"❌ Skipped Trades: {total_records-qualified_records:,} ({(total_records-qualified_records)/total_records*100:.1f}%)")
    
    # Trend filter stats
    trend_pass = len(df[df['Trend_Filter_Result'] == 'Pass'])
    trend_fail = len(df[df['Trend_Filter_Result'] == 'Fail'])
    print(f"\n📈 Trend Filter Results:")
    print(f"   Pass: {trend_pass:,} ({trend_pass/total_records*100:.1f}%)")
    print(f"   Fail: {trend_fail:,} ({trend_fail/total_records*100:.1f}%)")
    
    # Sentiment stats
    sentiment_scores = df['Weighted_Sentiment_Score']
    print(f"\n📰 Sentiment Statistics:")
    print(f"   Average: {sentiment_scores.mean():.4f}")
    print(f"   Median: {sentiment_scores.median():.4f}")
    print(f"   Min: {sentiment_scores.min():.4f}")
    print(f"   Max: {sentiment_scores.max():.4f}")
    
    # Stock-wise qualified trades
    print(f"\n🏆 Top Performing Stocks (Most Qualified Trades):")
    stock_qualified = df[df['Qualified'] == 'Yes']['Symbol'].value_counts().head(5)
    for symbol, count in stock_qualified.items():
        print(f"   {symbol}: {count} qualified trades")
    
    # Date-wise stats
    print(f"\n📅 Best Trading Days (Most Qualified Stocks):")
    date_qualified = df[df['Qualified'] == 'Yes']['Date'].value_counts().head(5)
    for date, count in date_qualified.items():
        print(f"   {date}: {count} qualified stocks")
    
    # Total potential capital
    total_capital = qualified_records * 1000000
    print(f"\n💰 Total Capital Deployed: ${total_capital:,.0f}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Generate comprehensive trading analysis table')
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--sentiment-min', type=float, default=0.1, help='Minimum sentiment threshold')
    parser.add_argument('--sentiment-max', type=float, default=0.6, help='Maximum sentiment threshold')
    parser.add_argument('--capital', type=float, default=1000000, help='Capital per stock')
    
    args = parser.parse_args()
    
    try:
        # Validate environment
        validate_environment()
        print("✅ Environment validation passed")
        
        # Generate analysis table
        df = generate_analysis_table(
            args.start, args.end, args.sentiment_min, args.sentiment_max, args.capital
        )
        
        # Generate output filenames
        start_clean = args.start.replace('-', '_')
        end_clean = args.end.replace('-', '_')
        csv_filename = f"analysis_{start_clean}_to_{end_clean}.csv"
        html_filename = f"analysis_{start_clean}_to_{end_clean}.html"
        
        # Export files
        export_to_csv(df, csv_filename)
        export_to_html(df, html_filename)
        
        # Print summary statistics
        print_summary_stats(df)
        
        print(f"\n🎉 Analysis complete!")
        print(f"📁 Files generated:")
        print(f"   • {csv_filename} (Excel/Pandas compatible)")
        print(f"   • {html_filename} (Interactive web table)")
        
    except Exception as e:
        logging.error(f"Analysis failed: {e}")
        print(f"❌ Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())

