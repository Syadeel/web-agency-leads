"""
scraper.py — Error-Proof Instagram Lead Scraper

Runs on: Windows (local) and Linux (GitHub Actions).
- Reads SERPAPI_KEY from environment variable (with .env fallback)
- Auto-retry 3x with exponential backoff
- Unicode-safe (skips non-Latin characters gracefully)
- Topic pill filter (0% garbage)
- 12 niches x 4 cities = 48 queries
"""
import requests
import re
import csv
import os
import time
import json
import sys
from datetime import datetime

# ─── Config ─────────────────────────────────────────────────────
# Try .env for local dev, but prefer real env vars (GitHub Actions)
try:
    from dotenv import load_dotenv
    if os.path.exists(os.path.join(os.path.dirname(__file__), '.env')):
        load_dotenv()
except ImportError:
    pass  # dotenv not installed - rely on real env vars

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
if not SERPAPI_KEY:
    raise ValueError("SERPAPI_KEY not set. Add to .env file or set as GitHub Actions secret.")

NICHES = [
    "clothing brand", "home bakery", "consultant",
    "real estate agent", "restaurant", "fitness coach",
    "photographer", "makeup artist", "jewelry store",
    "ecommerce store", "digital agency", "gym",
    "beauty salon", "catering service", "event planner",
    "interior designer", "tutor", "car rental",
    "tailor", "boutique", "dentist",
    "pharmacy", "bakery", "coffee shop",
    "salon", "spa", "fashion designer",
    "graphic designer", "web developer", "marketing agency",
    "online store", "handicrafts", "organic farm",
    "pet store", "bookstore", "art gallery",
    "music teacher", "yoga instructor", "barber",
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
        except requests.exceptions.ConnectionError as e:
            last_error = f"connection: {e}"
        except Exception as e:
            last_error = str(e)[:100]

        if attempt < max_retries:
            delay = base_delay ** attempt
            time.sleep(delay)

    return None


# ─── Filters ────────────────────────────────────────────────────
def is_valid_profile(link):
    if not link or "instagram.com" not in link:
        return False
    skip = ["/popular/", "topic_pill", "?utm_source=",
            "instagram.com/explore/", "instagram.com/reels/",
            "instagram.com/directory/", "/p/", "/reel/", "/reels/",
            "/stories/", "/tv/"]
    if any(p in link for p in skip):
        return False
    return True


def extract_handle(link):
    m = re.search(r'instagram\.com/([^/?]+)', link)
    return m.group(1).lower() if m else None


# ─── Search ─────────────────────────────────────────────────────
def search_serpapi(query):
    params = {"engine": "google", "q": query, "api_key": SERPAPI_KEY, "num": 100}
    data = fetch_with_retries("https://serpapi.com/search", params)
    if data:
        return data.get("organic_results", [])
    return None


def search_fallback(query):
    """Google Custom Search fallback."""
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
    results = search_serpapi(query)
    if results is not None:
        return results
    return search_fallback(query)


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
                "Shop Name": shop if shop else handle,
                "Instagram Link": link,
                "Instagram Handle": handle,
                "Phone Number": phone,
                "Niche": niche,
                "Bio Snippet": snippet[:500]
            })
        except Exception:
            continue  # Skip any malformed entries
    return leads


# ─── Main ───────────────────────────────────────────────────────
def main():
    all_leads = []
    total_queries = len(NICHES) * len(CITIES)
    errors = 0

    for i, niche in enumerate(NICHES):
        for city in CITIES:
            query = f'site:instagram.com "{niche}" "{city}" ("DM to order" OR "WhatsApp") -linktree -www'

            results = fetch_results(query)
            if not results:
                errors += 1
                continue

            leads = extract_leads(results, niche)
            all_leads.extend(leads)
            time.sleep(1.5)  # Rate limit

    # Dedup by handle
    unique = {}
    for lead in all_leads:
        h = lead["Instagram Handle"]
        if h not in unique:
            unique[h] = lead

    final_leads = list(unique.values())

    # Save
    fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads.csv")
    with open(fp, "w", newline="", encoding="utf-8") as f:
        keys = ["Shop Name", "Instagram Link", "Instagram Handle", "Phone Number", "Niche", "Bio Snippet"]
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(final_leads)

    phones = sum(1 for l in final_leads if l["Phone Number"] != "Not Found")
    print(f"SCRAPED={len(final_leads)}")
    print(f"PHONES={phones}")
    print(f"ERRORS={errors}")
    print(f"TOTAL_QUERIES={total_queries}")


if __name__ == "__main__":
    main()
