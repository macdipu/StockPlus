"""Every upstream URL, payload key and analysis parameter in one place.

Source: the official Dhaka Stock Exchange site (https://www.dse.com.bd/), a Next.js app.
Discovered from captured traffic on 2026-11-11:

* GET /company/{SYMBOL}      server-rendered page; the React Server Components ("flight") payload embedded in
                             it carries {"company": {...65 fields}, "series": [...~260 daily bars]}.
* GET /api/live/snapshot     JSON for the whole market: session, indices, breadth, and one row per traded
                             instrument (cols + rows). Served by CloudFront with max-age=10 / s-maxage=15;
                             DSE's own page polls it, and the trade time inside advances about once a minute.

No WebSocket exists upstream. If the site changes, run `python main.py SYMBOL --force --dump` and fix this file.
"""
import os

# --------------------------------------------------------------------------- upstream
BASE_URL = os.getenv("DSE_BASE_URL", "https://www.dse.com.bd")
COMPANY_URL = BASE_URL + "/company/{symbol}"
SNAPSHOT_URL = BASE_URL + "/api/live/snapshot"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
HTTP_TIMEOUT_S = 20
HTTP_RETRIES = 1                 # one retry on timeout / 5xx, then a clear error
MIN_PAGE_INTERVAL_S = 2.5        # politeness: gap between company-page loads (screener, batch CLI)

# Flight payload: the object that holds both keys below is the company page's data.
FLIGHT_PUSH_RE = r'self\.__next_f\.push\(\[1,"(.*?)"\]\)\s*</script>'
FLIGHT_COMPANY_KEY = "company"
FLIGHT_SERIES_KEY = "series"
# series item keys -> our OHLCV columns
SERIES_FIELDS = {"date": "date", "open": "open", "high": "high", "low": "low", "close": "price",
                 "volume": "volume", "trades": "trades"}
# interimFinancials row used for EPS (first match wins)
EPS_METRICS = ["EPS - Continuing Operations Basic", "Earnings Per Share (EPS) Basic"]

# Snapshot
SNAPSHOT_PRICE_COLS_KEY = ("prices", "cols")
SNAPSHOT_PRICE_ROWS_KEY = ("prices", "rows")

# --------------------------------------------------------------------------- live feed
LIVE_POLL_S = float(os.getenv("DSE_LIVE_POLL_S", "10"))        # = upstream max-age; faster only re-reads the cache
LIVE_POLL_CLOSED_S = float(os.getenv("DSE_LIVE_POLL_CLOSED_S", "60"))
LIVE_MIN_POLL_S = 5.0                                          # hard floor, whatever the env says
SSE_HEARTBEAT_S = 15
SUBSCRIBER_QUEUE = 256

# --------------------------------------------------------------------------- local storage
CAPTURE_DIR = "captured"
SCREENSHOT_DIR = "screenshots"
REPORT_DIR = "reports"
CACHE_DB = "cache/dse.sqlite"
TIMEZONE = "Asia/Dhaka"
SCREENER_MAX_SYMBOLS = 15

# --------------------------------------------------------------------------- analysis
FACE_VALUE_DEFAULT = 10.0  # DSE dividends are declared as % of face value

PE_MULTIPLES = [15, 20, 25]
PB_MULTIPLES = [1.5, 2.0, 3.0]

DDM_REQUIRED_RETURN = 0.12
DDM_GROWTH = 0.04

DCF_YEARS = 5
DCF_CASES = {  # stage-1 growth, terminal growth, discount rate
    "bear": {"g1": 0.00, "g2": 0.02, "r": 0.14},
    "base": {"g1": 0.08, "g2": 0.03, "r": 0.12},
    "bull": {"g1": 0.15, "g2": 0.04, "r": 0.11},
}

SWING_WINDOW = 3
LEVEL_MERGE_PCT = 1.5
PATTERN_LOOKBACK = 10
CHART_BARS = 260
