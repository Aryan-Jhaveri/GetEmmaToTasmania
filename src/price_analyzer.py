from src.models import DealOffer, FlightOffer

# How far below route average to earn the BELOW_ROUTE_AVG tag (8%)
BELOW_AVG_THRESHOLD = 0.92
# How close to all-time low to earn NEAR_ALL_TIME_LOW tag (within 5%)
NEAR_LOW_MARGIN = 1.05
# Max deal offers to surface per route in the email
MAX_DEALS_PER_ROUTE = 3


def cheapest_per_route_date(offers: list[FlightOffer]) -> list[FlightOffer]:
    """Return the single cheapest offer per (route_key, departure_date) combination."""
    best: dict[tuple[str, str], FlightOffer] = {}
    for offer in offers:
        key = (offer.route_key, offer.departure_date)
        if key not in best or offer.price_cad < best[key].price_cad:
            best[key] = offer
    return list(best.values())


def cheapest_per_route(offers: list[FlightOffer]) -> list[FlightOffer]:
    """Return only the single cheapest offer per route_key (for the dashboard)."""
    best: dict[str, FlightOffer] = {}
    for offer in offers:
        key = offer.route_key
        if key not in best or offer.price_cad < best[key].price_cad:
            best[key] = offer
    return list(best.values())


def find_deals(
    raw_offers: list[FlightOffer],
    historical_mins: dict[str, float],
    threshold_cad: float,
    min_drop_pct: float,
) -> list[DealOffer]:
    """
    Evaluate every (route, departure_date) pair and return DealOffer objects
    for the top MAX_DEALS_PER_ROUTE cheapest dates per route, tagged with why
    each qualifies.

    Email trigger: at least one DealOffer has is_primary_deal == True
    (BELOW_BUDGET, ALL_TIME_LOW, or NEAR_ALL_TIME_LOW tag).
    """
    # Best offer per (route, date) pair
    per_date = cheapest_per_route_date(raw_offers)

    # Per-route stats: average price and cheapest date across all departure dates
    from collections import defaultdict
    route_prices: dict[str, list[float]] = defaultdict(list)
    for o in per_date:
        route_prices[o.route_key].append(o.price_cad)

    route_avg:  dict[str, float] = {r: sum(p) / len(p) for r, p in route_prices.items()}
    route_min:  dict[str, float] = {r: min(p)          for r, p in route_prices.items()}

    # Tag every per-date offer
    tagged: list[DealOffer] = []
    for offer in per_date:
        tags: list[str] = []
        route = offer.route_key
        hist_min = historical_mins.get(route)
        avg = route_avg[route]

        if offer.price_cad < threshold_cad:
            tags.append("BELOW_BUDGET")

        if hist_min is not None:
            if offer.price_cad < hist_min * (1 - min_drop_pct / 100):
                tags.append("ALL_TIME_LOW")
            elif offer.price_cad < hist_min * NEAR_LOW_MARGIN:
                tags.append("NEAR_ALL_TIME_LOW")

        if offer.price_cad == route_min[route]:
            tags.append("BEST_DATE")

        if offer.price_cad < avg * BELOW_AVG_THRESHOLD:
            tags.append("BELOW_ROUTE_AVG")

        if tags:
            tagged.append(DealOffer(
                offer=offer,
                tags=tags,
                route_avg_cad=avg,
                hist_min_cad=hist_min,
            ))

    # Group by route, keep top MAX_DEALS_PER_ROUTE cheapest per route
    from collections import defaultdict as dd
    by_route: dict[str, list[DealOffer]] = dd(list)
    for d in tagged:
        by_route[d.offer.route_key].append(d)

    result: list[DealOffer] = []
    for route_deals in by_route.values():
        route_deals.sort(key=lambda d: d.offer.price_cad)
        result.extend(route_deals[:MAX_DEALS_PER_ROUTE])

    # Sort final list: primary deals first, then by price
    result.sort(key=lambda d: (not d.is_primary_deal, d.offer.price_cad))
    return result
