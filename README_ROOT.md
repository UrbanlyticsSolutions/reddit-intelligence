# Reddit Stock Intelligence + DeepSeek AI Analysis

## 📁 Folder Structure

```
Z:\Code\Backend\Stock\Reddit\
├── reddit_intelligence.py        # Main workflow script
├── clients/                       # Reddit API client
├── demos/                         # Demo and example scripts
│   ├── demo_complete_workflow.py  # Full workflow demonstration
│   └── test_output_demo.py        # Simple output demo
├── outputs/                       # Generated reports and data
│   ├── reddit_intelligence_demo_*.json
│   ├── deepseek_market_analysis_*.txt
│   ├── deepseek_symbol_analyses_*.txt
│   └── deepseek_risk_assessment_*.txt
└── docs/                          # Documentation
    ├── README.md
    ├── DEEPSEEK_INTEGRATION_COMPLETE.md
    ├── HOW_TO_USE_QWEN.md
    ├── COMPLETION_REPORT.md
    ├── qwen_output_examples.md
    └── requirements.txt
```

## 🚀 Quick Start

### Run Main Workflow
```bash
python reddit_intelligence.py
# Choose option 2 for DeepSeek AI Analysis
```

### Run Demo
```bash
python demos/demo_complete_workflow.py
```

### Programmatic Usage
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

## 📊 Features

- ✅ Real Reddit data collection from multiple subreddits
- ✅ Credibility scoring (0-10 scale) for posts
- ✅ DeepSeek AI analysis for market insights
- ✅ Symbol-specific investment analysis
- ✅ Comprehensive risk assessment
- ✅ JSON and text report outputs

## 📝 API Configuration

**DeepSeek API Key**: `sk-6c76c4fed1284aa2b1856cc59892ad08`

Configured in `reddit_intelligence.py` (line 55)

## 📖 Documentation

See `docs/` folder for:
- Complete integration guide
- Usage examples
- Output format documentation
