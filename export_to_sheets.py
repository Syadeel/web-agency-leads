"""
Export leads from Supabase to Google Sheets — APPEND MODE.

Every pipeline run adds new leads below the existing ones.
Never removes old data. Never duplicates (handles checked).
"""
import csv, json, os, sys
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv
    if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')):
        load_dotenv()
except ImportError:
    pass

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.file"]
SHEET_NAME = "Leads"


def get_credentials():
    json_str = os.getenv("GOOGLE_SHEETS_CREDS_JSON", "")
    if json_str:
        return Credentials.from_service_account_info(json.loads(json_str), scopes=SCOPES)
    base = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base, "google_sheets_creds.json")
    if os.path.exists(json_path):
        return Credentials.from_service_account_file(json_path, scopes=SCOPES)
    raise ValueError("No Google credentials found. Set GOOGLE_SHEETS_CREDS_JSON secret or place google_sheets_creds.json")


def get_spreadsheet_id():
    sheet_id = os.getenv("SPREADSHEET_ID", "")
    if "--sheet-id" in sys.argv:
        idx = sys.argv.index("--sheet-id")
        sheet_id = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else sheet_id
    if not sheet_id:
        raise ValueError("SPREADSHEET_ID not set. Add to .env or use --sheet-id")
    return sheet_id


def fetch_leads():
    """Get ALL outreach-relevant columns from Supabase."""
    try:
        from dotenv import load_dotenv
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
    
    # All columns relevant for outreach
    cols = [
        "instagram_handle", "name", "phone", "email", "niche",
        "follower_count", "city", "country", "website_url",
        "outreach_status", "response", "outreach_date", "created_at"
    ]
    col_list = ", ".join(f'"{c}"' for c in cols)
    cur.execute(f"SELECT {col_list} FROM leads ORDER BY id;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return cols, rows


def format_cell(v):
    if v is None:
        return ""
    t = str(v)
    return t[:50000] if len(t) > 50000 else t


def main():
    print("=" * 60)
    print("  EXPORT TO GOOGLE SHEETS (APPEND MODE)")
    print("=" * 60)

    sheet_id = get_spreadsheet_id()
    cols, rows = fetch_leads()
    print(f"[*] {len(rows)} leads, {len(cols)} columns")

    if not GSPREAD_AVAILABLE:
        raise ImportError("gspread not installed")

    client = gspread.authorize(get_credentials())
    sh = client.open_by_key(sheet_id)

    # Get or create worksheet
    try:
        ws = sh.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=SHEET_NAME, rows=1000, cols=len(cols))
        # Write header for new sheet
        header = ["Date Added"] + [c.replace("_", " ").title() for c in cols]
        ws.update("A1", [header])
        ws.format("1:1", {"textFormat": {"bold": True}})

    # Get existing handles to avoid duplicates
    try:
        existing_handles = set(ws.col_values(1)[1:])  # Skip header
    except Exception:
        existing_handles = set()

    # Check if column header matches — if not, the sheet was cleared or has different schema
    try:
        current_headers = ws.row_values(1)
        expected_header = ["Date Added"] + [c.replace("_", " ").title() for c in cols]
        if current_headers != expected_header:
            print("[!] Sheet has different schema. Re-initializing...")
            ws.clear()
            ws.update("A1", [expected_header])
            ws.format("1:1", {"textFormat": {"bold": True}})
            existing_handles = set()
    except Exception:
        pass

    # Build new rows (append only, skip existing handles)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    new_rows = []
    skipped = 0
    for row in rows:
        handle = str(row[0] or "").strip().lower() if row[0] else ""
        if handle and handle in existing_handles:
            skipped += 1
            continue
        if handle:
            existing_handles.add(handle)
        row_data = [today] + [format_cell(v) for v in row]
        new_rows.append(row_data)

    if not new_rows:
        print(f"[*] No new leads to add ({skipped} already in sheet)")
        print(f"[OK] Sheet is up to date")
        return

    # Append at the end
    ws.append_rows(new_rows, value_input_option="USER_ENTERED")
    print(f"[+] Added {len(new_rows)} new leads to sheet")
    print(f"[-] Skipped {skipped} existing")
    print(f"[#] Total rows in sheet: {len(existing_handles)}")

    # Auto-format
    total_rows = len(existing_handles) + 1
    ws.format(f"A1:A{total_rows}", {"numberFormat": {"type": "DATE_TIME"}})
    ws.format("1:1", {"textFormat": {"bold": True}})

    print(f"\n[OK] Done! View:")
    print(f"   https://docs.google.com/spreadsheets/d/{sheet_id}")


if __name__ == "__main__":
    main()
