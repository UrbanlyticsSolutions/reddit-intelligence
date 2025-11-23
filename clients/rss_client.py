"""
RSS News Feed Client
Comprehensive client for accessing financial news from multiple RSS sources
"""

import feedparser
from typing import List, Dict, Optional, Any
from datetime import datetime
import time


class RSSClient:
    """Complete RSS News Feed Client for Financial Markets"""

    # All working RSS feeds
    FEEDS = {
        # Stock Market
        "yahoo_finance": "https://finance.yahoo.com/news/rssindex",
        "yahoo_sp500": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US",
        "cnbc_top": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "cnbc_world": "https://www.cnbc.com/id/100727362/device/rss/rss.html",
        "marketwatch_top": "http://feeds.marketwatch.com/marketwatch/topstories/",
        "marketwatch_realtime": "http://feeds.marketwatch.com/marketwatch/realtimeheadlines/",
        "seeking_alpha": "https://seekingalpha.com/feed.xml",
        "financial_times": "https://www.ft.com/world?format=rss",
        "wsj_markets": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",

        # Forex
        "forex_live": "https://www.forexlive.com/feed/news",

        # Multi-Asset
        "investing_forex": "https://www.investing.com/rss/news_25.rss",
        "investing_stocks": "https://www.investing.com/rss/news_1.rss",

        # Analysis
        "benzinga": "https://www.benzinga.com/feed",
        "tradingview": "https://www.tradingview.com/feed/",
        "motley_fool": "https://www.fool.com/feeds/index.aspx",
    }

    CATEGORIES = {
        "stocks": ["yahoo_finance", "cnbc_top", "marketwatch_top", "seeking_alpha",
                  "wsj_markets", "investing_stocks", "motley_fool"],
        "forex": ["forex_live", "investing_forex", "cnbc_world"],
        "realtime": ["cnbc_top", "marketwatch_realtime", "yahoo_finance", "forex_live"],
        "analysis": ["seeking_alpha", "tradingview", "benzinga", "motley_fool"],
        "breaking": ["cnbc_top", "marketwatch_realtime", "yahoo_finance"],
        "all": list(FEEDS.keys())
    }

    def __init__(self, default_limit: int = 10):
        """
        Initialize RSS client

        Args:
            default_limit: Default number of articles to return per feed
        """
        self.default_limit = default_limit
        self._cache = {}
        self._cache_time = {}
        self._cache_ttl = 300  # 5 minutes cache

    def get_feed(self, feed_name: str, limit: Optional[int] = None) -> List[Dict]:
        """
        Get articles from a specific feed

        Args:
            feed_name: Name of the feed (e.g., 'yahoo_finance', 'cnbc_top')
            limit: Number of articles to return

        Returns:
            List of article dictionaries
        """
        if feed_name not in self.FEEDS:
            raise ValueError(f"Unknown feed: {feed_name}. Available: {list(self.FEEDS.keys())}")

        url = self.FEEDS[feed_name]
        limit = limit or self.default_limit

        # Check cache
        if feed_name in self._cache:
            age = time.time() - self._cache_time.get(feed_name, 0)
            if age < self._cache_ttl:
                return self._cache[feed_name][:limit]

        # Fetch feed
        feed = feedparser.parse(url)

        articles = []
        for entry in feed.entries[:limit]:
            article = {
                "title": entry.get("title", "No title"),
                "link": entry.get("link", ""),
                "published": entry.get("published", entry.get("updated", "No date")),
                "summary": entry.get("summary", entry.get("description", "No summary")),
                "source": feed_name,
                "feed_title": feed.feed.get("title", feed_name)
            }
            articles.append(article)

        # Update cache
        self._cache[feed_name] = articles
        self._cache_time[feed_name] = time.time()

        return articles

    def get_category(self, category: str, limit: Optional[int] = None) -> List[Dict]:
        """
        Get articles from all feeds in a category

        Args:
            category: Category name (stocks, forex, realtime, analysis, breaking, all)
            limit: Number of articles per feed

        Returns:
            List of articles from all feeds in category
        """
        if category not in self.CATEGORIES:
            raise ValueError(f"Unknown category: {category}. Available: {list(self.CATEGORIES.keys())}")

        all_articles = []
        for feed_name in self.CATEGORIES[category]:
            try:
                articles = self.get_feed(feed_name, limit)
                all_articles.extend(articles)
            except Exception as e:
                print(f"Warning: Failed to fetch {feed_name}: {e}")

        return all_articles

    def get_all(self, limit: Optional[int] = None) -> List[Dict]:
        """Get articles from ALL feeds"""
        return self.get_category("all", limit)

    def search(self, keyword: str, feeds: Optional[List[str]] = None,
              limit: Optional[int] = None) -> List[Dict]:
        """
        Search for keyword across feeds

        Args:
            keyword: Keyword to search (case-insensitive)
            feeds: List of feed names to search (default: all)
            limit: Articles per feed

        Returns:
            List of matching articles
        """
        feeds = feeds or list(self.FEEDS.keys())
        keyword = keyword.lower()

        matching = []
        for feed_name in feeds:
            try:
                articles = self.get_feed(feed_name, limit or 100)
                for article in articles:
                    # Search in title and summary
                    if (keyword in article["title"].lower() or
                        keyword in article["summary"].lower()):
                        matching.append(article)
            except Exception as e:
                print(f"Warning: Failed to search {feed_name}: {e}")

        return matching

    def get_latest(self, count: int = 20, category: str = "all") -> List[Dict]:
        """
        Get latest articles across all feeds in category

        Args:
            count: Total number of articles to return
            category: Category to fetch from

        Returns:
            Latest articles sorted by published date
        """
        articles = self.get_category(category, limit=50)

        # Parse dates and sort
        for article in articles:
            try:
                # Try to parse the date
                date_str = article["published"]
                # Common date formats in RSS
                for fmt in ["%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%S%z",
                           "%Y-%m-%dT%H:%M:%SZ"]:
                    try:
                        article["_parsed_date"] = datetime.strptime(date_str.split('+')[0].strip(), fmt)
                        break
                    except:
                        continue
            except:
                article["_parsed_date"] = datetime.min

        # Sort by date
        articles.sort(key=lambda x: x.get("_parsed_date", datetime.min), reverse=True)

        return articles[:count]

    def monitor(self, keywords: List[str], feeds: Optional[List[str]] = None,
               limit: Optional[int] = None) -> Dict[str, List[Dict]]:
        """
        Monitor multiple keywords across feeds

        Args:
            keywords: List of keywords to monitor
            feeds: Feeds to monitor (default: all)
            limit: Articles per feed

        Returns:
            Dict mapping keywords to matching articles
        """
        results = {keyword: [] for keyword in keywords}

        for keyword in keywords:
            results[keyword] = self.search(keyword, feeds, limit)

        return results

    def get_feed_info(self) -> Dict:
        """Get information about all available feeds"""
        info = {
            "total_feeds": len(self.FEEDS),
            "categories": {
                cat: len(feeds) for cat, feeds in self.CATEGORIES.items()
            },
            "feeds": {}
        }

        for name, url in self.FEEDS.items():
            # Determine categories
            cats = [cat for cat, feeds in self.CATEGORIES.items() if name in feeds]
            info["feeds"][name] = {
                "url": url,
                "categories": cats
            }

        return info

    def clear_cache(self):
        """Clear the article cache"""
        self._cache.clear()
        self._cache_time.clear()


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    # Initialize client
    client = RSSClient(default_limit=5)

    print("="*80)
    print("RSS CLIENT - EXAMPLE USAGE")
    print("="*80)

    # Example 1: Get articles from specific feed
    print("\n[1] Get Yahoo Finance articles")
    articles = client.get_feed("yahoo_finance", limit=3)
    print(f"Found {len(articles)} articles")
    if articles:
        print(f"Latest: {articles[0]['title']}")

    # Example 2: Get all stock market news
    print("\n[2] Get all stock market news")
    articles = client.get_category("stocks", limit=2)
    print(f"Found {len(articles)} articles from stock feeds")

    # Example 3: Get forex news
    print("\n[3] Get forex news")
    articles = client.get_category("forex", limit=3)
    print(f"Found {len(articles)} articles from forex feeds")

    # Example 4: Search for specific ticker
    print("\n[4] Search for 'AAPL'")
    articles = client.search("AAPL", limit=5)
    print(f"Found {len(articles)} articles mentioning AAPL")
    if articles:
        print(f"Match: {articles[0]['title'][:60]}...")

    # Example 5: Get latest articles across all feeds
    print("\n[5] Get 10 latest articles")
    articles = client.get_latest(count=10, category="realtime")
    print(f"Found {len(articles)} latest articles")
    if articles:
        print(f"Most recent: {articles[0]['title'][:60]}...")

    # Example 6: Monitor multiple keywords
    print("\n[6] Monitor keywords: ['Fed', 'earnings', 'EUR']")
    results = client.monitor(["Fed", "earnings", "EUR"], limit=5)
    for keyword, articles in results.items():
        print(f"  {keyword}: {len(articles)} articles")

    # Example 7: Get feed info
    print("\n[7] Available feeds")
    info = client.get_feed_info()
    print(f"Total feeds: {info['total_feeds']}")
    print(f"Categories: {list(info['categories'].keys())}")

    print("\n" + "="*80)
    print("CLIENT READY FOR USE!")
    print("="*80)
    print("\nAvailable feeds:")
    for name in sorted(client.FEEDS.keys()):
        print(f"  - {name}")

    print("\nAvailable categories:")
    for cat in sorted(client.CATEGORIES.keys()):
        if cat != "all":
            print(f"  - {cat}: {len(client.CATEGORIES[cat])} feeds")
