import json
import logging
import os
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

import config
from src.booking_links import get_booking_links
from src.models import FlightOffer

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class SheetsClient:
    def __init__(self):
        sa_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
        sheet_id = os.environ["GOOGLE_SHEET_ID"]

        creds = Credentials.from_service_account_info(
            json.loads(sa_json), scopes=SCOPES
        )
        gc = gspread.authorize(creds)
        self._sheet = gc.open_by_key(sheet_id)

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def read_settings(self) -> dict:
        """Read the Settings tab and return a dict of label → value."""
        ws = self._sheet.worksheet(config.SHEET_SETTINGS)
        rows = ws.get_all_values()
        settings = {}
        for row in rows:
            if len(row) >= 2 and row[0].strip():
                settings[row[0].strip()] = row[1].strip()
        return settings

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def write_dashboard(self, offers: list[FlightOffer], threshold: float) -> None:
        """Clear and rewrite the Dashboard tab with the latest best prices."""
        ws = self._get_or_create_tab(config.SHEET_DASHBOARD)
        ws.clear()

        now = datetime.utcnow().strftime("%b %d, %Y %H:%M UTC")

        # Header row
        rows = [config.DASHBOARD_HEADERS]

        for offer in offers:
            below = offer.price_cad < threshold
            threshold_label = (
                f"DEAL — below ${threshold:,.0f} threshold!" if below
                else f"Above ${threshold:,.0f} threshold"
            )
            links = get_booking_links(offer)
            primary_link = next(l for l in links if l["primary"])
            other_links = " | ".join(
                f'{l["label"]}: {l["url"]}' for l in links if not l["primary"]
            )
            rows.append([
                offer.route_key,
                offer.price_display,
                offer.departure_date,
                offer.airlines,
                str(offer.num_stops),
                offer.duration,
                offer.source,
                now,
                threshold_label,
                f'=HYPERLINK("{primary_link["url"]}","{primary_link["label"]}")',
                other_links,
            ])

        ws.update(rows, "A1")

        # Bold the header row
        ws.format("A1:H1", {"textFormat": {"bold": True}})

        # Freeze header row
        ws.freeze(rows=1)

        logger.info("Dashboard updated with %d offers.", len(offers))

    # ------------------------------------------------------------------
    # Price History
    # ------------------------------------------------------------------

    def append_price_history(self, offers: list[FlightOffer]) -> None:
        """Append new price records to the Price History tab."""
        ws = self._get_or_create_tab(config.SHEET_HISTORY)

        # Add headers if the sheet is empty
        existing = ws.get_all_values()
        if not existing:
            ws.append_row(config.HISTORY_HEADERS, value_input_option="RAW")
            ws.format("A1:G1", {"textFormat": {"bold": True}})
            ws.freeze(rows=1)

        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        rows = [
            [
                now,
                offer.route_key,
                offer.price_cad,
                offer.departure_date,
                offer.airlines,
                offer.num_stops,
                offer.duration,
            ]
            for offer in offers
        ]
        if rows:
            ws.append_rows(rows, value_input_option="USER_ENTERED")

        logger.info("Price History: appended %d rows.", len(rows))

    def read_historical_minimums(self) -> dict[str, float]:
        """Return the all-time cheapest price per route_key from Price History."""
        ws = self._get_or_create_tab(config.SHEET_HISTORY)
        rows = ws.get_all_values()
        if len(rows) <= 1:
            return {}

        minimums: dict[str, float] = {}
        for row in rows[1:]:  # skip header
            if len(row) < 3:
                continue
            route_key = row[1]
            try:
                price = float(row[2])
            except ValueError:
                continue
            if route_key not in minimums or price < minimums[route_key]:
                minimums[route_key] = price
        return minimums

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_or_create_tab(self, title: str) -> gspread.Worksheet:
        try:
            return self._sheet.worksheet(title)
        except gspread.WorksheetNotFound:
            logger.info("Creating missing tab: %s", title)
            return self._sheet.add_worksheet(title=title, rows=1000, cols=20)
