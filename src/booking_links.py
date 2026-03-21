"""
Generate booking/search URLs for a FlightOffer across multiple platforms.

Kiwi's deep_link (stored in offer.booking_url) goes directly to a bookable
itinerary. The others are search links — Emma picks the cheapest on the day.
"""

from src.models import FlightOffer


def get_booking_links(offer: FlightOffer) -> list[dict]:
    """
    Return a list of {label, url, primary} dicts for the email/dashboard.
    Ordered: direct booking first (if available), then comparison sites.
    """
    o, d, date = offer.origin, offer.destination, offer.departure_date
    # Skyscanner uses YYMMDD: 2025-06-07 → 250607
    sk_date = date.replace("-", "")[2:]

    links = []

    # Direct booking via Kiwi (only present if offer came from Kiwi API)
    if offer.booking_url:
        links.append({
            "label": "Book on Kiwi.com",
            "url": offer.booking_url,
            "primary": True,
        })

    links += [
        {
            "label": "Google Flights",
            "url": (
                f"https://www.google.com/travel/flights?q=Flights+from+"
                f"{o}+to+{d}+on+{date}"
            ),
            "primary": not offer.booking_url,  # primary if no Kiwi link
        },
        {
            "label": "Skyscanner",
            "url": f"https://www.skyscanner.com/transport/flights/{o}/{d}/{sk_date}/",
            "primary": False,
        },
        {
            "label": "Kayak",
            "url": f"https://www.kayak.com/flights/{o}-{d}/{date}",
            "primary": False,
        },
    ]
    return links
