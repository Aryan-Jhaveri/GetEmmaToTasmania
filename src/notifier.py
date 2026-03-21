import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config
from src.booking_links import get_booking_links
from src.models import FlightOffer

logger = logging.getLogger(__name__)


class EmailNotifier:
    def __init__(self):
        self._address = os.environ["GMAIL_ADDRESS"]
        self._password = os.environ["GMAIL_APP_PASSWORD"]

    def send_alert(
        self,
        deals: list[FlightOffer],
        all_offers: list[FlightOffer],
        recipient: str,
        threshold: float,
        historical_mins: dict[str, float],
    ) -> None:
        if not deals:
            return

        subject = self._subject(deals)
        html = self._build_html(deals, all_offers, threshold, historical_mins)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Emma's Flight Tracker <{self._address}>"
        msg["To"] = recipient
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.login(self._address, self._password)
            server.sendmail(self._address, recipient, msg.as_string())

        logger.info("Alert email sent to %s with %d deal(s).", recipient, len(deals))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _subject(deals: list[FlightOffer]) -> str:
        best = min(deals, key=lambda o: o.price_cad)
        return (
            f"Flight Deal: {best.origin} → {best.destination} "
            f"for {best.price_display} ({best.departure_date})"
        )

    def _build_html(
        self,
        deals: list[FlightOffer],
        all_offers: list[FlightOffer],
        threshold: float,
        historical_mins: dict[str, float],
    ) -> str:
        deal_cards = "\n".join(self._deal_card(d, historical_mins) for d in deals)
        other_rows = self._other_prices_table(all_offers, deals)

        from datetime import datetime
        run_time = datetime.utcnow().strftime("%B %d, %Y at %I:%M %p UTC")

        sheet_link = (
            f"https://docs.google.com/spreadsheets/d/{os.environ.get('GOOGLE_SHEET_ID', '')}"
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f5f5f7; margin: 0; padding: 16px; color: #1d1d1f; }}
  .container {{ max-width: 600px; margin: 0 auto; }}
  h1 {{ font-size: 22px; margin-bottom: 4px; }}
  .subtitle {{ color: #6e6e73; font-size: 14px; margin-bottom: 24px; }}
  .card {{ background: white; border-radius: 12px; padding: 20px;
           margin-bottom: 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
  .route {{ font-size: 20px; font-weight: 700; margin-bottom: 8px; }}
  .price {{ font-size: 32px; font-weight: 800; color: #30d158; }}
  .detail {{ font-size: 14px; color: #6e6e73; margin-top: 4px; }}
  .badge {{ display: inline-block; background: #ffd60a; color: #1d1d1f;
            font-size: 12px; font-weight: 600; border-radius: 6px;
            padding: 2px 8px; margin-top: 8px; }}
  .book-btn {{ display: block; background: #0071e3; color: white;
               text-decoration: none; text-align: center; border-radius: 10px;
               padding: 14px; margin-top: 10px; font-size: 16px;
               font-weight: 600; }}
  .book-btn-secondary {{ display: block; background: #f5f5f7; color: #0071e3;
               text-decoration: none; text-align: center; border-radius: 10px;
               padding: 12px; margin-top: 8px; font-size: 14px;
               font-weight: 600; border: 1px solid #d2d2d7; }}
  .buy-label {{ font-size: 12px; color: #6e6e73; margin-top: 16px;
                margin-bottom: 4px; font-weight: 600; text-transform: uppercase;
                letter-spacing: 0.5px; }}
  .other-section {{ background: white; border-radius: 12px; padding: 20px;
                    margin-bottom: 16px; }}
  .other-section h3 {{ font-size: 14px; color: #6e6e73; margin: 0 0 12px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  td {{ padding: 6px 4px; border-bottom: 1px solid #f0f0f0; }}
  td:last-child {{ text-align: right; }}
  .footer {{ font-size: 12px; color: #6e6e73; text-align: center;
             margin-top: 24px; line-height: 1.6; }}
  a.sheet-link {{ color: #0071e3; }}
</style>
</head>
<body>
<div class="container">
  <h1>Hi Emma!</h1>
  <p class="subtitle">
    Good news — we found prices below your ${threshold:,.0f} CAD alert threshold.
  </p>

  {deal_cards}

  {other_rows}

  <div class="footer">
    This check ran on {run_time}.<br>
    <a class="sheet-link" href="{sheet_link}">View full price history in Google Sheets</a><br>
    To change your alert threshold or search dates, update the Settings tab in your Sheet.
  </div>
</div>
</body>
</html>"""

    def _deal_card(self, offer: FlightOffer, historical_mins: dict[str, float]) -> str:
        prev_min = historical_mins.get(offer.route_key)
        savings_badge = ""
        if prev_min and offer.price_cad < prev_min:
            diff = prev_min - offer.price_cad
            savings_badge = (
                f'<div class="badge">New all-time low! '
                f'${diff:,.0f} cheaper than previous best</div>'
            )

        links = get_booking_links(offer)
        primary = next(l for l in links if l["primary"])
        secondary = [l for l in links if not l["primary"]]
        secondary_buttons = "\n  ".join(
            f'<a class="book-btn-secondary" href="{l["url"]}">{l["label"]}</a>'
            for l in secondary
        )

        source_note = f'<div class="detail">Found via: {offer.source}</div>' if offer.source else ""

        return f"""<div class="card">
  <div class="route">{offer.origin} → {offer.destination}</div>
  <div class="price">{offer.price_display}</div>
  <div class="detail">Departure: {offer.departure_date}</div>
  <div class="detail">Airlines: {offer.airlines}</div>
  <div class="detail">Stops: {offer.num_stops} &nbsp;·&nbsp; Duration: {offer.duration}</div>
  {source_note}
  {savings_badge}
  <div class="buy-label">Where to buy</div>
  <a class="book-btn" href="{primary['url']}">{primary['label']} →</a>
  {secondary_buttons}
</div>"""

    @staticmethod
    def _other_prices_table(
        all_offers: list[FlightOffer], deals: list[FlightOffer]
    ) -> str:
        deal_keys = {(d.route_key, d.departure_date) for d in deals}
        others = [
            o for o in all_offers
            if (o.route_key, o.departure_date) not in deal_keys
        ]
        if not others:
            return ""

        rows = "\n".join(
            f"<tr><td>{o.route_key}</td>"
            f"<td>{o.departure_date}</td>"
            f"<td>{o.airlines}</td>"
            f"<td>{o.price_display}</td></tr>"
            for o in sorted(others, key=lambda x: x.price_cad)
        )
        return f"""<div class="other-section">
  <h3>Other prices checked today (above threshold)</h3>
  <table>
    <tr><td><b>Route</b></td><td><b>Departure</b></td>
        <td><b>Airlines</b></td><td><b>Price</b></td></tr>
    {rows}
  </table>
</div>"""
