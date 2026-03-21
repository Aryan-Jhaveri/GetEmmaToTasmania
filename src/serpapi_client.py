import logging
import os
from itertools import product

import requests

import config
from src.models import FlightOffer, RouteConfig

logger = logging.getLogger(__name__)

SERPAPI_URL = "https://serpapi.com/search"


class SerpApiClient:
    def __init__(self):
        self._api_key = os.environ["SERPAPI_KEY"]

    def build_routes(
        self,
        origins: list[str],
        destinations: list[str],
        start_date: str,
        end_date: str,
        step_days: int = 7,
    ) -> list[tuple[RouteConfig, str]]:
        """
        Return (RouteConfig, end_date) pairs — one per origin/destination combo.
        SerpAPI searches a date range so we make one call per route pair, not per date.
        """
        return [
            (RouteConfig(o, d, start_date), end_date)
            for o, d in product(origins, destinations)
        ]

    def search_cheapest_offers(
        self,
        route_pairs: list[tuple[RouteConfig, str]],
        max_results: int = 10,
    ) -> list[FlightOffer]:
        all_offers: list[FlightOffer] = []
        for route, end_date in route_pairs:
            offers = self._search_route(route, end_date, max_results)
            all_offers.extend(offers)
        return all_offers

    def _search_route(
        self,
        route: RouteConfig,
        end_date: str,
        max_results: int,
    ) -> list[FlightOffer]:
        """
        SerpAPI Google Flights docs:
        https://serpapi.com/google-flights-api
        type=2 → one-way, currency=CAD, hl=en
        """
        params = {
            "engine": "google_flights",
            "departure_id": route.origin,
            "arrival_id": route.destination,
            "outbound_date": route.departure_date,   # start of range
            "type": "2",                             # 1=round-trip, 2=one-way
            "currency": config.CURRENCY,
            "hl": "en",
            "api_key": self._api_key,
            "no_cache": "false",
        }

        offers = []
        try:
            resp = requests.get(SERPAPI_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            if "error" in data:
                logger.warning("SerpAPI error for %s: %s", route.key, data["error"])
                return []

            raw_flights = data.get("best_flights", []) + data.get("other_flights", [])
            for raw in raw_flights[:max_results]:
                offer = self._parse(raw, route)
                if offer:
                    offers.append(offer)

        except requests.RequestException as e:
            logger.warning("SerpAPI request failed for %s: %s", route.key, e)

        logger.info(
            "SerpAPI: %s → %s on %s → %d offers",
            route.origin, route.destination, route.departure_date, len(offers),
        )
        return offers

    @staticmethod
    def _parse(raw: dict, route: RouteConfig) -> FlightOffer | None:
        try:
            price_cad = float(raw["price"])
            segments = raw.get("flights", [])
            if not segments:
                return None

            origin = segments[0]["departure_airport"]["id"]
            destination = segments[-1]["arrival_airport"]["id"]
            departure_date = segments[0]["departure_time"][:10]
            num_stops = len(segments) - 1

            airlines = " / ".join(
                dict.fromkeys(  # preserve order, deduplicate
                    seg.get("airline", "") for seg in segments
                    if seg.get("airline")
                )
            )

            total_minutes = raw.get("total_duration", 0)
            if not total_minutes:
                total_minutes = sum(seg.get("duration", 0) for seg in segments)
            hours, mins = divmod(int(total_minutes), 60)
            duration = f"{hours}h {mins:02d}m"

            # Construct a Google Flights search link for this route/date
            booking_url = (
                f"https://www.google.com/travel/flights?q=Flights+from+"
                f"{route.origin}+to+{route.destination}+on+{departure_date}"
            )

            return FlightOffer(
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                price_cad=price_cad,
                airlines=airlines,
                num_stops=num_stops,
                duration=duration,
                source="Google Flights",
                booking_url=booking_url,
            )
        except (KeyError, IndexError, ValueError, TypeError) as e:
            logger.debug("Could not parse SerpAPI offer: %s — %s", e, raw)
            return None
