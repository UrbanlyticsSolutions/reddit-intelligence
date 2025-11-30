#!/usr/bin/env python3
"""
Main Workflow Script for Reddit Intelligence
============================================

This script runs the entire workflow:
1.  Executes the comprehensive market intelligence analysis (Reddit + RSS + FMP + DeepSeek).
2.  Updates the frontend data file (`frontend/latest.json`).
3.  Deploys the changes to GitHub (commits and pushes).

Usage:
    python main.py [--no-deploy] [--horizon day|week]

"""

import argparse
import sys
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from reddit_intelligence import run_comprehensive_market_intelligence_sync

def run_git_commands(commit_message: str):
    """Run git add, commit, and push."""
    try:
        print(f"\n[DEPLOY] Deploying to GitHub...")
        subprocess.run(["git", "add", "frontend/latest.json"], check=True)
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        subprocess.run(["git", "push"], check=True)
        print("[DEPLOY] Successfully pushed to GitHub.")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Git deployment failed: {e}")

def main():
    parser = argparse.ArgumentParser(description='Run Reddit Intelligence Workflow & Deploy')
    parser.add_argument('--no-deploy', action='store_true', help='Skip GitHub deployment')
    parser.add_argument('--horizon', choices=['day', 'week'], default='day', help='Time horizon (default: day)')
    args = parser.parse_args()

    print("=" * 60)
    print(f"STARTING MAIN WORKFLOW (Horizon: {args.horizon})")
    print("=" * 60)

    try:
        # 1. Run Comprehensive Analysis
        print("\n[STEP 1] Running Comprehensive Analysis...")
        result = run_comprehensive_market_intelligence_sync(
            time_horizon=args.horizon,
            include_deepseek_analysis=True
        )

        # 2. Update Frontend Data
        print("\n[STEP 2] Updating Frontend Data...")
        output_dir = Path('outputs')
        # Find the latest comprehensive json file
        json_files = list(output_dir.glob('comprehensive_reddit_data_*.json'))
        if not json_files:
            print("[ERROR] No output file found!")
            sys.exit(1)
        
        latest_file = max(json_files, key=lambda p: p.stat().st_mtime)
        target_file = Path('frontend/latest.json')
        
        shutil.copy(latest_file, target_file)
        print(f"[OK] Copied {latest_file.name} to {target_file}")

        # 3. Deploy to GitHub
        if not args.no_deploy:
            print("\n[STEP 3] Deploying to GitHub...")
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
            run_git_commands(f"Update market intelligence data: {timestamp}")
        else:
            print("\n[SKIP] Deployment skipped (--no-deploy).")

        print("\n" + "=" * 60)
        print("WORKFLOW COMPLETED SUCCESSFULLY")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] Workflow failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
