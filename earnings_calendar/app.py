"""Stock Earnings Calendar - Flask application.

Search US stock tickers and view upcoming earnings report dates
on an interactive calendar.  Uses Finnhub (free API) for the
multi-stock calendar and Yahoo Finance for per-ticker detail.

Usage:
    python -m earnings_calendar.app          # production
    python -m earnings_calendar.app --demo   # demo mode with sample data

Environment variables:
    FINNHUB_API_KEY   Free API key from https://finnhub.io/register
                      Required to fetch upcoming earnings for many stocks at once.
    DEMO_MODE=1       Run with sample data (no network calls).
"""

import calendar as cal_mod
import json
import os
import random
import re
import sys
from datetime import datetime, timedelta

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# Enable demo mode via flag or env var (useful when Yahoo API is unreachable)
DEMO_MODE = "--demo" in sys.argv or os.environ.get("DEMO_MODE", "") == "1"

# Finnhub API key — free at https://finnhub.io/register
# Provides upcoming earnings calendar for many stocks at once.
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")

_YAHOO_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

_TICKER_RE = re.compile(r"^[A-Z]{1,5}$")


# ── Demo / sample data ──────────────────────────────────────────────

_DEMO_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "JPM",
    "V", "JNJ", "WMT", "PG", "MA", "UNH", "HD", "DIS", "BAC", "INTC",
    "VZ", "ADBE", "CRM", "NFLX", "CSCO", "PFE", "KO", "PEP", "NKE",
    "MRK", "T", "ABT",
]


def _demo_calendar(from_date: str, to_date: str) -> list[dict]:
    """Generate plausible demo calendar data for the given date range."""
    start = datetime.strptime(from_date, "%Y-%m-%d")
    end = datetime.strptime(to_date, "%Y-%m-%d")
    events = []
    # Spread tickers across weekdays in the range
    rng = random.Random(42)  # deterministic so page refreshes are stable
    day = start
    idx = 0
    while day <= end:
        if day.weekday() < 5:  # weekdays only
            # 2-4 companies per day
            count = rng.randint(2, 4)
            for _ in range(count):
                ticker = _DEMO_TICKERS[idx % len(_DEMO_TICKERS)]
                idx += 1
                hour = rng.choice(["bmo", "amc"])
                events.append(
                    {
                        "date": day.strftime("%Y-%m-%d"),
                        "symbol": ticker,
                        "epsEstimate": round(rng.uniform(0.5, 4.0), 2),
                        "revenueEstimate": rng.randint(5, 120) * 1_000_000_000,
                        "hour": hour,
                    }
                )
        day += timedelta(days=1)
    return events


def _demo_ticker_data(ticker: str) -> dict:
    """Return realistic sample data for a single ticker (demo mode)."""
    today = datetime.utcnow()
    samples = {
        "AAPL": ("Apple Inc.", 30),
        "MSFT": ("Microsoft Corporation", 45),
        "GOOGL": ("Alphabet Inc.", 60),
    }
    name, delta = samples.get(ticker, (f"{ticker} Corp.", 25))
    upcoming = (today + timedelta(days=delta)).strftime("%Y-%m-%d")
    return {
        "ticker": ticker,
        "companyName": name,
        "upcomingEarningsDates": [upcoming],
        "earningsHistory": [],
        "quarterlyFinancials": [],
        "yearlyFinancials": [],
    }


# ── Yahoo Finance fetcher ────────────────────────────────────────────


def _fetch_yahoo_data(ticker: str) -> dict:
    """Fetch earnings data from Yahoo Finance API."""
    url = (
        f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/"
        f"{ticker}?modules=calendarEvents,earningsHistory,earnings,"
        f"quoteType,summaryProfile"
    )
    resp = requests.get(url, headers=_YAHOO_HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


# ── Finnhub calendar fetcher ─────────────────────────────────────────


def _fetch_finnhub_calendar(
    from_date: str, to_date: str, api_key: str
) -> list[dict]:
    """Fetch upcoming earnings calendar from Finnhub (free API).

    Returns list of {date, symbol, epsEstimate, revenueEstimate, hour}.
    API docs: https://finnhub.io/docs/api/earnings-calendar
    """
    url = (
        "https://finnhub.io/api/v1/calendar/earnings"
        f"?from={from_date}&to={to_date}&token={api_key}"
    )
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    events = []
    for entry in data.get("earningsCalendar", []):
        events.append(
            {
                "date": entry.get("date", ""),
                "symbol": entry.get("symbol", ""),
                "epsEstimate": entry.get("epsEstimate"),
                "revenueEstimate": entry.get("revenueEstimate"),
                "hour": entry.get("hour", ""),  # bmo / amc / dmh
            }
        )
    return events


def _ts_to_date(ts):
    """Convert a Unix timestamp to ISO date string."""
    if ts is None:
        return None
    try:
        return datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d")
    except (ValueError, TypeError, OSError):
        return None


def _parse_earnings(data: dict) -> dict:
    """Parse Yahoo Finance response into structured earnings data."""
    result = data.get("quoteSummary", {}).get("result", [])
    if not result:
        return {"error": "No data found for this ticker."}

    info = result[0]

    # Company name
    quote_type = info.get("quoteType", {})
    company_name = quote_type.get("longName") or quote_type.get(
        "shortName", ""
    )

    # --- Upcoming earnings date from calendarEvents ---
    cal = info.get("calendarEvents", {})
    earnings_obj = cal.get("earnings", {})
    upcoming_dates = []
    raw_dates = earnings_obj.get("earningsDate", [])
    for d in raw_dates:
        raw = d.get("raw")
        if raw:
            upcoming_dates.append(_ts_to_date(raw))

    # --- Historical quarterly earnings from earningsHistory ---
    history = info.get("earningsHistory", {}).get("history", [])
    historical = []
    for entry in history:
        quarter_raw = entry.get("quarter", {}).get("raw")
        eps_actual = entry.get("epsActual", {}).get("raw")
        eps_estimate = entry.get("epsEstimate", {}).get("raw")
        surprise_pct = entry.get("surprisePercent", {}).get("raw")

        # Use the period string like "3Q2024"
        period = entry.get("period", "")

        # Try to extract the report date from the entry
        report_date = None
        for key in ("reportDate", "date"):
            if key in entry:
                val = entry[key]
                if isinstance(val, dict):
                    raw = val.get("raw")
                    if raw:
                        report_date = _ts_to_date(raw)
                        break
                elif isinstance(val, (int, float)):
                    report_date = _ts_to_date(val)
                    break

        historical.append(
            {
                "period": period,
                "quarter": quarter_raw,
                "reportDate": report_date,
                "epsActual": eps_actual,
                "epsEstimate": eps_estimate,
                "surprisePct": (
                    round(surprise_pct * 100, 2)
                    if surprise_pct is not None
                    else None
                ),
            }
        )

    # --- Quarterly earnings data (revenue + earnings) ---
    earnings_mod = info.get("earnings", {})
    quarterly_earnings = []
    for q in earnings_mod.get("financialsChart", {}).get("quarterly", []):
        quarterly_earnings.append(
            {
                "period": q.get("date", ""),
                "revenue": q.get("revenue", {}).get("raw"),
                "earnings": q.get("earnings", {}).get("raw"),
            }
        )

    yearly_earnings = []
    for y in earnings_mod.get("financialsChart", {}).get("yearly", []):
        yearly_earnings.append(
            {
                "period": str(y.get("date", "")),
                "revenue": y.get("revenue", {}).get("raw"),
                "earnings": y.get("earnings", {}).get("raw"),
            }
        )

    return {
        "ticker": info.get("quoteType", {}).get("symbol", ""),
        "companyName": company_name,
        "upcomingEarningsDates": [d for d in upcoming_dates if d],
        "earningsHistory": historical,
        "quarterlyFinancials": quarterly_earnings,
        "yearlyFinancials": yearly_earnings,
    }


# ── Routes ───────────────────────────────────────────────────────────


@app.route("/")
def index():
    """Serve the main calendar page."""
    return render_template("index.html")


@app.route("/api/calendar")
def api_calendar():
    """Fetch upcoming earnings dates for many stocks in a date range.

    Query parameters:
        from  — Start date YYYY-MM-DD (default: 1st of current month).
        to    — End date   YYYY-MM-DD (default: last day of current month).

    Returns JSON: { "events": [{date, symbol, epsEstimate, revenueEstimate, hour}, ...] }
    """
    today = datetime.utcnow()
    default_from = today.strftime("%Y-%m-01")
    _, last_day = cal_mod.monthrange(today.year, today.month)
    default_to = today.strftime(f"%Y-%m-{last_day:02d}")

    from_date = request.args.get("from", default_from)
    to_date = request.args.get("to", default_to)

    # Demo mode
    if DEMO_MODE:
        return jsonify(
            {"events": _demo_calendar(from_date, to_date), "source": "demo"}
        )

    if not FINNHUB_API_KEY:
        return (
            jsonify(
                {
                    "error": (
                        "FINNHUB_API_KEY not set. "
                        "Get a free key at https://finnhub.io/register "
                        "and export FINNHUB_API_KEY=your_key"
                    )
                }
            ),
            503,
        )

    try:
        events = _fetch_finnhub_calendar(from_date, to_date, FINNHUB_API_KEY)
        return jsonify({"events": events, "source": "finnhub"})
    except requests.exceptions.RequestException:
        return (
            jsonify({"error": "Failed to fetch calendar. Try again later."}),
            502,
        )


@app.route("/api/earnings")
def api_earnings():
    """Fetch detailed earnings data for a single stock ticker."""
    ticker = request.args.get("ticker", "").strip().upper()
    if not ticker:
        return jsonify({"error": "Please provide a stock ticker."}), 400
    if not _TICKER_RE.match(ticker):
        return (
            jsonify(
                {
                    "error": (
                        "Invalid ticker format. "
                        "Use 1-5 uppercase letters (e.g., AAPL, MSFT)."
                    )
                }
            ),
            400,
        )

    if DEMO_MODE:
        return jsonify(_demo_ticker_data(ticker))

    try:
        raw = _fetch_yahoo_data(ticker)
        parsed = _parse_earnings(raw)
        if "error" in parsed:
            return jsonify(parsed), 404
        return jsonify(parsed)
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return (
                jsonify({"error": f"Ticker '{ticker}' not found."}),
                404,
            )
        return (
            jsonify({"error": "Failed to fetch data. Please try again."}),
            502,
        )
    except requests.exceptions.RequestException:
        return (
            jsonify(
                {"error": "Network error. Please check your connection."}
            ),
            502,
        )
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": f"Error parsing data: {e}"}), 500


if __name__ == "__main__":
    print(f"Starting Earnings Calendar (demo={DEMO_MODE})")
    print("Open http://localhost:5000 in your browser")
    app.run(debug=True, host="0.0.0.0", port=5000)
