import os
import logging
from datetime import date, timedelta
from itertools import product

from amadeus import Client, ResponseError

import config
from src.models import FlightOffer, RouteConfig

logger = logging.getLogger(__name__)


class AmadeusClient:
    def __init__(self):
        self._client = Client(
            client_id=os.environ["AMADEUS_CLIENT_ID"],
            client_secret=os.environ["AMADEUS_CLIENT_SECRET"],
            log_level="warning",
        )

    def build_routes(
        self,
        origins: list[str],
        destinations: list[str],
        start_date: str,
        end_date: str,
        step_days: int,
    ) -> list[RouteConfig]:
        """Generate all route + date combinations to search."""
        routes = []
        current = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        while current <= end:
            for origin, dest in product(origins, destinations):
                routes.append(RouteConfig(origin, dest, current.isoformat()))
            current += timedelta(days=step_days)
        return routes

    def search_cheapest_offers(self, routes: list[RouteConfig]) -> list[FlightOffer]:
        """
        Search Amadeus for the cheapest offer per route.
        Batches into groups of 6 (API max per POST request).
        Skips routes with no results gracefully.
        """
        offers: list[FlightOffer] = []

        # Group routes by departure date — one POST per date, up to 6 pairs
        date_groups: dict[str, list[RouteConfig]] = {}
        for r in routes:
            date_groups.setdefault(r.departure_date, []).append(r)

        for dep_date, date_routes in date_groups.items():
            # Each date may have multiple origin-destination pairs; batch into ≤6
            for batch_start in range(0, len(date_routes), 6):
                batch = date_routes[batch_start:batch_start + 6]
                batch_offers = self._search_batch(batch)
                offers.extend(batch_offers)

        return offers

    def _search_batch(self, routes: list[RouteConfig]) -> list[FlightOffer]:
        """POST a single batch of ≤6 origin-destination pairs to Amadeus."""
        origin_destinations = []
        for i, route in enumerate(routes):
            origin_destinations.append({
                "id": str(i + 1),
                "originLocationCode": route.origin,
                "destinationLocationCode": route.destination,
                "departureDateTimeRange": {
                    "date": route.departure_date,
                    "dateWindow": "I3D",  # ±3 days flexibility
                },
            })

        body = {
            "currencyCode": config.CURRENCY,
            "originDestinations": origin_destinations,
            "travelers": [{"id": "1", "travelerType": "ADULT"}],
            "sources": ["GDS"],
            "searchCriteria": {
                "maxFlightOffers": 5,
                "flightFilters": {
                    "cabinRestrictions": [
                        {
                            "cabin": config.CABIN_CLASS,
                            "originDestinationIds": [str(i + 1) for i in range(len(routes))],
                        }
                    ]
                },
            },
        }

        offers = []
        try:
            response = self._client.shopping.flight_offers_search.post(body)
            raw_offers = response.data or []
            # Pick cheapest per route key
            cheapest: dict[str, FlightOffer] = {}
            for raw in raw_offers:
                offer = self._parse_offer(raw, routes)
                if offer:
                    key = offer.route_key + "|" + offer.departure_date
                    if key not in cheapest or offer.price_cad < cheapest[key].price_cad:
                        cheapest[key] = offer
            offers = list(cheapest.values())
        except ResponseError as e:
            logger.warning("Amadeus API error for batch %s: %s", routes, e)
        except Exception as e:
            logger.warning("Unexpected error searching batch %s: %s", routes, e)

        return offers

    def _parse_offer(self, raw: dict, routes: list[RouteConfig]) -> FlightOffer | None:
        """Parse a raw Amadeus offer dict into a FlightOffer."""
        try:
            price_cad = float(raw["price"]["grandTotal"])

            itineraries = raw.get("itineraries", [])
            if not itineraries:
                return None

            # Use first itinerary (outbound)
            itinerary = itineraries[0]
            segments = itinerary.get("segments", [])
            if not segments:
                return None

            origin = segments[0]["departure"]["iataCode"]
            destination = segments[-1]["arrival"]["iataCode"]
            departure_date = segments[0]["departure"]["at"][:10]
            num_stops = len(segments) - 1

            # Collect carrier codes
            carrier_codes = []
            for seg in segments:
                code = seg.get("carrierCode", "")
                if code and code not in carrier_codes:
                    carrier_codes.append(code)
            airlines = " / ".join(carrier_codes)

            # Parse total duration from ISO 8601 (e.g. "PT32H45M")
            duration_raw = itinerary.get("duration", "")
            duration = self._parse_duration(duration_raw)

            return FlightOffer(
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                price_cad=price_cad,
                airlines=airlines,
                num_stops=num_stops,
                duration=duration,
            )
        except (KeyError, IndexError, ValueError) as e:
            logger.debug("Could not parse offer: %s — %s", e, raw)
            return None

    @staticmethod
    def _parse_duration(iso: str) -> str:
        """Convert ISO 8601 duration 'PT32H45M' → '32h 45m'."""
        if not iso.startswith("PT"):
            return iso
        iso = iso[2:]
        hours = minutes = 0
        if "H" in iso:
            parts = iso.split("H")
            hours = int(parts[0])
            iso = parts[1]
        if "M" in iso:
            minutes = int(iso.replace("M", ""))
        return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"
