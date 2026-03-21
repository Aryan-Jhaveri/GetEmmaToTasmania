from dataclasses import dataclass, field
from datetime import datetime


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
