# Reddit Stock Intelligence + DeepSeek AI Analysis

## 📁 Project Structure

```
Z:\Code\Backend\Stock\Reddit\
├── reddit_intelligence.py        # Main workflow script
├── clients/                       # Reddit API client
├── outputs/                       # Generated reports and data
└── docs/                          # Documentation
    ├── README.md
    └── ...
```

## 🚀 Core Workflow Types

### 1. **Comprehensive Market Intelligence**
`python run_workflow.py --comprehensive --horizon day`

All-in-one pipeline covering Reddit trending posts, RSS finance feeds, FMP quotes, and a macro snapshot (FRED dashboard + gold quote). Generates JSON artifacts plus `deepseek_comprehensive_analysis_*.txt`.

### 2. **Stock Market Analysis Workflow**
Analyzes specific tickers (Reddit + political news + credible DD + DeepSeek symbol/risk reports).

### 3. **Keyword Analysis Workflow**
Runs the Reddit intelligence stack on arbitrary keywords (commodities, crypto, sectors, themes, etc.).

## 📊 Features

- ✅ Real Reddit data collection from multiple subreddits
- ✅ RSS ingest + AI topic discovery
- ✅ FMP quotes + macro snapshot (FRED dashboard, gold quote, equity risk premium)
- ✅ DeepSeek AI analysis for market + theme reports
- ✅ Symbol/keyword-specific insights when requested
- ✅ Comprehensive risk assessment
- ✅ JSON/text outputs saved under `outputs/`

## 🚀 Quick Start

### Run Interactive Workflow
```bash
python reddit_intelligence.py
```

Choose:
- **Option 1**: Stock Market Analysis (multiple stocks)
- **Option 2**: Keyword Analysis (specific stock/commodity/crypto)

### Programmatic Usage

#### Stock Market Analysis
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

#### Keyword Analysis ⭐
```python
from reddit_intelligence import run_keyword_intelligence_with_deepseek_sync

# Analyze commodities
result = run_keyword_intelligence_with_deepseek_sync(
    keywords=['gold', 'oil', 'bitcoin'],
    time_horizon='week',
    include_deepseek_analysis=True
)

market_report = result['deepseek_market_analysis']
keyword_analyses = result['deepseek_keyword_analyses']
risk_assessment = result['deepseek_risk_assessment']

# Analyze specific stocks
result = run_keyword_intelligence_with_deepseek_sync(
    keywords=['AAPL', 'TSLA'],
    time_horizon='day',
    include_deepseek_analysis=True
)
```

## 📝 API Configuration

**DeepSeek API Key**: Configured via environment variable `DEEPSEEK_API_KEY`

Set in `.env` file or GitHub Secrets for production deployment.

**Reddit Proxy (optional)**: Set `REDDIT_PROXY_URL` (or standard `HTTP(S)_PROXY`) if Reddit blocks the Cloud Run IP. All Reddit API calls will route through that proxy automatically.

## ☁️ Cloud Deployments (Currently Disabled)

- `ENABLE_GCS_UPLOADS` defaults to `false`, so workflow runs stay completely local. Set it to `true` (and provide `GCS_BUCKET_NAME`, `GCS_DEST_PREFIX`, and Google credentials) only when you explicitly want to sync artifacts to Cloud Storage.
- GitHub Actions workflows (`deploy.yml`, `schedule.yml`) now check `ENABLE_CLOUD_DEPLOY` and `ENABLE_SCHEDULED_RELEASES`. Both are hard-coded to `'false'`, which keeps Cloud Run deploys and scheduled jobs off. Flip either flag to `'true'` inside the workflow file when you are ready to push to GCP again.

With these guards in place you can run `python run_workflow.py ...` locally without hitting GCP or GitHub automation.

## 📤 Output Files

When you run the workflow, you'll get:

### For Stock Market Analysis
- `reddit_intelligence_YYYYMMDD_HHMMSS.json` - Complete dataset
- `deepseek_market_analysis_YYYYMMDD_HHMMSS.txt` - Market analysis
- `deepseek_symbol_analyses_YYYYMMDD_HHMMSS.txt` - Stock analyses
- `deepseek_risk_assessment_YYYYMMDD_HHMMSS.txt` - Risk report

### For Keyword Analysis
- `reddit_intelligence_YYYYMMDD_HHMMSS.json` - Complete dataset
- `deepseek_market_analysis_YYYYMMDD_HHMMSS.txt` - Market analysis
- `deepseek_keyword_analyses_YYYYMMDD_HHMMSS.txt` - Keyword analyses
- `deepseek_risk_assessment_YYYYMMDD_HHMMSS.txt` - Risk report

## 🔍 Examples

### Analyze Gold Market
```python
result = run_keyword_intelligence_with_deepseek_sync(
    keywords=['gold'],
    time_horizon='week'
)
# DeepSeek will analyze Reddit sentiment on gold prices, trends, and outlook
```

### Analyze Multiple Commodities
```python
result = run_keyword_intelligence_with_deepseek_sync(
    keywords=['gold', 'oil', 'silver', 'copper'],
    time_horizon='week'
)
# Get individual analysis for each commodity
```

### Analyze Crypto
```python
result = run_keyword_intelligence_with_deepseek_sync(
    keywords=['bitcoin', 'ethereum', 'crypto'],
    time_horizon='day'
)
# Track short-term crypto sentiment
```

## 📖 DeepSeek Analysis Reports

The AI generates three types of reports:

1. **Market Analysis Report**
   - Overall sentiment analysis
   - Key trends and patterns
   - Investment opportunities & risks
   - Actionable recommendations

2. **Symbol/Keyword Analyses**
   - Individual stock/commodity/crypto analysis
   - Sentiment (Bullish/Bearish/Neutral)
   - Risk factors and catalysts
   - Short-term and medium-term outlook

3. **Risk Assessment Report**
   - Market risk level
   - Sector-specific concerns
   - Early warning indicators
   - Risk mitigation strategies

## 🎯 Use Cases

### Stock Market Analysis
- Analyze market sentiment across multiple stocks
- Get political news impact on markets
- Track credible expert analysis

### Keyword Analysis
- **Commodities**: gold, oil, silver, copper, wheat, corn
- **Crypto**: bitcoin, ethereum, altcoins
- **Stocks**: AAPL, TSLA, NVDA (individual analysis)
- **Themes**: inflation, recession, Fed, AI boom
- **Sectors**: banking, tech, energy, healthcare

## 📊 Credibility Scoring

Posts are scored 0-10 based on source credibility:
- r/SecurityAnalysis: 9.5/10
- r/ValueInvesting: 9.0/10
- r/Economics: 8.5/10
- r/investing: 8.0/10
- r/StockMarket: 7.5/10
- r/stocks: 6.0/10
- r/wallstreetbets: 4.0/10

## 🆘 Need Help?

Run the interactive workflow:
```bash
python reddit_intelligence.py
```

The script will guide you through:
1. Choose workflow type (stocks or keywords)
2. Enter your keywords (for keyword analysis)
3. View real-time progress
4. Get comprehensive AI analysis

---

**Note**: The workflow now supports analyzing ANY keyword from Reddit, making it perfect for stocks, commodities, crypto, or any market topic!
