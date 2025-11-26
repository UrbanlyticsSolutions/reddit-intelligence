# Reddit Intelligence + DeepSeek AI - Complete Workflow Guide

## Local-Only Mode

- Cloud uploads are disabled unless you export `ENABLE_GCS_UPLOADS=true` alongside your bucket credentials. Leave it unset to keep every run on your workstation.
- GitHub Actions deploys are gated by `ENABLE_CLOUD_DEPLOY`/`ENABLE_SCHEDULED_RELEASES` in `.github/workflows/`. Both default to `'false'`, so no jobs will touch GCP until you opt back in.

Run `python run_workflow.py ...` locally and review the generated files under `outputs/`.

## 🚀 THREE POWERFUL WORKFLOWS

### 1. **AI-Powered Trending News Discovery** ⭐ NEW!
**Discovers what's hot automatically - NO keywords needed!**

```bash
python run_workflow.py --trending --horizon day
```

**Features:**
- ✅ NO hardcoded keywords
- ✅ NO hardcoded rankings
- ✅ AI discovers trending topics
- ✅ AI ranks by relevance
- ✅ 14 financial subreddits automatically scanned
- ✅ Dynamic credibility scoring
- ✅ DeepSeek generates actionable insights

**What it finds:**
- Home Depot cuts outlook
- Global recession fears
- Bitcoin drops
- Market-moving news
- Trending stocks
- Emerging themes

---

### 2. **Keyword Analysis**
**Analyze specific topics you choose**

```bash
# Analyze commodities
python run_workflow.py --keywords gold oil bitcoin --horizon week

# Analyze specific stocks
python run_workflow.py --keywords AAPL TSLA --horizon day

# Analyze anything!
python run_workflow.py --keywords recession inflation fed --horizon week
```

**Perfect for:**
- Commodities (gold, oil, silver, copper, wheat, corn)
- Crypto (bitcoin, ethereum, altcoins)
- Specific stocks as keywords (AAPL, TSLA, NVDA)
- Themes (inflation, recession, AI boom, fed policy)
- Sectors (banking, tech, energy, healthcare)

---

### 3. **Stock Market Analysis**
**Broad market analysis across multiple stocks**

```bash
python run_workflow.py --stocks GME TSLA NVDA AAPL --horizon week
```

**Includes:**
- Political news impact
- Credible expert analysis
- Symbol-specific investment analysis
- Risk assessment
- Market sentiment

---

## 🎯 PROGRAMMATIC USAGE

### AI-Powered Trending News Discovery
```python
from reddit_intelligence import run_trending_market_news_with_deepseek_sync

result = run_trending_market_news_with_deepseek_sync(
    time_horizon='day',
    include_deepseek_analysis=True
)

trending_posts = result['trending_posts']
summary = result['summary']
trending_analysis = result['deepseek_trending_analysis']
risk_assessment = result['deepseek_risk_assessment']
```

### Keyword Analysis
```python
from reddit_intelligence import run_keyword_intelligence_with_deepseek_sync

result = run_keyword_intelligence_with_deepseek_sync(
    keywords=['gold', 'oil', 'bitcoin'],
    time_horizon='week',
    include_deepseek_analysis=True
)

market_report = result['deepseek_market_analysis']
keyword_analyses = result['deepseek_keyword_analyses']
risk_assessment = result['deepseek_risk_assessment']
```

### Stock Market Analysis
```python
from reddit_intelligence import run_reddit_intelligence_with_deepseek_sync

result = run_reddit_intelligence_with_deepseek_sync(
    stocks=['GME', 'TSLA', 'NVDA', 'AAPL'],
    time_horizon='week',
    include_deepseek_analysis=True
)

market_report = result['deepseek_market_analysis']
symbol_analyses = result['deepseek_symbol_analyses']
risk_assessment = result['deepseek_risk_assessment']
```

---

## 📊 CREDIBILITY SCORING

**Dynamic scoring (NOT hardcoded!) based on:**
- Engagement Quality (40%): Balanced upvotes/comments ratio
- Upvote Quality (25%): Community agreement level
- Recency Score (15%): Bonus for newer posts
- Content Depth (20%): Title length & effort indicators
- Flair Bonus (5%): Quality content marker

**Score Range:** 0.0 - 10.0

---

## 📁 OUTPUT FILES

### Trending News Workflow
- `reddit_trending_news_YYYYMMDD_HHMMSS.json`
- `deepseek_trending_analysis_YYYYMMDD_HHMMSS.txt`
- `deepseek_risk_assessment_YYYYMMDD_HHMMSS.txt`

### Keyword Analysis Workflow
- `reddit_intelligence_YYYYMMDD_HHMMSS.json`
- `deepseek_market_analysis_YYYYMMDD_HHMMSS.txt`
- `deepseek_keyword_analyses_YYYYMMDD_HHMMSS.txt`
- `deepseek_risk_assessment_YYYYMMDD_HHMMSS.txt`

### Stock Market Analysis Workflow
- `reddit_intelligence_YYYYMMDD_HHMMSS.json`
- `deepseek_market_analysis_YYYYMMDD_HHMMSS.txt`
- `deepseek_symbol_analyses_YYYYMMDD_HHMMSS.txt`
- `deepseek_risk_assessment_YYYYMMDD_HHMMSS.txt`

---

## ⏰ TIME HORIZONS

- **day**: Last 24 hours (immediate sentiment)
- **week**: Last 7 days (recommended - balanced)
- **month**: Last 30 days (comprehensive trends)

---

## 🤖 AI ANALYSIS REPORTS

### Market Analysis Report
- Overall sentiment analysis
- Key trends and patterns
- Investment opportunities & risks
- Actionable recommendations

### Symbol/Keyword Analyses
- Individual stock/commodity/crypto analysis
- Sentiment (Bullish/Bearish/Neutral)
- Risk factors and catalysts
- Short-term and medium-term outlook

### Risk Assessment Report
- Market risk level
- Sector-specific concerns
- Early warning indicators
- Risk mitigation strategies

---

## 🎯 QUICK START

### Option 1: Manual Workflow (Recommended)
```bash
# AI discovers what's hot
python run_workflow.py --trending --horizon week

# Analyze specific topics
python run_workflow.py --keywords gold --horizon week

# Stock market analysis
python run_workflow.py --stocks TSLA NVDA --horizon week
```

### Option 2: Interactive Mode
```bash
python reddit_intelligence.py
# Choose: 1=Stock Market, 2=Keyword Analysis
```

### Option 3: Programmatic
```python
from reddit_intelligence import run_trending_market_news_with_deepseek_sync
result = run_trending_market_news_with_deepseek_sync(time_horizon='day')
```

---

## 🔥 FEATURES

✅ Real Reddit data collection from multiple subreddits
✅ Dynamic credibility scoring (no hardcoding)
✅ DeepSeek AI analysis for market insights
✅ Keyword-specific analysis (any topic!)
✅ AI-powered trending news discovery
✅ Comprehensive risk assessment
✅ JSON and text report outputs
✅ Both sync and async APIs
✅ 14 financial subreddits coverage
✅ Engagement + credibility + recency ranking

---

## 💡 USE CASES

**Trading:**
- Daily market sentiment check
- Identify momentum shifts
- Track trending stocks/topics

**Investing:**
- Long-term trend analysis
- Fundamental sentiment check
- Risk assessment

**Research:**
- Market intelligence gathering
- Competitive analysis
- Theme identification

**Monitoring:**
- Automated daily reports
- Alert for trending topics
- Market stress indicators

---

## ⚡ EXAMPLES

```bash
# What's hot in markets right now?
python run_workflow.py --trending --horizon day

# Gold investment thesis
python run_workflow.py --keywords gold --horizon week

# Crypto market analysis
python run_workflow.py --keywords bitcoin ethereum --horizon day

# Multiple stocks
python run_workflow.py --stocks AAPL MSFT GOOGL --horizon week

# No AI analysis (Reddit data only)
python run_workflow.py --keywords oil --no-deepseek
```

---

## 🎉 SUCCESS METRICS

**Latest Trending News Discovery:**
- 73 posts collected
- Average score: 616.7
- Average comments: 226.7
- Top topics: Home Depot warning, recession fears, Bitcoin drop

**Gold Keyword Analysis:**
- 19 posts collected
- Dynamic credibility: 0-10 scale
- AI sentiment: Neutral to slightly bearish
- Outlook: Cautiously bullish medium-term

---

**Ready to discover what's hot in markets? Start with trending news!**

```bash
python run_workflow.py --trending --horizon day
```