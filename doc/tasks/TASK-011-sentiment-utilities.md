# TASK-011: Shared NLP/Sentiment Scoring Utilities

## Task ID
TASK-011

## Status
COMPLETED

## Title
Implement Shared NLP/Sentiment Scoring Utilities

## Description
Implement `src/zaza/utils/sentiment.py` — shared NLP and sentiment scoring helpers used by the 4 sentiment analysis tools. This module provides keyword-based sentiment scoring for news headlines and social media posts, insider transaction analysis, and aggregate scoring functions.

## Acceptance Criteria

### Functional Requirements
- [ ] `src/zaza/utils/sentiment.py` implemented
- [ ] `score_headline(headline: str) -> dict` — keyword-based sentiment score for a news headline; returns `{"sentiment": "bullish"|"bearish"|"neutral", "confidence": 0.0-1.0}`
- [ ] `score_social_post(text: str) -> dict` — sentiment score for a social media post
- [ ] `aggregate_sentiment(scores: list[dict], recency_weights: bool = True) -> dict` — weighted aggregate of individual scores; recent items weighted higher when `recency_weights=True`
- [ ] `classify_insider_activity(transactions: list[dict]) -> dict` — analyze insider buy/sell patterns; detect cluster buying (3+ insiders within 2 weeks); return sentiment classification
- [ ] `detect_contrarian_signal(score: float) -> str | None` — returns "contrarian_bullish" if score is extremely negative (<-0.7), "contrarian_bearish" if extremely positive (>0.7), None otherwise
- [ ] Bullish lexicon: configurable list of positive financial keywords
- [ ] Bearish lexicon: configurable list of negative financial keywords

### Non-Functional Requirements
- [ ] **Testing**: Unit tests with known headlines/posts verifying expected classifications
- [ ] **Performance**: Scoring should be <10ms per headline
- [ ] **Documentation**: Docstrings explaining scoring methodology and limitations

## Dependencies
- TASK-001: Project scaffolding

## Technical Notes

### Keyword-Based Scoring
```python
BULLISH_KEYWORDS = [
    "beat", "beats", "exceeded", "surpassed", "upgrade", "upgraded",
    "outperform", "buy", "bullish", "growth", "record", "highest",
    "strong", "surge", "rally", "gain", "positive", "above expectations",
    "raised guidance", "dividend increase", "buyback", "acquisition"
]

BEARISH_KEYWORDS = [
    "miss", "missed", "below", "downgrade", "downgraded", "underperform",
    "sell", "bearish", "decline", "loss", "weak", "plunge", "drop",
    "negative", "below expectations", "lowered guidance", "layoffs",
    "investigation", "lawsuit", "recall", "warning"
]

def score_headline(headline: str) -> dict:
    text = headline.lower()
    bull_count = sum(1 for w in BULLISH_KEYWORDS if w in text)
    bear_count = sum(1 for w in BEARISH_KEYWORDS if w in text)
    total = bull_count + bear_count
    if total == 0:
        return {"sentiment": "neutral", "confidence": 0.5}
    score = (bull_count - bear_count) / total
    # Map to sentiment label
    ...
```

### Insider Cluster Detection
```python
def classify_insider_activity(transactions: list[dict]) -> dict:
    buys = [t for t in transactions if t["type"] == "Purchase"]
    sells = [t for t in transactions if t["type"] == "Sale"]
    # Cluster detection: 3+ buys within 14 days
    # Net buying ratio: len(buys) / (len(buys) + len(sells))
    # Dollar amounts: sum of buy values vs sell values
```

### Implementation Hints
1. Keyword matching is simple but effective for financial headlines — most financial news uses standard terminology
2. Recency weighting: use exponential decay based on article age (half-life of 3 days)
3. Insider cluster buying is one of the strongest medium-term bullish signals in academic research
4. The contrarian signal detector works best with aggregate scores, not individual article scores

## Estimated Complexity
**Small** (3-4 hours)

## References
- ZAZA_ARCHITECTURE.md Section 7.6 (Sentiment Analysis Tools)
