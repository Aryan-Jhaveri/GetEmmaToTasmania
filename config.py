# Static defaults — override via the Settings tab in Google Sheets

# Tracker lifecycle
# After EXPIRY_DATE the script exits immediately (no API calls, no email).
# After BOOKING_NUDGE_DATE a "book soon" countdown banner appears in every email.
# To disable the daily GitHub Actions cron after expiry:
#   Repository → Settings → Actions → Workflows → Daily Flight Check → Disable workflow
TRACKER_EXPIRY_DATE    = "2026-06-30"   # last departure date — stop tracking after this
TRACKER_BOOKING_NUDGE  = "2026-05-25"   # start showing "book soon" banner in emails
TRACKER_BOOKING_DEADLINE = "2026-05-31" # hard deadline shown in the banner

# Default search parameters
DEFAULT_ORIGINS = ["YYZ"]
DEFAULT_DESTINATIONS = ["HBA", "LST"]
DEFAULT_DATE_STEP_DAYS = 7          # Search one departure per week
DEFAULT_ALERT_THRESHOLD_CAD = 1500
DEFAULT_MIN_DROP_PCT = 5            # Re-alert if price drops another 5%

# Amadeus search preferences
CABIN_CLASS = "ECONOMY"
MAX_CONNECTIONS = 3
NUM_ADULTS = 1
CURRENCY = "CAD"

# Email
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465

# Google Sheets tab names
SHEET_DASHBOARD = "Dashboard"
SHEET_HISTORY = "Price History"
SHEET_SETTINGS = "Settings"

# Dashboard column headers
DASHBOARD_HEADERS = [
    "Route", "Cheapest (CAD)", "Departure Date",
    "Airlines", "Stops", "Duration", "Source", "Last Checked",
    "vs. Your Threshold", "Google Flights", "Skyscanner", "Kayak"
]

# Price History column headers
HISTORY_HEADERS = [
    "Date Checked", "Route", "Price (CAD)",
    "Departure Date", "Airlines", "Stops", "Duration"
]
