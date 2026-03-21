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

# Colours (0–1 scale for Sheets API)
COLOR_HEADER    = {"red": 0.157, "green": 0.306, "blue": 0.612}  # dark blue
COLOR_DEAL      = {"red": 0.714, "green": 0.929, "blue": 0.714}  # soft green
COLOR_ABOVE     = {"red": 0.953, "green": 0.953, "blue": 0.953}  # light grey
COLOR_WHITE     = {"red": 1.0,   "green": 1.0,   "blue": 1.0}
COLOR_HIST_HDR  = {"red": 0.235, "green": 0.235, "blue": 0.235}  # dark grey


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
        ws = self._get_or_create_tab(config.SHEET_DASHBOARD)
        ws.clear()

        now = datetime.utcnow().strftime("%b %d, %Y %H:%M UTC")
        num_cols = len(config.DASHBOARD_HEADERS)
        last_col = _col_letter(num_cols)

        rows = [config.DASHBOARD_HEADERS]
        deal_rows = []  # 1-indexed data row numbers that are deals

        for i, offer in enumerate(offers):
            below = offer.price_cad < threshold
            threshold_label = (
                f"DEAL — below ${threshold:,.0f}!" if below
                else f"Above ${threshold:,.0f}"
            )
            links = get_booking_links(offer)
            gf  = next((l for l in links if "google" in l["url"]), links[0])
            sk  = next((l for l in links if "skyscanner" in l["url"]), None)
            ky  = next((l for l in links if "kayak" in l["url"]), None)

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
                f'=HYPERLINK("{gf["url"]}","Book →")',
                f'=HYPERLINK("{sk["url"]}","Compare →")' if sk else "",
                f'=HYPERLINK("{ky["url"]}","Compare →")' if ky else "",
            ])
            if below:
                deal_rows.append(i + 2)  # +2: header is row 1, data starts row 2

        # Write all data — USER_ENTERED so HYPERLINK formulas are parsed
        ws.update(rows, "A1", value_input_option="USER_ENTERED")

        # --- Formatting ---
        # Header: white text on dark blue, bold
        ws.format(f"A1:{last_col}1", {
            "backgroundColor": COLOR_HEADER,
            "textFormat": {"bold": True, "foregroundColor": COLOR_WHITE},
            "horizontalAlignment": "CENTER",
        })

        # Data rows: alternate white / light grey
        for i, _ in enumerate(offers):
            row_num = i + 2
            bg = COLOR_WHITE if i % 2 == 0 else COLOR_ABOVE
            ws.format(f"A{row_num}:{last_col}{row_num}", {"backgroundColor": bg})

        # Deal rows: green background on the threshold column (col I = 9)
        threshold_col = _col_letter(9)
        for row_num in deal_rows:
            ws.format(f"{threshold_col}{row_num}", {
                "backgroundColor": COLOR_DEAL,
                "textFormat": {"bold": True},
            })

        # Price column (B): bold
        ws.format(f"B2:B{len(offers)+1}", {"textFormat": {"bold": True}})

        # Freeze header
        ws.freeze(rows=1)

        logger.info("Dashboard updated with %d offers.", len(offers))

    # ------------------------------------------------------------------
    # Price History
    # ------------------------------------------------------------------

    def append_price_history(self, offers: list[FlightOffer]) -> None:
        ws = self._get_or_create_tab(config.SHEET_HISTORY)

        existing = ws.get_all_values()
        has_header = existing and existing[0] == config.HISTORY_HEADERS

        if not has_header:
            # Prepend headers: insert at row 1 if data exists, else just append
            if existing:
                ws.insert_row(config.HISTORY_HEADERS, index=1)
            else:
                ws.append_row(config.HISTORY_HEADERS, value_input_option="RAW")
            _format_history_header(ws)

        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        rows = [
            [now, o.route_key, o.price_cad, o.departure_date, o.airlines, o.num_stops, o.duration]
            for o in offers
        ]
        if rows:
            ws.append_rows(rows, value_input_option="USER_ENTERED")

        ws.freeze(rows=1)
        logger.info("Price History: appended %d rows.", len(rows))

    def read_historical_minimums(self) -> dict[str, float]:
        ws = self._get_or_create_tab(config.SHEET_HISTORY)
        rows = ws.get_all_values()
        if len(rows) <= 1:
            return {}

        minimums: dict[str, float] = {}
        for row in rows[1:]:
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


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _col_letter(n: int) -> str:
    """Convert 1-based column index to letter(s). 1→A, 12→L, 27→AA."""
    result = ""
    while n:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def _format_history_header(ws: gspread.Worksheet) -> None:
    num_cols = len(config.HISTORY_HEADERS)
    last_col = _col_letter(num_cols)
    ws.format(f"A1:{last_col}1", {
        "backgroundColor": COLOR_HIST_HDR,
        "textFormat": {"bold": True, "foregroundColor": COLOR_WHITE},
        "horizontalAlignment": "CENTER",
    })
