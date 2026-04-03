#!/usr/bin/env python3
"""TikTok AI Video Automation - Main entry point."""

import argparse
import schedule
import time
from datetime import datetime

from config.settings import settings
from src.pipeline import run_pipeline


def daily_job():
    """Run the video pipeline once."""
    print(f"\n{'='*50}")
    print(f"Starting daily video generation at {datetime.now()}")
    print(f"{'='*50}\n")
    try:
        run_pipeline()
    except Exception as e:
        print(f"ERROR: Pipeline failed: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description="TikTok AI Video Automation")
    parser.add_argument(
        "--mode",
        choices=["once", "schedule", "test"],
        default="once",
        help="Run mode: 'once' for single run, 'schedule' for daily, 'test' for no upload",
    )
    parser.add_argument(
        "--niche",
        type=str,
        default=None,
        help="Video niche (motivational, facts, tech, finance, scary)",
    )
    args = parser.parse_args()

    if args.mode == "test":
        print("Running in TEST mode (no upload)...")
        run_pipeline(niche=args.niche, upload=False)

    elif args.mode == "once":
        print("Running single video generation + upload...")
        run_pipeline(niche=args.niche, upload=True)

    elif args.mode == "schedule":
        post_time = f"{settings.POSTING_HOUR:02d}:{settings.POSTING_MINUTE:02d}"
        print(f"Scheduling daily video at {post_time} ({settings.TIMEZONE})")
        schedule.every().day.at(post_time).do(daily_job)

        # Run immediately on first start
        print("Running first video now...")
        daily_job()

        print(f"\nScheduler active. Next run at {post_time} daily.")
        while True:
            schedule.run_pending()
            time.sleep(60)


if __name__ == "__main__":
    main()
