#!/usr/bin/env python3
"""TikTok AI Video Automation - Main entry point."""

import argparse
import schedule
import time
from datetime import datetime

from config.settings import settings
from src.pipeline import run_pipeline
from src.script_generator import NICHE_ROTATION, get_todays_niche
from src.monitor import print_dashboard, get_history


def daily_job():
    """Run the video pipeline with today's rotating niche."""
    niche = get_todays_niche()
    print(f"\n{'='*50}")
    print(f"Daily video generation at {datetime.now()}")
    print(f"Today's niche: {niche}")
    print(f"{'='*50}\n")
    try:
        run_pipeline(niche=niche)
    except Exception as e:
        print(f"ERROR: Pipeline failed for niche '{niche}': {e}")
        raise


def run_all_niches(upload: bool = True):
    """Generate and upload one video for each of the 5 niches."""
    results = []
    for niche in NICHE_ROTATION:
        print(f"\n{'='*50}")
        print(f"Generating video for niche: {niche}")
        print(f"{'='*50}\n")
        try:
            path = run_pipeline(niche=niche, upload=upload)
            results.append((niche, path, "success"))
        except Exception as e:
            print(f"ERROR: Pipeline failed for niche '{niche}': {e}")
            results.append((niche, None, str(e)))

    print(f"\n{'='*50}")
    print("ALL NICHES SUMMARY")
    print(f"{'='*50}")
    for niche, path, status in results:
        icon = "OK" if status == "success" else "FAIL"
        print(f"  [{icon}] {niche}: {path or status}")
    return results


def main():
    parser = argparse.ArgumentParser(description="TikTok AI Video Automation")
    parser.add_argument(
        "--mode",
        choices=["once", "schedule", "test", "all-niches", "dashboard"],
        default="once",
        help=(
            "Run mode: 'once' = single video, 'schedule' = daily rotation, "
            "'test' = no upload, 'all-niches' = all 5 niches, "
            "'dashboard' = view monitoring dashboard"
        ),
    )
    parser.add_argument(
        "--niche",
        type=str,
        default=None,
        help="Video niche (motivational, facts, tech, finance, scary). "
             "If omitted, auto-rotates based on day of year.",
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Skip TikTok upload (useful for testing with --mode all-niches)",
    )
    args = parser.parse_args()

    if args.mode == "dashboard":
        print_dashboard()
        return

    if args.mode == "test":
        niche = args.niche or get_todays_niche()
        print(f"Running in TEST mode (no upload), niche: {niche}")
        run_pipeline(niche=niche, upload=False)

    elif args.mode == "once":
        niche = args.niche or get_todays_niche()
        print(f"Running single video, niche: {niche}")
        run_pipeline(niche=niche, upload=not args.no_upload)

    elif args.mode == "all-niches":
        print("Running ALL 5 niches: " + ", ".join(NICHE_ROTATION))
        run_all_niches(upload=not args.no_upload)

    elif args.mode == "schedule":
        post_time = f"{settings.POSTING_HOUR:02d}:{settings.POSTING_MINUTE:02d}"
        print(f"Scheduling daily video at {post_time} ({settings.TIMEZONE})")
        print(f"Niche rotation order: {' -> '.join(NICHE_ROTATION)}")
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
