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

        # --- History Management ---
        history_dir = Path('frontend/history')
        history_dir.mkdir(exist_ok=True)
        
        # Copy to history with original name
        history_file = history_dir / latest_file.name
        shutil.copy(latest_file, history_file)
        print(f"[OK] Archived to {history_file}")

        # Prune history (keep last 10)
        # Filter out hidden files (like ._ files on Mac)
        all_history_files = list(history_dir.glob('*.json'))
        valid_history_files = [f for f in all_history_files if not f.name.startswith('.')]
        
        history_files = sorted(valid_history_files, key=lambda p: p.stat().st_mtime, reverse=True)
        
        if len(history_files) > 10:
            for old_file in history_files[10:]:
                try:
                    old_file.unlink()
                    print(f"[CLEANUP] Removed old history file: {old_file.name}")
                except Exception as e:
                    print(f"[WARNING] Failed to remove old history file {old_file.name}: {e}")
            history_files = history_files[:10]

        # Generate history.json index
        import json
        history_index = []
        for f in history_files:
            if f.name.startswith('.'):
                continue
            # Try to extract timestamp from filename or use mtime
            # Filename format: comprehensive_reddit_data_YYYYMMDD_HHMMSS.json
            try:
                ts_str = f.stem.split('_')[-2] + '_' + f.stem.split('_')[-1]
                dt = datetime.strptime(ts_str, '%Y%m%d_%H%M%S')
                display_time = dt.strftime('%Y-%m-%d %H:%M')
            except:
                display_time = datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
            
            history_index.append({
                'filename': f.name,
                'timestamp': display_time
            })
        
        with open('frontend/history.json', 'w') as f:
            json.dump(history_index, f, indent=2)
        print(f"[OK] Updated frontend/history.json with {len(history_index)} entries")
        # --------------------------

        # 3. Deploy to GitHub
        if not args.no_deploy:
            print("\n[STEP 3] Deploying to GitHub...")
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
            try:
                print(f"\n[DEPLOY] Deploying to GitHub...")
                subprocess.run(["git", "add", "frontend/latest.json", "frontend/history.json", "frontend/history/"], check=True)
                subprocess.run(["git", "commit", "-m", f"Update market intelligence data: {timestamp}"], check=True)
                subprocess.run(["git", "push"], check=True)
                print("[DEPLOY] Successfully pushed to GitHub.")
            except subprocess.CalledProcessError as e:
                print(f"[ERROR] Git deployment failed: {e}")
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
