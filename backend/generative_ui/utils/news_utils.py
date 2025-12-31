# --- News Utils Function Map ---
# Function: parse_published_at
#   Role: Normalize news timestamps into ISO-like strings.
#   Called from: map_news_event
#   Invokes: datetime.strptime
#   Why: Produces consistent NewsTimeline dates.
# Function: map_sentiment
#   Role: Map sentiment scores/labels to positive/neutral/negative.
#   Called from: map_news_event
#   Invokes: n/a
#   Why: Aligns sentiment values with frontend styling.
# Function: map_news_event
#   Role: Convert news tool payloads into NewsTimeline event objects.
#   Called from: agent_v2.A2UIAgent._execute_explain_move
#   Invokes: map_sentiment, parse_published_at
#   Why: Standardizes news data for the UI.
# --- End News Utils Function Map ---
"""
News data transformation utilities.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Mapping, Optional


def parse_published_at(raw: str) -> str:
    """Normalize news timestamps into ISO-like strings."""
    if not raw:
        return ""
    try:
        if "T" in raw and len(raw) >= 15:
            dt = datetime.strptime(raw[:15], "%Y%m%dT%H%M%S")
            return dt.isoformat()
    except ValueError:
        return raw
    return raw


def map_sentiment(score: Optional[float], label: Optional[str]) -> str:
    """Map sentiment scores/labels to positive/neutral/negative."""
    if score is not None:
        if score >= 0.15:
            return "positive"
        if score <= -0.15:
            return "negative"
        return "neutral"
    lowered = (label or "").lower()
    if "bull" in lowered:
        return "positive"
    if "bear" in lowered:
        return "negative"
    return "neutral"


def map_news_event(article: Mapping[str, Any]) -> Dict[str, Any]:
    """Convert news tool payloads into NewsTimeline event objects."""
    from .data_utils import coerce_float  # Import here to avoid circular dependency

    score = coerce_float(article.get("sentiment_score"))
    sentiment = map_sentiment(score, article.get("sentiment_label"))
    published_at = article.get("published_at") or ""
    return {
        "date": parse_published_at(str(published_at)),
        "title": article.get("title", ""),
        "summary": article.get("summary", ""),
        "sentiment": sentiment,
        "source": article.get("source", ""),
        "url": article.get("url", ""),
    }


__all__ = [
    "parse_published_at",
    "map_sentiment",
    "map_news_event",
]
