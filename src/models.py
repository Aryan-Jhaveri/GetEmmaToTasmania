from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class DealOffer:
    """A FlightOffer that qualified as a deal, with context explaining why."""
    offer: "FlightOffer"
    tags: list[str]          # e.g. ["BELOW_BUDGET", "BEST_DATE"]
    route_avg_cad: float     # average price across all departure dates for this route today
    hist_min_cad: float | None = None  # all-time low for this route (None if no history)

    @property
    def is_primary_deal(self) -> bool:
        """True if this qualifies to trigger an email (not just contextual filler)."""
        return any(t in self.tags for t in ("BELOW_BUDGET", "ALL_TIME_LOW", "NEAR_ALL_TIME_LOW"))

    @property
    def best_tag(self) -> str:
        """Single most important tag for display."""
        priority = ["ALL_TIME_LOW", "BELOW_BUDGET", "NEAR_ALL_TIME_LOW",
                    "BELOW_ROUTE_AVG", "BEST_DATE"]
        for t in priority:
            if t in self.tags:
                return t
        return self.tags[0] if self.tags else ""


@dataclass
class RouteConfig:
    origin: str        # IATA code, e.g. "YYZ"
    destination: str   # IATA code, e.g. "HBA"
    departure_date: str  # ISO date string, e.g. "2025-06-07"

    @property
    def key(self) -> str:
        return f"{self.origin}->{self.destination}"


@dataclass
class FlightOffer:
    origin: str
    destination: str
    departure_date: str
    price_cad: float
    airlines: str        # e.g. "Air Canada / Qantas"
    num_stops: int
    duration: str        # e.g. "32h 45m"
    source: str = "Amadeus"   # which API found this offer
    booking_url: str = ""     # direct booking link (populated by Kiwi API)
    fetched_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def route_key(self) -> str:
        return f"{self.origin}->{self.destination}"

    @property
    def price_display(self) -> str:
        return f"${self.price_cad:,.0f} CAD"
