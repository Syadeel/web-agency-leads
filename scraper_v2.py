# scraper_v2.py
"""
Web Agency Scraper v2
Primary search: Tavily (replaces SerpAPI/CSE)
Fallback search: Brave
Deep scrape: Firecrawl
Writes sanitized results to Google Sheets
"""

import os
import sys
import time
import logging
import re
import json
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional

import requests
from dotenv import load_dotenv

# Google Sheets
import gspread
from google.oauth2.service_account import Credentials

# ----------------------------------------------------------------------
# Environment & logging setup
# ----------------------------------------------------------------------
load_dotenv()

# File logging directory
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Logger setup: console + file
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, handlers=[
    logging.FileHandler(os.path.join(LOG_DIR, f"scraper-{datetime.now().strftime('%Y-%m-%d')}.log"), encoding='utf-8'),
    logging.StreamHandler(sys.stdout)
])
logger = logging.getLogger("scraper_v2")
# Fix Windows stdout
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# API keys from environment
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
# Google Sheets settings
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")

# Search settings
SEARCH_MAX_RESULTS = 10
SCRAPE_DELAY = 2  # seconds between Firecrawl calls
SEARCH_DELAY = 1   # seconds between searches

# ----------------------------------------------------------------------
# Sanitization for Google Sheets (charmap fix)
# ----------------------------------------------------------------------
def sanitize_for_sheets(text: Any) -> str:
    """
    Clean a string so it can be safely written into Google Sheets
    without causing charmap/encoding errors.
    Handles non-ASCII characters by replacing or stripping them.
    """
    if not isinstance(text, str):
        text = str(text) if text is not None else ""
    
    # First pass: replace known Unicode symbols with ASCII equivalents
    replacements = {
        "\u2192": "->",      # arrow right
        "\u2190": "<-",      # arrow left
        "\u2191": "^",       # arrow up
        "\u2193": "v",       # arrow down
        "\u2013": "-",       # en dash
        "\u2014": "-",       # em dash
        "\u2018": "'",       # left single quote
        "\u2019": "'",       # right single quote
        "\u201c": '"',       # left double quote
        "\u201d": '"',       # right double quote
        "\u2026": "...",     # ellipsis
        "\u00a0": " ",       # non-breaking space
        "\u00ab": "<<",      # left-pointing double angle
        "\u00bb": ">>",      # right-pointing double angle
        "\u00b0": "deg",     # degree symbol
        "\u00b1": "+/-",     # plus-minus
        "\u00d7": "x",       # multiplication sign
        "\u00f7": "/",       # division sign
        "\u2022": "*",       # bullet
        "\u2713": "OK",      # checkmark
        "\u2714": "OK",      # heavy checkmark
    }
    for uni_char, ascii_equiv in replacements.items():
        text = text.replace(uni_char, ascii_equiv)

    # Second pass: NFKD normalize and strip remaining non-ASCII
    import unicodedata
    normalized = unicodedata.normalize("NFKD", text)
    ascii_bytes = normalized.encode("ascii", "ignore")
    text = ascii_bytes.decode("ascii")

    # Clean up whitespace
    text = re.sub(r' +', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ----------------------------------------------------------------------
# Search Functions
# ----------------------------------------------------------------------
def search_tavily(query: str, max_results: int = SEARCH_MAX_RESULTS, attempt: int = 1) -> List[Dict[str, str]]:
    """
    Use Tavily Search API to find relevant URLs.
    Retries on DNS/network errors with backoff.
    """
    if not TAVILY_API_KEY:
        logger.warning("Tavily API key not set - skipping Tavily.")
        return []
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
    }
    try:
        # Pre-resolve hostname to catch DNS issues early
        import socket
        try:
            socket.getaddrinfo('api.tavily.com', 443)
        except socket.gaierror:
            if attempt <= 2:
                logger.warning(f"Tavily DNS resolution failed, retrying in {attempt*5}s...")
                time.sleep(attempt * 5)
                return search_tavily(query, max_results, attempt + 1)
            else:
                logger.error("Tavily DNS failed after retries, skipping.")
                return []
        
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        logger.info(f"Tavily returned {len(results)} results for query: {query}")
        return [{"title": r["title"], "url": r["url"], "snippet": r.get("snippet", "")} for r in results]
    except requests.exceptions.ConnectionError as e:
        if "NameResolutionError" in str(e) and attempt <= 2:
            logger.warning(f"Tavily DNS/connection error, retrying in {attempt*10}s...")
            time.sleep(attempt * 10)
            return search_tavily(query, max_results, attempt + 1)
        logger.error(f"Tavily search failed: {e}")
        return []
    except Exception as e:
        logger.error(f"Tavily search failed: {e}")
        return []


def search_brave(query: str, max_results: int = SEARCH_MAX_RESULTS) -> List[Dict[str, str]]:
    """
    Use Brave Search API as fallback.
    """
    if not BRAVE_API_KEY:
        logger.warning("Brave API key not set \u2013 skipping Brave.")
        return []
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": BRAVE_API_KEY,
    }
    params = {
        "q": query,
        "count": max_results,
    }
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        web_results = data.get("web", {}).get("results", [])
        logger.info(f"Brave returned {len(web_results)} results for query: {query}")
        return [{"title": r["title"], "url": r["url"], "snippet": r.get("description", "")} for r in web_results]
    except Exception as e:
        logger.error(f"Brave search failed: {e}")
        return []


def search_agencies(query: str) -> List[Dict[str, str]]:
    """
    Combine primary (Tavily) and fallback (Brave) searches.
    Returns list of unique results (by URL).
    """
    results = search_tavily(query)
    if not results:
        logger.info(f"No Tavily results, trying Brave for: {query}")
        results = search_brave(query)
    # Deduplicate by URL
    seen = set()
    unique = []
    for r in results:
        if r["url"] not in seen:
            seen.add(r["url"])
            unique.append(r)
    return unique


# ----------------------------------------------------------------------
# Deep Scrape with Firecrawl
# ----------------------------------------------------------------------
def deep_scrape_firecrawl(url: str, api_key: str = FIRECRAWL_API_KEY, attempt: int = 1) -> Optional[str]:
    """
    Use Firecrawl to extract the full page content.
    Retries on DNS/network errors with backoff.
    """
    if not api_key:
        logger.warning("Firecrawl API key not set - cannot deep scrape.")
        return None
    api_url = "https://api.firecrawl.dev/v2/scrape"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {"url": url}
    try:
        resp = requests.post(api_url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        content = data.get("data", {}).get("markdown", "") or data.get("data", {}).get("html", "")
        if not content:
            logger.warning(f"Firecrawl returned empty content for: {url}")
            return None
        logger.info(f"Firecrawl scraped content ({len(content)} chars) from: {url}")
        return content
    except requests.exceptions.ConnectionError as e:
        if "NameResolutionError" in str(e) and attempt <= 2:
            logger.warning(f"Firecrawl DNS error for {url}, retrying in {attempt*10}s...")
            time.sleep(attempt * 10)
            return deep_scrape_firecrawl(url, api_key, attempt + 1)
        logger.error(f"Firecrawl scrape error for {url}: {e}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Firecrawl scrape error for {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Firecrawl unexpected error for {url}: {e}")
        return None


def extract_contact_info(text: str) -> Dict[str, str]:
    """
    Extract email and phone from text using regex.
    Returns dict with keys: email, phone.
    """
    if not text:
        return {}
    email_re = r'[\w\.-]+@[\w\.-]+\.\w+'
    phone_re = r'(\+?[\d]{1,3}[- .]?)?\(?[\d]{2,4}\)?[- .]?[\d]{3,4}[- .]?[\d]{3,4}'
    emails = re.findall(email_re, text)
    phones = re.findall(phone_re, text)
    return {
        "email": emails[0] if emails else "",
        "phone": phones[0] if phones else "",
    }


# ----------------------------------------------------------------------
# Google Sheets Integration
# ----------------------------------------------------------------------
def get_google_sheet() -> Optional[gspread.Worksheet]:
    """
    Authenticate and return the first worksheet of the specified spreadsheet.
    Supports GOOGLE_SHEETS_CREDS_JSON env var or google_sheets_creds.json file.
    """
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive',
             'https://www.googleapis.com/auth/spreadsheets']
    try:
        json_str = os.getenv("GOOGLE_SHEETS_CREDS_JSON", "")
        if json_str:
            credentials = Credentials.from_service_account_info(json.loads(json_str), scopes=scope)
            logger.info("Authenticated via GOOGLE_SHEETS_CREDS_JSON env var")
        else:
            base = os.path.dirname(os.path.abspath(__file__))
            json_path = os.path.join(base, "google_sheets_creds.json")
            if os.path.exists(json_path):
                credentials = Credentials.from_service_account_file(json_path, scopes=scope)
                logger.info(f"Authenticated via {json_path}")
            else:
                raise ValueError("No Google credentials found. Set GOOGLE_SHEETS_CREDS_JSON env var or place google_sheets_creds.json")
        client = gspread.authorize(credentials)
    except Exception as e:
        logger.error(f"Google Sheets authentication failed: {e}")
        return None

    try:
        if SPREADSHEET_ID:
            sheet = client.open_by_key(SPREADSHEET_ID)
            logger.info(f"Opened spreadsheet: {sheet.title}")
        else:
            sheet = client.create("Web Agency Scraper Results")
            logger.info(f"Created new spreadsheet: {sheet.title}")
        worksheet = sheet.sheet1
        # Set up headers if worksheet is empty
        if not worksheet.row_values(1):
            headers = ["Country", "Agency Name", "Website", "Snippet", "Email", "Phone", "Scraped Content (First 500 char)"]
            worksheet.append_row(headers, value_input_option='RAW')
            logger.info("Initialized header row.")
        return worksheet
    except Exception as e:
        logger.error(f"Error accessing Google Sheet: {e}")
        return None


def load_existing_urls(worksheet: gspread.Worksheet) -> set:
    """Load all existing URLs from the sheet to avoid duplicates."""
    try:
        all_rows = worksheet.get_all_values()
        if len(all_rows) <= 1:
            return set()
        # URL is column index 2 (0-based: Country=0, Agency Name=1, Website=2)
        urls = set()
        for row in all_rows[1:]:
            if len(row) > 2 and row[2].strip():
                urls.add(row[2].strip().rstrip('/'))
        logger.info(f"Loaded {len(urls)} existing URLs from sheet (dedup reference)")
        return urls
    except Exception as e:
        logger.warning(f"Could not load existing URLs for dedup: {e}")
        return set()


def write_to_sheet(worksheet: gspread.Worksheet, row_data: List[Any], existing_urls: set = None):
    """
    Append a single sanitized row to the worksheet (with dedup).
    Uses sanitize_for_sheets to prevent charmap encoding errors.
    """
    safe_row = [sanitize_for_sheets(cell) for cell in row_data]
    
    # Dedup check: skip if URL already exists
    url = safe_row[2].strip().rstrip('/') if len(safe_row) > 2 else ''
    if url and existing_urls is not None and url in existing_urls:
        logger.info(f"  -> Skipped duplicate: {url}")
        return 'duplicate'
    
    try:
        worksheet.append_row(safe_row, value_input_option='RAW')
        logger.info(f"  + Added: {safe_row[0]} | {safe_row[1][:40]}...")
        if existing_urls is not None and url:
            existing_urls.add(url)
        return 'added'
    except Exception as e:
        logger.error(f"  ! Failed to write row: {e}")
        return 'error'


# ----------------------------------------------------------------------
# Main scraping routine
# ----------------------------------------------------------------------
def scrape_country(country: str, worksheet: gspread.Worksheet, existing_urls: set = None) -> int:
    """
    Search web agencies for one country, deep scrape each result,
    and write to the sheet. Returns number of agencies found.
    """
    query = f"web design agencies in {country}"
    logger.info(f"--- Searching: {country} ---")
    search_results = search_agencies(query)

    if not search_results:
        logger.warning(f"No search results for {country}")
        return 0

    count = 0
    for idx, result in enumerate(search_results[:SEARCH_MAX_RESULTS]):
        url = result["url"]
        title = result["title"]
        snippet = result.get("snippet", "")

        # Deep scrape with Firecrawl
        time.sleep(SCRAPE_DELAY)  # respect rate limits
        content = deep_scrape_firecrawl(url)

        contact = {}
        if content:
            short_content = sanitize_for_sheets(content[:500])
            contact = extract_contact_info(content)
        else:
            short_content = ""

        row = [
            country,
            title,
            url,
            snippet,
            contact.get("email", ""),
            contact.get("phone", ""),
            short_content
        ]
        result = write_to_sheet(worksheet, row, existing_urls)
        if result == 'added':
            count += 1

    return count


def main():
    parser = argparse.ArgumentParser(description="Web Agency Scraper v2")
    parser.add_argument("--daily", action="store_true", help="Daily mode: dedup by URL, skip existing")
    parser.add_argument("--force", action="store_true", help="Force re-scrape all (ignore dedup)")
    parser.add_argument("--countries", nargs="+", default=["UAE", "Saudi Arabia", "Qatar", "Kuwait", "Oman", "Bahrain", "Turkey"],
                        help="Countries to scrape (default: all ME)")
    parser.add_argument("--retry", type=int, default=2, help="Max retries per country on failure")
    args = parser.parse_args()

    logger.info(f"=== Starting Web Agency Scraper v2 ===")
    logger.info(f"Mode: {'DAILY (dedup)' if args.daily else 'FULL'}")
    logger.info(f"Countries: {args.countries}")

    worksheet = get_google_sheet()
    if not worksheet:
        logger.error("Could not get Google Sheet. Aborting.")
        sys.exit(1)

    # Load existing URLs for dedup
    existing_urls = load_existing_urls(worksheet) if args.daily else set()
    if args.force:
        logger.info("Force mode: ignoring existing URLs")
        existing_urls = set()

    total = 0
    for country in args.countries:
        for attempt in range(1, args.retry + 2):
            try:
                agencies = scrape_country(country, worksheet, existing_urls)
                total += agencies
                logger.info(f"  [{country}] Finished: {agencies} agencies saved.")
                time.sleep(SEARCH_DELAY)
                break  # success, move to next country
            except Exception as e:
                logger.error(f"  [{country}] Attempt {attempt}/{args.retry+1} failed: {e}")
                if attempt <= args.retry:
                    wait = attempt * 30
                    logger.info(f"  Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    logger.error(f"  [{country}] All attempts failed, skipping.")

    logger.info(f"=== Scraping complete. Total agencies saved: {total} ===")


if __name__ == "__main__":
    main()
