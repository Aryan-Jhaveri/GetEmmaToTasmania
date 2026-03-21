# ✈️ Emma's Flight Price Tracker

> Automatically tracks **Toronto (YYZ) → Tasmania (HBA / LST)** flight prices every morning.
> Results appear in a Google Sheet. Email alerts fire when prices drop below your threshold.
> Emma doesn't touch any code — ever.

---

## How It Works

```
Every morning at 10am Eastern
        ↓
Searches Google Flights via SerpAPI
        ↓
Writes best prices to Google Sheets
        ↓
Emails Emma if any price is below her threshold
```

**Tech:** Python · GitHub Actions (free) · SerpAPI · Google Sheets · Gmail SMTP

---

## What Emma Sees

### Dashboard tab — current best prices
| Route | Cheapest (CAD) | Departure | Airlines | Stops | Duration | Book |
|-------|---------------|-----------|----------|-------|----------|------|
| YYZ→HBA | **$1,370** 🟢 | 2026-06-01 | United / Jetstar | 2 | 30h 59m | [Google Flights]() · [Skyscanner]() · [Kayak]() |
| YYZ→LST | **$1,370** 🟢 | 2026-06-01 | Air Canada / United | 2 | 26h 25m | [Google Flights]() · [Skyscanner]() · [Kayak]() |

- 🟢 Green row = price is below Emma's alert threshold
- Updated every morning automatically
- Clickable booking links directly to each site

### Price History tab — every price ever recorded
Used to track trends over time. Add a Line Chart in Sheets to visualise price changes.

### Settings tab — Emma (or you) can change anytime
| Setting | Example |
|---------|---------|
| Departure Cities | `YYZ` |
| Destination Airports | `HBA, LST` |
| Search Start Date | `2026-06-01` |
| Search End Date | `2026-06-30` |
| Alert Threshold (CAD) | `1500` |
| Notification Email | `emma@gmail.com` |

Changes take effect on the next morning's run — no code needed.

---

## One-Time Setup

### Prerequisites
- GitHub account (free)
- Google account
- Gmail account (to send alerts from)
- SerpAPI account (free — 250 searches/month, no credit card)

---

### Step 1 — SerpAPI key `(5 min)`

1. Go to **[serpapi.com](https://serpapi.com)** → Sign Up (free, no credit card)
2. Dashboard → copy your **Private API Key**

---

### Step 2 — Google Sheet `(20 min)`

1. Go to **[sheets.google.com](https://sheets.google.com)** → create a new spreadsheet
2. Name it **"Emma's Flight Tracker"**
3. Create three tabs: `Dashboard` · `Price History` · `Settings`
4. In the **Settings** tab fill in column A (label) and column B (value):

   | A | B |
   |---|---|
   | Departure Cities | YYZ |
   | Destination Airports | HBA, LST |
   | Search Start Date | 2026-06-01 |
   | Search End Date | 2026-06-30 |
   | Date Step (days) | 7 |
   | Alert Threshold (CAD) | 1500 |
   | Notification Email | emma@gmail.com |
   | Min Price Drop for Re-alert (%) | 5 |

5. Copy the **Sheet ID** from the URL:
   `docs.google.com/spreadsheets/d/`**`← this part →`**`/edit`

---

### Step 3 — Google Service Account `(15 min)`

This lets the script write to the Sheet automatically.

1. Go to **[console.cloud.google.com](https://console.cloud.google.com)** → create a new project
2. Search and enable: **Google Sheets API** and **Google Drive API**
3. Go to **IAM & Admin → Service Accounts → Create Service Account**
   - Name it `flight-tracker` → click through to finish
4. Click the service account → **Keys → Add Key → JSON** → download the file
5. Open the JSON file and copy **all its contents**
6. In your Google Sheet → **Share** → paste the service account email
   (looks like `flight-tracker@your-project.iam.gserviceaccount.com`) → set as **Editor**

---

### Step 4 — Gmail App Password `(5 min)`

1. The sending Gmail account needs **2-Step Verification** enabled
2. Go to **[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)**
3. Create → name it "Flight Tracker" → copy the **16-character password**

---

### Step 5 — GitHub repo + secrets `(10 min)`

1. Create a **private** repo at [github.com/new](https://github.com/new)
2. Push this code:
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/emma-flight.git
   git push -u origin main
   ```
3. Go to repo → **Settings → Secrets and variables → Actions → New repository secret**

   Add these 5 secrets:

   | Secret Name | Value |
   |-------------|-------|
   | `SERPAPI_KEY` | Your SerpAPI private key |
   | `GOOGLE_SERVICE_ACCOUNT_JSON` | The entire contents of the JSON key file |
   | `GOOGLE_SHEET_ID` | The Sheet ID from the URL |
   | `GMAIL_ADDRESS` | Gmail address that sends the alerts |
   | `GMAIL_APP_PASSWORD` | The 16-character app password |

---

### Step 6 — Test it `(2 min)`

1. Repo → **Actions** tab → **Daily Flight Check** → **Run workflow**
2. Watch it complete (~30 seconds)
3. Check the Google Sheet — Dashboard and Price History should be populated
4. To test the email alert: temporarily set **Alert Threshold (CAD)** to `99999` in Settings, run again, then set it back

---

## Schedule

Runs automatically every day at **10:00 AM Eastern / 7:00 AM Pacific**.

To change the time, edit the cron expression in `.github/workflows/daily_check.yml`:
```yaml
- cron: "0 14 * * *"   # 14:00 UTC = 10:00 AM Eastern
```
Use [crontab.guru](https://crontab.guru) to pick a different time.

---

## Troubleshooting

**Sheet isn't updating**
- Check the Actions tab for error logs (click the failed run)
- Confirm the service account email is shared as **Editor** on the Sheet
- Double-check `GOOGLE_SHEET_ID` matches your Sheet URL

**No flight prices returned**
- Confirm `Search Start Date` and `Search End Date` in Settings are in the **future**
- Check `SERPAPI_KEY` is correct in GitHub Secrets

**Not receiving emails**
- Confirm `Notification Email` is filled in the Settings tab
- Check `GMAIL_APP_PASSWORD` is the 16-char app password, not your Gmail password
- Look in the Actions log for `Alert email sent` or `Deals found but no Notification Email`

**GitHub Actions stopped running**
- GitHub pauses scheduled workflows on repos with no recent activity
- Push any small change to reactivate (e.g. edit this README)

---

## Project Structure

```
emma-flight/
├── .github/
│   └── workflows/
│       └── daily_check.yml     # Cron schedule — runs automatically
├── src/
│   ├── serpapi_client.py       # Fetches prices from Google Flights
│   ├── sheets_client.py        # Reads settings, writes Dashboard & History
│   ├── notifier.py             # Sends HTML email alerts
│   ├── price_analyzer.py       # Identifies deals vs. threshold & all-time lows
│   ├── booking_links.py        # Generates Google Flights / Skyscanner / Kayak links
│   └── models.py               # Data classes: FlightOffer, RouteConfig
├── main.py                     # Entry point — orchestrates everything
├── config.py                   # Default settings (airports, cabin class, etc.)
├── requirements.txt            # Python dependencies
├── .env.example                # Template for local development
└── IMPLEMENTATIONS.md          # Notes on adding more APIs & future improvements
```

---

## Adding More Departure Cities

Update the **Settings tab** in the Sheet — no code needed:

```
Departure Cities → YYZ, YVR, YUL
```

SerpAPI is called once per origin-destination pair. 3 cities × 2 destinations = 6 calls/day ≈ 180/month (still within the 250 free limit).

---


