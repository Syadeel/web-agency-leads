import json, requests
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request

creds = Credentials.from_service_account_file(
    r"F:\Anitgravity Data\web_agency_business\google_sheets_creds.json",
    scopes=["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/spreadsheets"]
)
creds.refresh(Request())

email = "web-agency-sheets@web-agency-497823.iam.gserviceaccount.com"
sheet_id = "1zeyBwZLkJJSnPjikzmbpEX6rvOF6IBCCMGNHQ85re0c"
headers = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}

# Share
r = requests.post(
    f"https://www.googleapis.com/drive/v3/files/{sheet_id}/permissions",
    headers=headers,
    json={"type": "user", "role": "writer", "emailAddress": email, "sendNotificationEmail": False},
    timeout=10
)
print("Share:", r.status_code, r.text[:200])

# Read
r2 = requests.get(f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}", headers=headers, timeout=10)
print("Read:", r2.status_code)
if r2.status_code == 200:
    print("Title:", r2.json()["properties"]["title"])
    print("SUCCESS - Sheet is accessible!")
else:
    print(r2.text[:300])
