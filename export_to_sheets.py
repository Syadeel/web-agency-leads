"""
Export leads from Supabase to Google Sheets.

Works in two modes:
  1. Local: uses google_sheets_creds.json file
  2. GitHub Actions: uses GOOGLE_SHEETS_CREDS_JSON secret

Usage:
    python export_to_sheets.py                          # Uses SPREADSHEET_ID from env/.env
    python export_to_sheets.py --sheet-id YOUR_SHEET_ID # Explicit sheet ID
    python export_to_sheets.py --create                 # Create a new sheet (prints URL)

Setup:
    1. Go to https://console.cloud.google.com/apis/credentials
    2. Create a Service Account → download JSON key
    3. Rename it to google_sheets_creds.json and place in project folder
    4. Share your Google Sheet with the service account email (Editor)
    5. Set SPREADSHEET_ID in .env (the long ID from the sheet URL)
"""
import csv
import json
import os
import sys

# Load .env for local dev (optional on GitHub Actions)
try:
    from dotenv import load_dotenv
    if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')):
        load_dotenv()
except ImportError:
    pass

# ─── Optional deps (graceful if not installed) ───────────────
try:
    import gspread
    from google.oauth2.service_account import Credentials
    from gspread.utils import rowcol_to_a1
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

# ─── Config ──────────────────────────────────────────────────
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

SHEET_NAME = "Leads"  # Name of the tab within the spreadsheet


def get_credentials():
    """Load Google service account credentials from JSON or env var."""
    # GitHub Actions: GOOGLE_SHEETS_CREDS_JSON is a secret containing the full JSON
    json_str = os.getenv("GOOGLE_SHEETS_CREDS_JSON", "")

    if json_str:
        try:
            creds_dict = json.loads(json_str)
            return Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        except Exception as e:
            raise ValueError(f"GOOGLE_SHEETS_CREDS_JSON is invalid JSON: {e}")

    # Local: google_sheets_creds.json file
    base = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base, "google_sheets_creds.json")
    if os.path.exists(json_path):
        return Credentials.from_service_account_file(json_path, scopes=SCOPES)

    raise ValueError(
        "No Google credentials found. Either:\n"
        "  1. Place google_sheets_creds.json in project folder (local)\n"
        "  2. Set GOOGLE_SHEETS_CREDS_JSON secret (GitHub Actions)"
    )


def get_client():
    if not GSPREAD_AVAILABLE:
        raise ImportError("gspread not installed. Run: pip install gspread google-auth")
    creds = get_credentials()
    return gspread.authorize(creds)


def get_spreadsheet_id():
    """Get sheet ID from env, arg, or .env."""
    sheet_id = os.getenv("SPREADSHEET_ID", "")
    if "--sheet-id" in sys.argv:
        idx = sys.argv.index("--sheet-id")
        if idx + 1 < len(sys.argv):
            sheet_id = sys.argv[idx + 1]
    if not sheet_id:
        raise ValueError(
            "SPREADSHEET_ID not set. Provide it via:\n"
            "  --sheet-id YOUR_ID\n"
            "  Or set SPREADSHEET_ID in .env\n"
            "  Or use --create to make a new sheet"
        )
    return sheet_id


def fetch_leads_supabase():
    """Fetch leads from Supabase DB."""
    try:
        try:
            from dotenv import load_dotenv
            if os.path.exists(os.path.join(os.path.dirname(__file__), '.env')):
                load_dotenv()
        except ImportError:
            pass

        import psycopg2
        conn = psycopg2.connect(
            dbname=os.getenv("SUPABASE_DB", "postgres"),
            user=os.getenv("SUPABASE_USER"),
            password=os.getenv("SUPABASE_PASSWORD"),
            host=os.getenv("SUPABASE_HOST"),
            port=os.getenv("SUPABASE_PORT", "6543"),
        )
        cur = conn.cursor()

        # Get columns (skip internal ones)
        skip_cols = {"id", "created_at", "enriched_at", "bio", "follower_count",
                     "follower_display", "has_website", "website_status", "priority"}
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'leads'
            ORDER BY ordinal_position;
        """)
        all_cols = [r[0] for r in cur.fetchall()]
        cols = [c for c in all_cols if c not in skip_cols]

        # Fetch data
        col_list = ", ".join(f'"{c}"' for c in cols)
        cur.execute(f"SELECT {col_list} FROM leads ORDER BY id;")
        rows = cur.fetchall()

        cur.close()
        conn.close()
        return cols, rows
    except Exception as e:
        # Fallback: read from CSV if DB unavailable
        csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "all_leads_from_db.csv")
        if os.path.exists(csv_path):
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows_data = list(reader)
            if rows_data:
                cols = list(rows_data[0].keys())
                rows = [list(r.values()) for r in rows_data]
                return cols, rows
        raise e


def format_cell(value):
    """Format a value for Google Sheets (handle None, truncate long text)."""
    if value is None:
        return ""
    text = str(value)
    if len(text) > 50000:
        text = text[:50000] + "..."
    return text


def main():
    print("=" * 60)
    print("  EXPORT LEADS TO GOOGLE SHEETS")
    print("=" * 60)

    # Create mode
    if "--create" in sys.argv:
        print("\n[*] Creating new Google Sheet...")
        client = get_client()
        sheet = client.create("Web Agency Leads")
        sheet.share(None, perm_type="anyone", role="reader")  # Public read
        print(f"\n[OK] Sheet created!")
        print(f"   URL: {sheet.url}")
        print(f"   ID:  {sheet.id}")
        print(f"\n[INFO] Add this to .env:")
        print(f"   SPREADSHEET_ID={sheet.id}")
        print(f"\n[INFO] Share with your service account email (Editor):")
        creds = get_credentials()
        print(f"   {creds.service_account_email}")
        return

    # Get sheet
    sheet_id = get_spreadsheet_id()
    print(f"\n[*] Fetching leads from database...")
    cols, rows = fetch_leads_supabase()
    print(f"   Found {len(rows)} leads, {len(cols)} columns")

    # Connect to Google Sheets
    print("[*] Connecting to Google Sheets...")
    client = get_client()
    try:
        sh = client.open_by_key(sheet_id)
    except Exception as e:
        raise ValueError(
            f"Can't open sheet. Make sure:\n"
            f"  1. Sheet ID is correct: {sheet_id}\n"
            f"  2. Service account email has Editor access\n"
            f"  Error: {e}"
        )

    # Get or create the worksheet
    try:
        ws = sh.worksheet(SHEET_NAME)
        # Clear existing content
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=SHEET_NAME, rows=1000, cols=len(cols))

    # Build data: header row + all rows
    header = [c.replace("_", " ").title() for c in cols]
    data = [header]
    for row in rows:
        data.append([format_cell(v) for v in row])

    # Write to sheet
    print(f"[*] Writing {len(data)} rows to sheet...")
    ws.update(range_name="A1", values=data)
    print(f"   Rows: {len(data) - 1} leads + 1 header")
    print(f"   Cols: {len(cols)}")

    # Auto-resize columns (approximate by setting header bold)
    ws.format("1:1", {"textFormat": {"bold": True}})

    print(f"\n[OK] Done! View your sheet:")
    print(f"   https://docs.google.com/spreadsheets/d/{sheet_id}")


if __name__ == "__main__":
    main()
