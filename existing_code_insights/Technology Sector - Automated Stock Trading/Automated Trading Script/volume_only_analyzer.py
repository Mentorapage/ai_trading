#!/usr/bin/env python3
"""
VOLUME-ONLY ANALYZER
===================
Single filter: volume_yesterday > volume_ma20 (NO other signals)
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional
from pathlib import Path
import csv

# Import for market data
from historical_backtest import get_historical_data

class VolumeOnlyAnalyzer:
    """Ultra-simplified analyzer with ONLY volume filter"""
    
    def __init__(self, audit_dir: str = "audit_logs"):
        """Initialize the volume-only analyzer"""
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(exist_ok=True)
        
        logging.info("Volume-only analyzer initialized - Single filter: volume_yesterday > volume_ma20")
    
    def calculate_volume_eligibility(self, ticker: str, analysis_date: str) -> Dict:
        """Calculate volume eligibility - ONLY filter in the system"""
        try:
            # Get 30 days of data for volume analysis
            end_date = datetime.strptime(analysis_date, '%Y-%m-%d').date()
            start_date = end_date - timedelta(days=40)
            
            daily_data = get_historical_data(
                ticker=ticker,
                start_date=datetime.combine(start_date, datetime.min.time().replace(hour=9, minute=30)),
                end_date=datetime.combine(end_date - timedelta(days=1), datetime.min.time().replace(hour=16)),
                timeframe='1Day'
            )
            
            if len(daily_data) < 20:
                return {
                    'volume_yesterday': 0,
                    'volume_ma20': 0,
                    'passed_all_filters': False
                }
            
            # Volume metrics - ONLY what we need
            volume_yesterday = daily_data['volume'].iloc[-1]
            volume_ma20 = daily_data['volume'].rolling(window=20).mean().iloc[-1]
            
            # THE ONLY FILTER: volume_yesterday > volume_ma20
            passed_all_filters = volume_yesterday > volume_ma20
            
            return {
                'volume_yesterday': volume_yesterday,
                'volume_ma20': volume_ma20,
                'passed_all_filters': passed_all_filters
            }
            
        except Exception as e:
            logging.warning(f"Volume filter failed for {ticker}: {e}")
            return {
                'volume_yesterday': 0,
                'volume_ma20': 0,
                'passed_all_filters': False
            }
    
    def screen_stocks_by_volume_only(
        self, 
        stocks: List[str], 
        analysis_date: str
    ) -> List[Dict]:
        """Screen stocks using ONLY volume filter"""
        
        qualified_stocks = []
        audit_data = []
        
        for ticker in stocks:
            try:
                # ONLY volume filter
                volume_data = self.calculate_volume_eligibility(ticker, analysis_date)
                
                # Combine data
                stock_data = {
                    'ticker': ticker,
                    'date': analysis_date,
                    **volume_data
                }
                
                # Add to results if passed THE ONLY filter
                if volume_data['passed_all_filters']:
                    qualified_stocks.append(stock_data)
                
                # Add to audit log
                audit_data.append(stock_data)
                
            except Exception as e:
                logging.error(f"Error screening {ticker}: {e}")
                continue
        
        # Save audit log
        self._save_audit_log(analysis_date, audit_data)
        
        # No sorting needed - just return all that passed
        logging.info(f"Screened {len(stocks)} stocks, {len(qualified_stocks)} qualified (volume > MA20)")
        return qualified_stocks
    
    def _save_audit_log(self, analysis_date: str, audit_data: List[Dict]):
        """Save audit log with ultra-minimal schema"""
        audit_file = self.audit_dir / f"volume_only_audit_{analysis_date}.csv"
        
        # Ultra-minimal audit columns (ONLY 5 columns)
        audit_columns = [
            'date', 'ticker', 'volume_yesterday', 'volume_ma20', 'passed_all_filters'
        ]
        
        try:
            with open(audit_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=audit_columns)
                writer.writeheader()
                
                for data in audit_data:
                    # Extract only the columns we want
                    row = {col: data.get(col, '') for col in audit_columns}
                    writer.writerow(row)
                    
        except Exception as e:
            logging.error(f"Failed to save audit log: {e}")
