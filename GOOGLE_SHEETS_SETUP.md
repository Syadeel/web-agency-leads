# Google Sheets Setup Guide

## 10-Minute Setup

### Step 1: Create a Google Cloud Project

1. Go to https://console.cloud.google.com/apis/credentials
2. Sign in with your Google account
3. Click **Create Project** → Name: `web-agency` → Create
4. Make sure the project is selected (top bar)

### Step 2: Enable Google Sheets API

1. Go to https://console.cloud.google.com/apis/library/sheets.googleapis.com
2. Click **Enable**

### Step 3: Create a Service Account

1. Go to https://console.cloud.google.com/apis/credentials
2. Click **Create Credentials** → **Service Account**
3. Name: `web-agency-sheets` → Create → Done
4. Click on the service account you just created
5. Go to **Keys** tab → **Add Key** → **Create New Key** → **JSON** → **Download**

   A JSON file will download. **Keep it safe** — this is your API key.

### Step 4: Rename and Save the JSON

1. Rename the downloaded file to: `google_sheets_creds.json`
2. Move it to: `F:\Anitgravity Data\web_agency_business\google_sheets_creds.json`

### Step 5: Create a Google Sheet

1. Go to https://sheets.new
2. The URL will look like: `https://docs.google.com/spreadsheets/d/1ABC123xyz.../edit`
3. Copy the **ID** part: `1ABC123xyz...` (long string between /d/ and /edit)
4. Add this to your `.env` file:
   ```
   SPREADSHEET_ID=1ABC123xyz...
   ```

### Step 6: Share with Your Service Account

1. Open the JSON file you downloaded in Step 3
2. Find the field: `"client_email": "something@project.iam.gserviceaccount.com"`
3. Copy that email address
4. Open your Google Sheet → **Share** button (top-right)
5. Paste the email → set to **Editor** → Send

### Step 7: Test Locally

```bash
pip install gspread google-auth
python export_to_sheets.py
```

You should see: `Done! View your sheet: https://docs.google.com/spreadsheets/d/...`

### Step 8: Add to GitHub Actions

Two new secrets:

1. Go to https://github.com/Syadeel/web-agency-leads/settings/secrets/actions
2. Click **New repository secret**
3. **Name:** `GOOGLE_SHEETS_CREDS_JSON`
4. **Value:** Open `google_sheets_creds.json` in Notepad → Copy the **entire content** → Paste
5. Save

6. Click **New repository secret** again
7. **Name:** `SPREADSHEET_ID`
8. **Value:** Your sheet ID (the long string from Step 5)
9. Save

### Done!

After this, every pipeline run will automatically write all leads to your Google Sheet.

The sheet updates every 6 hours with fresh data. Previous data gets replaced.
