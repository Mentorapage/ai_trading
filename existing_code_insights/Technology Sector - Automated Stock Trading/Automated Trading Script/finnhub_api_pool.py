#!/usr/bin/env python3
"""
FINNHUB API POOL MANAGER
========================
Manages multiple Finnhub API keys with round-robin rotation and rate limiting
"""

import os
import time
import logging
import requests
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import threading
from collections import defaultdict

class FinnhubAPIPool:
    """Manages multiple Finnhub API keys with intelligent rotation and rate limiting"""
    
    def __init__(self, global_rpm_limit: int = 200, per_key_rpm_limit: int = 50):
        """
        Initialize the Finnhub API pool
        
        Args:
            global_rpm_limit: Global requests per minute limit across all keys
            per_key_rpm_limit: Per-key requests per minute soft limit
        """
        self.keys = self._load_api_keys()
        self.global_rpm_limit = global_rpm_limit
        self.per_key_rpm_limit = per_key_rpm_limit
        
        # Current key index for round-robin
        self.current_key_index = 0
        
        # Rate limiting tracking
        self.request_times = defaultdict(list)  # key_index -> [timestamp, ...]
        self.global_request_times = []
        
        # Statistics
        self.key_usage_stats = defaultdict(int)
        self.total_requests = 0
        self.rate_limit_hits = 0
        
        # Thread safety
        self.lock = threading.Lock()
        
        logging.info(f"Finnhub API Pool initialized with {len(self.keys)} keys")
        logging.info(f"Global limit: {global_rpm_limit} RPM, Per-key limit: {per_key_rpm_limit} RPM")
    
    def _load_api_keys(self) -> List[str]:
        """Load Finnhub API keys from environment"""
        keys_str = os.getenv('FINNHUB_KEYS', '')
        if not keys_str:
            raise ValueError("FINNHUB_KEYS environment variable not set")
        
        keys = [key.strip() for key in keys_str.split(',') if key.strip()]
        if len(keys) < 1:
            raise ValueError("At least 1 Finnhub API key required")
        
        logging.info(f"Loaded {len(keys)} Finnhub API keys")
        return keys
    
    def _clean_old_requests(self, current_time: float):
        """Remove request timestamps older than 1 minute"""
        cutoff_time = current_time - 60  # 1 minute ago
        
        # Clean per-key tracking
        for key_index in self.request_times:
            self.request_times[key_index] = [
                t for t in self.request_times[key_index] if t > cutoff_time
            ]
        
        # Clean global tracking
        self.global_request_times = [
            t for t in self.global_request_times if t > cutoff_time
        ]
    
    def _can_make_request(self, key_index: int) -> bool:
        """Check if we can make a request with the given key"""
        current_time = time.time()
        self._clean_old_requests(current_time)
        
        # Check global rate limit
        if len(self.global_request_times) >= self.global_rpm_limit:
            return False
        
        # Check per-key rate limit
        if len(self.request_times[key_index]) >= self.per_key_rpm_limit:
            return False
        
        return True
    
    def _record_request(self, key_index: int):
        """Record a successful request"""
        current_time = time.time()
        
        with self.lock:
            self.request_times[key_index].append(current_time)
            self.global_request_times.append(current_time)
            self.key_usage_stats[key_index] += 1
            self.total_requests += 1
    
    def _get_next_available_key(self) -> Optional[int]:
        """Get the next available key index, or None if all are rate limited"""
        start_index = self.current_key_index
        
        for _ in range(len(self.keys)):
            if self._can_make_request(self.current_key_index):
                return self.current_key_index
            
            # Move to next key
            self.current_key_index = (self.current_key_index + 1) % len(self.keys)
        
        # Reset to start position if no key available
        self.current_key_index = start_index
        return None
    
    def _wait_for_rate_limit(self):
        """Wait until we can make a request"""
        max_wait_time = 60  # Maximum 1 minute wait
        wait_start = time.time()
        
        while time.time() - wait_start < max_wait_time:
            if self._get_next_available_key() is not None:
                return
            
            # Wait 1 second before checking again
            time.sleep(1)
        
        logging.warning("Rate limit wait timeout - proceeding anyway")
    
    def make_request(self, endpoint: str, params: Dict[str, Any], max_retries: int = 3) -> Optional[Dict]:
        """
        Make a request to Finnhub API with automatic key rotation and rate limiting
        
        Args:
            endpoint: API endpoint (e.g., 'company-news')
            params: Request parameters
            max_retries: Maximum number of retries
            
        Returns:
            API response as dict, or None if failed
        """
        base_url = "https://finnhub.io/api/v1"
        
        for attempt in range(max_retries):
            # Get available key
            key_index = self._get_next_available_key()
            
            if key_index is None:
                logging.info("All keys rate limited - waiting...")
                self._wait_for_rate_limit()
                key_index = self._get_next_available_key()
                
                if key_index is None:
                    logging.error("Unable to get available API key after waiting")
                    continue
            
            # Prepare request
            api_key = self.keys[key_index]
            request_params = params.copy()
            request_params['token'] = api_key
            
            url = f"{base_url}/{endpoint}"
            
            try:
                logging.debug(f"Making request to {endpoint} with key {key_index + 1}/{len(self.keys)}")
                
                response = requests.get(url, params=request_params, timeout=30)
                
                if response.status_code == 200:
                    # Success - record the request and move to next key
                    self._record_request(key_index)
                    self.current_key_index = (key_index + 1) % len(self.keys)
                    
                    return response.json()
                
                elif response.status_code == 429:
                    # Rate limited - mark this key as rate limited and try next
                    logging.warning(f"Rate limit hit on key {key_index + 1}, switching to next key")
                    self.rate_limit_hits += 1
                    
                    # Force this key to be rate limited for a bit
                    current_time = time.time()
                    for _ in range(self.per_key_rpm_limit):
                        self.request_times[key_index].append(current_time)
                    
                    # Try next key
                    self.current_key_index = (key_index + 1) % len(self.keys)
                    continue
                
                else:
                    logging.error(f"API error {response.status_code}: {response.text}")
                    time.sleep(1)  # Brief pause before retry
                    continue
                    
            except requests.exceptions.RequestException as e:
                logging.error(f"Request failed: {e}")
                time.sleep(1)
                continue
        
        logging.error(f"Failed to make request to {endpoint} after {max_retries} attempts")
        return None
    
    def get_company_news(self, symbol: str, from_date: str, to_date: str) -> List[Dict]:
        """
        Get company news for a symbol
        
        Args:
            symbol: Stock symbol
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            
        Returns:
            List of news articles
        """
        params = {
            'symbol': symbol,
            'from': from_date,
            'to': to_date
        }
        
        result = self.make_request('company-news', params)
        return result if result is not None else []
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get API usage statistics"""
        current_time = time.time()
        self._clean_old_requests(current_time)
        
        stats = {
            'total_keys': len(self.keys),
            'total_requests': self.total_requests,
            'rate_limit_hits': self.rate_limit_hits,
            'current_key_index': self.current_key_index + 1,
            'key_usage': dict(self.key_usage_stats),
            'current_rpm': {
                'global': len(self.global_request_times),
                'per_key': {i: len(self.request_times[i]) for i in range(len(self.keys))}
            }
        }
        
        return stats
    
    def print_usage_stats(self):
        """Print current usage statistics"""
        stats = self.get_usage_stats()
        
        print(f"🔑 Finnhub API Pool Stats:")
        print(f"   Total Keys: {stats['total_keys']}")
        print(f"   Total Requests: {stats['total_requests']}")
        print(f"   Rate Limit Hits: {stats['rate_limit_hits']}")
        print(f"   Current Key: {stats['current_key_index']}/{stats['total_keys']}")
        print(f"   Current Global RPM: {stats['current_rpm']['global']}/{self.global_rpm_limit}")
        
        for i, usage in stats['key_usage'].items():
            current_rpm = stats['current_rpm']['per_key'].get(i, 0)
            print(f"   Key {i + 1}: {usage} requests, {current_rpm} RPM")

# Global instance
_finnhub_pool = None

def get_finnhub_pool() -> FinnhubAPIPool:
    """Get the global Finnhub API pool instance"""
    global _finnhub_pool
    if _finnhub_pool is None:
        _finnhub_pool = FinnhubAPIPool()
    return _finnhub_pool
