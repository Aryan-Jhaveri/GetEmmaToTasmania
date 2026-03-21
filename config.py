# Static defaults — override via the Settings tab in Google Sheets

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
