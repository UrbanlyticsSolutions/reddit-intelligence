import time
import subprocess
import sys
import shutil
import os
import glob
from datetime import datetime, timedelta

def run_command(command):
    """Run a shell command and print output."""
    try:
        subprocess.run(command, check=True, shell=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {command}")
        print(e)

def is_trading_hours():
    """
    Check if current time is within trading hours (Mon-Fri, 14:30 - 21:00 UTC).
    """
    now = datetime.utcnow()
    
    # Check for weekend (Saturday=5, Sunday=6)
    if now.weekday() >= 5:
        return False

    # Calculate minutes from start of day
    current_minute = now.hour * 60 + now.minute
    
    # Trading hours: 14:30 (870 mins) to 21:00 (1260 mins) UTC
    start_minute = 14 * 60 + 30
    end_minute = 21 * 60
    
    return start_minute <= current_minute <= end_minute

def main():
    print("="*60)
    print("REDDIT INTELLIGENCE SERVER")
    print("="*60)
    print("Press Ctrl+C to stop the server.")
    
    while True:
        try:
            start_time = datetime.now()
            print(f"\n[{start_time.strftime('%Y-%m-%d %H:%M:%S')}] Starting workflow execution...")
            
            # 1. Run the workflow
            # Running with DeepSeek analysis enabled
            run_command("python run_workflow.py --comprehensive --horizon day")

            # 2. Find the latest output file
            list_of_files = glob.glob('outputs/comprehensive_reddit_data_*.json')
            
            if list_of_files:
                latest_file = max(list_of_files, key=os.path.getctime)
                print(f"Found latest output: {latest_file}")
                
                # 3. Copy to frontend directory
                shutil.copy(latest_file, 'frontend/latest.json')
                print("Updated frontend/latest.json")
                
                # 4. Push to GitHub
                print("Pushing updates to GitHub...")
                run_command("git add frontend/latest.json")
                
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # Use --allow-empty to avoid error if no changes
                run_command(f'git commit --allow-empty -m "Update market intelligence data: {timestamp}"')
                
                run_command("git push")
                print("Successfully pushed to GitHub.")
                
            else:
                print("Warning: No output file found in outputs/ directory.")

            # 5. Determine sleep duration
            if is_trading_hours():
                sleep_seconds = 1800  # 30 minutes
                mode = "TRADING HOURS"
            else:
                sleep_seconds = 7200  # 2 hours
                mode = "OFF HOURS"
            
            next_run = datetime.now() + timedelta(seconds=sleep_seconds)
            print(f"[{mode}] Sleeping for {sleep_seconds/60:.0f} minutes.")
            print(f"Next run scheduled for: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            
            time.sleep(sleep_seconds)

        except KeyboardInterrupt:
            print("\nServer stopped by user.")
            sys.exit(0)
        except Exception as e:
            print(f"\nUnexpected error: {e}")
            print("Retrying in 60 seconds...")
            time.sleep(60)

if __name__ == "__main__":
    main()
