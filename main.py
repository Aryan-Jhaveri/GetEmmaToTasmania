"""
Emma's Flight Price Tracker
----------------------------
Entry point for GitHub Actions daily cron.
"""

import logging
import os
import sys
from datetime import date, timedelta

from dotenv import load_dotenv

import config
from src.serpapi_client import SerpApiClient
from src.notifier import EmailNotifier
from src.price_analyzer import cheapest_per_route, find_deals
from src.sheets_client import SheetsClient

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("main")


def parse_list(value: str) -> list[str]:
    return [v.strip().upper() for v in value.split(",") if v.strip()]


def main() -> None:
    logger.info("=== Emma's Flight Tracker starting ===")

    # ------------------------------------------------------------------
    # 1. Read settings from Google Sheets
    # ------------------------------------------------------------------
    sheets = SheetsClient()
    settings = sheets.read_settings()
    logger.info("Settings loaded: %s", settings)

    origins = parse_list(settings.get("Departure Cities", ",".join(config.DEFAULT_ORIGINS)))
    destinations = parse_list(settings.get("Destination Airports", ",".join(config.DEFAULT_DESTINATIONS)))

    # Date range: default to next ~6 weeks if not configured
    today = date.today()
    default_start = (today + timedelta(days=30)).isoformat()
    default_end = (today + timedelta(days=90)).isoformat()
    start_date = settings.get("Search Start Date", default_start)
    end_date = settings.get("Search End Date", default_end)
    step_days = int(settings.get("Date Step (days)", config.DEFAULT_DATE_STEP_DAYS))
    threshold = float(settings.get("Alert Threshold (CAD)", config.DEFAULT_ALERT_THRESHOLD_CAD))
    min_drop_pct = float(settings.get("Min Price Drop for Re-alert (%)", config.DEFAULT_MIN_DROP_PCT))
    recipient = settings.get("Notification Email", os.environ.get("GMAIL_ADDRESS", ""))

    logger.info(
        "Searching %s → %s from %s to %s (every %dd)",
        origins, destinations, start_date, end_date, step_days,
    )

    # ------------------------------------------------------------------
    # 2. Build route list and search Google Flights via SerpAPI
    # ------------------------------------------------------------------
    client = SerpApiClient()
    route_pairs = client.build_routes(origins, destinations, start_date, end_date, step_days)
    logger.info("Searching %d route(s) from %s to %s.", len(route_pairs), start_date, end_date)

    if not route_pairs:
        logger.warning("No routes to search — check date range in Settings.")
        return

    raw_offers = client.search_cheapest_offers(route_pairs)
    logger.info("SerpAPI returned %d offers total.", len(raw_offers))

    if not raw_offers:
        logger.warning("No offers returned. Check SERPAPI_KEY and that date range is in the future.")
        return

    # ------------------------------------------------------------------
    # 3. Load historical baselines and identify deals
    # ------------------------------------------------------------------
    historical_mins = sheets.read_historical_minimums()
    best_offers = cheapest_per_route(raw_offers)

    deals = find_deals(best_offers, historical_mins, threshold, min_drop_pct)
    logger.info(
        "Found %d deal(s) out of %d best offers.", len(deals), len(best_offers)
    )

    # ------------------------------------------------------------------
    # 4. Update Google Sheets
    # ------------------------------------------------------------------
    sheets.write_dashboard(best_offers, threshold)
    sheets.append_price_history(raw_offers)
    sheets.write_analysis_tab(threshold)

    # ------------------------------------------------------------------
    # 5. Send email alert if deals found
    # ------------------------------------------------------------------
    if deals and recipient:
        notifier = EmailNotifier()
        notifier.send_alert(deals, best_offers, recipient, threshold, historical_mins)
    elif deals and not recipient:
        logger.warning("Deals found but no Notification Email set in Settings!")
    else:
        logger.info("No deals today — no email sent.")

    logger.info("=== Done ===")


if __name__ == "__main__":
    main()
