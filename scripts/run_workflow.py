#!/usr/bin/env python3
"""
Manual Usage Script for Reddit Intelligence Workflow

This script provides direct command-line access to both workflows without interactive prompts.
"""

import argparse
import sys
from datetime import datetime
from reddit_intelligence import (
    run_reddit_intelligence_with_deepseek_sync,
    run_keyword_intelligence_with_deepseek_sync,
    run_trending_market_news_with_deepseek_sync,
    run_rss_news_scan_with_deepseek_sync,
    run_comprehensive_market_intelligence_sync,
    run_market_condition_analysis_with_deepseek_sync
)

def main():
    parser = argparse.ArgumentParser(
        description='Reddit Intelligence with DeepSeek AI Analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Stock Market Analysis
  python run_workflow.py --stocks GME TSLA NVDA AAPL --horizon week

  # Keyword Analysis - Gold
  python run_workflow.py --keywords gold --horizon week

  # Multiple Keywords
  python run_workflow.py --keywords gold oil bitcoin --horizon day

  # Analyze Specific Stocks as Keywords
  python run_workflow.py --keywords AAPL TSLA --horizon day

  # AI-Powered Trending News Discovery (NO keywords needed!)
  python run_workflow.py --trending --horizon day

  # Trending News - Week
  python run_workflow.py --trending --horizon week

  # RSS Financial News Scan (NO keywords needed!)
  python run_workflow.py --rss --horizon day

  # RSS News - Week
  python run_workflow.py --rss --horizon week

  # ALL-IN-ONE Comprehensive Analysis (Reddit + RSS + FMP)
  python run_workflow.py --comprehensive --horizon week

  # Exclude DeepSeek Analysis (Reddit data only)
  python run_workflow.py --keywords gold --no-deepseek
        """
    )

    # Create mutually exclusive group for workflow type
    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument(
        '--stocks',
        nargs='+',
        help='Stock symbols for market analysis (e.g., GME TSLA NVDA)'
    )

    group.add_argument(
        '--keywords',
        nargs='+',
        help='Keywords for analysis (e.g., gold oil bitcoin AAPL TSLA)'
    )

    group.add_argument(
        '--trending',
        action='store_true',
        help='AI-powered trending market news discovery (NO keywords needed!)'
    )

    group.add_argument(
        '--rss',
        action='store_true',
        help='AI-powered RSS financial news scan (NO keywords needed!)'
    )

    group.add_argument(
        '--comprehensive',
        action='store_true',
        help='ALL-IN-ONE: Reddit + RSS + FMP comprehensive analysis (NO flags needed!)'
    )

    group.add_argument(
        '--market-condition',
        action='store_true',
        help='Market condition analysis ONLY (Market movements + Political news)'
    )

    # Optional arguments
    parser.add_argument(
        '--horizon',
        choices=['day', 'week', 'month'],
        default='week',
        help='Time horizon for analysis (default: week)'
    )

    parser.add_argument(
        '--no-deepseek',
        action='store_true',
        help='Skip DeepSeek AI analysis (Reddit data only)'
    )

    parser.add_argument(
        '--max-results',
        type=int,
        default=30,
        help='Maximum posts per keyword/stock (default: 30)'
    )

    parser.add_argument(
        '--output-dir',
        default='outputs',
        help='Output directory for reports (default: outputs)'
    )

    args = parser.parse_args()

    print("=" * 60)
    print("REDDIT INTELLIGENCE WITH DEEPSEEK AI ANALYSIS")
    print("=" * 60)

    include_deepseek = not args.no_deepseek

    try:
        if args.stocks:
            # Stock Market Analysis Workflow
            print(f"\n[STOCK] STOCK MARKET ANALYSIS")
            print(f"Stocks: {', '.join(args.stocks)}")
            print(f"Time Horizon: {args.horizon}")
            print(f"DeepSeek Analysis: {'Yes' if include_deepseek else 'No'}")

            result = run_reddit_intelligence_with_deepseek_sync(
                stocks=args.stocks,
                time_horizon=args.horizon,
                include_deepseek_analysis=include_deepseek
            )

            workflow_type = "stock"

        elif args.trending:
            # AI-Powered Trending Market News Discovery
            print(f"\n[TRENDING] AI-POWERED TRENDING NEWS DISCOVERY")
            print(f"Time Horizon: {args.horizon}")
            print(f"DeepSeek Analysis: {'Yes' if include_deepseek else 'No'}")
            print(f"Method: AI discovers what's hot (NO keywords!)")

            result = run_trending_market_news_with_deepseek_sync(
                time_horizon=args.horizon,
                include_deepseek_analysis=include_deepseek
            )

            workflow_type = "trending"

        elif args.rss:
            # AI-Powered RSS Financial News Scan
            print(f"\n[RSS] AI-POWERED RSS FINANCIAL NEWS SCAN")
            print(f"Time Horizon: {args.horizon}")
            print(f"DeepSeek Analysis: {'Yes' if include_deepseek else 'No'}")
            print(f"Method: AI scans RSS feeds (NO keywords!)")

            result = run_rss_news_scan_with_deepseek_sync(
                time_horizon=args.horizon,
                include_deepseek_analysis=include_deepseek
            )

            workflow_type = "rss"

        elif args.comprehensive:
            # ALL-IN-ONE Comprehensive Analysis (Reddit + RSS + FMP)
            print(f"\n[COMPREHENSIVE] ALL-IN-ONE MARKET INTELLIGENCE")
            print(f"Sources: Reddit + RSS + FMP")
            print(f"Time Horizon: {args.horizon}")
            print(f"DeepSeek Analysis: {'Yes' if include_deepseek else 'No'}")
            print(f"Method: All sources combined automatically")

            result = run_comprehensive_market_intelligence_sync(
                time_horizon=args.horizon,
                include_deepseek_analysis=include_deepseek
            )

            workflow_type = "comprehensive"

        elif args.market_condition:
            # Market Condition Analysis
            print(f"\n[MARKET] MARKET CONDITION ANALYSIS")
            print(f"Scope: Market Movements + Political News")
            print(f"Time Horizon: {args.horizon}")
            print(f"DeepSeek Analysis: {'Yes' if include_deepseek else 'No'}")

            result = run_market_condition_analysis_with_deepseek_sync(
                time_horizon=args.horizon,
                include_deepseek_analysis=include_deepseek
            )

            workflow_type = "market_condition"

        else:
            # Keyword Analysis Workflow
            print(f"\n[KEYWORD] KEYWORD ANALYSIS")
            print(f"Keywords: {', '.join(args.keywords)}")
            print(f"Time Horizon: {args.horizon}")
            print(f"DeepSeek Analysis: {'Yes' if include_deepseek else 'No'}")

            result = run_keyword_intelligence_with_deepseek_sync(
                keywords=args.keywords,
                time_horizon=args.horizon,
                include_deepseek_analysis=include_deepseek
            )

            workflow_type = "keyword"

        # Display Results Summary
        print(f"\n[OK] WORKFLOW COMPLETED")

        if workflow_type == "comprehensive":
            sources = result.get('sources', {})
            reddit_data = sources.get('reddit', {})
            rss_data = sources.get('rss', {})
            fmp_data = sources.get('fmp', {})

            print(f"Reddit Posts Collected: {reddit_data.get('total_posts', 0)}")
            print(f"RSS Articles Collected: {rss_data.get('total_articles', 0)}")
            print(f"RSS Sources: {rss_data.get('sources_count', 0)}")

            if 'market_indices' in fmp_data:
                print(f"FMP Market Indices: {len(fmp_data['market_indices'])}")
            if 'top_movers' in fmp_data:
                movers = fmp_data['top_movers']
                print(f"FMP Top Gainers: {len(movers.get('gainers', []))}")
                print(f"FMP Top Losers: {len(movers.get('losers', []))}")

            print(f"Analysis Timestamp: {result.get('analysis_timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}")

        elif workflow_type == "trending":
            summary = result.get('summary', {})
            print(f"Total Reddit Posts Collected: {summary.get('total_posts_collected', 0)}")
            print(f"Average Score: {summary.get('average_score', 0):.1f}")
            print(f"Average Comments: {summary.get('average_comments', 0):.1f}")
            print(f"Analysis Timestamp: {summary.get('collection_timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}")
        elif workflow_type == "rss":
            summary = result.get('summary', {})
            print(f"Total RSS Articles Collected: {summary.get('total_articles_collected', 0)}")
            print(f"Average Credibility: {summary.get('average_credibility', 0):.1f}/10")
            print(f"Sources: {len(summary.get('by_source', {}))}")
            print(f"Analysis Timestamp: {summary.get('collection_timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}")
        elif workflow_type == "market_condition":
            print(f"Market Movement Posts: {len(result.get('market_data', []))}")
            print(f"Political News Posts: {len(result.get('political_data', []))}")
            print(f"Analysis Timestamp: {result.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}")
        else:
            print(f"Total Reddit Posts Collected: {result.get('total_posts', 0)}")
            print(f"Data Credibility Range: {result.get('credibility_range', 'N/A')}")
            print(f"Analysis Timestamp: {result.get('analysis_timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}")

        # Display DeepSeek Analysis if available
        if include_deepseek:
            print(f"\n[REPORT] DEEPSEEK ANALYSIS GENERATED")

            if workflow_type == "comprehensive":
                analysis = result.get('deepseek_analysis', {})
                if analysis:
                    raw_analysis = analysis.get('raw_analysis', '')
                    if raw_analysis:
                        lines = raw_analysis.split('\n')
                        print(f"Comprehensive Analysis: {len(lines)} lines")

                    key_themes = analysis.get('key_themes', [])
                    if key_themes:
                        print(f"Key Themes: {len(key_themes)} identified")

                    market_signals = analysis.get('market_signals', [])
                    if market_signals:
                        print(f"Market Signals: {len(market_signals)} analyzed")

                    risk_assessment = analysis.get('risk_assessment', {})
                    if risk_assessment:
                        risk_level = risk_assessment.get('overall_risk_level', 'Unknown')
                        print(f"Risk Assessment: {risk_level} risk level")

            elif workflow_type == "trending":
                trending_analysis = result.get('deepseek_trending_analysis', '')
                if trending_analysis:
                    lines = str(trending_analysis).split('\n')
                    print(f"Trending Analysis: {len(lines)} lines")

                risk_assessment = result.get('deepseek_risk_assessment', '')
                if risk_assessment:
                    lines = risk_assessment.split('\n')
                    print(f"Risk Assessment: {len(lines)} lines")

            elif workflow_type == "rss":
                trending_analysis = result.get('deepseek_trending_analysis', '')
                if trending_analysis:
                    lines = str(trending_analysis).split('\n')
                    print(f"RSS News Analysis: {len(lines)} lines")

                risk_assessment = result.get('deepseek_risk_assessment', '')
                if risk_assessment:
                    lines = risk_assessment.split('\n')
                    print(f"Risk Assessment: {len(lines)} lines")

            elif workflow_type == "market_condition":
                market_analysis = result.get('deepseek_market_analysis', '')
                if market_analysis:
                    lines = market_analysis.split('\n')
                    print(f"Market Analysis: {len(lines)} lines")

            elif workflow_type == "stock":
                market_analysis = result.get('deepseek_market_analysis', '')
                if market_analysis:
                    lines = market_analysis.split('\n')
                    print(f"Market Analysis: {len(lines)} lines")

                symbol_analyses = result.get('deepseek_symbol_analyses', '')
                if symbol_analyses:
                    lines = str(symbol_analyses).split('\n')
                    print(f"Symbol Analyses: {len(lines)} lines")

                risk_assessment = result.get('deepseek_risk_assessment', '')
                if risk_assessment:
                    lines = risk_assessment.split('\n')
                    print(f"Risk Assessment: {len(lines)} lines")

            else:  # keyword workflow
                market_analysis = result.get('deepseek_market_analysis', '')
                if market_analysis:
                    lines = market_analysis.split('\n')
                    print(f"Market Analysis: {len(lines)} lines")

                keyword_analyses = result.get('deepseek_keyword_analyses', '')
                if keyword_analyses:
                    if isinstance(keyword_analyses, dict):
                        count = len(keyword_analyses)
                        print(f"Keyword Analyses: {count} keywords analyzed")
                    else:
                        lines = str(keyword_analyses).split('\n')
                        print(f"Keyword Analyses: {len(lines)} lines")

                risk_assessment = result.get('deepseek_risk_assessment', '')
                if risk_assessment:
                    lines = risk_assessment.split('\n')
                    print(f"Risk Assessment: {len(lines)} lines")

        # Display Top Findings
        if workflow_type == "comprehensive":
            reddit_posts = result.get('sources', {}).get('reddit', {}).get('trending_posts', [])
            rss_articles = result.get('sources', {}).get('rss', {}).get('articles', [])

            if reddit_posts:
                print(f"\n[TOP] TOP REDDIT POSTS:")
                for i, post in enumerate(reddit_posts[:3], 1):
                    score = post.get('ai_relevance_score', 0)
                    title = post.get('title', 'No title')[:80]
                    print(f"  {i}. [{score:.2f}] {title}...")

            if rss_articles:
                print(f"\n[TOP] TOP RSS ARTICLES:")
                for i, article in enumerate(rss_articles[:3], 1):
                    credibility = article.get('credibility_score', 0)
                    title = article.get('title', 'No title')[:80]
                    source = article.get('source', 'Unknown')
                    print(f"  {i}. [{credibility:.1f}/10] {title}... ({source})")

        elif workflow_type == "rss":
            top_articles = result.get('top_articles', [])
            if top_articles:
                print(f"\n[TOP] TOP RELEVANT ARTICLES:")
                for i, article in enumerate(top_articles[:3], 1):
                    print(f"  {i}. [{article.get('ai_relevance_score', 0):.2f}] {article.get('title', 'No title')[:80]}...")
        else:
            top_posts = result.get('top_posts', [])
            if top_posts:
                print(f"\n[TOP] TOP RELEVANT POSTS:")
                for i, post in enumerate(top_posts[:3], 1):
                    if workflow_type == "trending":
                        print(f"  {i}. [{post.get('ai_relevance_score', 0):.2f}] {post.get('title', 'No title')[:80]}...")
                    else:
                        print(f"  {i}. [{post.get('credibility_score', 0):.1f}/10] {post.get('title', 'No title')[:80]}...")

        # Display Output Files
        if include_deepseek:
            print(f"\n[FILES] OUTPUT FILES GENERATED:")
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            if workflow_type == "comprehensive":
                print(f"  • comprehensive_reddit_data_{timestamp}.json")
                print(f"  • comprehensive_rss_data_{timestamp}.json")
                print(f"  • comprehensive_fmp_data_{timestamp}.json")
                print(f"  • deepseek_comprehensive_analysis_{timestamp}.txt")

            elif workflow_type == "trending":
                print(f"  • reddit_trending_news_{timestamp}.json")
                print(f"  • deepseek_trending_analysis_{timestamp}.txt")
                print(f"  • deepseek_risk_assessment_{timestamp}.txt")
            elif workflow_type == "rss":
                print(f"  • rss_financial_news_{timestamp}.json")
                print(f"  • deepseek_rss_trending_analysis_{timestamp}.txt")
                print(f"  • deepseek_risk_assessment_{timestamp}.txt")
            elif workflow_type == "market_condition":
                print(f"  • market_condition_data_{timestamp}.json")
                print(f"  • deepseek_market_condition_analysis_{timestamp}.txt")
            elif workflow_type == "stock":
                print(f"  • reddit_intelligence_{timestamp}.json")
                print(f"  • deepseek_market_analysis_{timestamp}.txt")
                print(f"  • deepseek_symbol_analyses_{timestamp}.txt")
                print(f"  • deepseek_risk_assessment_{timestamp}.txt")
            else:  # keyword
                print(f"  • reddit_intelligence_{timestamp}.json")
                print(f"  • deepseek_market_analysis_{timestamp}.txt")
                print(f"  • deepseek_keyword_analyses_{timestamp}.txt")
                print(f"  • deepseek_risk_assessment_{timestamp}.txt")

        print(f"\n[DONE] Workflow completed successfully!")

    except KeyboardInterrupt:
        print(f"\n\n[INTERRUPTED] Workflow interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] ERROR: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()