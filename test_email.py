"""
Send a test alert email using synthetic data — no SerpAPI or Sheets calls.
Usage: python test_email.py
Requires GMAIL_ADDRESS, GMAIL_APP_PASSWORD, and a recipient in .env
"""
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv()

from src.models import FlightOffer
from src.price_analyzer import find_deals
from src.notifier import EmailNotifier

import os

RECIPIENT = os.environ.get("GMAIL_ADDRESS", "")

# ------------------------------------------------------------------
# Synthetic flight data — two routes, five departure dates each
# ------------------------------------------------------------------
BASE = datetime(2026, 6, 1)

AIRLINES = [
    "Air Canada / Qantas",
    "United / Jetstar",
    "Air Canada / United / Qantas",
    "WestJet / Qantas",
    "Air Canada / Air New Zealand",
]

raw_offers: list[FlightOffer] = []
for week in range(5):
    dep = (BASE + timedelta(weeks=week)).strftime("%Y-%m-%d")
    for dest, base_price in [("HBA", 1310), ("LST", 1280)]:
        # Five offers per (route, date) at varying prices
        for i, (airline, price_bump) in enumerate(zip(AIRLINES, [0, 80, 140, 220, 310])):
            raw_offers.append(FlightOffer(
                origin="YYZ",
                destination=dest,
                departure_date=dep,
                price_cad=float(base_price + price_bump + week * 25),
                airlines=airline,
                num_stops=2 if i < 2 else 3,
                duration=f"{28 + i}h {(i * 13) % 60:02d}m",
                source="Google Flights",
            ))

# Historical minimums — simulate a few weeks of prior data
historical_mins = {
    "YYZ->HBA": 1350.0,
    "YYZ->LST": 1320.0,
}

# ------------------------------------------------------------------
# Run deal logic and send email
# ------------------------------------------------------------------
deals = find_deals(raw_offers, historical_mins, threshold_cad=1500.0, min_drop_pct=5.0)
primary = [d for d in deals if d.is_primary_deal]

print(f"Synthetic data: {len(raw_offers)} offers")
print(f"Deals found: {len(deals)} total, {len(primary)} primary")
for d in deals:
    print(f"  {d.offer.route_key} {d.offer.departure_date} "
          f"{d.offer.price_display} {d.tags}")

if not primary:
    print("No primary deals — email would not fire in production.")
    print("Sending anyway for test purposes...")

notifier = EmailNotifier()
notifier.send_alert(
    deals=deals,
    all_offers=[],          # not used by new notifier
    recipient=RECIPIENT,
    threshold=1500.0,
    historical_mins=historical_mins,
    raw_offers=raw_offers,
    booking_nudge=False,    # set True to preview the red banner
)
print(f"Test email sent to {RECIPIENT}")
