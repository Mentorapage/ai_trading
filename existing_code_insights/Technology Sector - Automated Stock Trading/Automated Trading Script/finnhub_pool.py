"""
FINNHUB MULTI-KEY ROTATION & RATE LIMITING
==========================================
Thread-safe key pool with global rate limiting and caching
"""

import os
import json
import time
import hashlib
import threading
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('finnhub_pool.log')],
    force=True
)

class FinnhubKeyPool:
    """Thread-safe Finnhub API key pool with rate limiting and caching"""
    
    def __init__(self):
        self.keys = self._load_keys()
        self.global_rpm = int(os.getenv('FINNHUB_GLOBAL_RPM', '200'))
        self.per_key_soft_rpm = int(os.getenv('FINNHUB_PER_KEY_SOFT_RPM', '55'))
        
        # Thread-safe counters
        self.lock = threading.Lock()
        self.current_key_index = 0
        self.per_key_counters = {key: 0 for key in self.keys}
        self.global_counter = 0
        self.last_reset_time = time.time()
        
        # Cache setup
        self.cache_dir = Path('./cache_finnhub')
        self.cache_dir.mkdir(exist_ok=True)
        
        logging.info(f"Initialized Finnhub pool: {len(self.keys)} keys, global_rpm={self.global_rpm}, per_key_soft_rpm={self.per_key_soft_rpm}")
    
    def _load_keys(self) -> List[str]:
        """Load API keys from environment"""
        keys_str = os.getenv('FINNHUB_KEYS', '')
        if not keys_str:
            # Fallback to single key
            single_key = os.getenv('finnhubkey', '')
            if not single_key:
                raise ValueError("No Finnhub keys found in environment")
            return [single_key]
        
        keys = [key.strip() for key in keys_str.split(',') if key.strip()]
        if not keys:
            raise ValueError("No valid Finnhub keys found")
        
        return keys
    
    def _reset_counters_if_needed(self):
        """Reset counters if a minute has passed"""
        current_time = time.time()
        if current_time - self.last_reset_time >= 60:
            self.per_key_counters = {key: 0 for key in self.keys}
            self.global_counter = 0
            self.last_reset_time = current_time
            logging.info(f"Reset rate limit counters at {datetime.now().strftime('%H:%M:%S')}")
    
    def _get_cache_key(self, endpoint: str, params: Dict) -> str:
        """Generate deterministic cache key"""
        # Sort params for deterministic hashing
        sorted_params = sorted(params.items()) if params else []
        cache_input = f"{endpoint}:{json.dumps(sorted_params, sort_keys=True)}"
        return hashlib.md5(cache_input.encode()).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path"""
        return self.cache_dir / f"{cache_key}.json"
    
    def _read_cache(self, cache_key: str) -> Optional[Dict]:
        """Read from cache if exists and valid"""
        cache_path = self._get_cache_path(cache_key)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r') as f:
                cached_data = json.load(f)
            
            # Check if cache is still valid (1 hour TTL for news)
            cache_time = cached_data.get('cached_at', 0)
            if time.time() - cache_time > 3600:  # 1 hour TTL
                cache_path.unlink()  # Remove expired cache
                return None
            
            logging.info(f"Cache hit for key: {cache_key[:8]}...")
            return cached_data.get('data')
            
        except Exception as e:
            logging.warning(f"Cache read error for {cache_key}: {e}")
            return None
    
    def _write_cache(self, cache_key: str, data: Dict):
        """Write to cache"""
        cache_path = self._get_cache_path(cache_key)
        
        try:
            cached_data = {
                'cached_at': time.time(),
                'data': data
            }
            
            with open(cache_path, 'w') as f:
                json.dump(cached_data, f)
                
        except Exception as e:
            logging.warning(f"Cache write error for {cache_key}: {e}")
    
    def _select_next_key(self) -> Optional[str]:
        """Select next available key respecting rate limits"""
        with self.lock:
            self._reset_counters_if_needed()
            
            # Check global limit
            if self.global_counter >= self.global_rpm:
                return None  # Need to wait
            
            # Try to find a key under soft limit
            for _ in range(len(self.keys)):
                key = self.keys[self.current_key_index]
                
                if self.per_key_counters[key] < self.per_key_soft_rpm:
                    # Increment counters
                    self.per_key_counters[key] += 1
                    self.global_counter += 1
                    
                    logging.info(f"Selected key {self.current_key_index + 1}/{len(self.keys)}, "
                               f"key_count={self.per_key_counters[key]}, global_count={self.global_counter}")
                    
                    # Move to next key for round-robin
                    self.current_key_index = (self.current_key_index + 1) % len(self.keys)
                    return key
                
                # Try next key
                self.current_key_index = (self.current_key_index + 1) % len(self.keys)
            
            return None  # All keys at soft limit
    
    def _wait_for_next_minute(self):
        """Wait until next minute bucket"""
        with self.lock:
            seconds_to_wait = 60 - (time.time() - self.last_reset_time)
            if seconds_to_wait > 0:
                logging.info(f"Rate limit reached, sleeping {seconds_to_wait:.1f}s until next minute")
                time.sleep(seconds_to_wait)
    
    def finnhub_get(self, endpoint: str, params: Dict = None, timeout: int = 10) -> Dict:
        """
        Make rate-limited Finnhub API request with caching and key rotation
        """
        if params is None:
            params = {}
        
        # Check cache first
        cache_key = self._get_cache_key(endpoint, params)
        cached_result = self._read_cache(cache_key)
        if cached_result is not None:
            return cached_result
        
        max_retries = 5
        base_backoff = 0.3
        
        for attempt in range(max_retries):
            # Select key
            selected_key = self._select_next_key()
            
            if selected_key is None:
                # All keys at limit, wait for next minute
                self._wait_for_next_minute()
                continue
            
            try:
                # Make request
                url = f"https://finnhub.io/api/v1/{endpoint}"
                request_params = params.copy()
                request_params['token'] = selected_key
                
                response = requests.get(url, params=request_params, timeout=timeout)
                
                if response.status_code == 200:
                    # Success - cache and return
                    data = response.json()
                    self._write_cache(cache_key, data)
                    return data
                
                elif response.status_code == 429:
                    # Rate limit hit - try next key
                    logging.warning(f"429 rate limit on key {self.current_key_index}, rotating to next key")
                    
                    # Backoff before retry
                    backoff_time = base_backoff * (2 ** attempt)
                    time.sleep(min(backoff_time, 2.0))
                    continue
                
                elif 500 <= response.status_code < 600:
                    # Server error - retry with backoff
                    logging.warning(f"Server error {response.status_code}, retrying...")
                    backoff_time = base_backoff * (2 ** attempt)
                    time.sleep(min(backoff_time, 5.0))
                    continue
                
                else:
                    # Client error - don't retry
                    logging.error(f"Client error {response.status_code}: {response.text}")
                    raise requests.RequestException(f"HTTP {response.status_code}: {response.text}")
            
            except requests.RequestException as e:
                if attempt == max_retries - 1:
                    logging.error(f"Request failed after {max_retries} attempts: {e}")
                    raise
                
                # Retry with backoff
                backoff_time = base_backoff * (2 ** attempt)
                time.sleep(min(backoff_time, 5.0))
        
        raise requests.RequestException(f"Failed to get response after {max_retries} attempts")

# Global instance
_pool = None

def get_finnhub_pool() -> FinnhubKeyPool:
    """Get global Finnhub pool instance"""
    global _pool
    if _pool is None:
        _pool = FinnhubKeyPool()
    return _pool

def finnhub_get(endpoint: str, params: Dict = None, timeout: int = 10) -> Dict:
    """Convenience function for making Finnhub API calls"""
    pool = get_finnhub_pool()
    return pool.finnhub_get(endpoint, params, timeout)

# Convenience functions for common endpoints
def get_company_news(symbol: str, from_date: str, to_date: str) -> List[Dict]:
    """Get company news with rate limiting"""
    params = {
        'symbol': symbol,
        'from': from_date,
        'to': to_date
    }
    return finnhub_get('company-news', params)

def get_general_news(category: str = 'general', min_id: int = 0) -> List[Dict]:
    """Get general news with rate limiting"""
    params = {
        'category': category,
        'minId': min_id
    }
    return finnhub_get('news', params)

def get_stock_candles(symbol: str, resolution: str, from_ts: int, to_ts: int) -> Dict:
    """Get stock candles with rate limiting"""
    params = {
        'symbol': symbol,
        'resolution': resolution,
        'from': from_ts,
        'to': to_ts
    }
    return finnhub_get('stock/candle', params)

