# Emma's Flight Price Tracker

Automatically tracks Toronto (YYZ) → Tasmania (HBA/LST) flight prices daily.
Results appear in a Google Sheet Emma can view on her iPhone or MacBook.
An email alert fires whenever a price drops below her threshold.

---

## How It Works

- GitHub Actions runs the script every morning at ~10am Eastern
- Amadeus API fetches current flight prices
- Prices are written to a Google Sheet (Dashboard + Price History tabs)
- Emma gets an email if any price is below her alert threshold

Emma doesn't need to do anything after setup — she just checks her email and Sheet.

---

## One-Time Setup (~1 hour)

### Step 1 — Amadeus API (15 min)

1. Create a free account at https://developers.amadeus.com
2. Go to **My Apps** → **Create new app**
3. Copy the **Client ID** and **Client Secret** — you'll need these later
4. **Important**: The test environment has fake/static flight data.
   To get real prices, click your app → **Move to Production** and submit the form.
   Approval is free and usually takes about 24 hours.

---

### Step 2 — Google Sheet (20 min)

1. Go to https://sheets.google.com and create a new spreadsheet
2. Rename it to something like **"Emma's Flight Tracker"**
3. Create three tabs (click the `+` at the bottom):
   - `Dashboard`
   - `Price History`
   - `Settings`

4. In the **Settings** tab, fill in column A (labels) and column B (values):

   | A | B |
   |---|---|
   | Departure Cities | YYZ |
   | Destination Airports | HBA, LST |
   | Search Start Date | 2025-06-01 |
   | Search End Date | 2025-06-30 |
   | Date Step (days) | 7 |
   | Alert Threshold (CAD) | 2000 |
   | Notification Email | emma@gmail.com |
   | Min Price Drop for Re-alert (%) | 5 |

   > You can change any of these later — the script reads them fresh every run.

5. Copy the **Sheet ID** from the URL:
   `https://docs.google.com/spreadsheets/d/`**`THIS_LONG_STRING`**`/edit`

---

### Step 3 — Google Service Account (15 min)

This gives the script permission to write to the Sheet automatically.

1. Go to https://console.cloud.google.com
2. Click the project dropdown → **New Project** → give it any name → Create
3. In the search bar, search for **"Google Sheets API"** → Enable it
4. Also search for **"Google Drive API"** → Enable it
5. Go to **IAM & Admin** → **Service Accounts** → **Create Service Account**
   - Name: `flight-tracker` (or anything)
   - Click through to finish
6. Click the service account you just created → **Keys** tab → **Add Key** → **JSON**
   - This downloads a `.json` file — keep it safe, it's a credential
7. Open the JSON file in a text editor and copy ALL the contents
8. Go back to your Google Sheet → click **Share** → paste the service account's email
   (it looks like `flight-tracker@your-project.iam.gserviceaccount.com`) → set role to **Editor**

---

### Step 4 — Gmail App Password (5 min)

The script sends email through Gmail using an "app password" (not your real password).

1. The Gmail account must have **2-Step Verification** enabled
   (Google Account → Security → 2-Step Verification)
2. Go to https://myaccount.google.com/apppasswords
3. Click **Create** → name it "Flight Tracker" → click Create
4. Copy the 16-character password that appears (you won't see it again)

---

### Step 5 — GitHub Repository (15 min)

1. Create a new repository at https://github.com/new
   - Name: `emma-flight` (or anything)
   - Set to **Private** (keeps your API keys safe)
2. Upload all the project files to the repository
   (drag and drop in the GitHub web UI, or use `git push`)
3. Go to your repo → **Settings** → **Secrets and variables** → **Actions**
4. Click **New repository secret** and add each of these:

   | Secret Name | Value |
   |---|---|
   | `AMADEUS_CLIENT_ID` | Your Amadeus Client ID |
   | `AMADEUS_CLIENT_SECRET` | Your Amadeus Client Secret |
   | `GOOGLE_SERVICE_ACCOUNT_JSON` | The entire contents of the JSON key file |
   | `GOOGLE_SHEET_ID` | The Sheet ID from the URL (Step 2) |
   | `GMAIL_ADDRESS` | The Gmail address sending alerts |
   | `GMAIL_APP_PASSWORD` | The 16-character app password (Step 4) |

---

### Step 6 — Test It

1. Go to your GitHub repo → **Actions** tab
2. Click **Daily Flight Check** in the left sidebar
3. Click **Run workflow** → **Run workflow** (green button)
4. Watch the run complete (should take ~60 seconds)
5. Check your Google Sheet — Dashboard and Price History tabs should have data
6. Check Emma's email — if a price is below the threshold you set, she'll get an alert

To force a test email, temporarily set **Alert Threshold (CAD)** in Settings to `99999`,
run again, then set it back.

---

## Adjusting Settings

Emma (or you) can change any setting in the **Settings** tab of the Google Sheet
without touching any code. Changes take effect on the next run.

| Setting | What it does |
|---|---|
| Departure Cities | Change the Canadian airport (e.g. `YYZ` for Toronto, `YVR` for Vancouver) |
| Destination Airports | `HBA` (Hobart), `LST` (Launceston), or both |
| Search Start / End Date | The range of departure dates to check |
| Date Step (days) | How far apart each checked date is (7 = weekly, 1 = daily) |
| Alert Threshold (CAD) | Send an email when any price is below this amount |
| Notification Email | Where to send the alert emails |
| Min Price Drop for Re-alert (%) | Also alert if price drops X% below the previous best, even above threshold |

---

## Troubleshooting

**The Sheet isn't updating**
- Check the GitHub Actions run for error messages (Actions tab → click the failed run)
- Verify the service account email is shared as Editor on the Sheet
- Double-check the `GOOGLE_SHEET_ID` secret matches the Sheet URL

**No flight prices coming back**
- Make sure your Amadeus app is switched to **Production** (test env has fake data)
- Check that `AMADEUS_CLIENT_ID` and `AMADEUS_CLIENT_SECRET` are correct

**Not receiving emails**
- Verify the `GMAIL_APP_PASSWORD` is the 16-char app password, not your Gmail password
- Check the Notification Email in the Settings tab is correct
- Look in the GitHub Actions run log for "Alert email sent" confirmation

**GitHub Actions isn't running automatically**
- GitHub may pause scheduled workflows on repos with no recent activity
- Simply push any small change (e.g. edit README) to reactivate the schedule

---

## Project Structure

```
emma-flight/
├── .github/workflows/daily_check.yml  # Automated daily schedule
├── src/
│   ├── amadeus_client.py              # Fetches flight prices
│   ├── sheets_client.py               # Reads/writes Google Sheets
│   ├── notifier.py                    # Sends email alerts
│   ├── price_analyzer.py              # Identifies deals
│   └── models.py                      # Data structures
├── main.py                            # Main entry point
├── config.py                          # Default settings
└── requirements.txt                   # Python dependencies
```
