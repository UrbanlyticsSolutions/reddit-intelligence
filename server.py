#!/usr/bin/env python3
"""
Continuous Automation Server for Reddit Intelligence
====================================================

This script runs the main workflow (`main.py`) on a configurable schedule.
It ensures that the analysis runs continuously and handles errors gracefully.

Usage:
    python3 server.py [--interval MINUTES] [--test] [--daemon]

Features:
- Automatic restart on failure
- Comprehensive logging
- Signal handling for graceful shutdown
- Health check endpoint
- Automatic git push after successful runs
"""

import time
import subprocess
import sys
import argparse
import signal
import logging
import os
import json
from datetime import datetime, timedelta
from pathlib import Path

# Configure logging
logging.basicConfig(
    filename='automation.log',
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Add stdout handler for console output
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%H:%M:%S')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

# Health monitoring
server_stats = {
    'start_time': datetime.now(),
    'last_run': None,
    'last_success': None,
    'total_runs': 0,
    'successful_runs': 0,
    'failed_runs': 0
}

def update_stats(success=False):
    """Update server statistics."""
    server_stats['last_run'] = datetime.now()
    server_stats['total_runs'] += 1

    if success:
        server_stats['last_success'] = datetime.now()
        server_stats['successful_runs'] += 1
    else:
        server_stats['failed_runs'] += 1

    # Save stats to file
    try:
        with open('server_stats.json', 'w') as f:
            stats_copy = server_stats.copy()
            stats_copy['start_time'] = stats_copy['start_time'].isoformat()
            if stats_copy['last_run']:
                stats_copy['last_run'] = stats_copy['last_run'].isoformat()
            if stats_copy['last_success']:
                stats_copy['last_success'] = stats_copy['last_success'].isoformat()
            json.dump(stats_copy, f, indent=2)
    except Exception as e:
        logging.warning(f"Failed to save stats: {e}")

def get_uptime():
    """Get server uptime as formatted string."""
    uptime = datetime.now() - server_stats['start_time']
    hours, remainder = divmod(uptime.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"

def run_workflow(horizon='day'):
    """Run the main.py workflow."""
    logging.info(f"Starting workflow execution (Horizon: {horizon})...")
    start_time = time.time()

    try:
        # Run main.py using the same python interpreter
        # We use subprocess to isolate the workflow execution
        cmd = [sys.executable, "-u", "main.py", "--horizon", horizon]

        # Stream output to both log and console for better monitoring
        with open('automation.log', 'a') as log_file:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )

            # Stream output in real-time
            for line in process.stdout:
                log_file.write(line)
                log_file.flush()
                # Also output to console if it's important
                if any(keyword in line.lower() for keyword in ['error', 'failed', 'success', 'completed', 'workflow']):
                    print(line.strip())

            process.wait()

        duration = time.time() - start_time

        if process.returncode == 0:
            logging.info(f"Workflow completed successfully in {duration:.1f}s")
            update_stats(success=True)

            # Additional git push to ensure changes are committed
            try:
                logging.info("Performing additional git push...")
                subprocess.run(["git", "push"], check=True, capture_output=True)
                logging.info("Additional git push completed")
            except subprocess.CalledProcessError as e:
                logging.warning(f"Additional git push failed: {e}")

            return True
        else:
            logging.error(f"Workflow failed with exit code {process.returncode}")
            update_stats(success=False)
            return False

    except Exception as e:
        logging.error(f"Unexpected error running workflow: {e}")
        update_stats(success=False)
        return False

def print_status():
    """Print current server status."""
    uptime = get_uptime()
    success_rate = 0
    if server_stats['total_runs'] > 0:
        success_rate = (server_stats['successful_runs'] / server_stats['total_runs']) * 100

    logging.info(f"Status | Uptime: {uptime} | Runs: {server_stats['total_runs']} | Success: {server_stats['successful_runs']} | Rate: {success_rate:.1f}%")

def signal_handler(sig, frame):
    """Handle interrupt signals."""
    logging.info("Received shutdown signal. Exiting...")
    logging.info(f"Final stats - Total runs: {server_stats['total_runs']}, Success: {server_stats['successful_runs']}")
    sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description='Reddit Intelligence Automation Server')
    parser.add_argument('--interval', type=int, default=30, help='Interval between runs in minutes (default: 30)')
    parser.add_argument('--test', action='store_true', help='Run once and exit (for testing)')
    parser.add_argument('--daemon', action='store_true', help='Run in daemon mode with enhanced logging')
    parser.add_argument('--horizon', choices=['day', 'week'], default='day', help='Analysis horizon (default: day)')
    args = parser.parse_args()

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Log startup information
    logging.info("=" * 60)
    logging.info(f"REDDIT INTELLIGENCE AUTOMATION SERVER v2.0")
    logging.info(f"Interval: {args.interval}m | Horizon: {args.horizon} | Daemon: {args.daemon}")
    logging.info(f"Process ID: {os.getpid()}")
    logging.info("=" * 60)

    if args.test:
        logging.info("Running in TEST mode (one-off execution)")
        success = run_workflow(args.horizon)
        print_status()
        sys.exit(0 if success else 1)

    # Main Loop with enhanced monitoring
    consecutive_failures = 0
    max_consecutive_failures = 3

    while True:
        next_run = time.time() + (args.interval * 60)

        try:
            # Print status before each run
            print_status()

            # Run the workflow
            success = run_workflow(args.horizon)

            if success:
                consecutive_failures = 0
                logging.info("✓ Workflow completed successfully")
            else:
                consecutive_failures += 1
                logging.warning(f"✗ Workflow failed (consecutive failures: {consecutive_failures})")

                # If too many consecutive failures, increase sleep time
                if consecutive_failures >= max_consecutive_failures:
                    extended_sleep = min(args.interval * 2, 120)  # Cap at 2 hours
                    logging.warning(f"Too many failures, extending sleep to {extended_sleep} minutes")
                    next_run = time.time() + (extended_sleep * 60)

        except KeyboardInterrupt:
            signal_handler(None, None)
        except Exception as e:
            logging.error(f"Unexpected error in main loop: {e}")
            consecutive_failures += 1

        # Calculate sleep time
        sleep_seconds = max(0, next_run - time.time())
        next_run_dt = datetime.fromtimestamp(next_run)

        if args.daemon:
            logging.info(f"[DAEMON] Next run at {next_run_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            logging.info(f"Sleeping {int(sleep_seconds//60)}m {int(sleep_seconds%60)}s. Next at {next_run_dt.strftime('%H:%M:%S')}")

        try:
            time.sleep(sleep_seconds)
        except KeyboardInterrupt:
            signal_handler(None, None)

if __name__ == "__main__":
    main()
