"""
CONFIG LOADER
=============
Handles loading and validation of strategy configuration from YAML files
"""

import yaml
import os
import logging
from typing import Dict, Any, Optional

class ConfigLoader:
    """Configuration loader with validation and defaults"""
    
    def __init__(self, config_path: str = "config.yml"):
        self.config_path = config_path
        self._config = None
        self._load_config()
    
    def _load_config(self):
        """Load configuration from YAML file with fallback to defaults"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as file:
                    self._config = yaml.safe_load(file) or {}
                logging.info(f"Configuration loaded from {self.config_path}")
            else:
                logging.warning(f"Config file {self.config_path} not found, using defaults")
                self._config = {}
        except Exception as e:
            logging.error(f"Error loading config from {self.config_path}: {e}")
            self._config = {}
        
        # Ensure required structure exists
        self._ensure_defaults()
    
    def _ensure_defaults(self):
        """Ensure all required configuration sections exist with defaults"""
        defaults = {
            'strategy': {
                'trend_filter': {
                    'enabled': False,
                    'lookback_days': 20,
                    'comparator': 'yesterday_gt_ma'
                },
                'news_weighting': {
                    'enabled': False,
                    'default_weight': 1.0,
                    'source_weights': {
                        'bloomberg.com': 1.30,
                        'reuters.com': 1.25,
                        'wsj.com': 1.20,
                        'cnbc.com': 1.10,
                        'seekingalpha.com': 0.95,
                        'marketwatch.com': 1.05,
                        'yahoo.com': 0.90,
                        'unknown': 1.00
                    }
                },
                'sentiment': {
                    'min_news_count': 1,
                    'top_k_articles': 10
                }
            },
            'logging': {
                'debug_trend_filter': False,
                'debug_news_weighting': False
            }
        }
        
        # Deep merge defaults with loaded config
        self._config = self._deep_merge(defaults, self._config)
    
    def _deep_merge(self, default: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries, with override taking precedence"""
        result = default.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    def get(self, path: str, default: Any = None) -> Any:
        """Get configuration value by dot-separated path"""
        keys = path.split('.')
        value = self._config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_trend_filter_config(self) -> Dict[str, Any]:
        """Get trend filter configuration"""
        return self.get('strategy.trend_filter', {})
    
    def get_news_weighting_config(self) -> Dict[str, Any]:
        """Get news weighting configuration"""
        return self.get('strategy.news_weighting', {})
    
    def is_trend_filter_enabled(self) -> bool:
        """Check if trend filter is enabled"""
        return self.get('strategy.trend_filter.enabled', False)
    
    def is_news_weighting_enabled(self) -> bool:
        """Check if news weighting is enabled"""
        return self.get('strategy.news_weighting.enabled', False)
    
    def get_source_weight(self, domain: str) -> float:
        """Get weight for a specific news source domain"""
        weights = self.get('strategy.news_weighting.source_weights', {})
        return weights.get(domain, weights.get('unknown', 1.0))
    
    def reload(self):
        """Reload configuration from file"""
        self._load_config()
        logging.info("Configuration reloaded")

# Global configuration instance
config = ConfigLoader()

