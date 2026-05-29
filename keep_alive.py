"""
keep_alive.py -- Prevents Hugging Face Space from sleeping.

Hugging Face Spaces sleep after ~30 minutes of inactivity.
Cold starts cause n8n workflow timeouts (the 3 previous errors).

This script pings the Space every 20 minutes to keep it warm.

Usage:
    python keep_alive.py              # One ping
    python keep_alive.py --loop       # Ping every 20 min (runs forever)
    python keep_alive.py --loop --interval 10  # Every 10 min

For permanent solution, schedule this with Task Scheduler (Windows):
    schtasks /create /sc minute /mo 20 /tn "n8n-keepalive" /tr "python F:\\Anitgravity Data\\web_agency_business\\keep_alive.py"
"""
import requests
import time
import argparse
import os
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from datetime import datetime

# Your n8n Space URL
N8N_URL = os.getenv("N8N_URL", "https://Adeel020-brains-n8n.hf.space/healthz")


def ping():
    """Send a request to wake up the Space."""
    ts = datetime.now().strftime('%H:%M:%S')
    try:
        r = requests.get(N8N_URL, timeout=10)
        if r.status_code == 200:
            print(f"[{ts}] OK n8n is alive ({r.elapsed.total_seconds():.1f}s)")
            return True
        else:
            print(f"[{ts}] WARN n8n responded {r.status_code}")
            return False
    except requests.exceptions.Timeout:
        print(f"[{ts}] TIMEOUT n8n cold-start (request timed out) -- Space is waking up")
        return False
    except Exception as e:
        print(f"[{ts}] FAIL Could not reach n8n: {e}")
        return False


def ping_with_retries(max_retries=3):
    """Ping and wait for cold start to complete."""
    for attempt in range(1, max_retries + 1):
        if ping():
            return True
        if attempt < max_retries:
            wait = attempt * 5
            print(f"     Retrying in {wait}s (attempt {attempt+1}/{max_retries})...")
            time.sleep(wait)
    return False


def main():
    parser = argparse.ArgumentParser(description="Hugging Face Space Keep-Alive")
    parser.add_argument("--loop", action="store_true", help="Keep running (ping every interval)")
    parser.add_argument("--interval", type=int, default=20, help="Minutes between pings (default: 20)")
    parser.add_argument("--once", action="store_true", help="Single ping then exit")
    args = parser.parse_args()

    if args.once:
        ping_with_retries()
        return

    if args.loop:
        print(f"🔄 Keep-alive started — pinging every {args.interval} minutes")
        print(f"   URL: {N8N_URL}")
        print(f"   Press Ctrl+C to stop\n")
        while True:
            ping_with_retries()
            print(f"   Sleeping {args.interval} min...\n")
            time.sleep(args.interval * 60)
    else:
        ping_with_retries()
        print("\n💡 To keep n8n alive permanently:")
        print(f"   python keep_alive.py --loop")
        print(f"   Or schedule with Task Scheduler every 20 min")


if __name__ == "__main__":
    main()
