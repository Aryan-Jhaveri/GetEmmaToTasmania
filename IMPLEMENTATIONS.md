# Implementation Notes

## Current Setup: SerpAPI (Google Flights scraper) — Primary

**Why SerpAPI:**
- Google Flights has the widest airline inventory — best for complex routes like YYZ → Tasmania
- Free tier: **250 queries/month**, no credit card required
- For 2 routes (YYZ→HBA + YYZ→LST), we use ~60 queries/month — well within limits
- Returns prices in CAD
- Still actively accepting new users (as of March 2026)

**Registration:**
1. Go to https://serpapi.com → Sign Up (free, no credit card)
2. Dashboard → copy your **Private API Key**
3. Add as GitHub secret: `SERPAPI_KEY`

**API used:** `GET https://serpapi.com/search?engine=google_flights`

---

## API History / What Was Tried

| API | Status | Notes |
|-----|--------|-------|
| **Amadeus** | ❌ Closed new registrations | Decommissioning self-service portal July 17, 2026 |
| **Kiwi.com (Tequila)** | ❌ Closed new registrations | Was ideal — free + direct booking `deep_link` |
| **SerpAPI** | ✅ **Current** | 250 free/month, Google Flights data |
| **Duffel** | ✅ Open | Free trial → paid. Full booking API (overkill for this use case) |
| **FlightAPI.io** | ✅ Open | 20 free calls to test, then $49/month |
| **Aviationstack** | ✅ Open | 100 free calls/month — but NO pricing data, schedules only |
| **Travelpayouts** | ✅ Open | Free, but prices in Russian Rubles; data is cached/historical |
| **OpenSky Network** | ✅ Open | ADS-B flight tracking only, no pricing |

---

## If You Hit the SerpAPI Free Limit (250/month)

Options in order of cost:
1. **SerpAPI paid** — $50/month for 5,000 queries (still overkill; we use ~60/month)
2. **Duffel** — https://app.duffel.com — real flight booking API, free trial, then usage-based
3. **FlightAPI.io** — https://www.flightapi.io — $49/month for 30,000 credits

---

## Adding a Second Source (Optional)

If you want to compare prices across two APIs, `price_analyzer.cheapest_per_route()` already
handles merging — it picks the lowest price per route regardless of source.

In `main.py`, add a second client after the SerpAPI search:

```python
# Run SerpAPI (current)
serpapi_offers = SerpApiClient().search_cheapest_offers(route_pairs)

# Add a second source, e.g. FlightAPI.io
flightapi_offers = FlightApiClient().search_cheapest_offers(routes)

all_offers = serpapi_offers + flightapi_offers
best_offers = cheapest_per_route(all_offers)
```

`src/kiwi_client.py` and `src/amadeus_client.py` are kept in the codebase in case either
service reopens registrations in the future.

---

## Booking Links (Already Implemented)

`src/booking_links.py` generates links for every offer:
- **Primary button**: Google Flights link (from `offer.booking_url`, set by `serpapi_client.py`)
- **Secondary links**: Skyscanner and Kayak search links

If Kiwi were available, `offer.booking_url` would be a direct booking URL and the primary
button would read "Book on Kiwi.com" — the logic is already in place.

---

## Other Potential Improvements

### Add more departure cities
Currently defaults to `YYZ`. To also search Vancouver or Montreal, update the Settings tab:
`Departure Cities` → `YYZ, YVR, YUL`

SerpAPI is called once per origin-destination pair, so 3 origins × 2 destinations = 6 calls/day = ~180/month (still within free tier).

### Price trend chart in email
Google Sheets accumulates Price History. A future enhancement could generate a chart image
server-side and embed it in the email body.

### Push notification (WhatsApp / Pushover)
If Emma prefers a push notification over email:
- **Pushover** — one-time $5 app purchase, simple API, great iPhone notifications
- **Twilio WhatsApp sandbox** — free for testing, ~$0.005/message in production

Both can be added to `src/notifier.py` alongside the existing email.

### Multiple travellers
Currently `NUM_ADULTS = 1` in `config.py`. Change to `2` to track prices for 2 passengers.
SerpAPI passes this as the `adults` parameter.
