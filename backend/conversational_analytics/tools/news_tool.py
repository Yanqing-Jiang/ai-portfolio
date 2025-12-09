"""News Sentiment Tool for Conversational Analytics.

Function: news_tool — provides news sentiment analysis with citations for semiconductor companies.
Called from: agent.py via TOOL_EXECUTORS when Claude requests news analysis.
Invokes: Alpha Vantage News API or mock data for demo.
Purpose: Fetch recent news articles with sentiment scores and source citations.
"""
from __future__ import annotations

import os
import httpx
from typing import Any, Dict, List, Optional
from datetime import datetime

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


def _get_sentiment_label(score: float) -> str:
    """Convert sentiment score to human-readable label."""
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
    """Get color for sentiment visualization."""
    if score >= 0.15:
        return "#22c55e"  # green
    elif score > -0.15:
        return "#eab308"  # yellow
    else:
        return "#ef4444"  # red


async def fetch_news_from_api(ticker: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Fetch news from Alpha Vantage News API.
    
    Args:
        ticker: Stock ticker symbol
        limit: Maximum number of articles
        
    Returns:
        List of news articles with sentiment data
    """
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "")
    
    if not api_key:
        # Return demo data if no API key
        return _get_demo_news(ticker, limit)
    
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "NEWS_SENTIMENT",
        "tickers": ticker.upper(),
        "limit": min(limit, 50),
        "apikey": api_key
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
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
            
            return articles
            
    except Exception as e:
        # Fallback to demo data on error
        return _get_demo_news(ticker, limit)


def _get_demo_news(ticker: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Generate demo news data for testing without API key."""
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


async def execute_news_tool(
    ticker: str,
    limit: int = 5,
    topics: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Execute the news sentiment tool.
    
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
        
        articles = await fetch_news_from_api(ticker, limit)
        
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

