"""
News Sentiment Tool for shared data access.

Function: execute_news_tool — fetches news and sentiment for stock tickers.
Called from: backend.generative_ui.agent_v2, backend.conversational_analytics.tools
Invokes: Alpha Vantage News API or demo data.
Purpose: Single implementation of news fetching for all projects.

Optimizations:
  - #3: Shared httpx.AsyncClient for connection reuse (avoids TCP handshake per request)
  - #5: TTL-based response cache (5 minutes) to avoid redundant API calls
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

# ============================================================================
# Optimization #3: Shared HTTP Client
# ============================================================================

_http_client: Optional[httpx.AsyncClient] = None
_http_client_lock = asyncio.Lock()


async def _get_http_client() -> httpx.AsyncClient:
    """
    Get or create a shared httpx.AsyncClient for connection reuse.

    Function: _get_http_client — returns singleton HTTP client.
    Called from: _fetch_news_from_api
    Why: Reuses TCP connections to reduce latency on repeated API calls.
    """
    global _http_client
    if _http_client is None:
        async with _http_client_lock:
            if _http_client is None:
                _http_client = httpx.AsyncClient(
                    timeout=10.0,
                    limits=httpx.Limits(
                        max_keepalive_connections=5,
                        max_connections=10,
                        keepalive_expiry=30.0,
                    ),
                )
                logger.info("[NEWS_SERVICE] HTTP client initialized (keepalive enabled)")
    return _http_client


async def close_http_client() -> None:
    """
    Close the shared HTTP client. Call during application shutdown.

    Function: close_http_client — gracefully closes HTTP client.
    Called from: backend.main.shutdown_event
    Why: Ensures clean resource cleanup.
    """
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None
        logger.info("[NEWS_SERVICE] HTTP client closed")


# ============================================================================
# Optimization #5: TTL-based Response Cache
# ============================================================================

@dataclass
class CachedNewsResponse:
    """Cached news response with metadata."""
    articles: List[Dict[str, Any]]
    created_at: float = field(default_factory=time.time)
    hit_count: int = 0


class NewsCache:
    """
    TTL-based cache for news API responses.

    Class: NewsCache
    Role: Caches news responses to avoid redundant API calls.
    Called from: _fetch_news_from_api
    Why: Alpha Vantage has rate limits; caching reduces latency and costs.
    """

    def __init__(self, ttl_seconds: int = 300, max_size: int = 50):
        """
        Initialize news cache.

        Args:
            ttl_seconds: Cache entry TTL (default 5 minutes)
            max_size: Maximum cache entries before eviction
        """
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._cache: Dict[str, CachedNewsResponse] = {}

    def _make_key(self, ticker: str, limit: int, topics: Optional[List[str]]) -> str:
        """Generate cache key from request parameters."""
        topic_str = ",".join(sorted(topics)) if topics else ""
        key_str = f"{ticker.upper()}:{limit}:{topic_str}"
        return hashlib.md5(key_str.encode()).hexdigest()[:16]

    def get(self, ticker: str, limit: int, topics: Optional[List[str]] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached articles if not expired.

        Returns:
            List of articles if cache hit, None otherwise.
        """
        key = self._make_key(ticker, limit, topics)
        cached = self._cache.get(key)

        if cached is None:
            return None

        # Check expiration
        if time.time() - cached.created_at > self.ttl_seconds:
            del self._cache[key]
            return None

        cached.hit_count += 1
        logger.debug("[NEWS_CACHE] Hit for %s (hits=%d)", ticker, cached.hit_count)
        return cached.articles

    def set(self, ticker: str, limit: int, topics: Optional[List[str]], articles: List[Dict[str, Any]]) -> None:
        """
        Cache articles for a request.

        Evicts oldest entries if cache is full.
        """
        # Evict oldest entries if at capacity
        if len(self._cache) >= self.max_size:
            oldest_key = min(self._cache, key=lambda k: self._cache[k].created_at)
            del self._cache[oldest_key]

        key = self._make_key(ticker, limit, topics)
        self._cache[key] = CachedNewsResponse(articles=articles)
        logger.debug("[NEWS_CACHE] Cached %d articles for %s", len(articles), ticker)

    def stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        now = time.time()
        valid_entries = sum(
            1 for c in self._cache.values()
            if now - c.created_at <= self.ttl_seconds
        )
        return {
            "size": len(self._cache),
            "valid_entries": valid_entries,
            "ttl_seconds": self.ttl_seconds,
            "max_size": self.max_size,
        }


# Global cache instance
_news_cache = NewsCache(ttl_seconds=300, max_size=50)


def get_news_cache() -> NewsCache:
    """Get the global news cache instance."""
    return _news_cache


# ============================================================================
# Tool Definition
# ============================================================================

# Tool definition for Claude
NEWS_TOOL_DEFINITION = {
    "name": "get_news_sentiment",
    "description": """Fetch recent news articles and sentiment analysis for a stock ticker.

Use this tool when the user wants to:
- See recent news about a company
- Understand market sentiment
- Get news context for price movements
- Research company announcements

Returns news articles with titles, summaries, sentiment scores, and source citations.""",
    "input_schema": {
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "description": "Stock ticker symbol (e.g., 'NVDA', 'AMD', 'INTC')"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of news articles to return (default: 5, max: 10)"
            },
            "topics": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional topic filters (e.g., 'earnings', 'technology', 'mergers')"
            }
        },
        "required": ["ticker"]
    }
}


# ============================================================================
# Sentiment Helpers
# ============================================================================

def _get_sentiment_label(score: float) -> str:
    """
    Convert sentiment score to human-readable label.
    
    Function: _get_sentiment_label — maps numeric sentiment to text.
    Called from: _get_demo_news, execute_news_tool
    Invokes: n/a
    Purpose: Consistent sentiment labeling across the app.
    """
    if score >= 0.35:
        return "Bullish"
    elif score >= 0.15:
        return "Somewhat Bullish"
    elif score > -0.15:
        return "Neutral"
    elif score > -0.35:
        return "Somewhat Bearish"
    else:
        return "Bearish"


def _get_sentiment_color(score: float) -> str:
    """
    Get color for sentiment visualization.
    
    Function: _get_sentiment_color — maps sentiment to CSS color.
    Called from: news formatting logic
    Invokes: n/a
    Purpose: Visual consistency for sentiment displays.
    """
    if score >= 0.15:
        return "#22c55e"  # green
    elif score > -0.15:
        return "#eab308"  # yellow
    else:
        return "#ef4444"  # red


# ============================================================================
# API Fetch with Caching
# ============================================================================

async def _fetch_news_from_api(
    ticker: str,
    limit: int = 5,
    topics: Optional[List[str]] = None,
    skip_cache: bool = False,
) -> List[Dict[str, Any]]:
    """
    Fetch news from Alpha Vantage News API.
    
    Function: _fetch_news_from_api — calls external news API with caching.
    Called from: execute_news_tool
    Invokes: _get_http_client, NewsCache
    Purpose: Real news data when API key is configured; uses shared client + cache.

    Optimizations:
      - Uses shared httpx.AsyncClient (connection reuse)
      - TTL cache for responses (5 min default)
    """
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "")
    
    if not api_key:
        return _get_demo_news(ticker, limit)
    
    # Check cache first (unless skip_cache is set)
    if not skip_cache:
        cached = _news_cache.get(ticker, limit, topics)
        if cached is not None:
            return cached
    
    url = "https://www.alphavantage.co/query"
    params: Dict[str, Any] = {
        "function": "NEWS_SENTIMENT",
        "tickers": ticker.upper(),
        "limit": min(limit, 50),
        "apikey": api_key
    }
    if topics:
        params["topics"] = ",".join(topics)
    
    try:
        client = await _get_http_client()
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if "feed" not in data:
            return _get_demo_news(ticker, limit)
        
        articles = []
        for item in data.get("feed", [])[:limit]:
            # Find ticker-specific sentiment
            ticker_sentiment = None
            for ts in item.get("ticker_sentiment", []):
                if ts.get("ticker", "").upper() == ticker.upper():
                    ticker_sentiment = ts
                    break
            
            sentiment_score = float(ticker_sentiment.get("ticker_sentiment_score", 0)) if ticker_sentiment else 0
            
            articles.append({
                "title": item.get("title", ""),
                "summary": item.get("summary", "")[:300] + "..." if len(item.get("summary", "")) > 300 else item.get("summary", ""),
                "url": item.get("url", ""),
                "source": item.get("source", "Unknown"),
                "published_at": item.get("time_published", ""),
                "sentiment_score": round(sentiment_score, 3),
                "sentiment_label": _get_sentiment_label(sentiment_score),
                "sentiment_color": _get_sentiment_color(sentiment_score),
                "topics": [t.get("topic", "") for t in item.get("topics", [])][:3],
            })
        
        # Cache the result
        _news_cache.set(ticker, limit, topics, articles)
        return articles
        
    except Exception as e:
        logger.warning("[NEWS_SERVICE] API fetch failed: %s", e)
        return _get_demo_news(ticker, limit)


# ============================================================================
# Demo Data
# ============================================================================

def _get_demo_news(ticker: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Generate demo news data for testing without API key.
    
    Function: _get_demo_news — provides mock news for demos.
    Called from: _fetch_news_from_api (fallback), execute_news_tool
    Invokes: n/a
    Purpose: Enables testing and demos without external API dependencies.
    """
    ticker = ticker.upper()
    
    demo_articles = {
        "NVDA": [
            {
                "title": "NVIDIA Reports Record Q1 Revenue of $26 Billion, Beating Estimates",
                "summary": "NVIDIA Corporation announced record quarterly revenue driven by unprecedented demand for AI chips. Data center revenue grew 427% year-over-year as enterprises race to deploy AI infrastructure.",
                "url": "https://investor.nvidia.com/news",
                "source": "NVIDIA Investor Relations",
                "published_at": datetime.now().strftime("%Y%m%dT%H%M%S"),
                "sentiment_score": 0.45,
                "sentiment_label": "Bullish",
                "sentiment_color": "#22c55e",
                "topics": ["Earnings", "AI", "Data Center"]
            },
            {
                "title": "NVIDIA's Blackwell GPUs See Strong Demand from Cloud Providers",
                "summary": "Major cloud providers including Microsoft, Google, and Amazon have placed significant orders for NVIDIA's next-generation Blackwell architecture GPUs, signaling continued AI infrastructure buildout.",
                "url": "https://www.reuters.com/technology",
                "source": "Reuters",
                "published_at": datetime.now().strftime("%Y%m%dT%H%M%S"),
                "sentiment_score": 0.38,
                "sentiment_label": "Bullish",
                "sentiment_color": "#22c55e",
                "topics": ["Technology", "Cloud Computing", "AI"]
            },
            {
                "title": "Analysts Raise NVIDIA Price Targets Following AI Momentum",
                "summary": "Multiple Wall Street analysts have raised their price targets for NVIDIA, citing strong AI demand visibility and the company's dominant market position in accelerated computing.",
                "url": "https://www.bloomberg.com/news",
                "source": "Bloomberg",
                "published_at": datetime.now().strftime("%Y%m%dT%H%M%S"),
                "sentiment_score": 0.32,
                "sentiment_label": "Somewhat Bullish",
                "sentiment_color": "#22c55e",
                "topics": ["Analyst Ratings", "AI", "Stocks"]
            },
        ],
        "AMD": [
            {
                "title": "AMD Gains Data Center Market Share with MI300X AI Accelerators",
                "summary": "AMD's MI300X accelerators are gaining traction in the data center market as customers seek alternatives to NVIDIA's GPUs. The company reported strong enterprise adoption.",
                "url": "https://www.amd.com/news",
                "source": "AMD Newsroom",
                "published_at": datetime.now().strftime("%Y%m%dT%H%M%S"),
                "sentiment_score": 0.28,
                "sentiment_label": "Somewhat Bullish",
                "sentiment_color": "#22c55e",
                "topics": ["AI", "Data Center", "Competition"]
            },
            {
                "title": "AMD Reports Solid Quarter, Raises AI Revenue Outlook",
                "summary": "AMD exceeded expectations with data center growth offsetting PC market softness. The company raised its AI accelerator revenue forecast for the year.",
                "url": "https://www.cnbc.com/technology",
                "source": "CNBC",
                "published_at": datetime.now().strftime("%Y%m%dT%H%M%S"),
                "sentiment_score": 0.22,
                "sentiment_label": "Somewhat Bullish",
                "sentiment_color": "#22c55e",
                "topics": ["Earnings", "AI", "Semiconductors"]
            },
        ],
        "INTC": [
            {
                "title": "Intel Foundry Services Secures New Customer Wins",
                "summary": "Intel's foundry business announced new partnerships as the company executes on its IDM 2.0 strategy. The 18A process node is on track for production.",
                "url": "https://www.intel.com/newsroom",
                "source": "Intel Newsroom",
                "published_at": datetime.now().strftime("%Y%m%dT%H%M%S"),
                "sentiment_score": 0.15,
                "sentiment_label": "Somewhat Bullish",
                "sentiment_color": "#22c55e",
                "topics": ["Foundry", "Manufacturing", "Technology"]
            },
            {
                "title": "Intel Faces Challenges in AI Chip Market Competition",
                "summary": "Intel continues to work on catching up in the AI accelerator market as NVIDIA and AMD dominate. The company's Gaudi chips are gaining some enterprise interest.",
                "url": "https://www.wsj.com/tech",
                "source": "Wall Street Journal",
                "published_at": datetime.now().strftime("%Y%m%dT%H%M%S"),
                "sentiment_score": -0.05,
                "sentiment_label": "Neutral",
                "sentiment_color": "#eab308",
                "topics": ["AI", "Competition", "Semiconductors"]
            },
        ],
    }
    
    # Default articles for unknown tickers
    default_articles = [
        {
            "title": f"{ticker} Stock Moves on Market Sentiment",
            "summary": f"Shares of {ticker} traded in line with broader semiconductor sector movements as investors weigh economic data and industry trends.",
            "url": "https://finance.yahoo.com",
            "source": "Yahoo Finance",
            "published_at": datetime.now().strftime("%Y%m%dT%H%M%S"),
            "sentiment_score": 0.05,
            "sentiment_label": "Neutral",
            "sentiment_color": "#eab308",
            "topics": ["Stocks", "Semiconductors", "Markets"]
        },
    ]
    
    articles = demo_articles.get(ticker, default_articles)
    return articles[:limit]


# ============================================================================
# Main Tool Entry Point
# ============================================================================

async def execute_news_tool(
    ticker: str,
    limit: int = 5,
    topics: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Execute the news sentiment tool.
    
    Function: execute_news_tool — fetches and formats news with sentiment.
    Called from: backend.generative_ui.agent_v2, backend.conversational_analytics.tools
    Invokes: _fetch_news_from_api
    Purpose: Single news fetch implementation for all projects.
    
    Args:
        ticker: Stock ticker symbol
        limit: Maximum number of articles to return
        topics: Optional topic filters
        
    Returns:
        Dictionary with success status, articles, and aggregate sentiment
    """
    try:
        # Clamp limit
        limit = max(1, min(limit or 5, 10))
        
        articles = await _fetch_news_from_api(ticker, limit, topics)
        
        if not articles:
            return {
                "success": True,
                "ticker": ticker.upper(),
                "articles": [],
                "article_count": 0,
                "aggregate_sentiment": 0,
                "aggregate_label": "No Data",
                "message": f"No news articles found for {ticker.upper()}"
            }
        
        # Calculate aggregate sentiment
        sentiment_scores = [a.get("sentiment_score", 0) for a in articles]
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
        
        return {
            "success": True,
            "ticker": ticker.upper(),
            "articles": articles,
            "article_count": len(articles),
            "aggregate_sentiment": round(avg_sentiment, 3),
            "aggregate_label": _get_sentiment_label(avg_sentiment),
            "aggregate_color": _get_sentiment_color(avg_sentiment),
        }
        
    except Exception as e:
        return {
            "success": False,
            "ticker": ticker.upper(),
            "error": str(e),
            "articles": []
        }


__all__ = [
    "NEWS_TOOL_DEFINITION",
    "execute_news_tool",
    "close_http_client",
    "get_news_cache",
]
