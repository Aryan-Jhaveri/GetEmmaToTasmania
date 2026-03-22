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
        sheet_id = os.environ["GOOGLE_SHEET_ID"].strip()

        # Prefer file path (GitHub Actions) over inline JSON (local .env)
        sa_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH", "")
        if sa_path and os.path.exists(sa_path):
            with open(sa_path) as f:
                sa_info = json.load(f)
        else:
            sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip().strip("'\"")
            if not sa_json:
                raise ValueError(
                    "Set GOOGLE_SERVICE_ACCOUNT_PATH (file path) or "
                    "GOOGLE_SERVICE_ACCOUNT_JSON (raw JSON) in your environment."
                )
            sa_info = json.loads(sa_json)

        creds = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
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
    # Analysis tab
    # ------------------------------------------------------------------

    def write_analysis_tab(self, threshold: float) -> None:
        """Recreate the Analysis tab with pivot summary + embedded charts."""
        # Always delete + recreate to avoid duplicate charts on each run
        try:
            self._sheet.del_worksheet(self._sheet.worksheet("Analysis"))
        except gspread.WorksheetNotFound:
            pass
        ws = self._sheet.add_worksheet(title="Analysis", rows=500, cols=12)
        sid = ws.id  # numeric sheetId needed for chart API calls

        # Read raw price history
        history_ws = self._get_or_create_tab(config.SHEET_HISTORY)
        raw = history_ws.get_all_values()
        if len(raw) <= 1:
            ws.update([["No price history yet — run the tracker first."]], "A1")
            return

        # Parse into pivot: date → route → min_price
        from collections import defaultdict
        pivot: dict[str, dict[str, float]] = defaultdict(dict)
        all_time_best: dict[str, tuple[float, str, str]] = {}  # route→(price,date,airlines)
        routes: set[str] = set()

        for row in raw[1:]:
            if len(row) < 5:
                continue
            date_str = row[0][:10]
            route    = row[1]
            airlines = row[4]
            try:
                price = float(row[2])
            except ValueError:
                continue
            routes.add(route)
            if route not in pivot[date_str] or price < pivot[date_str][route]:
                pivot[date_str][route] = price
            if route not in all_time_best or price < all_time_best[route][0]:
                all_time_best[route] = (price, date_str, airlines)

        sorted_routes = sorted(routes)
        sorted_dates  = sorted(pivot.keys())
        now = datetime.utcnow().strftime("%b %d, %Y %H:%M UTC")

        # ------ Build sheet data (track row indices as we go) ------
        data: list[list] = []

        data.append(["Emma's Flight Price Analysis — YYZ to Tasmania"])
        data.append([f"Last updated: {now}"])
        data.append([])

        sect1_idx = len(data)           # "ALL-TIME BEST PRICES" header row (0-indexed)
        data.append(["ALL-TIME BEST PRICES"])
        best_hdr_idx = len(data)        # column header row
        data.append(["Route", "Best Price (CAD)", "Date Found", "Airlines"])
        best_data_start = len(data)
        for route in sorted_routes:
            if route in all_time_best:
                price, date, airlines = all_time_best[route]
                data.append([route, price, date, airlines])
        best_data_end = len(data)       # exclusive

        data.append([])

        sect2_idx = len(data)           # "PRICE TREND" header row
        data.append(["PRICE TREND OVER TIME"])
        pivot_hdr_idx = len(data)       # pivot column-header row
        data.append(["Date Checked"] + sorted_routes)
        for date in sorted_dates:
            data.append([date] + [pivot[date].get(r, "") for r in sorted_routes])
        pivot_end_idx = len(data)       # exclusive

        ws.update(data, "A1", value_input_option="USER_ENTERED")

        # ------ Formatting ------
        last_pivot_col = _col_letter(len(sorted_routes) + 1)

        # Big title
        ws.format("A1", {
            "textFormat": {"bold": True, "fontSize": 14,
                           "foregroundColor": COLOR_WHITE},
            "backgroundColor": COLOR_HEADER,
        })
        # Section headers
        for idx in [sect1_idx, sect2_idx]:
            ws.format(f"A{idx+1}", {
                "textFormat": {"bold": True, "fontSize": 11},
                "backgroundColor": {"red": 0.878, "green": 0.878, "blue": 0.878},
            })
        # Best-prices column headers
        ws.format(f"A{best_hdr_idx+1}:D{best_hdr_idx+1}", {
            "backgroundColor": COLOR_HIST_HDR,
            "textFormat": {"bold": True, "foregroundColor": COLOR_WHITE},
            "horizontalAlignment": "CENTER",
        })
        # Pivot column headers
        ws.format(f"A{pivot_hdr_idx+1}:{last_pivot_col}{pivot_hdr_idx+1}", {
            "backgroundColor": COLOR_HIST_HDR,
            "textFormat": {"bold": True, "foregroundColor": COLOR_WHITE},
            "horizontalAlignment": "CENTER",
        })
        # Highlight best-price cells below threshold
        for i in range(best_data_start, best_data_end):
            route = sorted_routes[i - best_data_start] if (i - best_data_start) < len(sorted_routes) else None
            if route and route in all_time_best and all_time_best[route][0] < threshold:
                ws.format(f"B{i+1}", {"backgroundColor": COLOR_DEAL,
                                       "textFormat": {"bold": True}})
        ws.freeze(rows=1)

        # ------ Charts via Sheets API batch_update ------
        chart_anchor_row = pivot_end_idx + 2  # 0-indexed, below pivot data

        requests = []

        # 1. Line chart: price trend over time
        series = [
            {
                "series": {"sourceRange": {"sources": [{
                    "sheetId": sid,
                    "startRowIndex": pivot_hdr_idx,
                    "endRowIndex":   pivot_end_idx,
                    "startColumnIndex": col + 1,
                    "endColumnIndex":   col + 2,
                }]}},
                "targetAxis": "LEFT_AXIS",
            }
            for col, _ in enumerate(sorted_routes)
        ]
        requests.append({"addChart": {"chart": {
            "spec": {
                "title": "Price Trend — YYZ → Tasmania (CAD)",
                "basicChart": {
                    "chartType": "LINE",
                    "legendPosition": "BOTTOM_LEGEND",
                    "axis": [
                        {"position": "BOTTOM_AXIS", "title": "Date Checked"},
                        {"position": "LEFT_AXIS",   "title": "Price (CAD)"},
                    ],
                    "domains": [{"domain": {"sourceRange": {"sources": [{
                        "sheetId": sid,
                        "startRowIndex":    pivot_hdr_idx,
                        "endRowIndex":      pivot_end_idx,
                        "startColumnIndex": 0,
                        "endColumnIndex":   1,
                    }]}}}],
                    "series": series,
                    "headerCount": 1,
                },
            },
            "position": {"overlayPosition": {
                "anchorCell": {"sheetId": sid,
                               "rowIndex": chart_anchor_row, "columnIndex": 0},
                "widthPixels": 680, "heightPixels": 400,
            }},
        }}})

        # 2. Bar chart: best price per route vs budget
        if best_data_end > best_data_start:
            requests.append({"addChart": {"chart": {
                "spec": {
                    "title": f"Best Price per Route vs Budget (${threshold:,.0f} CAD)",
                    "basicChart": {
                        "chartType": "BAR",
                        "legendPosition": "NO_LEGEND",
                        "axis": [
                            {"position": "BOTTOM_AXIS", "title": "Price (CAD)"},
                            {"position": "LEFT_AXIS",   "title": "Route"},
                        ],
                        "domains": [{"domain": {"sourceRange": {"sources": [{
                            "sheetId": sid,
                            "startRowIndex":    best_data_start,
                            "endRowIndex":      best_data_end,
                            "startColumnIndex": 0,
                            "endColumnIndex":   1,
                        }]}}}],
                        "series": [{"series": {"sourceRange": {"sources": [{
                            "sheetId": sid,
                            "startRowIndex":    best_data_start,
                            "endRowIndex":      best_data_end,
                            "startColumnIndex": 1,
                            "endColumnIndex":   2,
                        }]}}, "targetAxis": "BOTTOM_AXIS"}],
                        "headerCount": 0,
                    },
                },
                "position": {"overlayPosition": {
                    "anchorCell": {"sheetId": sid,
                                   "rowIndex": chart_anchor_row, "columnIndex": 6},
                    "widthPixels": 480, "heightPixels": 300,
                }},
            }}})

        if requests:
            self._sheet.batch_update({"requests": requests})

        logger.info(
            "Analysis tab built: %d route(s), %d date(s), %d chart(s).",
            len(sorted_routes), len(sorted_dates), len(requests),
        )

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
