"""Monitoring and logging for the TikTok automation pipeline."""

import json
import os
from datetime import datetime
from config.settings import settings

LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "history.json")


def _ensure_log_file():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            json.dump([], f)


def log_video(niche: str, title: str, video_path: str, uploaded: bool, error: str = None):
    """Log a video generation event."""
    _ensure_log_file()

    with open(LOG_FILE, "r") as f:
        history = json.load(f)

    entry = {
        "id": len(history) + 1,
        "timestamp": datetime.now().isoformat(),
        "niche": niche,
        "title": title,
        "video_path": video_path,
        "uploaded": uploaded,
        "error": error,
    }
    history.append(entry)

    with open(LOG_FILE, "w") as f:
        json.dump(history, f, indent=2)

    return entry


def get_history(limit: int = 30) -> list[dict]:
    """Get recent video generation history."""
    _ensure_log_file()
    with open(LOG_FILE, "r") as f:
        history = json.load(f)
    return history[-limit:]


def print_dashboard():
    """Print a monitoring dashboard to the console."""
    history = get_history(30)

    print("\n" + "=" * 60)
    print("  TIKTOK AI VIDEO AUTOMATION - DASHBOARD")
    print("=" * 60)

    if not history:
        print("\n  No videos generated yet. Run your first one!")
        print("  python main.py --mode test\n")
        return

    # Stats
    total = len(history)
    uploaded = sum(1 for v in history if v["uploaded"])
    failed = sum(1 for v in history if v.get("error"))
    niches_used = {}
    for v in history:
        niches_used[v["niche"]] = niches_used.get(v["niche"], 0) + 1

    print(f"\n  Total videos generated: {total}")
    print(f"  Successfully uploaded:  {uploaded}")
    print(f"  Failed:                 {failed}")

    print("\n  Videos per niche:")
    for niche in ["motivational", "facts", "tech", "finance", "scary"]:
        count = niches_used.get(niche, 0)
        bar = "#" * count
        print(f"    {niche:<14} {count:>3}  {bar}")

    # Recent activity
    print("\n  Recent activity:")
    print(f"  {'Date':<20} {'Niche':<14} {'Status':<10} Title")
    print("  " + "-" * 56)
    for v in history[-10:]:
        date = v["timestamp"][:16].replace("T", " ")
        status = "UPLOADED" if v["uploaded"] else ("FAILED" if v.get("error") else "LOCAL")
        title = v["title"][:40] if v.get("title") else "N/A"
        print(f"  {date:<20} {v['niche']:<14} {status:<10} {title}")

    # Next niche
    from src.script_generator import get_todays_niche
    print(f"\n  Next niche in rotation: {get_todays_niche()}")
    print("=" * 60 + "\n")
