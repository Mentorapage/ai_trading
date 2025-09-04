"""
NEWS WEIGHTING MODULE
=====================
Implements source-weighted news sentiment aggregation
"""

import re
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from urllib.parse import urlparse
import hashlib

def extract_domain(url: str) -> str:
    """
    Extract domain from URL for source weighting
    
    Args:
        url (str): Article URL
        
    Returns:
        str: Domain name or 'unknown' if extraction fails
    """
    try:
        if not url or not isinstance(url, str):
            return 'unknown'
        
        # Handle URLs that might not have protocol
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Remove 'www.' prefix if present
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Validate that we have a proper domain
        if not domain or '.' not in domain:
            return 'unknown'
        
        return domain
        
    except Exception as e:
        logging.debug(f"Error extracting domain from URL '{url}': {e}")
        return 'unknown'

def create_article_hash(title: str, url: str, published_at: int) -> str:
    """
    Create a hash for article deduplication
    
    Args:
        title (str): Article title
        url (str): Article URL
        published_at (int): Publication timestamp
        
    Returns:
        str: Hash string for deduplication
    """
    # Normalize title (lowercase, remove extra whitespace)
    normalized_title = ' '.join(title.lower().split()) if title else ''
    normalized_url = url.lower() if url else ''
    
    # Create hash from title, url, and timestamp
    hash_input = f"{normalized_title}|{normalized_url}|{published_at}"
    return hashlib.md5(hash_input.encode()).hexdigest()

def deduplicate_articles(articles: List[Dict]) -> List[Dict]:
    """
    Remove duplicate articles based on title, URL, and timestamp
    
    Args:
        articles (List[Dict]): List of article dictionaries
        
    Returns:
        List[Dict]: Deduplicated list of articles
    """
    seen_hashes = set()
    deduplicated = []
    
    for article in articles:
        article_hash = create_article_hash(
            article.get('headline', ''),
            article.get('url', ''),
            article.get('datetime', 0)
        )
        
        if article_hash not in seen_hashes:
            seen_hashes.add(article_hash)
            deduplicated.append(article)
    
    if len(articles) != len(deduplicated):
        logging.debug(f"Deduplicated articles: {len(articles)} -> {len(deduplicated)}")
    
    return deduplicated

def filter_articles_by_time(articles: List[Dict], decision_time: datetime) -> List[Dict]:
    """
    Filter articles to only include those published before decision time
    
    Args:
        articles (List[Dict]): List of article dictionaries
        decision_time (datetime): Decision timestamp (UTC)
        
    Returns:
        List[Dict]: Time-filtered articles
    """
    decision_timestamp = decision_time.timestamp()
    filtered_articles = []
    excluded_count = 0
    
    for article in articles:
        published_at = article.get('datetime', 0)
        
        if published_at <= decision_timestamp:
            filtered_articles.append(article)
        else:
            excluded_count += 1
            logging.debug(f"Excluded future article: published_at={published_at}, decision_time={decision_timestamp}")
    
    if excluded_count > 0:
        logging.debug(f"Time filter excluded {excluded_count} future articles")
    
    return filtered_articles

def compute_weighted_sentiment(articles: List[Dict], sentiment_scores: List[float], 
                             source_weights: Dict[str, float], default_weight: float = 1.0) -> Tuple[float, Dict[str, Any]]:
    """
    Compute weighted sentiment score from articles and their sentiment scores
    
    Args:
        articles (List[Dict]): List of article dictionaries
        sentiment_scores (List[float]): Corresponding sentiment scores
        source_weights (Dict[str, float]): Domain to weight mapping
        default_weight (float): Default weight for unknown sources
        
    Returns:
        Tuple[float, Dict[str, Any]]: (weighted_sentiment, debug_info)
    """
    if not articles or not sentiment_scores or len(articles) != len(sentiment_scores):
        return 0.0, {'error': 'Invalid input data'}
    
    weighted_sum = 0.0
    total_weight = 0.0
    source_counts = {}
    
    for article, sentiment in zip(articles, sentiment_scores):
        # Extract domain and get weight
        url = article.get('url', '')
        domain = extract_domain(url)
        weight = source_weights.get(domain, default_weight)
        
        # Update weighted sum
        weighted_sum += sentiment * weight
        total_weight += weight
        
        # Track source counts for debugging
        source_counts[domain] = source_counts.get(domain, 0) + 1
    
    # Calculate weighted average
    weighted_sentiment = weighted_sum / total_weight if total_weight > 0 else 0.0
    
    # Debug information
    debug_info = {
        'n_articles_raw': len(articles),
        'weighted_compound': weighted_sentiment,
        'sum_weights': total_weight,
        'source_counts': source_counts,
        'avg_weight': total_weight / len(articles) if articles else 0.0
    }
    
    return weighted_sentiment, debug_info

def apply_news_weighting(ticker: str, articles: List[Dict], sentiment_scores: List[float],
                        decision_time: datetime, weighting_config: Dict) -> Tuple[float, Dict[str, Any]]:
    """
    Apply news weighting pipeline to compute final sentiment score
    
    Args:
        ticker (str): Stock ticker
        articles (List[Dict]): Raw articles from news API
        sentiment_scores (List[float]): Corresponding sentiment scores
        decision_time (datetime): Decision timestamp for time filtering
        weighting_config (Dict): News weighting configuration
        
    Returns:
        Tuple[float, Dict[str, Any]]: (final_sentiment, debug_info)
    """
    debug_info = {
        'ticker': ticker,
        'n_articles_initial': len(articles),
        'enabled': weighting_config.get('enabled', False)
    }
    
    if not weighting_config.get('enabled', False):
        # If weighting is disabled, return simple average
        simple_avg = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0
        debug_info.update({
            'final_sentiment': simple_avg,
            'method': 'simple_average'
        })
        return simple_avg, debug_info
    
    try:
        # Step 1: Filter by time (no look-ahead)
        time_filtered_articles = filter_articles_by_time(articles, decision_time)
        
        if len(time_filtered_articles) != len(articles):
            # Adjust sentiment scores to match filtered articles
            filtered_indices = []
            decision_timestamp = decision_time.timestamp()
            
            for i, article in enumerate(articles):
                if article.get('datetime', 0) <= decision_timestamp:
                    filtered_indices.append(i)
            
            time_filtered_scores = [sentiment_scores[i] for i in filtered_indices]
        else:
            time_filtered_scores = sentiment_scores
        
        debug_info['n_articles_after_time_filter'] = len(time_filtered_articles)
        
        # Step 2: Deduplicate articles
        deduplicated_articles = deduplicate_articles(time_filtered_articles)
        
        if len(deduplicated_articles) != len(time_filtered_articles):
            # Adjust sentiment scores to match deduplicated articles
            # Create mapping from original articles to deduplicated ones
            dedup_hashes = {create_article_hash(
                article.get('headline', ''),
                article.get('url', ''),
                article.get('datetime', 0)
            ): article for article in deduplicated_articles}
            
            deduplicated_scores = []
            for i, article in enumerate(time_filtered_articles):
                article_hash = create_article_hash(
                    article.get('headline', ''),
                    article.get('url', ''),
                    article.get('datetime', 0)
                )
                if article_hash in dedup_hashes:
                    deduplicated_scores.append(time_filtered_scores[i])
        else:
            deduplicated_scores = time_filtered_scores
        
        debug_info['n_articles_after_dedupe'] = len(deduplicated_articles)
        
        if not deduplicated_articles or not deduplicated_scores:
            debug_info.update({
                'final_sentiment': 0.0,
                'method': 'no_articles_after_filtering'
            })
            return 0.0, debug_info
        
        # Step 3: Apply source weighting
        source_weights = weighting_config.get('source_weights', {})
        default_weight = weighting_config.get('default_weight', 1.0)
        
        weighted_sentiment, weight_debug = compute_weighted_sentiment(
            deduplicated_articles, deduplicated_scores, source_weights, default_weight
        )
        
        debug_info.update(weight_debug)
        debug_info.update({
            'final_sentiment': weighted_sentiment,
            'method': 'weighted_average'
        })
        
        return weighted_sentiment, debug_info
        
    except Exception as e:
        logging.error(f"Error in news weighting for {ticker}: {e}")
        # Fallback to simple average
        simple_avg = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0
        debug_info.update({
            'final_sentiment': simple_avg,
            'method': 'error_fallback',
            'error': str(e)
        })
        return simple_avg, debug_info

def log_news_weighting_debug(ticker: str, debug_info: Dict[str, Any], enabled: bool = False):
    """
    Log detailed news weighting debug information
    
    Args:
        ticker (str): Stock ticker
        debug_info (Dict[str, Any]): Debug information from weighting process
        enabled (bool): Whether debug logging is enabled
    """
    if not enabled and not logging.getLogger().isEnabledFor(logging.DEBUG):
        return
    
    method = debug_info.get('method', 'unknown')
    final_sentiment = debug_info.get('final_sentiment', 0.0)
    
    log_msg = f"news_weighting: {ticker} method={method}, final_sentiment={final_sentiment:.4f}"
    
    if method == 'weighted_average':
        log_msg += f", n_articles_raw={debug_info.get('n_articles_initial', 0)}"
        log_msg += f", n_after_dedupe={debug_info.get('n_articles_after_dedupe', 0)}"
        log_msg += f", sum_weights={debug_info.get('sum_weights', 0.0):.2f}"
        
        source_counts = debug_info.get('source_counts', {})
        if source_counts:
            sources_str = ', '.join([f"{domain}:{count}" for domain, count in source_counts.items()])
            log_msg += f", sources=[{sources_str}]"
    
    logging.debug(log_msg)

def validate_news_weighting_config(config: Dict) -> bool:
    """
    Validate news weighting configuration
    
    Args:
        config (Dict): News weighting configuration
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not isinstance(config, dict):
        return False
    
    # Check enabled flag
    if 'enabled' in config and not isinstance(config['enabled'], bool):
        return False
    
    # Check default_weight
    if 'default_weight' in config:
        if not isinstance(config['default_weight'], (int, float)) or config['default_weight'] <= 0:
            return False
    
    # Check source_weights
    if 'source_weights' in config:
        weights = config['source_weights']
        if not isinstance(weights, dict):
            return False
        
        for domain, weight in weights.items():
            if not isinstance(domain, str) or not isinstance(weight, (int, float)) or weight <= 0:
                return False
    
    return True
