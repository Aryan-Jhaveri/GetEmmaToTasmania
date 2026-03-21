import logging
import os
from datetime import datetime
from itertools import product

import requests

import config
from src.models import FlightOffer, RouteConfig

logger = logging.getLogger(__name__)

BASE_URL = "https://tequila-api.kiwi.com/v2/search"


class KiwiClient:
    def __init__(self):
        self._api_key = os.environ["KIWI_API_KEY"]

    def build_routes(
        self,
        origins: list[str],
        destinations: list[str],
        start_date: str,
        end_date: str,
        step_days: int = 7,  # not used by Kiwi — it searches the full range in one call
    ) -> list[RouteConfig]:
        """Generate one RouteConfig per origin-destination pair (Kiwi searches the full date range)."""
        return [
            RouteConfig(origin, dest, start_date)  # departure_date = range start
            for origin, dest in product(origins, destinations)
        ]

    def search_cheapest_offers(
        self,
        routes: list[RouteConfig],
        start_date: str,
        end_date: str,
        max_results: int = 10,
    ) -> list[FlightOffer]:
        """
        Search Kiwi for the cheapest offers per route across the full date range.
        One API call per origin-destination pair.
        """
        all_offers: list[FlightOffer] = []
        for route in routes:
            offers = self._search_route(route, start_date, end_date, max_results)
            all_offers.extend(offers)
        return all_offers

    def _search_route(
        self,
        route: RouteConfig,
        start_date: str,
        end_date: str,
        max_results: int,
    ) -> list[FlightOffer]:
        # Kiwi expects DD/MM/YYYY
        date_from = _fmt_date(start_date)
        date_to = _fmt_date(end_date)

        params = {
            "fly_from": route.origin,
            "fly_to": route.destination,
            "date_from": date_from,
            "date_to": date_to,
            "flight_type": "oneway",
            "max_stopovers": config.MAX_CONNECTIONS,
            "curr": config.CURRENCY,
            "sort": "price",
            "asc": 1,
            "limit": max_results,
            "partner_market": "ca",   # Canadian market for CAD pricing
        }
        headers = {"apikey": self._api_key}

        try:
            resp = requests.get(BASE_URL, params=params, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json().get("data", [])
            return [o for raw in data if (o := self._parse(raw, route)) is not None]
        except requests.RequestException as e:
            logger.warning("Kiwi API error for %s: %s", route.key, e)
            return []

    @staticmethod
    def _parse(raw: dict, route: RouteConfig) -> FlightOffer | None:
        try:
            price_cad = float(raw["price"])
            segments = raw.get("route", [])
            if not segments:
                return None

            origin = segments[0]["flyFrom"]
            destination = segments[-1]["flyTo"]
            departure_date = segments[0]["local_departure"][:10]
            num_stops = len(segments) - 1

            carriers = []
            for seg in segments:
                code = seg.get("airline", "")
                if code and code not in carriers:
                    carriers.append(code)
            airlines = " / ".join(carriers)

            # Duration: difference between first departure and last arrival
            dep_dt = datetime.fromisoformat(segments[0]["local_departure"])
            arr_dt = datetime.fromisoformat(segments[-1]["local_arrival"])
            total_minutes = int((arr_dt - dep_dt).total_seconds() / 60)
            hours, mins = divmod(total_minutes, 60)
            duration = f"{hours}h {mins:02d}m"

            booking_url = raw.get("deep_link", "")

            return FlightOffer(
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                price_cad=price_cad,
                airlines=airlines,
                num_stops=num_stops,
                duration=duration,
                source="Kiwi",
                booking_url=booking_url,
            )
        except (KeyError, IndexError, ValueError, TypeError) as e:
            logger.debug("Could not parse Kiwi offer: %s — %s", e, raw)
            return None


def _fmt_date(iso_date: str) -> str:
    """Convert '2025-06-01' → '01/06/2025' for Kiwi API."""
    y, m, d = iso_date.split("-")
    return f"{d}/{m}/{y}"
