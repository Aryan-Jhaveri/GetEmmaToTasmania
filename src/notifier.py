import logging
import os
import smtplib
from collections import Counter, defaultdict
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config
from src.booking_links import get_booking_links
from src.models import DealOffer, FlightOffer

logger = logging.getLogger(__name__)

# Tag display config: (badge label, hex background, hex text)
TAG_STYLE = {
    "ALL_TIME_LOW":      ("All-time low!",        "#ffd60a", "#1d1d1f"),
    "BELOW_BUDGET":      ("Under budget",          "#30d158", "#ffffff"),
    "NEAR_ALL_TIME_LOW": ("Near record low",        "#5e5ce6", "#ffffff"),
    "BELOW_ROUTE_AVG":   ("Below typical price",   "#0071e3", "#ffffff"),
    "BEST_DATE":         ("Cheapest date",          "#636366", "#ffffff"),
}


class EmailNotifier:
    def __init__(self):
        self._address = os.environ["GMAIL_ADDRESS"]
        self._password = os.environ["GMAIL_APP_PASSWORD"]

    def send_alert(
        self,
        deals: list[DealOffer],
        all_offers: list[FlightOffer],
        recipient: str,
        threshold: float,
        historical_mins: dict[str, float],
        raw_offers: list[FlightOffer] | None = None,
        booking_nudge: bool = False,
    ) -> None:
        if not deals:
            return

        subject = self._subject(deals, booking_nudge)
        html = self._build_html(deals, threshold, raw_offers or [], booking_nudge)

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

    @staticmethod
    def _subject(deals: list[DealOffer], booking_nudge: bool) -> str:
        best = min(deals, key=lambda d: d.offer.price_cad)
        prefix = "⚠️ BOOK SOON — " if booking_nudge else "✈️ "
        return (
            f"{prefix}Flight Deal: {best.offer.route_key} "
            f"for {best.offer.price_display} ({best.offer.departure_date})"
        )

    def _build_html(
        self,
        deals: list[DealOffer],
        threshold: float,
        raw_offers: list[FlightOffer],
        booking_nudge: bool,
    ) -> str:
        from datetime import datetime
        run_time = datetime.utcnow().strftime("%B %d, %Y at %I:%M %p UTC")
        sheet_link = f"https://docs.google.com/spreadsheets/d/{os.environ.get('GOOGLE_SHEET_ID', '')}"

        nudge_banner   = self._nudge_banner() if booking_nudge else ""
        top_pick       = self._top_pick_card(deals)
        route_tables   = self._route_tables(deals)
        insights_block = self._insights_block(deals, raw_offers, threshold)
        all_prices     = self._all_prices_table(raw_offers)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f5f5f7; margin: 0; padding: 16px; color: #1d1d1f; }}
  .container {{ max-width: 600px; margin: 0 auto; }}
  h1  {{ font-size: 22px; margin-bottom: 4px; }}
  h2  {{ font-size: 16px; font-weight: 700; margin: 0 0 12px; color: #1d1d1f; }}
  .subtitle {{ color: #6e6e73; font-size: 14px; margin-bottom: 20px; }}

  /* Nudge banner */
  .nudge {{ background: #ff3b30; color: white; border-radius: 12px; padding: 16px 20px;
            margin-bottom: 20px; font-size: 15px; font-weight: 600; text-align: center;
            line-height: 1.5; }}

  /* Top pick */
  .top-pick {{ background: white; border-radius: 14px; padding: 20px;
               margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.10);
               border-top: 4px solid #30d158; }}
  .top-pick .route {{ font-size: 20px; font-weight: 800; margin-bottom: 2px; }}
  .top-pick .price {{ font-size: 36px; font-weight: 800; color: #30d158; line-height: 1.1; }}
  .top-pick .meta  {{ font-size: 14px; color: #6e6e73; margin-top: 6px; line-height: 1.6; }}
  .book-btn {{ display: block; background: #0071e3; color: white;
               text-decoration: none; text-align: center; border-radius: 10px;
               padding: 14px; margin-top: 14px; font-size: 16px; font-weight: 600; }}
  .book-btn-sm {{ display: inline-block; background: #f5f5f7; color: #0071e3;
                  text-decoration: none; border-radius: 8px; padding: 8px 14px;
                  margin: 4px 4px 0 0; font-size: 13px; font-weight: 600;
                  border: 1px solid #d2d2d7; }}

  /* Tag badges */
  .badge {{ display: inline-block; border-radius: 6px; padding: 2px 8px;
            font-size: 11px; font-weight: 700; margin: 0 3px 3px 0;
            text-transform: uppercase; letter-spacing: 0.3px; }}

  /* Section cards */
  .section {{ background: white; border-radius: 12px; padding: 20px;
              margin-bottom: 16px; }}

  /* Route date table */
  .date-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  .date-table th {{ text-align: left; color: #6e6e73; font-weight: 600;
                    padding: 0 6px 8px; border-bottom: 2px solid #f0f0f0; font-size: 11px;
                    text-transform: uppercase; letter-spacing: 0.4px; }}
  .date-table td {{ padding: 8px 6px; border-bottom: 1px solid #f5f5f7;
                    vertical-align: top; }}
  .date-table tr:last-child td {{ border-bottom: none; }}
  .date-table .price-cell {{ font-weight: 700; font-size: 15px; white-space: nowrap; }}
  .deal-price {{ color: #30d158; }}
  .route-label {{ font-size: 15px; font-weight: 700; margin-bottom: 12px; color: #1d1d1f; }}

  /* Insights */
  .insight-row {{ font-size: 13px; color: #1d1d1f; padding: 6px 0;
                  border-bottom: 1px solid #f5f5f7; line-height: 1.5; }}
  .insight-row:last-child {{ border-bottom: none; }}
  .insight-label {{ color: #6e6e73; }}

  /* All-prices table */
  .all-prices-table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  .all-prices-table th {{ text-align: left; color: #aeaeb2; font-weight: 600;
                          padding: 0 4px 6px; font-size: 10px; text-transform: uppercase; }}
  .all-prices-table td {{ padding: 5px 4px; border-bottom: 1px solid #f5f5f7; color: #3c3c43; }}
  .all-prices-table tr:last-child td {{ border-bottom: none; }}
  .all-prices-table .deal {{ font-weight: 700; color: #30d158; }}

  /* Footer */
  .footer {{ font-size: 12px; color: #6e6e73; text-align: center;
             margin-top: 24px; line-height: 1.8; }}
  .clanker {{ font-size: 11px; color: #aeaeb2; margin-top: 10px; font-style: italic; }}
  a {{ color: #0071e3; }}
</style>
</head>
<body>
<div class="container">

  <h1>Hi Emma! ✈️</h1>
  <p class="subtitle">Here's today's flight price report for your trip to Tasmania.</p>

  {nudge_banner}
  {top_pick}
  {route_tables}
  {insights_block}
  {all_prices}

  <div class="footer">
    Checked on {run_time}.<br>
    <a href="{sheet_link}">View full price history &amp; charts in Google Sheets</a><br>
    To change your budget or search dates, edit the Settings tab in your Sheet.
    <div class="clanker">** this email was generated by a clanker</div>
  </div>

</div>
</body>
</html>"""

    # ------------------------------------------------------------------
    # Top pick card — single best-value deal across all routes
    # ------------------------------------------------------------------

    @staticmethod
    def _top_pick_card(deals: list[DealOffer]) -> str:
        best = min(deals, key=lambda d: d.offer.price_cad)
        o = best.offer
        links = get_booking_links(o)
        primary = next(l for l in links if l["primary"])
        secondary = [l for l in links if not l["primary"]]

        badges = "".join(_badge(t) for t in best.tags)
        sec_btns = "".join(
            f'<a class="book-btn-sm" href="{l["url"]}">{l["label"]}</a>'
            for l in secondary
        )

        savings = ""
        if best.hist_min_cad and o.price_cad < best.hist_min_cad:
            diff = best.hist_min_cad - o.price_cad
            savings = f'<div style="font-size:13px;color:#ff9f0a;font-weight:600;margin-top:4px;">New all-time low — ${diff:,.0f} cheaper than previous best</div>'

        return f"""<div class="top-pick">
  <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.5px;color:#6e6e73;margin-bottom:4px;">Top pick today</div>
  <div class="route">{o.origin} → {o.destination}</div>
  <div class="price">{o.price_display}</div>
  <div class="meta">
    Departs {o.departure_date} &nbsp;·&nbsp; {o.airlines}<br>
    {o.num_stops} stop{"s" if o.num_stops != 1 else ""} &nbsp;·&nbsp; {o.duration} total flight time
  </div>
  <div style="margin-top:8px;">{badges}</div>
  {savings}
  <a class="book-btn" href="{primary['url']}">{primary['label']} →</a>
  <div style="margin-top:6px;">{sec_btns}</div>
</div>"""

    # ------------------------------------------------------------------
    # Per-route date tables
    # ------------------------------------------------------------------

    @staticmethod
    def _route_tables(deals: list[DealOffer]) -> str:
        by_route: dict[str, list[DealOffer]] = defaultdict(list)
        for d in deals:
            by_route[d.offer.route_key].append(d)

        blocks = []
        for route, route_deals in sorted(by_route.items()):
            route_deals.sort(key=lambda d: d.offer.price_cad)
            rows = []
            for d in route_deals:
                o = d.offer
                links = get_booking_links(o)
                primary = next(l for l in links if l["primary"])
                price_class = "price-cell deal-price" if "BELOW_BUDGET" in d.tags else "price-cell"
                badges = "".join(_badge(t) for t in d.tags if t != "BEST_DATE" or len(d.tags) == 1)
                rows.append(f"""<tr>
    <td><b>{o.departure_date}</b></td>
    <td class="{price_class}">{o.price_display}</td>
    <td style="color:#6e6e73">{o.airlines}<br><span style="font-size:11px">{o.num_stops} stop{"s" if o.num_stops != 1 else ""} · {o.duration}</span></td>
    <td>{badges}<br><a href="{primary['url']}" style="font-size:12px;white-space:nowrap">Book →</a></td>
  </tr>""")

            blocks.append(f"""<div class="section">
  <div class="route-label">{route}</div>
  <table class="date-table">
    <tr>
      <th>Departs</th><th>Price</th><th>Airlines / Details</th><th>Status</th>
    </tr>
    {''.join(rows)}
  </table>
</div>""")

        return "\n".join(blocks)

    # ------------------------------------------------------------------
    # Insights block
    # ------------------------------------------------------------------

    @staticmethod
    def _insights_block(
        deals: list[DealOffer],
        raw_offers: list[FlightOffer],
        threshold: float,
    ) -> str:
        if not raw_offers:
            return ""

        rows = []

        # Flights scanned
        dep_dates = sorted({o.departure_date for o in raw_offers})
        rows.append(
            f'<div class="insight-row">'
            f'<span class="insight-label">Scanned today: </span>'
            f'<b>{len(raw_offers)} flights</b> across {len(dep_dates)} departure dates '
            f'({dep_dates[0]} – {dep_dates[-1]})'
            f'</div>'
        )

        # Price range
        prices = [o.price_cad for o in raw_offers]
        rows.append(
            f'<div class="insight-row">'
            f'<span class="insight-label">Price range: </span>'
            f'<b>${min(prices):,.0f} – ${max(prices):,.0f} CAD</b> '
            f'(your budget: ${threshold:,.0f})'
            f'</div>'
        )

        # How many dates are below budget per route
        by_route: dict[str, list[float]] = defaultdict(list)
        for o in raw_offers:
            by_route[o.route_key].append(o.price_cad)
        for route, rprices in sorted(by_route.items()):
            below = sum(1 for p in rprices if p < threshold)
            avg = sum(rprices) / len(rprices)
            rows.append(
                f'<div class="insight-row">'
                f'<span class="insight-label">{route}: </span>'
                f'<b>{below} of {len(rprices)} prices below ${threshold:,.0f}</b> '
                f'· avg ${avg:,.0f} today'
                f'</div>'
            )

        # Top cheapest airline
        cheapest_per_combo: dict[tuple, FlightOffer] = {}
        for o in raw_offers:
            key = (o.route_key, o.departure_date)
            if key not in cheapest_per_combo or o.price_cad < cheapest_per_combo[key].price_cad:
                cheapest_per_combo[key] = o
        airline_counts: Counter = Counter(
            o.airlines for o in cheapest_per_combo.values() if o.airlines
        )
        if airline_counts:
            top_airline, top_count = airline_counts.most_common(1)[0]
            rows.append(
                f'<div class="insight-row">'
                f'<span class="insight-label">Most frequent cheapest airline: </span>'
                f'<b>{top_airline}</b> '
                f'(cheapest on {top_count}/{len(cheapest_per_combo)} date–route combos)'
                f'</div>'
            )

        # Historical context per deal route
        seen_routes: set[str] = set()
        for deal in deals:
            r = deal.offer.route_key
            if r in seen_routes:
                continue
            seen_routes.add(r)
            if deal.hist_min_cad:
                diff = deal.offer.price_cad - deal.hist_min_cad
                if diff < 0:
                    verdict = f'<b style="color:#30d158">New all-time low by ${abs(diff):,.0f}!</b>'
                else:
                    verdict = f'${diff:,.0f} above all-time low of ${deal.hist_min_cad:,.0f}'
            else:
                verdict = 'First data — no baseline yet'
            rows.append(
                f'<div class="insight-row">'
                f'<span class="insight-label">{r} vs. history: </span>'
                f'{verdict}'
                f'</div>'
            )

        return f"""<div class="section" style="border-left:4px solid #0071e3;">
  <h2>Today's insights</h2>
  {''.join(rows)}
</div>"""

    # ------------------------------------------------------------------
    # All prices table — compact reference for every date checked
    # ------------------------------------------------------------------

    @staticmethod
    def _all_prices_table(raw_offers: list[FlightOffer]) -> str:
        if not raw_offers:
            return ""

        # Best offer per (route, date)
        best: dict[tuple, FlightOffer] = {}
        for o in raw_offers:
            key = (o.route_key, o.departure_date)
            if key not in best or o.price_cad < best[key].price_cad:
                best[key] = o

        sorted_offers = sorted(best.values(), key=lambda o: o.price_cad)

        rows = []
        for o in sorted_offers:
            cls = ' class="deal"' if "BELOW_BUDGET" else ""
            rows.append(
                f"<tr><td>{o.route_key}</td>"
                f"<td>{o.departure_date}</td>"
                f"<td{cls}><b>{o.price_display}</b></td>"
                f"<td style='color:#6e6e73'>{o.airlines}</td>"
                f"<td style='color:#6e6e73'>{o.num_stops} stop{'s' if o.num_stops != 1 else ''} · {o.duration}</td></tr>"
            )

        return f"""<div class="section">
  <h2 style="color:#6e6e73;font-size:13px;">All prices checked today</h2>
  <table class="all-prices-table">
    <tr><th>Route</th><th>Departs</th><th>Price</th><th>Airlines</th><th>Details</th></tr>
    {''.join(rows)}
  </table>
</div>"""

    # ------------------------------------------------------------------

    @staticmethod
    def _nudge_banner() -> str:
        from datetime import date
        import config as _cfg
        deadline = date.fromisoformat(_cfg.TRACKER_BOOKING_DEADLINE)
        days_left = (deadline - date.today()).days
        countdown = (
            f"{days_left} day{'s' if days_left != 1 else ''} left to book"
            if days_left > 0 else "booking deadline has passed"
        )
        return (
            f'<div class="nudge">'
            f'⚠️ Book by {deadline.strftime("%B %d, %Y")} — {countdown}!<br>'
            f'<span style="font-weight:400;font-size:13px;">'
            f'Flights depart in June. Prices typically rise as departure approaches.'
            f'</span>'
            f'</div>'
        )


# ------------------------------------------------------------------
# Module helper
# ------------------------------------------------------------------

def _badge(tag: str) -> str:
    label, bg, fg = TAG_STYLE.get(tag, (tag, "#636366", "#ffffff"))
    return (
        f'<span class="badge" style="background:{bg};color:{fg};">{label}</span>'
    )
