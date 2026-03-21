from src.models import FlightOffer


def find_deals(
    offers: list[FlightOffer],
    historical_mins: dict[str, float],
    threshold_cad: float,
    min_drop_pct: float,
) -> list[FlightOffer]:
    """
    Return offers that qualify as deals. An offer qualifies if:
    1. Its price is below the user's alert threshold, OR
    2. It is at least min_drop_pct% cheaper than the historical minimum
       for that route (catches significant drops even above threshold).
    """
    deals = []
    for offer in offers:
        below_threshold = offer.price_cad < threshold_cad

        prev_min = historical_mins.get(offer.route_key)
        new_record = (
            prev_min is not None
            and offer.price_cad < prev_min * (1 - min_drop_pct / 100)
        )

        if below_threshold or new_record:
            deals.append(offer)

    return deals


def cheapest_per_route(offers: list[FlightOffer]) -> list[FlightOffer]:
    """Return only the single cheapest offer per route_key."""
    best: dict[str, FlightOffer] = {}
    for offer in offers:
        key = offer.route_key
        if key not in best or offer.price_cad < best[key].price_cad:
            best[key] = offer
    return list(best.values())
