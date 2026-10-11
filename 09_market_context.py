"""
Step 9: market context -- live news sentiment + Fear & Greed index.

Pulls real, current data from public, keyless sources:
  - CoinDesk and Cointelegraph RSS feeds (latest ~30 headlines each)
  - Alternative.me's Crypto Fear & Greed Index (daily, no auth needed)

Scores headlines with VADER, a standard lexicon-based sentiment model (not
an LLM, just word-polarity scoring -- transparent and reproducible).

Honest limitation: RSS only gives recent headlines, there is no free way to
get historical news sentiment for past months, so this can only start
contributing data FORWARD from whenever it's run, it can't be backtested
against our existing price history.

Can be imported (get_market_context()) or run standalone to print the
current reading.
"""
import feedparser
import requests
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from datetime import datetime, timezone
import json

RSS_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml",
    "https://cointelegraph.com/rss/tag/bitcoin",
]
FEAR_GREED_URL = "https://api.alternative.me/fng/"

analyzer = SentimentIntensityAnalyzer()


def get_news_sentiment(max_headlines=40):
    headlines = []
    feeds_failed = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            entries = [e.title for e in feed.entries[:20] if hasattr(e, "title")]
            if not entries:
                feeds_failed.append(url)
            headlines.extend(entries)
        except Exception as e:
            print(f"Warning: failed to fetch {url}: {e}")
            feeds_failed.append(url)

    headlines = headlines[:max_headlines]
    if not headlines:
        return {"headline_count": 0, "avg_compound": 0.0, "label": "unknown", "sample": [],
                "feeds_failed": feeds_failed}

    scores = [analyzer.polarity_scores(h)["compound"] for h in headlines]
    avg = sum(scores) / len(scores)

    if avg >= 0.2:
        label = "positive"
    elif avg <= -0.2:
        label = "negative"
    else:
        label = "neutral"

    return {
        "headline_count": len(headlines),
        "avg_compound": round(avg, 4),
        "label": label,
        "sample": headlines[:5],
        "feeds_failed": feeds_failed,
    }


def get_fear_greed():
    try:
        resp = requests.get(FEAR_GREED_URL, timeout=10)
        data = resp.json()["data"][0]
        return {"value": int(data["value"]), "label": data["value_classification"]}
    except Exception as e:
        print(f"Warning: failed to fetch Fear & Greed index: {e}")
        return {"value": None, "label": "unknown"}


def get_market_context():
    context = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "news": get_news_sentiment(),
        "fear_greed": get_fear_greed(),
    }
    return context


if __name__ == "__main__":
    context = get_market_context()
    print(json.dumps(context, indent=2))

    with open("market_context.json", "w") as f:
        json.dump(context, f, indent=2)
    print("\nSaved to market_context.json")
