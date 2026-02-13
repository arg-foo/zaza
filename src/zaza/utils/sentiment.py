"""Shared NLP/sentiment scoring utilities."""

from __future__ import annotations

import math
from typing import Any

BULLISH_KEYWORDS = [
    "beat",
    "beats",
    "exceeded",
    "surpassed",
    "upgrade",
    "upgraded",
    "outperform",
    "buy",
    "bullish",
    "growth",
    "record",
    "highest",
    "strong",
    "surge",
    "rally",
    "gain",
    "positive",
    "above expectations",
    "raised guidance",
    "dividend increase",
    "buyback",
    "acquisition",
]

BEARISH_KEYWORDS = [
    "miss",
    "missed",
    "below",
    "downgrade",
    "downgraded",
    "underperform",
    "sell",
    "bearish",
    "decline",
    "loss",
    "weak",
    "plunge",
    "drop",
    "negative",
    "below expectations",
    "lowered guidance",
    "layoffs",
    "investigation",
    "lawsuit",
    "recall",
    "warning",
]


def score_headline(headline: str) -> dict[str, Any]:
    """Score a news headline for financial sentiment."""
    text = headline.lower()
    bull_count = sum(1 for w in BULLISH_KEYWORDS if w in text)
    bear_count = sum(1 for w in BEARISH_KEYWORDS if w in text)
    total = bull_count + bear_count
    if total == 0:
        return {"sentiment": "neutral", "score": 0.0, "confidence": 0.3}
    score = (bull_count - bear_count) / total
    if score > 0.3:
        sentiment = "bullish"
    elif score < -0.3:
        sentiment = "bearish"
    else:
        sentiment = "neutral"
    confidence = min(total / 5, 1.0) * 0.5 + abs(score) * 0.5
    return {"sentiment": sentiment, "score": round(score, 4), "confidence": round(confidence, 4)}


def score_social_post(text: str) -> dict[str, Any]:
    """Score a social media post for sentiment."""
    return score_headline(text)


def aggregate_sentiment(
    scores: list[dict[str, Any]], recency_weights: bool = True
) -> dict[str, Any]:
    """Aggregate individual sentiment scores with optional recency weighting."""
    if not scores:
        return {"sentiment": "neutral", "score": 0.0, "confidence": 0.0, "count": 0}
    n = len(scores)
    if recency_weights:
        weights = [math.exp(-i * 0.3) for i in range(n)]
    else:
        weights = [1.0] * n
    total_weight = sum(weights)
    weighted_score = (
        sum(s.get("score", 0) * w for s, w in zip(scores, weights)) / total_weight
    )
    avg_confidence = (
        sum(s.get("confidence", 0.5) * w for s, w in zip(scores, weights)) / total_weight
    )
    if weighted_score > 0.2:
        sentiment = "bullish"
    elif weighted_score < -0.2:
        sentiment = "bearish"
    else:
        sentiment = "neutral"
    return {
        "sentiment": sentiment,
        "score": round(weighted_score, 4),
        "confidence": round(avg_confidence, 4),
        "count": n,
    }


def classify_insider_activity(transactions: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyze insider buy/sell patterns."""
    if not transactions:
        return {"sentiment": "neutral", "score": 0.0, "cluster_buying": False}
    buys = [
        t
        for t in transactions
        if t.get("type", "").lower() in ("purchase", "buy", "p - purchase")
    ]
    sells = [
        t for t in transactions if t.get("type", "").lower() in ("sale", "sell", "s - sale")
    ]
    total = len(buys) + len(sells)
    if total == 0:
        return {"sentiment": "neutral", "score": 0.0, "cluster_buying": False}
    net_ratio = (len(buys) - len(sells)) / total
    cluster_buying = len(buys) >= 3
    if net_ratio > 0.5:
        sentiment = "strong_buy"
    elif net_ratio > 0.2:
        sentiment = "buy"
    elif net_ratio < -0.5:
        sentiment = "strong_sell"
    elif net_ratio < -0.2:
        sentiment = "sell"
    else:
        sentiment = "neutral"
    return {
        "sentiment": sentiment,
        "score": round(net_ratio, 4),
        "buys": len(buys),
        "sells": len(sells),
        "cluster_buying": cluster_buying,
    }


def detect_contrarian_signal(score: float) -> str | None:
    """Detect contrarian signals from extreme sentiment."""
    if score < -0.7:
        return "contrarian_bullish"
    elif score > 0.7:
        return "contrarian_bearish"
    return None
