import logging
import os
from datetime import date, timedelta
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
    ) -> list[RouteConfig]:
        """One RouteConfig per (origin, destination, departure_date) step."""
        routes = []
        current = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        while current <= end:
            for o, d in product(origins, destinations):
                routes.append(RouteConfig(o, d, current.isoformat()))
            current += timedelta(days=step_days)
        return routes

    def search_cheapest_offers(
        self,
        routes: list[RouteConfig],
        max_results: int = 5,
    ) -> list[FlightOffer]:
        """One SerpAPI call per route — returns cheapest offers per departure date."""
        all_offers: list[FlightOffer] = []
        for route in routes:
            offers = self._search_route(route, max_results)
            all_offers.extend(offers)
        return all_offers

    def _search_route(self, route: RouteConfig, max_results: int) -> list[FlightOffer]:
        params = {
            "engine":        "google_flights",
            "departure_id":  route.origin,
            "arrival_id":    route.destination,
            "outbound_date": route.departure_date,
            "type":          "2",       # one-way
            "currency":      config.CURRENCY,
            "hl":            "en",
            "api_key":       self._api_key,
            "no_cache":      "false",
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

            origin      = segments[0]["departure_airport"]["id"]
            destination = segments[-1]["arrival_airport"]["id"]
            departure_date = segments[0]["departure_airport"]["time"][:10]
            num_stops   = len(segments) - 1

            airlines = " / ".join(dict.fromkeys(
                seg.get("airline", "") for seg in segments if seg.get("airline")
            ))

            total_minutes = raw.get("total_duration", 0) or sum(
                seg.get("duration", 0) for seg in segments
            )
            hours, mins = divmod(int(total_minutes), 60)
            duration = f"{hours}h {mins:02d}m"

            booking_url = (
                f"https://www.google.com/travel/flights?q=Flights+from+"
                f"{route.origin}+to+{route.destination}+on+{departure_date}"
            )

            return FlightOffer(
                origin=origin, destination=destination,
                departure_date=departure_date, price_cad=price_cad,
                airlines=airlines, num_stops=num_stops, duration=duration,
                source="Google Flights", booking_url=booking_url,
            )
        except (KeyError, IndexError, ValueError, TypeError) as e:
            logger.debug("Could not parse SerpAPI offer: %s — %s", e, raw)
            return None
