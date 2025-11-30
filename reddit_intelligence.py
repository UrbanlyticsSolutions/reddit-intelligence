#!/usr/bin/env python3
"""
Reddit Stock Intelligence Collection Workflow + DeepSeek AI Analysis
=====================================================================

Production-ready workflow to collect and analyze Reddit data for:
1. Stock market movements and trends
2. Political news and policy changes affecting markets
3. Credible analysis and expert insights
4. AI-powered analysis and reporting using DeepSeek

Features:
- Multi-source data collection from Reddit
- Credibility scoring system (0-10 scale)
- Ranked insights with composite scoring
- Market relevance assessment
- Comprehensive summary generation
- DeepSeek AI analysis for market insights, symbol-specific reports, and risk assessment

Usage Examples:
```python
# Standard workflow (Reddit data only)
result = run_reddit_intelligence_sync(['GME', 'TSLA'], 'week')

# Full workflow with DeepSeek AI analysis
result = run_reddit_intelligence_with_deepseek_sync(['GME', 'TSLA'], 'week', include_deepseek_analysis=True)

# Access DeepSeek reports
market_report = result.get('deepseek_market_analysis', '')
symbol_analysis = result.get('deepseek_symbol_analyses', {})
risk_assessment = result.get('deepseek_risk_assessment', '')
```
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
import sys
import json
import asyncio
import requests
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from openai import AsyncOpenAI

# Add clients directory to path
sys.path.insert(0, 'clients')
from fmp_stable_client import FMPStableClient
from fred_client import FREDClient

# Configure environment variables (loaded from .env file automatically)
os.environ.setdefault('REDDIT_DB_PATH', 'news/reddit_index.db')

# Get API keys from environment (loaded from .env file)
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
DEEPSEEK_API_BASE = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_REASONER_MODEL = "deepseek-reasoner"

# FMP API Configuration
FMP_API_KEY = os.environ.get('FMP_API_KEY')
FRED_API_KEY = os.environ.get('FRED_API_KEY')

# Optional Google Cloud Storage configuration for output publishing
GCS_BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME')
GCS_DEST_PREFIX = os.environ.get('GCS_DEST_PREFIX', '').strip('/')
ENABLE_GCS_UPLOADS = os.environ.get('ENABLE_GCS_UPLOADS', 'false').lower() in ('1', 'true', 'yes')

# =============================================================================
# MEME STOCK FILTERING
# =============================================================================

# Meme stocks to exclude from analysis
MEME_STOCKS = {
    'GME', 'AMC', 'BB', 'NOK', 'BBBY', 'CLOV', 'WISH',
    'PLTR', 'SPCE', 'TLRY', 'SNDL', 'MVIS', 'WKHS',
    'EXPR', 'KOSS', 'NAKD', 'RKT', 'SKLZ', 'SOFI'
}

# Meme-focused subreddits to exclude
MEME_SUBREDDITS = {
    'wallstreetbets', 'superstonk', 'gme', 'amcstock',
    'gme_meltdown', 'shortsqueeze', 'squeezeplays',
    'wallstreetbetsnew', 'wallstreetbetselite'
}

def is_meme_content(post: Dict) -> bool:
    """
    Check if a post is meme stock related
    
    Args:
        post: Post data dictionary
        
    Returns:
        True if post is meme-related, False otherwise
    """
    # Check subreddit
    subreddit = post.get('subreddit', '').lower()
    if subreddit in MEME_SUBREDDITS:
        return True
    
    # Check title for meme stock symbols
    title = post.get('title', '').upper()
    content = post.get('content', '').upper()
    
    # Check if any meme stock symbol appears in title or content
    for symbol in MEME_STOCKS:
        # Use word boundaries to avoid false positives (e.g., "GAME" containing "AME")
        if f' {symbol} ' in f' {title} ' or f'${symbol}' in title:
            return True
        if f' {symbol} ' in f' {content} ' or f'${symbol}' in content:
            return True
    
    return False


# =============================================================================
# RSS FEED READER
# =============================================================================

import feedparser
import requests
from urllib.parse import urlparse

def fetch_rss_feed(url: str, timeout: int = 10) -> List[Dict]:
    """
    Fetch and parse RSS feed

    Args:
        url: RSS feed URL
        timeout: Request timeout in seconds

    Returns:
        List of parsed feed items
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()

        feed = feedparser.parse(response.content)

        items = []
        for entry in feed.entries:
            # Calculate time since publication
            published_timestamp = 0
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published_timestamp = time.mktime(entry.published_parsed)
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                published_timestamp = time.mktime(entry.updated_parsed)

            items.append({
                'title': entry.get('title', ''),
                'link': entry.get('link', ''),
                'summary': entry.get('summary', entry.get('description', '')),
                'published': entry.get('published', ''),
                'published_timestamp': published_timestamp,
                'author': entry.get('author', ''),
                'tags': [tag.get('term', '') for tag in entry.get('tags', [])]
            })

        return items

    except Exception as e:
        print(f"    Error fetching {url}: {str(e)[:100]}")
        return []

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def calculate_post_credibility(post_data: Dict, all_posts: List[Dict] = None) -> float:
    """
    Calculate dynamic credibility score for a Reddit post (0-10 scale)

    Credibility is determined by:
    - Engagement quality (upvotes/comments ratio)
    - Post age (newer posts score slightly higher)
    - Content quality indicators
    - Author reputation (if available)
    - Source diversity

    Args:
        post_data: Reddit post data dictionary
        all_posts: All collected posts for context (optional)

    Returns:
        Credibility score (0-10)
    """
    # Base metrics from post
    score = post_data.get('score', 0)
    num_comments = post_data.get('num_comments', 0)
    upvote_ratio = post_data.get('upvote_ratio', 0.5)
    created_utc = post_data.get('created_utc', 0)
    subreddit = post_data.get('subreddit', '').lower()

    # 1. Engagement Quality Score (40% weight)
    # Balanced upvotes and comments indicate quality discussion
    engagement_quality = 0
    if score > 0 and num_comments > 0:
        # Good ratio: comments should be 5-20% of upvotes for quality
        comment_ratio = num_comments / max(score, 1)
        if 0.05 <= comment_ratio <= 0.5:
            engagement_quality = 10
        elif 0.01 <= comment_ratio <= 1.0:
            engagement_quality = 7
        else:
            engagement_quality = 4
    elif score > 0:
        # Upvotes only but high engagement
        engagement_quality = min(score / 50, 8)

    # 2. Upvote Quality Score (25% weight)
    # High upvote ratio indicates community agreement
    upvote_quality = upvote_ratio * 10

    # 3. Recency Score (15% weight)
    # Recent posts get slight bonus (up to 1.5 points)
    if created_utc:
        import time
        current_time = time.time()
        age_hours = (current_time - created_utc) / 3600
        if age_hours < 24:
            recency_score = 1.5
        elif age_hours < 168:  # 1 week
            recency_score = 1.0
        elif age_hours < 720:  # 1 month
            recency_score = 0.5
        else:
            recency_score = 0
    else:
        recency_score = 0

    # 4. Content Depth Score (20% weight)
    # Based on title length and detail (indicates effort)
    title = post_data.get('title', '')
    title_length = len(title)
    if title_length > 100:
        content_depth = 10
    elif title_length > 50:
        content_depth = 8
    elif title_length > 20:
        content_depth = 6
    else:
        content_depth = 3

    # Bonus for flairs (often indicates effort/topic relevance)
    flair = post_data.get('link_flair_text', '')
    flair_bonus = 1 if flair else 0

    # Calculate weighted total
    total = (
        engagement_quality * 0.40 +
        upvote_quality * 0.25 +
        recency_score * 0.15 +
        content_depth * 0.15 +
        flair_bonus * 0.05
    )

    return min(max(total, 0), 10.0)

def assess_market_relevance(content: str) -> float:
    """
    Assess how relevant content is to markets (0-1 scale)

    Args:
        content: Text content to analyze

    Returns:
        Market relevance score (0-1)
    """
    market_keywords = {
        'primary': ['market', 'stock', 'stocks', 'economy', 'financial', 'investment'],
        'secondary': ['trading', 'price', 'volatility', 'inflation', 'fed', 'sec', 'regulation', 'fed rate'],
        'tertiary': ['earnings', 'revenue', 'profit', 'loss', 'bull', 'bear', 'rally', 'crash']
    }

    content_lower = content.lower()

    primary_hits = sum(3 for keyword in market_keywords['primary']
                      if keyword in content_lower)
    secondary_hits = sum(2 for keyword in market_keywords['secondary']
                        if keyword in content_lower)
    tertiary_hits = sum(1 for keyword in market_keywords['tertiary']
                       if keyword in content_lower)

    total_weighted_hits = primary_hits + secondary_hits + tertiary_hits

    return min(total_weighted_hits / 15, 1.0)

def classify_analysis_type(content: str) -> str:
    """
    Classify the type of analysis in the content

    Args:
        content: Text content to classify

    Returns:
        Analysis type string
    """
    content_lower = content.lower()

    technical_terms = ['technical', 'chart', 'rsi', 'macd', 'moving average',
                      'support', 'resistance', 'trend', 'indicators']
    fundamental_terms = ['fundamental', 'valuation', 'pe ratio', 'revenue',
                        'earnings', 'debt', 'cash flow', 'balance sheet']
    options_terms = ['options', 'calls', 'puts', 'theta', 'gamma', 'delta', 'vega']

    if any(term in content_lower for term in technical_terms):
        return 'technical_analysis'
    elif any(term in content_lower for term in fundamental_terms):
        return 'fundamental_analysis'
    elif any(term in content_lower for term in options_terms):
        return 'options_analysis'
    else:
        return 'general_analysis'

def get_top_mentioned_symbols(all_data: List[Dict]) -> List[Dict]:
    """
    Get most mentioned stock symbols

    Args:
        all_data: List of collected data

    Returns:
        List of (symbol, count) tuples
    """
    symbol_counts = {}

    for item in all_data:
        symbol = item.get('symbol', '')
        if symbol:
            symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1

    return sorted(symbol_counts.items(), key=lambda x: x[1], reverse=True)[:5]


def upload_outputs_to_gcs(result: Dict[str, Any], timestamp: str, local_files: Dict[str, Path], output_dir: Path) -> bool:
    """
    Upload generated output artifacts to Google Cloud Storage, including a latest summary JSON.

    Args:
        result: Workflow result dictionary containing DeepSeek analyses.
        timestamp: Timestamp string used for this workflow run.
        local_files: Mapping label -> Path for generated local artifacts.
        output_dir: Directory where artifacts are stored locally.
    """
    if not ENABLE_GCS_UPLOADS:
        print("[SKIP] ENABLE_GCS_UPLOADS is false; running fully local.")
        return False

    if not GCS_BUCKET_NAME:
        return False

    try:
        from google.cloud import storage
    except ImportError:
        print("[WARN] google-cloud-storage not installed; skipping GCS upload.")
        return False

    try:
        client = storage.Client()
        bucket = client.bucket(GCS_BUCKET_NAME)
    except Exception as exc:
        print(f"[WARN] Failed to initialize GCS client: {exc}")
        return False

    prefix = GCS_DEST_PREFIX + '/' if GCS_DEST_PREFIX else ''
    uploaded = False

    def _upload(path: Path, content_type: str) -> None:
        nonlocal uploaded
        blob_name = prefix + path.name
        blob = bucket.blob(blob_name)
        blob.cache_control = 'no-cache'
        try:
            blob.upload_from_filename(str(path), content_type=content_type)
            uploaded = True
        except Exception as upload_exc:
            print(f"[WARN] Failed to upload {path.name} to GCS: {upload_exc}")

    for path in local_files.values():
        if not path or not path.exists():
            continue
        suffix = path.suffix.lower()
        if suffix == '.json':
            content_type = 'application/json'
        else:
            content_type = 'text/plain'
        _upload(path, content_type)

    if result.get('deepseek_market_analysis') or result.get('deepseek_symbol_analyses') or result.get('deepseek_risk_assessment'):
        print(f"[DEBUG] Found DeepSeek analysis keys: {list(result.keys())}")
        print(f"[DEBUG] Market Analysis length: {len(result.get('deepseek_market_analysis', ''))}")
        latest_payload = {
            'timestamp': timestamp,
            'generated_at': datetime.utcnow().isoformat() + 'Z',
            'summary': result.get('summary', ''),
            'top_insights': result.get('top_insights', []),
            'deepseek_market_analysis': result.get('deepseek_market_analysis', ''),
            'deepseek_symbol_analyses': result.get('deepseek_symbol_analyses', {}),
            'deepseek_risk_assessment': result.get('deepseek_risk_assessment', '')
        }

        latest_path = output_dir / 'latest_deepseek_result.json'
        try:
            with open(latest_path, 'w', encoding='utf-8') as latest_file:
                json.dump(latest_payload, latest_file, indent=2, ensure_ascii=False)
        except Exception as write_exc:
            print(f"[WARN] Failed to write latest summary file: {write_exc}")
        else:
            _upload(latest_path, 'application/json')

    return uploaded


def build_insights_from_posts(posts: List[Dict], limit: int = 20) -> List[Dict]:
    """Convert collected posts or articles into a normalized insight list."""

    insights: List[Dict[str, Any]] = []
    for item in posts[:limit]:
        content = item.get('content') or item.get('summary') or ''
        if content and len(content) > 500:
            content = content[:500] + '...'

        created_ts = item.get('created_utc') or item.get('published_timestamp')
        created_time = ''
        if created_ts:
            try:
                created_time = datetime.fromtimestamp(float(created_ts)).strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                created_time = ''

        insights.append({
            'title': item.get('title', ''),
            'content': content,
            'type': item.get('type') or item.get('category', ''),
            'source': item.get('source') or item.get('subreddit', ''),
            'credibility_score': item.get('credibility_score', item.get('ai_relevance_score', 0)),
            'composite_score': item.get('composite_score', item.get('ai_relevance_score', 0)),
            'url': item.get('url') or item.get('link', ''),
            'created_time': created_time,
            'symbol': item.get('symbol', ''),
            'keyword': item.get('keyword', ''),
        })

    return insights

# =============================================================================
# DEEPSEEK ANALYSIS FUNCTIONS
# =============================================================================

def call_deepseek_api(prompt: str, max_tokens: int = 2000, model: str = None) -> str:
    """
    Call DeepSeek API for analysis

    Args:
        prompt: The prompt to send to DeepSeek
        max_tokens: Maximum tokens in response
        model: Model to use (default: deepseek-chat)

    Returns:
        DeepSeek's response text
    """
    if model is None:
        model = DEEPSEEK_MODEL

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are an expert financial analyst analyzing Reddit sentiment and market intelligence. Note that Reddit users are primarily retail traders, so sentiment may reflect retail behavior rather than institutional moves. Provide detailed, actionable insights."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": 0.3
    }

    try:
        response = requests.post(f"{DEEPSEEK_API_BASE}/chat/completions",
                               headers=headers,
                               json=data,
                               timeout=60)

        if response.status_code == 200:
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]
        elif response.status_code == 401:
            return "Error: Invalid DeepSeek API key. Please check your API credentials."
        else:
            return f"API Error: HTTP {response.status_code} - {response.text}"
    except Exception as e:
        return f"Error calling DeepSeek API: {str(e)}"

def generate_market_analysis_report(market_data: List[Dict], political_data: List[Dict], macro_data: Dict = None, rss_data: List[Dict] = None, data_check_msg: str = "") -> str:
    """
    Generate a broad market analysis report using DeepSeek
    """
    if macro_data is None:
        macro_data = {}
    if rss_data is None:
        rss_data = []

    # 1. Calculate Date Range
    all_items = market_data + political_data + rss_data
    timestamps = [item.get('created_utc', 0) for item in all_items if item.get('created_utc')]
    
    if timestamps:
        min_ts = datetime.fromtimestamp(min(timestamps))
        max_ts = datetime.fromtimestamp(max(timestamps))
        date_range_str = f"{min_ts.strftime('%b %d, %Y')} - {max_ts.strftime('%b %d, %Y')}"
    else:
        date_range_str = datetime.now().strftime('%b %d, %Y')

    # 2. Split Market Data (WSB vs Others)
    wsb_data = [item for item in market_data if item.get('source', '').lower() == 'wallstreetbets']
    other_market_data = [item for item in market_data if item.get('source', '').lower() != 'wallstreetbets']

    # 3. Prepare High-Credibility Insights
    
    # Helper to format list
    def format_list(items, limit=10):
        return chr(10).join([f"- {item.get('title', '')} (Source: {item.get('source', 'Unknown')}, Score: {item.get('score', 0)})" for item in items[:limit]])

    def format_rss(items, limit=10):
        return chr(10).join([f"- {item.get('title', '')} (Source: {item.get('source', 'RSS')})" for item in items[:limit]])

    def format_fmp_news(items, limit=10):
        return chr(10).join([f"- {item.get('title', '')} (Source: {item.get('site', 'FMP')})" for item in items[:limit]])

    fmp_news = macro_data.get('fmp', {}).get('general_news', [])

    # 4. Construct Prompt
    prompt = f"""
    You are a senior Wall Street market strategist. Provide a **REVIEW OF CURRENT MARKET CONDITIONS** based on the following recent data.
    
    **CRITICAL INSTRUCTION**: Focus on what the user needs to pay attention to RIGHT NOW. Highlight risks, anomalies, and urgent developments. Be forward-looking.

    REPORT METADATA:
    - Date Range: {date_range_str}
    - Data Sources: Reddit (Sentiment), RSS Feeds (News), FMP (Financials & News), FRED (Macro), Gold (Commodities)

    {data_check_msg}

    SECTION 1: RETAIL SENTIMENT & SPECULATION (r/wallstreetbets)
    Use this ONLY for gauging retail sentiment, risk appetite, and contrarian indicators. DO NOT use as fundamental analysis.
    {format_list(wsb_data, 10)}

    SECTION 2: MARKET DISCUSSION & NEWS (Reddit, RSS, FMP)
    Use this for identifying key market trends, political impacts, and serious discussions.
    
    REDDIT (r/stocks, r/investing, r/Economics, r/politics):
    {format_list(other_market_data, 10)}
    {format_list(political_data, 10)}

    RSS FINANCIAL NEWS:
    {format_rss(rss_data, 10)}

    FMP MARKET NEWS:
    {format_fmp_news(fmp_news, 10)}

    SECTION 3: MACROECONOMIC & FINANCIAL DATA (FMP, FRED)
    Use this for fundamental context.
    - Gold Price: {macro_data.get('gold', {}).get('price', 'N/A')}
    - Market Risk Premium (US): {macro_data.get('fmp', {}).get('market_risk_premium', {}).get('totalEquityRiskPremium', 'N/A')}%
    - Inflation (CPI): {macro_data.get('fred', {}).get('inflation_cpi', {}).get('value', 'N/A')}
    - Fed Funds Rate: {macro_data.get('fred', {}).get('fed_funds', {}).get('value', 'N/A')}%
    - 10Y Treasury Yield: {macro_data.get('fred', {}).get('10y_treasury', {}).get('value', 'N/A')}%
    - VIX: {macro_data.get('fred', {}).get('vix', {}).get('value', 'N/A')}%

    Please provide a detailed analysis report.

    STRUCTURE:
    1. **Executive Summary**: High-level review of the CURRENT market condition. What is the dominant theme?
    2. **CRITICAL ALERTS**: What does the user need to pay attention to IMMEDIATELY? (e.g., sudden volatility, breaking news, extreme sentiment).
    3. **Retail Sentiment Analysis**: Specific analysis of WSB activity (Greed/Fear/Speculation).
    4. **Fundamental & Macro Outlook**: Analysis based on FRED/FMP data and serious market news.
    5. **Forward-Looking Outlook**: Based on recent data, what is likely to happen next? (Short-term prediction).
    
    FOOTER REQUIREMENTS:
    - Explicitly state the Data Date Range: {date_range_str}
    - Explicitly list ALL Data Sources: Reddit (r/wallstreetbets for Sentiment, r/stocks, r/investing, r/politics, r/Economics), RSS Feeds (Financial News), FMP (Gold, Risk Premium, News), FRED (Macro Data).
    """

    return call_deepseek_api(prompt, max_tokens=3000)

def generate_symbol_specific_analysis(symbol: str, symbol_data: List[Dict], data_check_msg: str = "") -> str:
    """
    Generate analysis for a specific stock symbol
    """
    if not symbol_data:
        return f"No significant data found for {symbol}"

    # Sort by credibility
    symbol_data.sort(key=lambda x: x.get('credibility_score', 0), reverse=True)
    top_data = symbol_data[:10]

    data_summary = []
    for i, item in enumerate(top_data, 1):
        content_snippet = item.get('content', '')[:250] + '...' if len(item.get('content', '')) > 250 else item.get('content', '')
        data_summary.append(
            f"{i}. {item.get('title', '')}\n"
            f"   Source: r/{item.get('source', '')} | Credibility: {item.get('credibility_score', 0):.2f}\n"
            f"   Content: {content_snippet}\n"
            f"   Engagement: {item.get('score', 0)} upvotes, {item.get('comments', 0)} comments"
        )

    prompt = f"""
    You are a specialized equity analyst covering {symbol}. Analyze the following Reddit discussions.
    
    {data_check_msg}

    DISCUSSIONS ON {symbol}:
    {chr(10).join([f"- {item['title']} (Score: {item['score']}) - {item['content'][:200]}..." for item in symbol_data[:15]])}

    SYMBOL: {symbol}
    TOTAL MENTIONS: {len(symbol_data)}

    TOP REDDIT INSIGHTS:
    {chr(10).join(data_summary)}

    Please provide:
    1. Current Sentiment Analysis (Bullish/Bearish/Neutral)
    2. Key Discussion Themes and Concerns
    3. Credibility Assessment of Sources
    4. Technical vs Fundamental Focus
    5. Risk Factors and Catalysts
    6. Short-term Outlook (1-2 weeks)
    7. Medium-term Considerations (1-3 months)

    Provide specific, actionable insights for {symbol} with confidence levels.
    """

    return call_deepseek_api(prompt, max_tokens=2500)

def generate_risk_assessment(all_data: List[Dict], data_check_msg: str = "") -> str:
    """
    Generate a risk assessment report
    """
    # Filter for risk-related content
    risk_keywords = ['risk', 'concern', 'warning', 'crash', 'bubble', 'overvalued',
                    'downside', 'bearish', 'short', 'margin', 'debt', 'regulation']

    risk_content = []
    for item in all_data:
        content_lower = (item.get('title', '') + ' ' + item.get('content', '')).lower()
        if any(keyword in content_lower for keyword in risk_keywords):
            risk_content.append(item)

    risk_content.sort(key=lambda x: x.get('credibility_score', 0), reverse=True)
    top_risks = risk_content[:12]

    risk_summary = []
    for i, item in enumerate(top_risks, 1):
        content_snippet = item.get('content', '')[:200] + '...' if len(item.get('content', '')) > 200 else item.get('content', '')


        risk_summary.append(
            f"{i}. {item.get('title', '')}\n"
            f"   Source: r/{item.get('source', '')} | Credibility: {item.get('credibility_score', 0):.2f}\n"
            f"   Content: {content_snippet}"
        )

    prompt = f"""
    You are a Chief Risk Officer. Analyze the following social sentiment data for potential market risks.
    
    {data_check_msg}

    RECENT DISCUSSIONS:
    {chr(10).join([f"- {item['title']} (Score: {item['score']})" for item in all_data[:20]])}

    Based on Reddit intelligence analysis, provide a comprehensive market risk assessment:

    RISK-RELATED POSTS ANALYZED: {len(risk_content)}

    TOP RISK INDICATORS:
    {chr(10).join(risk_summary)}

    Please analyze and report on:
    1. Systemic Market Risks
    2. Sector-Specific Concerns
    3. Regulatory/Political Risks
    4. Sentiment-Driven Risks
    5. Liquidity and Volatility Risks
    6. Credibility-Weighted Risk Level (High/Medium/Low)
    7. Risk Mitigation Strategies
    8. Early Warning Indicators to Monitor

    Provide specific risk factors with probability assessments and potential impact levels.
    """

    return call_deepseek_api(prompt, max_tokens=2800)

def generate_keyword_analysis(keyword: str, keyword_data: List[Dict], data_check_msg: str = "") -> str:
    """
    Generate analysis for a specific keyword
    """
    if not keyword_data:
        return f"No significant data found for keyword: {keyword}"

    # Sort by credibility
    keyword_data.sort(key=lambda x: x.get('credibility_score', 0), reverse=True)
    top_data = keyword_data[:10]

    data_summary = []
    for i, item in enumerate(top_data, 1):
        content_snippet = item.get('content', '')[:250] + '...' if len(item.get('content', '')) > 250 else item.get('content', '')
        data_summary.append(
            f"{i}. {item.get('title', '')}\n"
            f"   Source: r/{item.get('source', '')} | Credibility: {item.get('credibility_score', 0):.2f}\n"
            f"   Content: {content_snippet}\n"
            f"   Engagement: {item.get('score', 0)} upvotes, {item.get('comments', 0)} comments"
        )

    prompt = f"""
    Analyze Reddit sentiment and intelligence specifically for the keyword "{keyword}" based on the following data:

    KEYWORD: {keyword}
    TOTAL MENTIONS: {len(keyword_data)}

    TOP REDDIT INSIGHTS:
    {chr(10).join(data_summary)}

    Please provide:
    1. Current Sentiment Analysis (Bullish/Bearish/Neutral)
    2. Key Discussion Themes and Trends
    3. Credibility Assessment of Sources
    4. Market Drivers and Catalysts
    5. Risk Factors and Concerns
    6. Short-term Outlook (1-2 weeks)
    7. Medium-term Considerations (1-3 months)
    8. Actionable Insights for Traders/Investors

    Provide specific, actionable insights for {keyword} with confidence levels.
    """

    return call_deepseek_api(prompt, max_tokens=2500)

# =============================================================================
# WORKFLOW CLASS
# =============================================================================

class RedditIntelligenceWorkflow:
    """
    Main workflow for collecting Reddit stock intelligence

    Collects and analyzes Reddit posts about stock movements, political news,
    and credible analysis with scoring and ranking.
    """

    def __init__(self):
        from clients.reddit_client import create_reddit_client_from_env
        self.reddit = create_reddit_client_from_env(rate_limit_delay=1.0)

    async def collect_market_movement_data(self, stocks: List[str], time_horizon: str, max_results: int = 50) -> Dict:
        """
        Collect Reddit posts about stock market movements
        
        Args:
            stocks: List of stock symbols
            time_horizon: Time period ('day', 'week', 'month', 'year', 'all')
            max_results: Maximum results to collect
            
        Returns:
            Dictionary with market movement posts and data check result
        """
        trending_subreddits = ['wallstreetbets', 'stocks', 'Superstonk', 'investing', 'ValueInvesting']
        
        async def fetch_data(horizon):
            data = []
            for symbol in stocks:
                for subreddit in trending_subreddits:
                    try:
                        posts = self.reddit.search_posts(
                            query=f"{symbol}",
                            subreddit=subreddit,
                            sort='hot',
                            time_filter=horizon,
                            limit=max_results // len(trending_subreddits)
                        )
                        
                        for post in posts:
                            post_data = post.get('data', {})
                            credibility = calculate_post_credibility(post_data)
                            
                            data.append({
                                'type': 'market_movement',
                                'symbol': symbol,
                                'source': subreddit,
                                'title': post_data.get('title', ''),
                                'content': self.reddit.extract_post_text(post),
                                'score': post_data.get('score', 0),
                                'comments': post_data.get('num_comments', 0),
                                'created_utc': post_data.get('created_utc'),
                                'author': post_data.get('author', ''),
                                'url': f"https://reddit.com{post_data.get('permalink', '')}",
                                'flair': post_data.get('link_flair_text', ''),
                                'upvote_ratio': post_data.get('upvote_ratio', 0),
                                'credibility_score': credibility
                            })
                        await asyncio.sleep(0.5)
                    except Exception:
                        pass
            
            # Filter out meme stocks
            return [post for post in data if not is_meme_content(post)]

        print(f"[COLLECT] Fetching market movement data (horizon: {time_horizon})...")
        market_data = await fetch_data(time_horizon)
        data_check_msg = ""
        
        if time_horizon == 'day':
            cutoff_time = time.time() - (24 * 3600)
            fresh_posts = [p for p in market_data if p.get('created_utc', 0) >= cutoff_time]
            
            if len(fresh_posts) < 10:
                print(f"[FALLBACK] Only {len(fresh_posts)} posts in last 24h. Extending search to week...")
                week_data = await fetch_data('week')
                week_data.sort(key=lambda x: x.get('created_utc', 0), reverse=True)
                market_data = week_data[:10]
                data_check_msg = f"DATA CHECK: WARNING. Only found {len(fresh_posts)} posts in last 24h. Included top 10 most recent posts from last week."
            else:
                market_data = fresh_posts
                data_check_msg = f"DATA CHECK: PASSED. Found {len(market_data)} posts in last 24 hours."
        
        return {'data': market_data, 'data_check_result': data_check_msg}

    async def collect_political_news_data(self, keywords: List[str], time_horizon: str, max_results: int = 30) -> Dict:
        """
        Collect political and policy news affecting markets

        Args:
            keywords: List of keywords to search
            time_horizon: Time period
            max_results: Maximum results

        Returns:
            Dictionary with political news posts and data check result
        """
        credible_subreddits = ['politics', 'Economics', 'geopolitics', 'worldnews', 'business']

        async def fetch_data(horizon):
            data = []
            for keyword in keywords:
                for subreddit in credible_subreddits:
                    try:
                        posts = self.reddit.search_posts(
                            query=keyword,
                            subreddit=subreddit,
                            sort='top',
                            time_filter=horizon,
                            limit=max_results // len(credible_subreddits)
                        )

                        for post in posts:
                            post_data = post.get('data', {})
                            credibility = calculate_post_credibility(post_data)

                            data.append({
                                'type': 'political_news',
                                'keyword': keyword,
                                'source': subreddit,
                                'title': post_data.get('title', ''),
                                'content': self.reddit.extract_post_text(post),
                                'score': post_data.get('score', 0),
                                'comments': post_data.get('num_comments', 0),
                                'created_utc': post_data.get('created_utc'),
                                'author': post_data.get('author', ''),
                                'url': f"https://reddit.com{post_data.get('permalink', '')}",
                                'credibility_score': credibility
                            })
                        await asyncio.sleep(0.5)
                    except Exception:
                        pass
            return data

        print(f"[COLLECT] Fetching political news data (horizon: {time_horizon})...")
        political_data = await fetch_data(time_horizon)
        data_check_msg = ""

        if time_horizon == 'day':
            cutoff_time = time.time() - (24 * 3600)
            fresh_posts = [p for p in political_data if p.get('created_utc', 0) >= cutoff_time]
            
            if len(fresh_posts) < 10:
                print(f"[FALLBACK] Only {len(fresh_posts)} political posts in last 24h. Extending search to week...")
                week_data = await fetch_data('week')
                week_data.sort(key=lambda x: x.get('created_utc', 0), reverse=True)
                political_data = week_data[:10]
                data_check_msg = f"DATA CHECK: WARNING. Only found {len(fresh_posts)} political posts in last 24h. Included top 10 most recent posts from last week."
            else:
                political_data = fresh_posts
                data_check_msg = f"DATA CHECK: PASSED. Found {len(political_data)} political posts in last 24 hours."
        
        return {'data': political_data, 'data_check_result': data_check_msg}

    async def collect_credible_analysis_data(self, stocks: List[str], time_horizon: str, max_results: int = 30) -> Dict:
        """
        Collect detailed analysis from credible subreddits

        Args:
            stocks: List of stock symbols
            time_horizon: Time period
            max_results: Maximum results

        Returns:
            Dictionary with credible analysis posts and data check result
        """
        credible_subreddits = ['SecurityAnalysis', 'ValueInvesting', 'investing', 'Economics', 'finance', 'StockMarket']

        async def fetch_data(horizon):
            data = []
            for symbol in stocks:
                for subreddit in credible_subreddits:
                    try:
                        posts = self.reddit.search_posts(
                            query=f"{symbol} analysis",
                            subreddit=subreddit,
                            sort='relevance',
                            time_filter=horizon,
                            limit=max_results // len(credible_subreddits)
                        )

                        for post in posts:
                            post_data = post.get('data', {})
                            content = self.reddit.extract_post_text(post)
                            
                            if len(content) < 200:  # Skip short posts
                                continue

                            credibility = calculate_post_credibility(post_data)
                            if credibility < 5.0:  # Filter low credibility
                                continue

                            data.append({
                                'type': 'credible_analysis',
                                'symbol': symbol,
                                'source': subreddit,
                                'title': post_data.get('title', ''),
                                'content': content,
                                'score': post_data.get('score', 0),
                                'comments': post_data.get('num_comments', 0),
                                'created_utc': post_data.get('created_utc'),
                                'author': post_data.get('author', ''),
                                'url': f"https://reddit.com{post_data.get('permalink', '')}",
                                'content_length': len(content),
                                'analysis_type': classify_analysis_type(content),
                                'credibility_score': credibility
                            })

                        await asyncio.sleep(0.5)
                    except Exception:
                        pass
            return data

        print(f"[COLLECT] Fetching credible analysis data (horizon: {time_horizon})...")
        analysis_data = await fetch_data(time_horizon)
        data_check_msg = ""

        if time_horizon == 'day':
            cutoff_time = time.time() - (24 * 3600)
            fresh_posts = [p for p in analysis_data if p.get('created_utc', 0) >= cutoff_time]
            
            if len(fresh_posts) < 10:
                print(f"[FALLBACK] Only {len(fresh_posts)} analysis posts in last 24h. Extending search to week...")
                week_data = await fetch_data('week')
                week_data.sort(key=lambda x: x.get('created_utc', 0), reverse=True)
                analysis_data = week_data[:10]
                data_check_msg = f"DATA CHECK: WARNING. Only found {len(fresh_posts)} analysis posts in last 24h. Included top 10 most recent posts from last week."
            else:
                analysis_data = fresh_posts
                data_check_msg = f"DATA CHECK: PASSED. Found {len(analysis_data)} analysis posts in last 24 hours."
        
        return {'data': analysis_data, 'data_check_result': data_check_msg}

    async def collect_keyword_data(self, keywords: List[str], time_horizon: str, max_results: int = 30) -> Dict:
        """
        Collect Reddit posts for specific keywords

        Args:
            keywords: List of keywords to search
            time_horizon: Time period
            max_results: Maximum results

        Returns:
            Dictionary with keyword posts and data check result
        """
        market_subreddits = [
            'investing', 'stocks', 'SecurityAnalysis', 'ValueInvesting',
            'StockMarket', 'economics', 'business', 'finance',
            'wallstreetbets', 'CryptoCurrency', 'Superstonk',
            'market_news', 'stocks_news', 'economy'
        ]

        async def fetch_data(horizon):
            data = []
            for keyword in keywords:
                for subreddit in market_subreddits:
                    try:
                        posts = self.reddit.search_posts(
                            query=keyword,
                            subreddit=subreddit,
                            sort='relevance',
                            time_filter=horizon,
                            limit=max_results // len(market_subreddits)
                        )

                        for post in posts:
                            post_data = post.get('data', {})
                            credibility = calculate_post_credibility(post_data)

                            data.append({
                                'type': 'keyword_data',
                                'keyword': keyword,
                                'symbol': keyword.upper(), # Assuming keyword might be a symbol
                                'source': subreddit,
                                'title': post_data.get('title', ''),
                                'content': self.reddit.extract_post_text(post),
                                'score': post_data.get('score', 0),
                                'comments': post_data.get('num_comments', 0),
                                'created_utc': post_data.get('created_utc'),
                                'author': post_data.get('author', ''),
                                'url': f"https://reddit.com{post_data.get('permalink', '')}",
                                'credibility_score': credibility
                            })
                        await asyncio.sleep(0.5)
                    except Exception:
                        pass
            return data

        print(f"[COLLECT] Fetching keyword data (horizon: {time_horizon})...")
        keyword_data = await fetch_data(time_horizon)
        data_check_msg = ""

        if time_horizon == 'day':
            cutoff_time = time.time() - (24 * 3600)
            fresh_posts = [p for p in keyword_data if p.get('created_utc', 0) >= cutoff_time]
            
            if len(fresh_posts) < 10:
                print(f"[FALLBACK] Only {len(fresh_posts)} keyword posts in last 24h. Extending search to week...")
                week_data = await fetch_data('week')
                week_data.sort(key=lambda x: x.get('created_utc', 0), reverse=True)
                keyword_data = week_data[:10]
                data_check_msg = f"DATA CHECK: WARNING. Only found {len(fresh_posts)} keyword posts in last 24h. Included top 10 most recent posts from last week."
            else:
                keyword_data = fresh_posts
                data_check_msg = f"DATA CHECK: PASSED. Found {len(keyword_data)} keyword posts in last 24 hours."
        
        return {'data': keyword_data, 'data_check_result': data_check_msg}

    async def generate_intelligence_summary(self, market_data: List[Dict], political_data: List[Dict], analysis_data: List[Dict]) -> Dict:
        """
        Generate comprehensive intelligence summary

        Args:
            market_data: Market movement posts
            political_data: Political news posts
            analysis_data: Credible analysis posts

        Returns:
            Dictionary with summary and insights
        """
        all_data = []
        all_data.extend(market_data)
        all_data.extend(political_data)
        all_data.extend(analysis_data)

        # Calculate composite scores
        for item in all_data:
            credibility = item.get('credibility_score', 0)
            engagement = item.get('score', 0) + (item.get('comments', 0) * 2)
            item['composite_score'] = credibility * 0.7 + min(engagement / 100, 1) * 0.3

        # Sort by composite score
        all_data.sort(key=lambda x: x.get('composite_score', 0), reverse=True)

        # Generate summary
        summary = {
            'total_posts_collected': len(all_data),
            'by_type': {
                'market_movements': len(market_data),
                'political_news': len(political_data),
                'credible_analysis': len(analysis_data)
            },
            'average_credibility_scores': {
                'market': sum(item.get('credibility_score', 0) for item in market_data) / len(market_data) if market_data else 0,
                'political': sum(item.get('credibility_score', 0) for item in political_data) / len(political_data) if political_data else 0,
                'analysis': sum(item.get('credibility_score', 0) for item in analysis_data) / len(analysis_data) if analysis_data else 0
            },
            'top_symbols': get_top_mentioned_symbols(all_data),
            'collection_timestamp': datetime.now().isoformat()
        }

        # Extract top insights
        top_insights = []
        for item in all_data[:30]:
            top_insights.append({
                'title': item.get('title', ''),
                'content': item.get('content', '')[:500] + '...' if len(item.get('content', '')) > 500 else item.get('content', ''),
                'type': item.get('type', ''),
                'source': item.get('source', ''),
                'credibility_score': item.get('credibility_score', 0),
                'composite_score': item.get('composite_score', 0),
                'url': item.get('url', ''),
                'created_time': datetime.fromtimestamp(item.get('created_utc', 0)).strftime('%Y-%m-%d %H:%M:%S'),
                'symbol': item.get('symbol', ''),
                'keyword': item.get('keyword', '')
            })

        high_cred_insights = [item for item in top_insights if item['credibility_score'] > 6.0][:10]

        return {
            'summary': summary,
            'top_insights': top_insights,
            'high_credibility_insights': high_cred_insights
        }

    async def generate_deepseek_analysis(self, market_data: List[Dict], political_data: List[Dict],
                                       analysis_data: List[Dict], stocks: List[str], keywords: List[str] = None,
                                       data_check_results: Dict[str, str] = None) -> Dict:
        """
        Generate comprehensive analysis reports using DeepSeek AI

        Args:
            market_data: Market movement posts
            political_data: Political news posts
            analysis_data: Credible analysis posts
            stocks: List of analyzed stock symbols
            keywords: List of keywords to analyze (optional)
            data_check_results: Dictionary of data check messages (optional)

        Returns:
            Dictionary with all DeepSeek-generated reports
        """
        print("\n[DEEPSEEK STEP] Generating AI-powered analysis reports...")

        all_data = market_data + political_data + analysis_data
        deepseek_reports = {}
        
        if data_check_results is None:
            data_check_results = {}

        try:
            # 1. Broad market analysis
            print("  - Generating broad market analysis...")
            market_msg = data_check_results.get('market', '') + "\n" + data_check_results.get('political', '')
            market_report = generate_market_analysis_report(market_data, political_data, data_check_msg=market_msg)
            deepseek_reports['market_analysis'] = market_report

            # 2. Symbol-specific analyses
            if stocks:
                print("  - Generating symbol-specific analyses...")
                symbol_analyses = {}
                for symbol in stocks:
                    symbol_data = [item for item in all_data if item.get('symbol') == symbol or symbol in item.get('title', '')]
                    if symbol_data:
                        # Use analysis data check for symbol analysis
                        symbol_msg = data_check_results.get('analysis', '')
                        symbol_analysis = generate_symbol_specific_analysis(symbol, symbol_data, data_check_msg=symbol_msg)
                        symbol_analyses[symbol] = symbol_analysis
                deepseek_reports['symbol_analyses'] = symbol_analyses

            # 3. Keyword analyses (stocks, commodities, crypto, etc.)
            if keywords:
                print("  - Generating keyword analyses...")
                keyword_analyses = {}
                for keyword in keywords:
                    keyword_data = [item for item in all_data if item.get('keyword') == keyword or keyword.lower() in item.get('title', '').lower() + ' ' + item.get('content', '').lower()]
                    if keyword_data:
                        # Use keyword data check for keyword analysis
                        keyword_msg = data_check_results.get('keyword', '')
                        keyword_analysis = generate_keyword_analysis(keyword, keyword_data, data_check_msg=keyword_msg)
                        keyword_analyses[keyword] = keyword_analysis
                deepseek_reports['keyword_analyses'] = keyword_analyses

            # 4. Risk assessment
            print("  - Generating risk assessment...")
            # Combine all data checks for risk assessment
            risk_msg = "\n".join([msg for msg in data_check_results.values() if msg])
            risk_report = generate_risk_assessment(all_data, data_check_msg=risk_msg)
            deepseek_reports['risk_assessment'] = risk_report

            print(f"[DONE] Generated {len(deepseek_reports)} DeepSeek analysis reports")

        except Exception as e:
            print(f"[ERROR] DeepSeek analysis failed: {e}")
            deepseek_reports['error'] = str(e)

        return deepseek_reports

    async def run_workflow_with_deepseek(self, stocks: List[str], time_horizon: str = 'day',
                                        include_deepseek_analysis: bool = True) -> Dict:
        """
        Run the complete Reddit intelligence workflow with DeepSeek AI analysis

        Args:
            stocks: List of stock symbols to analyze
            time_horizon: Time period ('day', 'week', 'month', 'year', 'all')
            include_deepseek_analysis: Whether to include DeepSeek AI analysis

        Returns:
            Dictionary with all collected data, insights, and DeepSeek analysis
        """
        print("\n" + "="*80)
        print("REDDIT INTELLIGENCE COLLECTION WORKFLOW + DEEPSEEK AI ANALYSIS")
        print("="*80)
        print(f"Target stocks: {', '.join(stocks)}")
        print(f"Time horizon: {time_horizon}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"DeepSeek Analysis: {'Enabled' if include_deepseek_analysis else 'Disabled'}")
        print("="*80 + "\n")

        try:
            # Step 1: Market movement data
            print("[STEP 1] Collecting market movement data...")
            market_result = await self.collect_market_movement_data(stocks, time_horizon)
            market_data = market_result.get('data', [])
            if market_result.get('data_check_result'):
                print(f"         {market_result.get('data_check_result')}")
            print(f"[DONE] Collected {len(market_data)} market movement posts")
            await asyncio.sleep(1)

            # Step 2: Political news
            print("\n[STEP 2] Collecting political news...")
            political_keywords = ['Fed', 'SEC', 'inflation', 'interest rates', 'tariff', 'regulation', 'Congress']
            political_result = await self.collect_political_news_data(political_keywords, time_horizon)
            political_data = political_result.get('data', [])
            if political_result.get('data_check_result'):
                print(f"         {political_result.get('data_check_result')}")
            print(f"[DONE] Collected {len(political_data)} political news posts")
            await asyncio.sleep(1)

            # Step 3: Credible analysis
            print("\n[STEP 3] Collecting credible analysis...")
            analysis_result = await self.collect_credible_analysis_data(stocks, time_horizon)
            analysis_data = analysis_result.get('data', [])
            if analysis_result.get('data_check_result'):
                print(f"         {analysis_result.get('data_check_result')}")
            print(f"[DONE] Collected {len(analysis_data)} credible analysis posts")
            await asyncio.sleep(1)

            # Step 4: Generate summary
            print("\n[STEP 4] Generating summary...")
            intelligence_summary = await self.generate_intelligence_summary(market_data, political_data, analysis_data)
            print(f"[DONE] Generated summary with {len(intelligence_summary['top_insights'])} insights")

            # Step 5: DeepSeek AI Analysis (optional)
            deepseek_analysis = {}
            if include_deepseek_analysis:
                data_check_results = {
                    'market': market_result.get('data_check_result', ''),
                    'political': political_result.get('data_check_result', ''),
                    'analysis': analysis_result.get('data_check_result', '')
                }
                deepseek_analysis = await self.generate_deepseek_analysis(market_data, political_data, analysis_data, stocks, data_check_results=data_check_results)

            print("\n" + "="*80)
            print("WORKFLOW COMPLETED SUCCESSFULLY")
            print("="*80)

            result = {
                'market_data': market_data,
                'political_data': political_data,
                'analysis_data': analysis_data,
                'summary': intelligence_summary['summary'],
                'top_insights': intelligence_summary['top_insights'],
                'high_credibility_insights': intelligence_summary['high_credibility_insights']
            }

            if include_deepseek_analysis:
                result.update({
                    'deepseek_market_analysis': deepseek_analysis.get('market_analysis', ''),
                    'deepseek_symbol_analyses': deepseek_analysis.get('symbol_analyses', {}),
                    'deepseek_risk_assessment': deepseek_analysis.get('risk_assessment', '')
                })

            # Save output files
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_dir = Path('outputs')
            output_dir.mkdir(exist_ok=True)

            saved_files: Dict[str, Path] = {}

            # Save stock data
            stock_file = output_dir / f'reddit_intelligence_{timestamp}.json'
            with open(stock_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\n[SAVED] {stock_file.name}")
            saved_files['full_result'] = stock_file

            # Save DeepSeek analysis files
            if include_deepseek_analysis:
                if result.get('deepseek_market_analysis'):
                    analysis_file = output_dir / f'deepseek_market_analysis_{timestamp}.txt'
                    with open(analysis_file, 'w', encoding='utf-8') as f:
                        f.write("DEEPSEEK AI MARKET ANALYSIS\n")
                        f.write("="*40 + "\n\n")
                        f.write(result['deepseek_market_analysis'])
                    print(f"[SAVED] {analysis_file.name}")
                    saved_files['market_analysis'] = analysis_file
                
                if result.get('deepseek_symbol_analyses'):
                    symbol_analyses_file = output_dir / f'deepseek_symbol_analyses_{timestamp}.txt'
                    with open(symbol_analyses_file, 'w', encoding='utf-8') as f:
                        f.write("DEEPSEEK AI SYMBOL ANALYSES\n")
                        f.write("="*40 + "\n\n")
                        for symbol, analysis in result['deepseek_symbol_analyses'].items():
                            f.write(f"\n{symbol} ANALYSIS:\n")
                            f.write("-" * 40 + "\n")
                            f.write(analysis + "\n")
                    print(f"[SAVED] {symbol_analyses_file.name}")
                    saved_files['symbol_analyses'] = symbol_analyses_file
                
                if result.get('deepseek_risk_assessment'):
                    risk_file = output_dir / f'deepseek_risk_assessment_{timestamp}.txt'
                    with open(risk_file, 'w', encoding='utf-8') as f:
                        f.write("DEEPSEEK AI RISK ASSESSMENT\n")
                        f.write("="*40 + "\n\n")
                        f.write(result['deepseek_risk_assessment'])
                    print(f"[SAVED] {risk_file.name}")
                    saved_files['risk_assessment'] = risk_file

            if upload_outputs_to_gcs(result, timestamp, saved_files, output_dir):
                gcs_prefix_display = f"{GCS_DEST_PREFIX}/" if GCS_DEST_PREFIX else ''
                print(f"[UPLOAD] Synced outputs to gs://{GCS_BUCKET_NAME}/{gcs_prefix_display}*")

            return result

        except Exception as e:
            print(f"\n[ERROR] Workflow failed: {e}")
            raise

    async def run_workflow(self, stocks: List[str], time_horizon: str = 'day') -> Dict:
        """
        Run the complete Reddit intelligence workflow

        Args:
            stocks: List of stock symbols to analyze
            time_horizon: Time period ('day', 'week', 'month', 'year', 'all')

        Returns:
            Dictionary with all collected data and insights
        """
        print("\n" + "="*80)
        print("REDDIT INTELLIGENCE COLLECTION WORKFLOW")
        print("="*80)
        print(f"Target stocks: {', '.join(stocks)}")
        print(f"Time horizon: {time_horizon}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80 + "\n")

        try:
            # Step 1: Market movement data
            print("[STEP 1] Collecting market movement data...")
            market_result = await self.collect_market_movement_data(stocks, time_horizon)
            market_data = market_result.get('data', [])
            if market_result.get('data_check_result'):
                print(f"         {market_result.get('data_check_result')}")
            print(f"[DONE] Collected {len(market_data)} market movement posts")
            await asyncio.sleep(1)

            # Step 2: Political news
            print("\n[STEP 2] Collecting political news...")
            political_keywords = ['Fed', 'SEC', 'inflation', 'interest rates', 'tariff', 'regulation', 'Congress']
            political_result = await self.collect_political_news_data(political_keywords, time_horizon)
            political_data = political_result.get('data', [])
            if political_result.get('data_check_result'):
                print(f"         {political_result.get('data_check_result')}")
            print(f"[DONE] Collected {len(political_data)} political news posts")
            await asyncio.sleep(1)

            # Step 3: Credible analysis
            print("\n[STEP 3] Collecting credible analysis...")
            analysis_result = await self.collect_credible_analysis_data(stocks, time_horizon)
            analysis_data = analysis_result.get('data', [])
            if analysis_result.get('data_check_result'):
                print(f"         {analysis_result.get('data_check_result')}")
            print(f"[DONE] Collected {len(analysis_data)} credible analysis posts")
            await asyncio.sleep(1)

            # Step 4: Generate summary
            print("\n[STEP 4] Generating summary...")
            intelligence_summary = await self.generate_intelligence_summary(market_data, political_data, analysis_data)
            print(f"[DONE] Generated summary with {len(intelligence_summary['top_insights'])} insights")

            print("\n" + "="*80)
            print("WORKFLOW COMPLETED SUCCESSFULLY")
            print("="*80)

            return {
                'market_data': market_data,
                'political_data': political_data,
                'analysis_data': analysis_data,
                'summary': intelligence_summary['summary'],
                'top_insights': intelligence_summary['top_insights'],
                'high_credibility_insights': intelligence_summary['high_credibility_insights']
            }

        except Exception as e:
            print(f"\n[ERROR] Workflow failed: {e}")
            raise

    async def run_keyword_workflow_with_deepseek(self, keywords: List[str], time_horizon: str = 'day',
                                                include_deepseek_analysis: bool = True) -> Dict:
        """
        Run keyword-specific Reddit intelligence workflow with DeepSeek AI analysis
        (For analyzing stocks, commodities, crypto, or any keyword)

        Args:
            keywords: List of keywords to analyze (e.g., ['gold', 'oil', 'bitcoin', 'AAPL'])
            time_horizon: Time period ('day', 'week', 'month', 'year', 'all')
            include_deepseek_analysis: Whether to include DeepSeek AI analysis

        Returns:
            Dictionary with collected data, insights, and DeepSeek analysis
        """
        print("\n" + "="*80)
        print("REDDIT KEYWORD INTELLIGENCE WORKFLOW + DEEPSEEK AI ANALYSIS")
        print("="*80)
        print(f"Target keywords: {', '.join(keywords)}")
        print(f"Time horizon: {time_horizon}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"DeepSeek Analysis: {'Enabled' if include_deepseek_analysis else 'Disabled'}")
        print("="*80 + "\n")

        try:
            # Step 1: Keyword data collection
            print("[STEP 1] Collecting keyword data...")
            keyword_result = await self.collect_keyword_data(keywords, time_horizon)
            keyword_data = keyword_result.get('data', [])
            if keyword_result.get('data_check_result'):
                print(f"         {keyword_result.get('data_check_result')}")
            print(f"[DONE] Collected {len(keyword_data)} keyword posts")
            await asyncio.sleep(1)

            # Step 2: Generate summary
            print("\n[STEP 2] Generating summary...")

            # Calculate composite scores
            for item in keyword_data:
                credibility = item.get('credibility_score', 0)
                engagement = item.get('score', 0) + (item.get('comments', 0) * 2)
                item['composite_score'] = credibility * 0.7 + min(engagement / 100, 1) * 0.3

            # Sort by composite score
            keyword_data.sort(key=lambda x: x.get('composite_score', 0), reverse=True)

            # Generate summary
            summary = {
                'total_posts_collected': len(keyword_data),
                'average_credibility_score': sum(item.get('credibility_score', 0) for item in keyword_data) / len(keyword_data) if keyword_data else 0,
                'top_keywords': [(kw, sum(1 for item in keyword_data if item.get('keyword') == kw)) for kw in keywords],
                'collection_timestamp': datetime.now().isoformat()
            }

            print(f"[DONE] Generated summary with {len(keyword_data)} insights")

            # Step 3: DeepSeek AI Analysis (optional)
            deepseek_analysis = {}
            if include_deepseek_analysis:
                data_check_results = {
                    'keyword': keyword_result.get('data_check_result', '')
                }
                deepseek_analysis = await self.generate_deepseek_analysis([], [], [], [], keywords=keywords, data_check_results=data_check_results)
                print("\n[DEEPSEEK STEP] Generating AI-powered analysis reports...")

                try:
                    # 1. Overall market analysis for keywords
                    print("  - Generating keyword market analysis...")
                    overall_prompt = f"""
                    Analyze the following Reddit market intelligence data for keywords: {', '.join(keywords)}

                    DATA SUMMARY:
                    - Total Posts: {len(keyword_data)}
                    - Average Credibility Score: {summary['average_credibility_score']:.2f}

                    TOP CREDIBLE INSIGHTS:
                    {chr(10).join([f"- {item.get('title', '')} (r/{item.get('source', '')}, {item.get('credibility_score', 0):.2f}/10)" for item in keyword_data[:10]])}

                    Please provide a comprehensive analysis covering:
                    1. Overall Market Sentiment
                    2. Key Trends and Patterns
                    3. Top Keyword Performance
                    4. Investment Opportunities & Risks
                    5. Actionable Recommendations

                    Format as a professional analyst report.
                    """
                    overall_report = call_deepseek_api(overall_prompt, max_tokens=2500)
                    deepseek_analysis['market_analysis'] = overall_report

                    # 2. Individual keyword analyses
                    print("  - Generating individual keyword analyses...")
                    keyword_analyses = {}
                    for keyword in keywords:
                        keyword_specific_data = [item for item in keyword_data if item.get('keyword') == keyword]
                        if keyword_specific_data:
                            keyword_analysis = generate_keyword_analysis(keyword, keyword_specific_data)
                            keyword_analyses[keyword] = keyword_analysis
                    deepseek_analysis['keyword_analyses'] = keyword_analyses

                    # 3. Risk assessment
                    print("  - Generating risk assessment...")
                    risk_report = generate_risk_assessment(keyword_data)
                    deepseek_analysis['risk_assessment'] = risk_report

                    print(f"[DONE] Generated {len(deepseek_analysis)} DeepSeek analysis reports")

                except Exception as e:
                    print(f"[ERROR] DeepSeek analysis failed: {e}")
                    deepseek_analysis['error'] = str(e)

            print("\n" + "="*80)
            print("WORKFLOW COMPLETED SUCCESSFULLY")
            print("="*80)

            result = {
                'keyword_data': keyword_data,
                'summary': summary,
                'top_insights': keyword_data[:30],
                'high_credibility_insights': [item for item in keyword_data if item.get('credibility_score', 0) > 6.0][:10]
            }

            if include_deepseek_analysis:
                result.update({
                    'deepseek_market_analysis': deepseek_analysis.get('market_analysis', ''),
                    'deepseek_keyword_analyses': deepseek_analysis.get('keyword_analyses', {}),
                    'deepseek_risk_assessment': deepseek_analysis.get('risk_assessment', '')
                })

            # Save output files
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_dir = Path('outputs')
            output_dir.mkdir(exist_ok=True)

            # Save keyword data
            keyword_file = output_dir / f'reddit_intelligence_{timestamp}.json'
            with open(keyword_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\n[SAVED] {keyword_file.name}")

            # Save DeepSeek analysis files
            if include_deepseek_analysis:
                if result.get('deepseek_market_analysis'):
                    analysis_file = output_dir / f'deepseek_market_analysis_{timestamp}.txt'
                    with open(analysis_file, 'w', encoding='utf-8') as f:
                        f.write("DEEPSEEK AI MARKET ANALYSIS\n")
                        f.write("="*40 + "\n\n")
                        f.write(result['deepseek_market_analysis'])
                    print(f"[SAVED] {analysis_file.name}")
                
                if result.get('deepseek_keyword_analyses'):
                    keyword_analyses_file = output_dir / f'deepseek_keyword_analyses_{timestamp}.txt'
                    with open(keyword_analyses_file, 'w', encoding='utf-8') as f:
                        f.write("DEEPSEEK AI KEYWORD ANALYSES\n")
                        f.write("="*40 + "\n\n")
                        for keyword, analysis in result['deepseek_keyword_analyses'].items():
                            f.write(f"\n{keyword.upper()} ANALYSIS:\n")
                            f.write("-" * 40 + "\n")
                            f.write(analysis + "\n")
                    print(f"[SAVED] {keyword_analyses_file.name}")
                
                if result.get('deepseek_risk_assessment'):
                    risk_file = output_dir / f'deepseek_risk_assessment_{timestamp}.txt'
                    with open(risk_file, 'w', encoding='utf-8') as f:
                        f.write("DEEPSEEK AI RISK ASSESSMENT\n")
                        f.write("="*40 + "\n\n")
                        f.write(result['deepseek_risk_assessment'])
                    print(f"[SAVED] {risk_file.name}")

            return result

        except Exception as e:
            print(f"\n[ERROR] Workflow failed: {e}")
            raise

    async def collect_trending_market_news(self, time_horizon: str = 'day', max_posts: int = 100) -> Dict:
        """
        Collect trending market news from Reddit without hardcoded keywords.
        AI will identify what's hot and relevant.

        Args:
            time_horizon: Time period to collect posts from
            max_posts: Maximum posts to collect

        Returns:
            Dictionary with trending posts and data check result
        """
        print(f"\n[AI DISCOVERY] Collecting trending market news...")
        print(f"Time Horizon: {time_horizon}")
        print(f"Max Posts: {max_posts}")
        print(f"Method: AI-powered topic discovery (no hardcoded keywords)")

        market_subreddits = [
            'investing', 'stocks', 'SecurityAnalysis', 'ValueInvesting',
            'StockMarket', 'economics', 'business', 'finance',
            'wallstreetbets', 'CryptoCurrency', 'Superstonk',
            'market_news', 'stocks_news', 'economy'
        ]

        async def fetch_data(horizon):
            posts_list = []
            # Collect from multiple sources
            for subreddit in market_subreddits:
                try:
                    print(f"  - Fetching from r/{subreddit}...")

                    # Get hot posts (trending naturally by Reddit's algorithm)
                    posts = self.reddit.search_posts(
                        query='',  # Empty query to get all hot posts
                        subreddit=subreddit,
                        sort='hot',
                        time_filter=horizon,
                        limit=max_posts // len(market_subreddits)
                    )

                    for post in posts:
                        post_data = post.get('data', {})

                        # Dynamic credibility scoring (no hardcoded subreddit scores)
                        post_data['subreddit'] = subreddit
                        credibility = calculate_post_credibility(post_data, posts_list)

                        posts_list.append({
                            'type': 'trending_news',
                            'subreddit': subreddit,
                            'title': post_data.get('title', ''),
                            'content': self.reddit.extract_post_text(post),
                            'score': post_data.get('score', 0),
                            'comments': post_data.get('num_comments', 0),
                            'created_utc': post_data.get('created_utc'),
                            'author': post_data.get('author', ''),
                            'url': f"https://reddit.com{post_data.get('permalink', '')}",
                            'flair': post_data.get('link_flair_text', ''),
                            'upvote_ratio': post_data.get('upvote_ratio', 0),
                            'credibility_score': credibility
                        })
                    await asyncio.sleep(0.5)
                except Exception:
                    pass
            return posts_list

        trending_posts = await fetch_data(time_horizon)
        data_check_msg = ""

        if time_horizon == 'day':
            cutoff_time = time.time() - (24 * 3600)
            fresh_posts = [p for p in trending_posts if p.get('created_utc', 0) >= cutoff_time]
            
            if len(fresh_posts) < 10:
                print(f"[FALLBACK] Only {len(fresh_posts)} posts in last 24h. Extending search to week...")
                week_posts = await fetch_data('week')
                week_posts.sort(key=lambda x: x.get('created_utc', 0), reverse=True)
                trending_posts = week_posts[:10]
                data_check_msg = f"DATA CHECK: WARNING. Only found {len(fresh_posts)} posts in last 24h. Included top 10 most recent posts from last week."
            else:
                trending_posts = fresh_posts
                data_check_msg = f"DATA CHECK: PASSED. Found {len(trending_posts)} posts in last 24 hours."

        # AI-POWERED TOPIC DISCOVERY
        print(f"\n[AI ANALYSIS] Discovering hot topics from {len(trending_posts)} posts...")

        # Use AI to identify trending topics
        posts_for_ai = []
        for post in trending_posts[:30]:  # Top 30 for AI analysis
            posts_for_ai.append({
                'title': post['title'][:200],
                'score': post['score'],
                'comments': post['comments'],
                'subreddit': post['subreddit']
            })

        topic_discovery_prompt = f"""
        Analyze these {len(posts_for_ai)} trending Reddit posts to identify the HOTTEST market topics.
        
        {data_check_msg}

        POSTS:
        {chr(10).join([f"{i+1}. [{p['subreddit']}] {p['title']} (↑{p['score']} | 💬{p['comments']})" for i, p in enumerate(posts_for_ai)])}

        Please:
        1. Identify the TOP 5 HOTTEST topics/keywords/themes
        2. Rank them by importance and trend potential
        3. Summarize why each is hot right now
        4. Format as: TOPIC | EXPLANATION | RELEVANCE_SCORE (1-10)
        """

        topic_report = call_deepseek_api(topic_discovery_prompt, max_tokens=1500)

        # Rank posts by AI-determined relevance
        for post in trending_posts:
            # Dynamic ranking based on engagement + credibility + recency
            score = post.get('score', 0)
            comments = post.get('comments', 0)
            credibility = post.get('credibility_score', 0)
            upvote_ratio = post.get('upvote_ratio', 0.5)

            # Calculate dynamic AI-powered relevance score
            engagement = score + (comments * 2)
            engagement_normalized = min(engagement / 500, 1.0)  # Normalize to 0-1

            post['ai_relevance_score'] = (
                engagement_normalized * 0.40 +
                (credibility / 10) * 0.35 +
                upvote_ratio * 0.20 +
                (1 if post.get('flair') else 0) * 0.05  # Flair bonus
            )

        # Sort by AI-determined relevance
        trending_posts.sort(key=lambda x: x['ai_relevance_score'], reverse=True)

        print(f"[OK] Collected and ranked {len(trending_posts)} trending posts")
        print(f"[AI] Trending topics identified: {topic_report[:100]}...")

        return {'trending_posts': trending_posts, 'data_check_result': data_check_msg}

    async def run_trending_market_news_with_deepseek(self, time_horizon: str = 'day',
                                                   include_deepseek_analysis: bool = True) -> Dict:
        """
        Run AI-powered trending market news discovery workflow
        - No hardcoded keywords
        - No hardcoded rankings
        - AI discovers what's hot
        - AI ranks by relevance

        Args:
            time_horizon: Time period ('day', 'week', 'month')
            include_deepseek_analysis: Whether to include DeepSeek AI analysis

        Returns:
            Dictionary with trending news, AI insights, and analysis
        """
        print("\n" + "="*80)
        print("AI-POWERED TRENDING MARKET NEWS DISCOVERY")
        print("="*80)
        print(f"Time horizon: {time_horizon}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"DeepSeek Analysis: {'Enabled' if include_deepseek_analysis else 'Disabled'}")
        print("="*80 + "\n")

        try:
            # Step 1: Collect trending news (AI-powered discovery)
            print("[STEP 1] Collecting trending market news...")
            trending_result = await self.collect_trending_market_news(time_horizon)
            trending_posts = trending_result.get('trending_posts', [])
            data_check_msg = trending_result.get('data_check_result', '')
            
            if data_check_msg:
                print(f"         {data_check_msg}")
            print(f"[DONE] Collected {len(trending_posts)} trending posts")

            # Step 2: Generate summary with AI insights
            print("\n[STEP 2] Generating AI-powered insights...")

            # Calculate summary statistics
            summary = {
                'total_posts_collected': len(trending_posts),
                'average_score': sum(post.get('score', 0) for post in trending_posts) / len(trending_posts) if trending_posts else 0,
                'average_comments': sum(post.get('comments', 0) for post in trending_posts) / len(trending_posts) if trending_posts else 0,
                'top_subreddits': {},
                'collection_timestamp': datetime.now().isoformat()
            }

            # Count posts by subreddit
            for post in trending_posts:
                sub = post.get('subreddit', '')
                summary['top_subreddits'][sub] = summary['top_subreddits'].get(sub, 0) + 1

            print(f"[DONE] Generated summary with {len(trending_posts)} insights")

            # Step 3: DeepSeek AI Analysis
            deepseek_analysis = {}
            if include_deepseek_analysis:
                print("\n[DEEPSEEK STEP] Generating AI-powered analysis reports...")

                try:
                    # 1. Trending topics report
                    print("  - Generating trending topics analysis...")
                    top_posts = trending_posts[:20]
                    trending_prompt = f"""
                    Analyze these {len(top_posts)} hottest trending market posts from Reddit.
                    
                    {data_check_msg}

                    POSTS (ranked by AI relevance):
                    {chr(10).join([f"{i+1}. [{post.get('subreddit', '')}] {post.get('title', '')} | Score: {post.get('score', 0)} | Comments: {post.get('comments', 0)} | Relevance: {post.get('ai_relevance_score', 0):.2f}" for i, post in enumerate(top_posts)])}

                    Please provide:
                    1. TOP 5 HOTTEST MARKET TOPICS (what's trending NOW)
                    2. MARKET SENTIMENT ANALYSIS
                    3. KEY THEMES AND PATTERNS
                    4. INVESTMENT IMPLICATIONS
                    5. WHAT TO WATCH NEXT

                    Focus on ACTIONABLE insights for traders and investors.
                    """
                    trending_report = call_deepseek_api(trending_prompt, max_tokens=2500)
                    deepseek_analysis['trending_topics'] = trending_report

                    # 2. Risk assessment for current market environment
                    print("  - Generating market environment risk assessment...")
                    risk_prompt = f"""
                    Based on these trending market posts, assess the current market environment:

                    SUMMARY STATS:
                    - Total Trending Posts: {len(trending_posts)}
                    - Average Score: {summary['average_score']:.1f}
                    - Average Comments: {summary['average_comments']:.1f}

                    TOP POSTS:
                    {chr(10).join([f"- {post.get('title', '')[:150]}" for post in top_posts[:10]])}

                    Analyze:
                    1. Current Market Risk Level (Low/Medium/High + explanation)
                    2. Key Risk Factors
                    3. Market Stress Indicators
                    4. Early Warning Signs
                    5. Risk Management Recommendations

                    Be concise but thorough.
                    """
                    risk_report = call_deepseek_api(risk_prompt, max_tokens=1500)
                    deepseek_analysis['risk_assessment'] = risk_report

                    print(f"[DONE] Generated {len(deepseek_analysis)} DeepSeek analysis reports")

                except Exception as e:
                    print(f"[ERROR] DeepSeek analysis failed: {e}")
                    deepseek_analysis['error'] = str(e)

            print("\n" + "="*80)
            print("TRENDING NEWS DISCOVERY COMPLETED")
            print("="*80)

            # Compile results
            result = {
                'trending_posts': trending_posts,
                'data_check_result': data_check_msg,
                'summary': summary,
                'top_posts': trending_posts[:50],  # Top 50 most relevant
                'high_credibility_posts': [post for post in trending_posts if post.get('credibility_score', 0) > 6.0][:20]
            }

            if include_deepseek_analysis:
                result.update({
                    'deepseek_trending_analysis': deepseek_analysis.get('trending_topics', ''),
                    'deepseek_risk_assessment': deepseek_analysis.get('risk_assessment', '')
                })

            # Save output files
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_dir = Path('outputs')
            output_dir.mkdir(exist_ok=True)

            # Save trending posts data
            trending_file = output_dir / f'reddit_trending_news_{timestamp}.json'
            with open(trending_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\n[SAVED] {trending_file.name}")

            # Save DeepSeek analysis files
            if include_deepseek_analysis:
                if result.get('deepseek_trending_analysis'):
                    analysis_file = output_dir / f'deepseek_trending_analysis_{timestamp}.txt'
                    with open(analysis_file, 'w', encoding='utf-8') as f:
                        f.write("DEEPSEEK AI TRENDING NEWS ANALYSIS\n")
                        f.write("="*40 + "\n\n")
                        f.write(result['deepseek_trending_analysis'])
                    print(f"[SAVED] {analysis_file.name}")
                
                if result.get('deepseek_risk_assessment'):
                    risk_file = output_dir / f'deepseek_risk_assessment_{timestamp}.txt'
                    with open(risk_file, 'w', encoding='utf-8') as f:
                        f.write("DEEPSEEK AI RISK ASSESSMENT\n")
                        f.write("="*40 + "\n\n")
                        f.write(result['deepseek_risk_assessment'])
                    print(f"[SAVED] {risk_file.name}")

            return result

        except Exception as e:
            print(f"\n[ERROR] Workflow failed: {e}")
            raise

    async def scan_rss_feeds(self, time_horizon: str = 'day', max_articles: int = 100) -> Dict:
        """
        Scan RSS feeds from financial news sources with smart filtering and fallback.
        
        Args:
            time_horizon: Time period to collect articles from
            max_articles: Maximum articles to collect

        Returns:
            Dictionary containing 'articles' (List[Dict]) and 'data_check_result' (str)
        """
        print(f"\n[RSS SCANNER] Scanning financial news feeds...")
        print(f"Time Horizon: {time_horizon}")
        print(f"Max Articles: {max_articles}")
        print(f"Method: AI-powered topic discovery from RSS feeds")

        # Financial news RSS sources
        rss_feeds = [
            ('Yahoo Finance', 'https://finance.yahoo.com/news/rssindex'),
            ('MarketWatch', 'https://feeds.marketwatch.com/marketwatch/topstories/'),
            ('CNBC Markets', 'https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664'),
            ('Bloomberg Markets', 'https://feeds.bloomberg.com/markets/news.rss'),
            ('CNN Business', 'http://rss.cnn.com/rss/money_latest.rss'),
            ('BBC Business', 'http://feeds.bbci.co.uk/news/business/rss.xml'),
            ('The Guardian Business', 'https://www.theguardian.com/business/rss'),
            ('Investing.com', 'https://www.investing.com/rss/news.rss')
        ]

        raw_articles = []

        # Fetch from RSS feeds
        for source_name, feed_url in rss_feeds:
            try:
                print(f"  - Fetching from {source_name}...")
                feed_items = fetch_rss_feed(feed_url, timeout=10)
                
                for item in feed_items:
                    # Dynamic credibility scoring
                    credibility = self._calculate_rss_credibility(item)
                    
                    raw_articles.append({
                        'type': 'rss_article',
                        'source': source_name,
                        'title': item.get('title', ''),
                        'link': item.get('link', ''),
                        'summary': item.get('summary', ''),
                        'published': item.get('published', ''),
                        'published_timestamp': item.get('published_timestamp', 0),
                        'author': item.get('author', ''),
                        'tags': item.get('tags', []),
                        'credibility_score': credibility
                    })
                
                await asyncio.sleep(0.5)

            except Exception as e:
                print(f"    Warning: Could not fetch from {source_name}: {str(e)[:50]}")
                continue

        # Apply Filtering and Fallback Logic
        final_articles = []
        data_check_msg = ""
        
        # Sort by timestamp descending (newest first)
        raw_articles.sort(key=lambda x: x.get('published_timestamp', 0), reverse=True)
        
        if time_horizon == 'day':
            cutoff_time = time.time() - (24 * 3600)
            filtered_articles = [a for a in raw_articles if a.get('published_timestamp', 0) >= cutoff_time]
            
            if len(filtered_articles) >= 10:
                final_articles = filtered_articles
                data_check_msg = f"DATA CHECK: PASSED. Found {len(final_articles)} articles in the last 24 hours."
            else:
                # Fallback: Take top 10 most recent regardless of time
                final_articles = raw_articles[:10]
                data_check_msg = f"DATA CHECK: WARNING. Only found {len(filtered_articles)} articles in last 24h. Included top {len(final_articles)} most recent articles to ensure sufficient data."
        else:
            # For other horizons, just use the horizon filter (simplified for now)
            if time_horizon == 'week':
                cutoff_time = time.time() - (7 * 24 * 3600)
            elif time_horizon == 'month':
                cutoff_time = time.time() - (30 * 24 * 3600)
            else:
                cutoff_time = 0
                
            final_articles = [a for a in raw_articles if a.get('published_timestamp', 0) >= cutoff_time]
            data_check_msg = f"DATA CHECK: PASSED. Found {len(final_articles)} articles for horizon '{time_horizon}'."

        # Limit to max_articles
        final_articles = final_articles[:max_articles]
        
        print(f"\n{data_check_msg}")

        # AI-POWERED TOPIC DISCOVERY
        print(f"\n[AI ANALYSIS] Discovering hot topics from {len(final_articles)} RSS articles...")

        # Use AI to identify trending topics
        articles_for_ai = []
        for article in final_articles[:30]:  # Top 30 for AI analysis
            articles_for_ai.append({
                'title': article['title'][:200],
                'source': article['source'],
                'published': article['published']
            })

        if articles_for_ai:
            topic_discovery_prompt = f"""
            Analyze these {len(articles_for_ai)} trending RSS articles to identify the HOTTEST financial news topics.
            
            {data_check_msg}

            ARTICLES:
            {chr(10).join([f"{i+1}. [{article['source']}] {article['title']}" for i, article in enumerate(articles_for_ai)])}

            Please:
            1. Identify the TOP 5 HOTTEST topics/themes in financial news
            2. Rank them by importance and news impact
            3. Summarize why each is hot right now
            4. Format as: TOPIC | EXPLANATION | IMPACT_SCORE (1-10)
            """

            topic_report = call_deepseek_api(topic_discovery_prompt, max_tokens=1500)

            # Rank articles by AI-determined relevance
            for article in final_articles:
                # Dynamic ranking based on recency + source credibility + content depth
                published_timestamp = article.get('published_timestamp', 0)
                source = article.get('source', '')

                # Recency score (0-10)
                if published_timestamp:
                    age_hours = (time.time() - published_timestamp) / 3600
                    if age_hours < 1:
                        recency_score = 10
                    elif age_hours < 6:
                        recency_score = 9
                    elif age_hours < 24:
                        recency_score = 8
                    elif age_hours < 48:
                        recency_score = 6
                    elif age_hours < 168:
                        recency_score = 4
                    else:
                        recency_score = 2
                else:
                    recency_score = 5

                # Source credibility (0-10)
                high_cred_sources = ['Reuters', 'Bloomberg', 'Financial Times', 'WSJ', 'Yahoo Finance']
                medium_cred_sources = ['CNBC', 'MarketWatch', 'The Street']
                source_score = 8 if any(src in source for src in high_cred_sources) else \
                              6 if any(src in source for src in medium_cred_sources) else 5

                # Content depth score (0-10)
                title = article.get('title', '')
                summary = article.get('summary', '')
                content_length = len(title) + len(summary[:500])
                if content_length > 1000:
                    content_score = 10
                elif content_length > 500:
                    content_score = 8
                elif content_length > 200:
                    content_score = 6
                else:
                    content_score = 4

                # Calculate AI-powered relevance score
                article['ai_relevance_score'] = (
                    (recency_score / 10) * 0.40 +
                    (source_score / 10) * 0.35 +
                    (content_score / 10) * 0.25
                )

            # Sort by AI-determined relevance
            final_articles.sort(key=lambda x: x['ai_relevance_score'], reverse=True)

        print(f"[OK] Collected and ranked {len(final_articles)} RSS articles")
        if articles_for_ai:
            print(f"[AI] Trending topics identified: {topic_report[:100]}...")

        return {
            'articles': final_articles,
            'data_check_result': data_check_msg
        }

    def _calculate_rss_credibility(self, article: Dict) -> float:
        """
        Calculate credibility score for RSS article

        Args:
            article: Article data dictionary

        Returns:
            Credibility score (0-10)
        """
        source = article.get('source', '')

        # Source credibility weights
        high_cred_sources = {
            'Reuters': 9.5, 'Bloomberg': 9.5, 'Financial Times': 9.0,
            'WSJ': 9.0, 'Wall Street Journal': 9.0, 'BBC': 8.5
        }
        medium_cred_sources = {
            'Yahoo Finance': 8.0, 'CNBC': 7.5, 'MarketWatch': 7.0,
            'The Street': 6.5, 'CNN Business': 6.5
        }

        # Get base score
        base_score = 0
        for src, score in high_cred_sources.items():
            if src.lower() in source.lower():
                base_score = score
                break

        if base_score == 0:
            for src, score in medium_cred_sources.items():
                if src.lower() in source.lower():
                    base_score = score
                    break

        if base_score == 0:
            base_score = 6.0  # Default for unknown sources

        # Recency bonus
        published_timestamp = article.get('published_timestamp', 0)
        recency_bonus = 0
        if published_timestamp:
            age_hours = (time.time() - published_timestamp) / 3600
            if age_hours < 1:
                recency_bonus = 1.0
            elif age_hours < 6:
                recency_bonus = 0.8
            elif age_hours < 24:
                recency_bonus = 0.5
            elif age_hours < 48:
                recency_bonus = 0.2

        # Content quality indicators
        title = article.get('title', '')
        has_summary = 1 if article.get('summary') else 0
        has_tags = 1 if article.get('tags') else 0

        content_bonus = (has_summary + has_tags) * 0.5

        total_score = base_score + recency_bonus + content_bonus
        return min(total_score, 10.0)

    async def run_rss_news_scan_with_deepseek(self, time_horizon: str = 'day',
                                            include_deepseek_analysis: bool = True) -> Dict:
        """
        Run AI-powered RSS news scan workflow
        - NO hardcoded keywords
        - NO hardcoded rankings
        - AI discovers what's hot
        - AI ranks by relevance

        Args:
            time_horizon: Time period ('day', 'week', 'month')
            include_deepseek_analysis: Whether to include DeepSeek AI analysis

        Returns:
            Dictionary with RSS articles, AI insights, and analysis
        """
        print("\n" + "="*80)
        print("AI-POWERED RSS FINANCIAL NEWS SCAN")
        print("="*80)
        print(f"Time horizon: {time_horizon}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"DeepSeek Analysis: {'Enabled' if include_deepseek_analysis else 'Disabled'}")
        print("="*80 + "\n")

        try:
            # Step 1: Scan RSS feeds
            print("[STEP 1] Scanning financial news RSS feeds...")
            scan_result = await self.scan_rss_feeds(time_horizon)
            rss_articles = scan_result.get('articles', [])
            data_check_msg = scan_result.get('data_check_result', '')
            
            print(f"[DONE] Collected {len(rss_articles)} RSS articles")
            if data_check_msg:
                print(f"         {data_check_msg}")

            # Step 2: Generate summary with AI insights
            print("\n[STEP 2] Generating AI-powered insights...")

            # Calculate summary statistics
            summary = {
                'total_articles_collected': len(rss_articles),
                'average_credibility': sum(article.get('credibility_score', 0) for article in rss_articles) / len(rss_articles) if rss_articles else 0,
                'by_source': {},
                'collection_timestamp': datetime.now().isoformat()
            }

            # Count articles by source
            for article in rss_articles:
                source = article.get('source', '')
                summary['by_source'][source] = summary['by_source'].get(source, 0) + 1

            print(f"[DONE] Generated summary with {len(rss_articles)} insights")

            # Step 3: DeepSeek AI Analysis
            deepseek_analysis = {}
            if include_deepseek_analysis:
                print("\n[DEEPSEEK STEP] Generating AI-powered analysis reports...")

                try:
                    # 1. Trending news analysis
                    print("  - Generating trending news analysis...")
                    top_articles = rss_articles[:20]
                    trending_prompt = f"""
                    Analyze these {len(top_articles)} hottest financial news articles from RSS feeds.
                    
                    {data_check_msg}

                    ARTICLES (ranked by AI relevance):
                    {chr(10).join([f"{i+1}. [{article.get('source', '')}] {article.get('title', '')} | Credibility: {article.get('credibility_score', 0):.1f}/10 | Relevance: {article.get('ai_relevance_score', 0):.2f}" for i, article in enumerate(top_articles)])}

                    Please provide:
                    1. TOP 5 HOTTEST FINANCIAL NEWS TOPICS
                    2. MARKET SENTIMENT ANALYSIS
                    3. KEY THEMES AND PATTERNS
                    4. INVESTMENT IMPLICATIONS
                    5. WHAT TO WATCH NEXT

                    Focus on ACTIONABLE insights for traders and investors.
                    """
                    trending_report = call_deepseek_api(trending_prompt, max_tokens=2500)
                    deepseek_analysis['trending_news'] = trending_report

                    # 2. Risk assessment
                    print("  - Generating market environment risk assessment...")
                    risk_prompt = f"""
                    Based on these financial news articles, assess the current market environment:

                    SUMMARY STATS:
                    - Total Articles: {len(rss_articles)}
                    - Average Credibility: {summary['average_credibility']:.1f}/10
                    - Top Sources: {', '.join(list(summary['by_source'].keys())[:5])}

                    TOP ARTICLES:
                    {chr(10).join([f"- {article.get('title', '')[:150]}" for article in top_articles[:10]])}

                    Analyze:
                    1. Current Market Risk Level (Low/Medium/High + explanation)
                    2. Key Risk Factors
                    3. Market Stress Indicators
                    4. Early Warning Signs
                    5. Risk Management Recommendations

                    Be concise but thorough.
                    """
                    risk_report = call_deepseek_api(risk_prompt, max_tokens=1500)
                    deepseek_analysis['risk_assessment'] = risk_report

                    print(f"[DONE] Generated {len(deepseek_analysis)} DeepSeek analysis reports")

                except Exception as e:
                    print(f"[ERROR] DeepSeek analysis failed: {e}")
                    deepseek_analysis['error'] = str(e)

            print("\n" + "="*80)
            print("RSS NEWS SCAN COMPLETED")
            print("="*80)

            # Compile results
            result = {
                'rss_articles': rss_articles,
                'summary': summary,
                'top_articles': rss_articles[:50],  # Top 50 most relevant
                'high_credibility_articles': [article for article in rss_articles if article.get('credibility_score', 0) > 7.0][:20]
            }

            if include_deepseek_analysis:
                result.update({
                    'deepseek_trending_analysis': deepseek_analysis.get('trending_news', ''),
                    'deepseek_risk_assessment': deepseek_analysis.get('risk_assessment', '')
                })

            # Save output files
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_dir = Path('outputs')
            output_dir.mkdir(exist_ok=True)

            # Save RSS data
            rss_file = output_dir / f'rss_financial_news_{timestamp}.json'
            with open(rss_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\n[SAVED] {rss_file.name}")

            # Save DeepSeek analysis files
            if include_deepseek_analysis:
                if result.get('deepseek_trending_analysis'):
                    analysis_file = output_dir / f'deepseek_rss_trending_analysis_{timestamp}.txt'
                    with open(analysis_file, 'w', encoding='utf-8') as f:
                        f.write("DEEPSEEK AI RSS NEWS ANALYSIS\n")
                        f.write("="*40 + "\n\n")
                        f.write(result['deepseek_trending_analysis'])
                    print(f"[SAVED] {analysis_file.name}")
                
                if result.get('deepseek_risk_assessment'):
                    risk_file = output_dir / f'deepseek_risk_assessment_{timestamp}.txt'
                    with open(risk_file, 'w', encoding='utf-8') as f:
                        f.write("DEEPSEEK AI RISK ASSESSMENT\n")
                        f.write("="*40 + "\n\n")
                        f.write(result['deepseek_risk_assessment'])
                    print(f"[SAVED] {risk_file.name}")

            return result

        except Exception as e:
            print(f"\n[ERROR] Workflow failed: {e}")
            raise

    async def collect_macro_and_technical_data(self, time_horizon: str = 'day') -> Dict:
        """
        Collect macro economic and technical data from FMP and FRED
        """
        print("\n[MACRO] Collecting financial and economic data...")
        data = {
            'fmp': {},
            'fred': {},
            'gold': {},
            'timestamp': datetime.now().isoformat()
        }

        # Initialize clients
        fmp = FMPStableClient(FMP_API_KEY)
        fred = FREDClient(FRED_API_KEY)

        # 1. FMP Data
        print("        Fetching FMP market data...")
        
        # Market Risk Premium
        try:
            mrp_list = fmp.market_risk_premium()
            usa_mrp = next((item for item in mrp_list if item.get('country') == 'United States'), {})
            data['fmp']['market_risk_premium'] = usa_mrp
        except Exception as e:
            print(f"        [WARNING] FMP Market Risk Premium failed: {e}")

        # Gold Price
        try:
            print("        Fetching Gold (GLD) price...")
            gold = fmp.quote('GLD')
            data['gold'] = gold[0] if gold else {}
        except Exception as e:
            print(f"        [WARNING] FMP Gold Price failed: {e}")

        # 2. FRED Data
        try:
            print("        Fetching FRED economic data...")
            dashboard = fred.get_macro_dashboard()
            data['fred'] = dashboard
        except Exception as e:
            print(f"        [WARNING] FRED data collection failed: {e}")
            data['fred']['error'] = str(e)

        # Note: Sector snapshots, premium technicals, and FMP news endpoints are disabled for local runs

        print(f"[DONE] Macro and technical data collected")
        return data

    async def run_market_condition_analysis_with_deepseek(self, time_horizon: str = 'day',
                                                        include_deepseek_analysis: bool = True) -> Dict:
        """
        Run ONLY the market condition analysis workflow
        - Collects market movement data
        - Collects political news
        - Generates market analysis report
        - NO symbol specific analysis
        - NO risk assessment (unless part of market report)

        Args:
            time_horizon: Time period ('day', 'week', 'month')
            include_deepseek_analysis: Whether to include DeepSeek AI analysis

        Returns:
            Dictionary with market data and analysis
        """
        print("\n" + "="*80)
        print("MARKET CONDITION ANALYSIS WORKFLOW")
        print("="*80)
        print(f"Time horizon: {time_horizon}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"DeepSeek Analysis: {'Enabled' if include_deepseek_analysis else 'Disabled'}")
        print("="*80 + "\n")

        try:
            # Step 1: Market movement data
            print("[STEP 1] Collecting market movement data...")
            market_result = await self.collect_market_movement_data(['SPY', 'QQQ', 'DIA', 'IWM'], time_horizon)
            market_data = market_result.get('data', [])
            if market_result.get('data_check_result'):
                print(f"         {market_result.get('data_check_result')}")
            print(f"[DONE] Collected {len(market_data)} market movement posts")
            await asyncio.sleep(1)

            # Step 2: Political news
            print("\n[STEP 2] Collecting political news...")
            political_keywords = ['Fed', 'SEC', 'inflation', 'interest rates', 'tariff', 'regulation', 'Congress']
            political_result = await self.collect_political_news_data(political_keywords, time_horizon)
            political_data = political_result.get('data', [])
            if political_result.get('data_check_result'):
                print(f"         {political_result.get('data_check_result')}")
            print(f"[DONE] Collected {len(political_data)} political news posts")
            await asyncio.sleep(1)

            # Step 3: RSS News
            print("\n[STEP 3] Collecting RSS financial news...")
            rss_result = await self.scan_rss_feeds(time_horizon)
            rss_data = rss_result.get('articles', [])
            print(f"[DONE] Collected {len(rss_data)} RSS news articles")
            await asyncio.sleep(1)

            # Step 4: Macro and Technical Data
            print("\n[STEP 4] Collecting macro and technical data...")
            macro_data = await self.collect_macro_and_technical_data(time_horizon)
            await asyncio.sleep(1)

            # Step 5: DeepSeek AI Analysis
            deepseek_analysis = {}
            if include_deepseek_analysis:
                print("\n[DEEPSEEK STEP] Generating AI-powered market analysis report...")
                
                data_check_results = {
                    'market': market_result.get('data_check_result', ''),
                    'political': political_result.get('data_check_result', '')
                }
                
                try:
                    market_msg = data_check_results.get('market', '') + "\n" + data_check_results.get('political', '')
                    
                    # Pass macro_data and rss_data directly to the report generator
                    market_report = generate_market_analysis_report(
                        market_data, 
                        political_data, 
                        macro_data=macro_data,
                        rss_data=rss_data,
                        data_check_msg=market_msg
                    )
                    deepseek_analysis['market_analysis'] = market_report
                    print(f"[DONE] Generated market analysis report")
                except Exception as e:
                    print(f"[ERROR] DeepSeek analysis failed: {e}")
                    deepseek_analysis['error'] = str(e)

            print("\n" + "="*80)
            print("MARKET CONDITION ANALYSIS COMPLETED")
            print("="*80)

            result = {
                'market_data': market_data,
                'political_data': political_data,
                'rss_data': rss_data,
                'macro_data': macro_data,
                'timestamp': datetime.now().isoformat()
            }

            if include_deepseek_analysis:
                result.update({
                    'deepseek_market_analysis': deepseek_analysis.get('market_analysis', '')
                })

            # Save output files
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_dir = Path('outputs')
            output_dir.mkdir(exist_ok=True)

            # Save data
            data_file = output_dir / f'market_condition_data_{timestamp}.json'
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\n[SAVED] {data_file.name}")

            # Save DeepSeek analysis
            if include_deepseek_analysis and result.get('deepseek_market_analysis'):
                analysis_file = output_dir / f'deepseek_market_condition_analysis_{timestamp}.txt'
                with open(analysis_file, 'w', encoding='utf-8') as f:
                    f.write("DEEPSEEK AI MARKET CONDITION ANALYSIS\n")
                    f.write("="*40 + "\n\n")
                    f.write(result['deepseek_market_analysis'])
                print(f"[SAVED] {analysis_file.name}")

            return result

        except Exception as e:
            print(f"\n[ERROR] Workflow failed: {e}")
            raise

async def run_comprehensive_market_intelligence(time_horizon: str = 'week',
                                                include_deepseek_analysis: bool = True,
                                                max_reddit_posts: int = 100,
                                                max_rss_articles: int = 50) -> Dict:
    """
    COMPREHENSIVE ALL-IN-ONE WORKFLOW: Reddit + RSS + FMP

    Runs ALL data sources simultaneously without flags:
    1. Reddit trending news discovery
    2. RSS financial news scan
    3. FMP real-time market data
    4. Macro + technical indicators (FMP/FRED/Gold)

    Args:
        time_horizon: Time period ('day', 'week', 'month')
        include_deepseek_analysis: Whether to include DeepSeek AI analysis
        max_reddit_posts: Maximum Reddit posts to collect
        max_rss_articles: Maximum RSS articles to collect

    Returns:
        Dictionary with all collected data and comprehensive DeepSeek analysis
    """
    print("=" * 60)
    print("COMPREHENSIVE MARKET INTELLIGENCE WORKFLOW")
    print("=" * 60)
    print(f"Time Horizon: {time_horizon}")
    print(f"Sources: Reddit + RSS + FMP")
    print(f"DeepSeek Analysis: {'Yes' if include_deepseek_analysis else 'No'}")
    print()

    results = {
        'workflow_type': 'comprehensive',
        'time_horizon': time_horizon,
        'analysis_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'sources': {},
        'deepseek_analysis': {}
    }

    try:
        # STEP 1: REDDIT TRENDING DISCOVERY
        print("[1/4] REDDIT: Trending market news discovery...")
        reddit_result = await run_trending_market_news_with_deepseek(
            time_horizon=time_horizon,
            include_deepseek_analysis=False  # We'll do comprehensive analysis later
        )

        results['sources']['reddit'] = {
            'trending_posts': reddit_result.get('trending_posts', [])[:max_reddit_posts],
            'data_check_result': reddit_result.get('data_check_result', ''),
            'summary': reddit_result.get('summary', {}),
            'total_posts': len(reddit_result.get('trending_posts', []))
        }

        print(f"     [OK] Collected {results['sources']['reddit']['total_posts']} trending posts")

        # STEP 2: RSS FINANCIAL NEWS SCAN
        print("[2/4] RSS: Financial news scan...")

        # Use RedditIntelligenceWorkflow to scan RSS feeds
        workflow = RedditIntelligenceWorkflow()
        scan_result = await workflow.scan_rss_feeds(time_horizon, max_rss_articles)
        rss_data = scan_result.get('articles', [])
        rss_data_check = scan_result.get('data_check_result', '')
        
        if rss_data_check:
            print(f"     [INFO] {rss_data_check}")

        # Filter duplicates
        filtered_articles = []
        seen_titles = set()

        for article in rss_data:
            title = article.get('title', '').lower()
            if title not in seen_titles and len(filtered_articles) < max_rss_articles:
                seen_titles.add(title)
                filtered_articles.append(article)

        results['sources']['rss'] = {
            'articles': filtered_articles,
            'data_check_result': rss_data_check,
            'total_articles': len(filtered_articles),
            'sources_count': len(set(article.get('source', '') for article in filtered_articles))
        }

        print(f"     [OK] Collected {results['sources']['rss']['total_articles']} articles from {results['sources']['rss']['sources_count']} sources")

        # STEP 3: FMP MARKET DATA
        print("[3/5] FMP: Real-time market data...")
        fmp_data: Dict[str, Any] = {}

        try:
            from fmp_stable_client import create_fmp_stable_client
            client = create_fmp_stable_client(FMP_API_KEY)

            def _clean_quotes(quotes: List[Dict]) -> List[Dict]:
                cleaned: List[Dict[str, Any]] = []
                for quote in quotes:
                    symbol = quote.get('ticker') or quote.get('symbol') or quote.get('name')
                    price = quote.get('price') or quote.get('priceRealtime') or quote.get('lastSalePrice')
                    volume = quote.get('volume') or quote.get('avgVolume') or quote.get('volAvg')
                    change_pct = quote.get('changesPercentage') or quote.get('changePercent')
                    if not symbol or price in (None, 0):
                        continue
                    if volume is not None and volume < 10000:
                        continue
                    cleaned.append({
                        'symbol': symbol,
                        'price': round(float(price), 2) if isinstance(price, (int, float)) else price,
                        'changesPercentage': round(float(change_pct), 2) if isinstance(change_pct, (int, float)) else change_pct,
                        'volume': int(volume) if isinstance(volume, (int, float)) else volume
                    })
                return cleaned

            snapshot: List[Dict[str, Any]] = []
            active_quotes: List[Dict[str, Any]] = []

            try:
                active_quotes = client.most_actives()
            except Exception as active_error:
                print(f"     [WARNING] FMP most actives failed: {active_error}")

            if active_quotes:
                snapshot = _clean_quotes(active_quotes)

            if not snapshot:
                fallback_quotes = client.stock_list(limit=200)
                snapshot = _clean_quotes(fallback_quotes)

            snapshot = snapshot[:50]
            fmp_data['market_snapshot'] = snapshot

            print(f"     [OK] Retrieved {len(snapshot)} liquid symbols from FMP")

            # Fetch market status (Local Fallback)
            try:
                print("     [DEBUG] Checking local market status...")
                # client.market_hours() is failing with 403 on v3 endpoint
                # Using local time check as fallback
                now_utc = datetime.utcnow()
                # Trading hours: 14:30 - 21:00 UTC (Mon-Fri)
                is_weekday = now_utc.weekday() < 5
                start_min = 14 * 60 + 30
                end_min = 21 * 60
                curr_min = now_utc.hour * 60 + now_utc.minute
                is_open = is_weekday and (start_min <= curr_min <= end_min)
                
                market_status = {'isTheStockMarketOpen': is_open}
                fmp_data['market_status'] = market_status
                print(f"     [OK] Retrieved market status (Local): {'Open' if is_open else 'Closed'}")
            except Exception as status_error:
                print(f"     [WARNING] Market status check failed: {status_error}")

        except Exception as e:
            print(f"     [WARNING] FMP data retrieval failed: {str(e)}")
            fmp_data['error'] = str(e)

        results['sources']['fmp'] = fmp_data

        # STEP 4: MACRO + TECHNICAL DATA
        print("[4/5] MACRO: Economic and technical indicators...")
        macro_data = {}
        try:
            macro_data = await workflow.collect_macro_and_technical_data(time_horizon)
            results['sources']['macro'] = macro_data
            macro_sections = sum(bool(macro_data.get(section)) for section in ('fmp', 'fred', 'gold'))
            print(f"     [OK] Collected macro snapshot ({macro_sections} data blocks)")
        except Exception as e:
            print(f"     [WARNING] Macro data collection failed: {str(e)}")
            results['sources']['macro'] = {'error': str(e)}

        # STEP 5: COMPREHENSIVE DEEPSEEK ANALYSIS
        if include_deepseek_analysis:
            print("[5/5] DEEPSEEK: Comprehensive analysis...")

            # Prepare data for DeepSeek analysis
            reddit_posts = results['sources']['reddit']['trending_posts'][:20]  # Top 20 for analysis
            rss_articles = results['sources']['rss']['articles'][:15]  # Top 15 for analysis
            macro_snapshot = results['sources'].get('macro', {})

            deepseek_context = _prepare_comprehensive_analysis_context(
                reddit_posts, rss_articles, fmp_data, macro_snapshot, time_horizon,
                rss_data_check=results['sources']['rss'].get('data_check_result', '')
            )

            # Generate comprehensive analysis
            comprehensive_analysis = await generate_comprehensive_market_analysis(deepseek_context)

            results['deepseek_analysis'] = comprehensive_analysis

            print(f"     [OK] Generated comprehensive market analysis")
            print(f"     [OK] Identified {len(comprehensive_analysis.get('key_themes', []))} key themes")
            print(f"     [OK] Analyzed {len(comprehensive_analysis.get('market_signals', []))} market signals")

        # Display Results Summary
        print("\n" + "=" * 60)
        print("COMPREHENSIVE ANALYSIS COMPLETE")
        print("=" * 60)

        print(f"\n[DATA] DATA COLLECTION SUMMARY:")
        print(f"   Reddit Posts: {results['sources']['reddit']['total_posts']}")
        print(f"   RSS Articles: {results['sources']['rss']['total_articles']}")
        print(f"   RSS Sources: {results['sources']['rss']['sources_count']}")

        if 'market_snapshot' in fmp_data:
            print(f"   FMP Symbols: {len(fmp_data['market_snapshot'])}")

        macro_snapshot = results['sources'].get('macro', {})
        if macro_snapshot and not macro_snapshot.get('error'):
            print(f"   Macro Snapshot: {macro_snapshot.get('timestamp', 'available')}")
        elif macro_snapshot.get('error'):
            print(f"   Macro Snapshot: ERROR - {macro_snapshot['error']}")

        if include_deepseek_analysis and 'deepseek_analysis' in results:
            analysis = results['deepseek_analysis']
            print(f"\n[AI] DEEPSEEK ANALYSIS:")
            print(f"   Market Sentiment: {analysis.get('overall_sentiment', 'Unknown')}")
            print(f"   Key Themes: {len(analysis.get('key_themes', []))}")
            print(f"   Market Signals: {len(analysis.get('market_signals', []))}")
            print(f"   Risk Level: {analysis.get('risk_assessment', {}).get('overall_risk_level', 'Unknown')}")

        reddit_posts = results['sources']['reddit'].get('trending_posts', [])
        rss_articles = results['sources']['rss'].get('articles', [])
        total_posts = results['sources']['reddit']['total_posts']
        total_articles = results['sources']['rss']['total_articles']

        def _avg_score(items: List[Dict], key: str) -> float:
            scores = [item.get(key) for item in items if isinstance(item.get(key), (int, float))]
            if not scores:
                return 0.0
            return sum(scores) / len(scores)

        summary = {
            'total_posts_collected': total_posts + total_articles,
            'by_type': {
                'reddit_trending': total_posts,
                'rss_articles': total_articles,
                'fmp_market_snapshot': len(results['sources'].get('fmp', {}).get('market_snapshot', []) or [])
            },
            'average_credibility_scores': {
                'reddit': round(_avg_score(reddit_posts, 'credibility_score'), 2) if reddit_posts else 0,
                'rss': round(_avg_score(rss_articles, 'credibility_score'), 2) if rss_articles else 0
            },
            'top_symbols': get_top_mentioned_symbols(reddit_posts),
            'collection_timestamp': results['analysis_timestamp'],
            'macro_snapshot_timestamp': results.get('sources', {}).get('macro', {}).get('timestamp'),
            'market_status': results.get('sources', {}).get('fmp', {}).get('market_status'),
            'generated_at': datetime.utcnow().isoformat() + 'Z'
        }

        top_insights = build_insights_from_posts(reddit_posts + rss_articles, limit=20)

        results['summary'] = summary
        results['top_insights'] = top_insights

        analysis = results.get('deepseek_analysis', {})
        market_text = analysis.get('raw_analysis', '')
        risk_section = analysis.get('risk_assessment', {})
        key_risks = risk_section.get('key_risks') or []
        opportunities = risk_section.get('opportunities') or []

        risk_lines = []
        if risk_section.get('overall_risk_level'):
            risk_lines.append(f"Overall Risk Level: {risk_section['overall_risk_level']}")
        risk_lines.extend(f"- Risk: {risk}" for risk in key_risks)
        risk_lines.extend(f"- Opportunity: {opp}" for opp in opportunities)
        risk_text = "\n".join(risk_lines)

        actionable = analysis.get('actionable_insights') or []
        actionable = analysis.get('actionable_insights') or []
        symbol_analyses = {}
        for idx, insight in enumerate(actionable, 1):
            if ':' in insight:
                parts = insight.split(':', 1)
                key = parts[0].strip()
                # Clean up key if it has bullet points or bold markers
                key = key.replace('*', '').replace('-', '').strip()
                val = parts[1].strip()
                symbol_analyses[key] = val
            else:
                symbol_analyses[f"Insight {idx}"] = insight

        results['deepseek_market_analysis'] = market_text
        results['deepseek_symbol_analyses'] = symbol_analyses
        results['deepseek_risk_assessment'] = risk_text

        # Save output files
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = Path('outputs')
        output_dir.mkdir(exist_ok=True)

        # Save Reddit data
        reddit_data = results.get('sources', {}).get('reddit', {})
        reddit_file = output_dir / f'comprehensive_reddit_data_{timestamp}.json'
        with open(reddit_file, 'w', encoding='utf-8') as f:
            json.dump({
                'trending_posts': reddit_data.get('trending_posts', []),
                'summary': results.get('summary', {}),
                'total_posts': reddit_data.get('total_posts', 0),
                'timestamp': results.get('analysis_timestamp', ''),
                'deepseek_market_analysis': results.get('deepseek_market_analysis', ''),
                'deepseek_symbol_analyses': results.get('deepseek_symbol_analyses', {}),
                'deepseek_risk_assessment': results.get('deepseek_risk_assessment', '')
            }, f, indent=2, ensure_ascii=False)
        print(f"\n[SAVED] {reddit_file.name}")

        # Save RSS data
        rss_data = results.get('sources', {}).get('rss', {})
        rss_file = output_dir / f'comprehensive_rss_data_{timestamp}.json'
        with open(rss_file, 'w', encoding='utf-8') as f:
            json.dump({
                'articles': rss_data.get('articles', []),
                'total_articles': rss_data.get('total_articles', 0),
                'sources_count': rss_data.get('sources_count', 0),
                'timestamp': results.get('analysis_timestamp', '')
            }, f, indent=2, ensure_ascii=False)
        print(f"[SAVED] {rss_file.name}")

        # Save FMP data
        fmp_data = results.get('sources', {}).get('fmp', {})
        fmp_file = output_dir / f'comprehensive_fmp_data_{timestamp}.json'
        with open(fmp_file, 'w', encoding='utf-8') as f:
            json.dump(fmp_data, f, indent=2, ensure_ascii=False)
        print(f"[SAVED] {fmp_file.name}")

        # Save macro data
        macro_snapshot = results.get('sources', {}).get('macro')
        if macro_snapshot:
            macro_file = output_dir / f'comprehensive_macro_data_{timestamp}.json'
            with open(macro_file, 'w', encoding='utf-8') as f:
                json.dump(macro_snapshot, f, indent=2, ensure_ascii=False)
            print(f"[SAVED] {macro_file.name}")

        # Save DeepSeek comprehensive analysis
        if include_deepseek_analysis and 'deepseek_analysis' in results:
            analysis = results['deepseek_analysis']
            analysis_file = output_dir / f'deepseek_comprehensive_analysis_{timestamp}.txt'
            with open(analysis_file, 'w', encoding='utf-8') as f:
                run_timestamp = results.get('analysis_timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                header = [
                    "DEEPSEEK AI COMPREHENSIVE MARKET ANALYSIS",
                    f"Generated At: {run_timestamp}",
                    f"Time Horizon: {results.get('time_horizon', time_horizon)}",
                    "",
                ]
                f.write("\n".join(header))
                f.write(analysis.get('raw_analysis', ''))
            print(f"[SAVED] {analysis_file.name}")

        overview_file = output_dir / f'comprehensive_overview_{timestamp}.json'
        with open(overview_file, 'w', encoding='utf-8') as f:
            json.dump({
                'summary': summary,
                'top_insights': top_insights,
                'deepseek_market_analysis': results.get('deepseek_market_analysis', ''),
                'deepseek_symbol_analyses': results.get('deepseek_symbol_analyses', {}),
                'deepseek_risk_assessment': results.get('deepseek_risk_assessment', '')
            }, f, indent=2, ensure_ascii=False)
        print(f"[SAVED] {overview_file.name}")

        saved_files: Dict[str, Path] = {
            'reddit': reddit_file,
            'rss': rss_file,
            'fmp': fmp_file,
            'overview': overview_file
        }
        if macro_snapshot:
            saved_files['macro'] = macro_file
        if include_deepseek_analysis and 'analysis_file' in locals():
            saved_files['deepseek'] = analysis_file

        if upload_outputs_to_gcs({
            'summary': summary,
            'top_insights': top_insights,
            'deepseek_market_analysis': results.get('deepseek_market_analysis', ''),
            'deepseek_symbol_analyses': results.get('deepseek_symbol_analyses', {}),
            'deepseek_risk_assessment': results.get('deepseek_risk_assessment', '')
        }, timestamp, saved_files, output_dir):
            gcs_prefix_display = f"{GCS_DEST_PREFIX}/" if GCS_DEST_PREFIX else ''
            print(f"[UPLOAD] Synced comprehensive outputs to gs://{GCS_BUCKET_NAME}/{gcs_prefix_display}*")

        return results

    except Exception as e:
        print(f"[ERROR] Comprehensive workflow failed: {str(e)}")
        results['error'] = str(e)
        return results

def _prepare_comprehensive_analysis_context(reddit_posts: List[Dict], rss_articles: List[Dict],
                                           fmp_data: Dict, macro_data: Dict, time_horizon: str,
                                           rss_data_check: str = "") -> str:
    """Prepare comprehensive context for DeepSeek analysis"""

    context_parts = [
        f"COMPREHENSIVE MARKET INTELLIGENCE ANALYSIS",
        f"Time Horizon: {time_horizon}",
        f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "=== REDDIT TRENDING DISCUSSIONS ==="
    ]

    # Add Reddit posts
    for i, post in enumerate(reddit_posts[:15], 1):
        context_parts.append(
            f"{i}. {post.get('title', 'No title')} "
            f"(Score: {post.get('ai_relevance_score', 0):.2f}, "
            f"Comments: {post.get('comment_count', 0)})"
        )

    context_parts.extend([
        "",
        "=== RSS FINANCIAL NEWS ==="
    ])
    
    if rss_data_check:
        context_parts.append(f"Data Freshness Note: {rss_data_check}")

    # Add RSS articles
    for i, article in enumerate(rss_articles[:10], 1):
        context_parts.append(
            f"{i}. {article.get('title', 'No title')} "
            f"({article.get('source', 'Unknown')}, "
            f"Credibility: {article.get('credibility_score', 0):.1f}/10)"
        )

    context_parts.extend([
        "",
        "=== FMP MARKET DATA ==="
    ])

    # Add FMP market data
    if 'market_indices' in fmp_data:
        context_parts.append("Market Indices:")
        for index in fmp_data['market_indices'][:5]:
            context_parts.append(f"  - {index}")

    if 'top_movers' in fmp_data:
        movers = fmp_data['top_movers']
        context_parts.append("Top Gainers:")
        for gainer in movers.get('gainers', [])[:3]:
            context_parts.append(f"  - {gainer}")
        context_parts.append("Top Losers:")
        for loser in movers.get('losers', [])[:3]:
            context_parts.append(f"  - {loser}")

    stock_list = fmp_data.get('market_snapshot', [])
    if stock_list:
        context_parts.append("Top FMP Market Snapshot:")
        for stock in stock_list[:5]:
            context_parts.append(
                (
                    f"  - {stock.get('symbol', 'N/A')}: ${stock.get('price', 'N/A')} "
                    f"({stock.get('changesPercentage', '0')}%) | Vol: {stock.get('volume', 'N/A')}"
                )
            )

    context_parts.extend([
        "",
        "=== MACRO & TECHNICAL DATA ==="
    ])

    macro_fmp = macro_data.get('fmp', {}) if macro_data else {}
    macro_fred = macro_data.get('fred', {}) if macro_data else {}

    if macro_fmp.get('market_risk_premium'):
        mrp = macro_fmp['market_risk_premium']
        context_parts.append(
            f"US Equity Risk Premium: {mrp.get('totalEquityRiskPremium', 'N/A')}% | Risk-Free: {mrp.get('riskFreeRate', 'N/A')}%"
        )

    if macro_fmp.get('sector_performance'):
        context_parts.append("Top Sector Performance (FMP):")
        for sector in macro_fmp['sector_performance'][:3]:
            context_parts.append(f"  - {sector.get('sector', 'Unknown')}: {sector.get('changesPercentage', 'N/A')}%")

    spy_data = macro_fmp.get('spy_technicals', {})
    if spy_data:
        context_parts.append(
            "SPY Technicals: "
            f"RSI {spy_data.get('rsi', {}).get('value', 'N/A')}, "
            f"SMA50 {spy_data.get('sma50', {}).get('value', 'N/A')}, "
            f"SMA200 {spy_data.get('sma200', {}).get('value', 'N/A')}"
        )

    if macro_data.get('gold'):
        gold_quote = macro_data['gold']
        context_parts.append(f"Gold (GLD) Price: {gold_quote.get('price', gold_quote.get('previousClose', 'N/A'))}")

    def _fred_line(key: str, label: str) -> Optional[str]:
        metric = macro_fred.get(key, {})
        if metric:
            value = metric.get('value', 'N/A')
            change = metric.get('change', '')
            if change:
                return f"{label}: {value} ({change})"
            return f"{label}: {value}"
        return None

    fred_lines = [
        _fred_line('inflation_cpi', 'Inflation (CPI)'),
        _fred_line('fed_funds', 'Fed Funds Rate'),
        _fred_line('10y_treasury', '10Y Treasury Yield'),
        _fred_line('vix', 'VIX'),
        _fred_line('unemployment', 'Unemployment Rate')
    ]

    fred_lines = [line for line in fred_lines if line]
    context_parts.extend(fred_lines)

    context_parts.extend([
        "",
        "=== ANALYSIS TASKS ===",
        "1. MARKET SENTIMENT: What is the overall market sentiment (Bullish/Bearish/Neutral)?",
        "2. KEY THEMES: What are the major themes/topics across ALL sources?",
        "3. MARKET SIGNALS: What are the important market signals and catalysts?",
        "4. RISK ASSESSMENT: What are the primary risks and opportunities?",
        "5. ACTIONABLE INSIGHTS: What should investors/traders watch or do? (Format: 'SYMBOL: Insight' or 'SECTOR: Insight')",
        "",
        "Provide specific, actionable analysis combining insights from all data sources."
    ])

    return "\n".join(context_parts)

def get_deepseek_client() -> AsyncOpenAI:
    """Create and return AsyncOpenAI client configured for DeepSeek API"""
    api_key = os.environ.get('DEEPSEEK_API_KEY')
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY not found in environment variables or .env file")
    base_url = 'https://api.deepseek.com/v1'
    return AsyncOpenAI(api_key=api_key, base_url=base_url)

async def generate_comprehensive_market_analysis(context: str) -> Dict:
    """Generate comprehensive market analysis using DeepSeek"""

    try:
        client = get_deepseek_client()

        messages = [
            {
                "role": "system",
                "content": "You are a senior market analyst providing comprehensive investment intelligence. Analyze the provided data from Reddit discussions, RSS financial news, and real-time market data to deliver actionable insights. Note that Reddit users are primarily retail traders, so sentiment may reflect retail behavior rather than institutional moves."
            },
            {
                "role": "user",
                "content": context
            }
        ]

        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            max_tokens=4000,
            temperature=0.3
        )

        analysis_text = response.choices[0].message.content

        # Parse the analysis into structured format
        analysis = {
            'raw_analysis': analysis_text,
            'overall_sentiment': 'Neutral',
            'key_themes': [],
            'market_signals': [],
            'risk_assessment': {
                'overall_risk_level': 'Medium',
                'key_risks': [],
                'opportunities': []
            },
            'actionable_insights': []
        }

        # Extract key sections from the analysis
        lines = analysis_text.split('\n')
        current_section = None

        for line in lines:
            line = line.strip()

            # Look for sentiment indicators
            if any(word in line.lower() for word in ['bullish', 'bearish', 'neutral']):
                if 'bullish' in line.lower():
                    analysis['overall_sentiment'] = 'Bullish'
                elif 'bearish' in line.lower():
                    analysis['overall_sentiment'] = 'Bearish'

            # Track sections
            if 'key theme' in line.lower() or 'major theme' in line.lower():
                current_section = 'themes'
            elif 'market signal' in line.lower() or 'catalyst' in line.lower():
                current_section = 'signals'
            elif 'risk' in line.lower():
                current_section = 'risks'
            elif 'actionable' in line.lower() or 'insight' in line.lower():
                current_section = 'insights'

            # Extract bullet points
            elif line.startswith('•') or line.startswith('-') or line.startswith('*'):
                item = line.lstrip('•-* ').strip()
                if current_section == 'themes' and len(analysis['key_themes']) < 10:
                    analysis['key_themes'].append(item)
                elif current_section == 'signals' and len(analysis['market_signals']) < 10:
                    analysis['market_signals'].append(item)
                elif current_section == 'risks' and len(analysis['risk_assessment']['key_risks']) < 8:
                    analysis['risk_assessment']['key_risks'].append(item)
                elif current_section == 'insights' and len(analysis['actionable_insights']) < 8:
                    analysis['actionable_insights'].append(item)

        return analysis

    except Exception as e:
        return {
            'error': f"DeepSeek analysis failed: {str(e)}",
            'raw_analysis': '',
            'overall_sentiment': 'Unknown',
            'key_themes': [],
            'market_signals': [],
            'risk_assessment': {'overall_risk_level': 'Unknown', 'key_risks': [], 'opportunities': []},
            'actionable_insights': []
        }

def run_comprehensive_market_intelligence_sync(time_horizon: str = 'week',
                                               include_deepseek_analysis: bool = True) -> Dict:
    """
    Synchronous wrapper for comprehensive market intelligence workflow
    """
    try:
        loop = asyncio.get_running_loop()
        is_new_loop = False
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        is_new_loop = True

    try:
        return loop.run_until_complete(
            run_comprehensive_market_intelligence(
                time_horizon=time_horizon,
                include_deepseek_analysis=include_deepseek_analysis
            )
        )
    finally:
        if is_new_loop:
            loop.close()
            asyncio.set_event_loop(None)

# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def run_reddit_intelligence(stocks: List[str], time_horizon: str = 'day') -> Dict:
    """
    Run the complete Reddit intelligence collection workflow

    Args:
        stocks: List of stock symbols
        time_horizon: Time period ('day', 'week', 'month', 'year', 'all')

    Returns:
        Dictionary with all collected data and insights
    """
    workflow = RedditIntelligenceWorkflow()
    return await workflow.run_workflow(stocks, time_horizon)

async def run_reddit_intelligence_with_deepseek(stocks: List[str], time_horizon: str = 'day',
                                              include_deepseek_analysis: bool = True) -> Dict:
    """
    Run the complete Reddit intelligence workflow with DeepSeek AI analysis

    Args:
        stocks: List of stock symbols
        time_horizon: Time period ('day', 'week', 'month', 'year', 'all')
        include_deepseek_analysis: Whether to include DeepSeek AI analysis

    Returns:
        Dictionary with all collected data, insights, and DeepSeek analysis reports
    """
    workflow = RedditIntelligenceWorkflow()
    return await workflow.run_workflow_with_deepseek(stocks, time_horizon, include_deepseek_analysis)

def run_reddit_intelligence_sync(stocks: List[str], time_horizon: str = 'day') -> Dict:
    """
    Synchronous wrapper for the workflow

    Args:
        stocks: List of stock symbols
        time_horizon: Time period

    Returns:
        Dictionary with all collected data and insights
    """
    try:
        loop = asyncio.get_running_loop()
        is_new_loop = False
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        is_new_loop = True

    try:
        return loop.run_until_complete(run_reddit_intelligence(stocks, time_horizon))
    finally:
        if is_new_loop:
            loop.close()

def run_reddit_intelligence_with_deepseek_sync(stocks: List[str], time_horizon: str = 'day',
                                              include_deepseek_analysis: bool = True) -> Dict:
    """
    Synchronous wrapper for the workflow with DeepSeek AI analysis

    Args:
        stocks: List of stock symbols
        time_horizon: Time period
        include_deepseek_analysis: Whether to include DeepSeek AI analysis

    Returns:
        Dictionary with all collected data, insights, and DeepSeek analysis reports
    """
    try:
        loop = asyncio.get_running_loop()
        is_new_loop = False
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        is_new_loop = True

    try:
        return loop.run_until_complete(run_reddit_intelligence_with_deepseek(stocks, time_horizon, include_deepseek_analysis))
    finally:
        if is_new_loop:
            loop.close()

# =============================================================================
# KEYWORD WORKFLOW CONVENIENCE FUNCTIONS
# =============================================================================

async def run_keyword_intelligence_with_deepseek(keywords: List[str], time_horizon: str = 'day',
                                                include_deepseek_analysis: bool = True) -> Dict:
    """
    Run keyword-specific Reddit intelligence workflow with DeepSeek AI analysis
    (For analyzing stocks, commodities, crypto, or any keyword)

    Args:
        keywords: List of keywords to analyze (e.g., ['gold', 'oil', 'bitcoin', 'AAPL'])
        time_horizon: Time period ('day', 'week', 'month', 'year', 'all')
        include_deepseek_analysis: Whether to include DeepSeek AI analysis

    Returns:
        Dictionary with collected data, insights, and DeepSeek analysis reports
    """
    workflow = RedditIntelligenceWorkflow()
    return await workflow.run_keyword_workflow_with_deepseek(keywords, time_horizon, include_deepseek_analysis)

def run_keyword_intelligence_with_deepseek_sync(keywords: List[str], time_horizon: str = 'day',
                                               include_deepseek_analysis: bool = True) -> Dict:
    """
    Synchronous wrapper for the keyword workflow with DeepSeek AI analysis

    Args:
        keywords: List of keywords to analyze
        time_horizon: Time period
        include_deepseek_analysis: Whether to include DeepSeek AI analysis

    Returns:
        Dictionary with collected data, insights, and DeepSeek analysis reports
    """
    try:
        loop = asyncio.get_running_loop()
        is_new_loop = False
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        is_new_loop = True

    try:
        return loop.run_until_complete(run_keyword_intelligence_with_deepseek(keywords, time_horizon, include_deepseek_analysis))
    finally:
        if is_new_loop:
            loop.close()

async def run_trending_market_news_with_deepseek(time_horizon: str = 'day',
                                               include_deepseek_analysis: bool = True) -> Dict:
    """
    Run the AI-powered trending market news discovery workflow
    - NO hardcoded keywords
    - NO hardcoded rankings
    - AI discovers what's hot
    - AI ranks by relevance

    Args:
        time_horizon: Time period ('day', 'week', 'month')
        include_deepseek_analysis: Whether to include DeepSeek AI analysis

    Returns:
        Dictionary with trending news, AI insights, and analysis
    """
    workflow = RedditIntelligenceWorkflow()
    return await workflow.run_trending_market_news_with_deepseek(time_horizon, include_deepseek_analysis)

def run_trending_market_news_with_deepseek_sync(time_horizon: str = 'day',
                                              include_deepseek_analysis: bool = True) -> Dict:
    """
    Synchronous wrapper for the trending market news workflow

    Args:
        time_horizon: Time period
        include_deepseek_analysis: Whether to include DeepSeek AI analysis

    Returns:
        Dictionary with trending news and analysis
    """
    try:
        loop = asyncio.get_running_loop()
        is_new_loop = False
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        is_new_loop = True

    try:
        return loop.run_until_complete(run_trending_market_news_with_deepseek(time_horizon, include_deepseek_analysis))
    finally:
        if is_new_loop:
            loop.close()

async def run_rss_news_scan_with_deepseek(time_horizon: str = 'day',
                                        include_deepseek_analysis: bool = True) -> Dict:
    """
    Run the AI-powered RSS news scan workflow
    - NO hardcoded keywords
    - NO hardcoded rankings
    - AI discovers what's hot
    - AI ranks by relevance

    Args:
        time_horizon: Time period ('day', 'week', 'month')
        include_deepseek_analysis: Whether to include DeepSeek AI analysis

    Returns:
        Dictionary with RSS articles, AI insights, and analysis
    """
    workflow = RedditIntelligenceWorkflow()
    return await workflow.run_rss_news_scan_with_deepseek(time_horizon, include_deepseek_analysis)

def run_rss_news_scan_with_deepseek_sync(time_horizon: str = 'day',
                                       include_deepseek_analysis: bool = True) -> Dict:
    """
    Synchronous wrapper for the RSS news scan workflow

    Args:
        time_horizon: Time period
        include_deepseek_analysis: Whether to include DeepSeek AI analysis

    Returns:
        Dictionary with RSS articles and analysis
    """
    try:
        loop = asyncio.get_running_loop()
        is_new_loop = False
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        is_new_loop = True

    try:
        return loop.run_until_complete(run_rss_news_scan_with_deepseek(time_horizon, include_deepseek_analysis))
    finally:
        if is_new_loop:
            loop.close()

def run_market_condition_analysis_with_deepseek_sync(time_horizon: str = 'day',
                                                   include_deepseek_analysis: bool = True) -> Dict:
    """
    Synchronous wrapper for the market condition analysis workflow

    Args:
        time_horizon: Time period
        include_deepseek_analysis: Whether to include DeepSeek AI analysis

    Returns:
        Dictionary with market data and analysis
    """
    try:
        loop = asyncio.get_running_loop()
        is_new_loop = False
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        is_new_loop = True

    try:
        return loop.run_until_complete(RedditIntelligenceWorkflow().run_market_condition_analysis_with_deepseek(time_horizon, include_deepseek_analysis))
    finally:
        if is_new_loop:
            loop.close()

# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    print("Starting Reddit Intelligence Collection with DeepSeek AI Analysis...")
    print()
    print("Choose workflow type:")
    print("1. Stock Market Analysis (multiple stocks)")
    print("2. Keyword Analysis (specific stock/commodity/crypto)")
    print()

    try:
        workflow_type = input("Enter choice (1 or 2): ").strip()
        if workflow_type not in ['1', '2']:
            workflow_type = '1'
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)

    if workflow_type == '1':
        print("\nRunning Stock Market Analysis Workflow...")
        target_stocks = ['AMC', 'TSLA', 'NVDA', 'SPY', 'AAPL']
        time_horizon = 'week'
        result = run_reddit_intelligence_with_deepseek_sync(target_stocks, time_horizon, include_deepseek_analysis=True)
    else:
        print("\nRunning Keyword Analysis Workflow...")
        print("Enter keywords (comma-separated, e.g., 'gold,oil,bitcoin,AAPL'): ", end='')
        try:
            keywords_input = input().strip()
            target_keywords = [kw.strip() for kw in keywords_input.split(',') if kw.strip()]
            if not target_keywords:
                target_keywords = ['gold', 'oil', 'bitcoin']
        except KeyboardInterrupt:
            print("\nExiting...")
            sys.exit(0)

        time_horizon = 'week'
        result = run_keyword_intelligence_with_deepseek_sync(target_keywords, time_horizon, include_deepseek_analysis=True)

    # Display results
    print("\n" + "="*80)
    print("REDDIT INTELLIGENCE SUMMARY")
    print("="*80)

    summary = result['summary']

    print(f"\nTotal posts analyzed: {summary['total_posts_collected']}")

    if workflow_type == '1':
        print(f"\nBy category:")
        print(f"  - Market movements: {summary['by_type']['market_movements']}")
        print(f"  - Political news: {summary['by_type']['political_news']}")
        print(f"  - Credible analysis: {summary['by_type']['credible_analysis']}")

        print(f"\nAverage credibility scores:")
        print(f"  - Market: {summary['average_credibility_scores']['market']:.2f}")
        print(f"  - Political: {summary['average_credibility_scores']['political']:.2f}")
        print(f"  - Analysis: {summary['average_credibility_scores']['analysis']:.2f}")

        print(f"\nTop mentioned symbols:")
        for symbol, count in summary['top_symbols']:
            print(f"  - {symbol}: {count} mentions")
    else:
        print(f"\nAnalyzed keywords:")
        for kw, count in summary['top_keywords']:
            print(f"  - {kw}: {count} mentions")

        print(f"\nAverage credibility score: {summary['average_credibility_score']:.2f}")

    print(f"\nHIGH CREDIBILITY INSIGHTS (Score > 6.0): {len(result['high_credibility_insights'])}")

    for i, insight in enumerate(result['high_credibility_insights'][:5], 1):
        print(f"\n{i}. {insight['title'][:60]}...")
        print(f"   Source: r/{insight['source']} | Type: {insight['type']}")
        print(f"   Credibility: {insight['credibility_score']:.2f} | Composite: {insight['composite_score']:.2f}")
        if insight.get('symbol'):
            print(f"   Symbol: {insight['symbol']}")
        if insight.get('keyword'):
            print(f"   Keyword: {insight['keyword']}")

    # Display DeepSeek Analysis Results (if available)
    if 'deepseek_market_analysis' in result and result['deepseek_market_analysis']:
        print("\n" + "="*80)
        print("DEEPSEEK AI MARKET ANALYSIS REPORT")
        print("="*80)
        print(result['deepseek_market_analysis'])

    # Display Symbol or Keyword Analyses
    if 'deepseek_symbol_analyses' in result and result['deepseek_symbol_analyses']:
        print("\n" + "="*80)
        print("DEEPSEEK AI SYMBOL-SPECIFIC ANALYSES")
        print("="*80)
        for symbol, analysis in result['deepseek_symbol_analyses'].items():
            print(f"\n{symbol} ANALYSIS:")
            print("-" * 40)
            print(analysis)

    if 'deepseek_keyword_analyses' in result and result['deepseek_keyword_analyses']:
        print("\n" + "="*80)
        print("DEEPSEEK AI KEYWORD ANALYSES")
        print("="*80)
        for keyword, analysis in result['deepseek_keyword_analyses'].items():
            print(f"\n{keyword.upper()} ANALYSIS:")
            print("-" * 40)
            print(analysis)

    if 'deepseek_risk_assessment' in result and result['deepseek_risk_assessment']:
        print("\n" + "="*80)
        print("DEEPSEEK AI RISK ASSESSMENT REPORT")
        print("="*80)
        print(result['deepseek_risk_assessment'])

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path('outputs')
    output_dir.mkdir(exist_ok=True)

    result_file = output_dir / f"reddit_intelligence_{timestamp}.json"

    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # Also save DeepSeek reports as separate text files for easier reading
    if 'deepseek_market_analysis' in result and result['deepseek_market_analysis']:
        analysis_file = output_dir / f"deepseek_market_analysis_{timestamp}.txt"
        with open(analysis_file, 'w', encoding='utf-8') as f:
            f.write("DEEPSEEK AI MARKET ANALYSIS REPORT\n")
            f.write("="*40 + "\n\n")
            f.write(result['deepseek_market_analysis'])

    if 'deepseek_risk_assessment' in result and result['deepseek_risk_assessment']:
        risk_file = output_dir / f"deepseek_risk_assessment_{timestamp}.txt"
        with open(risk_file, 'w', encoding='utf-8') as f:
            f.write("DEEPSEEK AI RISK ASSESSMENT REPORT\n")
            f.write("="*40 + "\n\n")
            f.write(result['deepseek_risk_assessment'])

    if 'deepseek_symbol_analyses' in result and result['deepseek_symbol_analyses']:
        symbol_file = output_dir / f"deepseek_symbol_analyses_{timestamp}.txt"
        with open(symbol_file, 'w', encoding='utf-8') as f:
            f.write("DEEPSEEK AI SYMBOL-SPECIFIC ANALYSES\n")
            f.write("="*40 + "\n\n")
            for symbol, analysis in result['deepseek_symbol_analyses'].items():
                f.write(f"\n{symbol} ANALYSIS:\n")
                f.write("-" * 40 + "\n")
                f.write(analysis + "\n")

    if 'deepseek_keyword_analyses' in result and result['deepseek_keyword_analyses']:
        keyword_file = output_dir / f"deepseek_keyword_analyses_{timestamp}.txt"
        with open(keyword_file, 'w', encoding='utf-8') as f:
            f.write("DEEPSEEK AI KEYWORD ANALYSES\n")
            f.write("="*40 + "\n\n")
            for keyword, analysis in result['deepseek_keyword_analyses'].items():
                f.write(f"\n{keyword.upper()} ANALYSIS:\n")
                f.write("-" * 40 + "\n")
                f.write(analysis + "\n")

    print(f"\n[SAVED] Results saved to: {result_file}")
    print(f"Total insights: {len(result['top_insights'])}")
    print(f"High credibility: {len(result['high_credibility_insights'])}")

    reports_count = len([r for r in [result.get('deepseek_market_analysis'), result.get('deepseek_risk_assessment')] if r])
    reports_count += len(result.get('deepseek_symbol_analyses', {}))
    reports_count += len(result.get('deepseek_keyword_analyses', {}))

    if 'deepseek_market_analysis' in result:
        print(f"DeepSeek Analysis Reports: {reports_count} files generated")
