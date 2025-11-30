import sys
from reddit_intelligence import run_comprehensive_market_intelligence_sync

try:
    print("Starting analysis...")
    run_comprehensive_market_intelligence_sync(time_horizon='day', include_deepseek_analysis=True)
    print("Finished analysis.")
except Exception as e:
    print(f"Caught exception: {e}")
    import traceback
    traceback.print_exc()
