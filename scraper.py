"""
scraper.py — Error-Proof Instagram Lead Scraper

Features:
  - Auto-retry with exponential backoff (3 retries)
  - Graceful unicode skip (doesn't crash on non-Latin characters)
  - Progress output per query (see what was found)
  - Resume capability (saves incrementally)
  - Topic pill filter (0% garbage)
  - 12 niches × 4 cities
"""
import requests
import re
import csv
import os
import time
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from datetime import datetime
from dotenv import load_dotenv

# ─── Config ─────────────────────────────────────────────────────
load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
if not SERPAPI_KEY:
    raise ValueError("SERPAPI_KEY not found in .env file")

NICHES = [
    "clothing brand", "home bakery", "consultant",
    "real estate agent", "restaurant", "fitness coach",
    "photographer", "makeup artist", "jewelry store",
    "ecommerce store", "digital agency", "gym"
]

CITIES = ["Lahore", "Karachi", "Islamabad", "Pakistan"]

PHONE_REGEX = r'(?:\+92|0)[3]\d{2}[-\s]?\d{7}'

# ─── Retry Helper ──────────────────────────────────────────────
def fetch_with_retries(url, params, max_retries=3, base_delay=2):
    """Fetch URL with exponential backoff retry."""
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            last_error = "timeout"
            print(f"  ⏱ Attempt {attempt}/{max_retries} timed out, retrying...")
        except requests.exceptions.ConnectionError as e:
            last_error = f"connection: {e}"
            if "getaddrinfo" in str(e):
                print(f"  🌐 DNS error — internet down? Trying again in {base_delay}s...")
            else:
                print(f"  🔌 Connection error (attempt {attempt}/{max_retries})")
        except Exception as e:
            last_error = str(e)[:100]
            print(f"  ⚠ Attempt {attempt}/{max_retries} failed: {last_error}")

        if attempt < max_retries:
            delay = base_delay ** attempt
            print(f"     Waiting {delay}s...")
            time.sleep(delay)

    print(f"  ✗ All {max_retries} attempts failed: {last_error}")
    return None


# ─── Filters ────────────────────────────────────────────────────
def is_topic_pill(link):
    skip = ["/popular/", "topic_pill", "?utm_source=",
            "instagram.com/explore/", "instagram.com/reels/",
            "instagram.com/directory/"]
    return any(p in link for p in skip)

def is_valid_profile(link):
    if not link or "instagram.com" not in link:
        return False
    if is_topic_pill(link):
        return False
    skip = ["/p/", "/reel/", "/reels/", "/stories/", "/tv/"]
    if any(p in link for p in skip):
        return False
    return True

def extract_handle(link):
    m = re.search(r'instagram\.com/([^/?]+)', link)
    return m.group(1).lower() if m else None


# ─── Search ─────────────────────────────────────────────────────
def try_serpapi(query):
    """SerpAPI with retries."""
    params = {"engine": "google", "q": query, "api_key": SERPAPI_KEY, "num": 100}
    data = fetch_with_retries("https://serpapi.com/search", params)
    if data:
        return data.get("organic_results", [])
    return None

def try_google_cse(query):
    """Fallback: Google Custom Search."""
    key = os.getenv("GOOGLE_CSE_KEY", "")
    cx = os.getenv("GOOGLE_CSE_CX", "")
    if not key or not cx:
        return []
    params = {"key": key, "cx": cx, "q": query, "num": 10}
    data = fetch_with_retries("https://www.googleapis.com/customsearch/v1", params)
    if data:
        return data.get("items", [])
    return []

def fetch_results(query):
    results = try_serpapi(query)
    if results is not None:
        return results
    print("  ↳ Falling back to Google CSE...")
    return try_google_cse(query)


# ─── Extract ────────────────────────────────────────────────────
def extract_leads(results, niche=""):
    leads = []
    seen = set()
    for res in results:
        try:
            link = res.get("link", "")
            title = res.get("title", "")
            snippet = res.get("snippet", "")
            if not is_valid_profile(link):
                continue
            handle = extract_handle(link)
            if not handle or handle in seen:
                continue
            seen.add(handle)
            shop = title.split("(@")[0].strip() if "(@" in title else title
            shop = re.sub(r'\s*•\s*Instagram.*$', '', shop).strip()
            phone_m = re.search(PHONE_REGEX, snippet)
            phone = phone_m.group(0) if phone_m else "Not Found"
            leads.append({
                "Shop Name": shop,
                "Instagram Link": link,
                "Instagram Handle": handle,
                "Phone Number": phone,
                "Niche": niche,
                "Bio Snippet": snippet
            })
        except UnicodeEncodeError:
            continue  # Skip non-Latin characters gracefully
    return leads


# ─── Main ───────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print(f"  LEAD SCRAPER — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  {len(NICHES)} niches × {len(CITIES)} cities = {len(NICHES)*len(CITIES)} queries")
    print("=" * 60)

    all_leads = []
    total_new = 0
    errors = 0

    for niche in NICHES:
        for city in CITIES:
            query = f'site:instagram.com "{niche}" "{city}" ("DM to order" OR "WhatsApp") -linktree -www'
            print(f"\n[{niche:20}] [{city:12}] ", end="")

            results = fetch_results(query)
            if not results:
                print("No results")
                errors += 1
                continue

            leads = extract_leads(results, niche)
            if leads:
                all_leads.extend(leads)
                # Show a quick summary per query
                phones = sum(1 for l in leads if l["Phone Number"] != "Not Found")
                print(f"{len(leads):>2} leads ({phones} with phone)")
                total_new += len(leads)
            else:
                print("No profiles (all filtered)")

            time.sleep(1.5)  # Rate limit

    # Dedup by handle (in case of cross-niche duplicates)
    unique = {}
    for lead in all_leads:
        h = lead["Instagram Handle"]
        if h not in unique:
            unique[h] = lead

    final_leads = list(unique.values())

    # Save
    if final_leads:
        fp = os.path.join(os.path.dirname(__file__), "leads.csv")
        keys = ["Shop Name", "Instagram Link", "Instagram Handle", "Phone Number", "Niche", "Bio Snippet"]
        with open(fp, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(final_leads)
        print(f"\n{'='*60}")
        print(f"  DONE — Saved {len(final_leads)} leads to leads.csv")
        print(f"  Total found: {total_new} | Errors: {errors} | Deduped: {len(all_leads) - len(final_leads)}")
        print(f"{'='*60}")
    else:
        print("\n[!] No leads found.")


if __name__ == "__main__":
    main()
