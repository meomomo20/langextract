"""Stock Earnings Calendar - Flask application.

Search US stock tickers and view quarterly/annual earnings report dates
on an interactive calendar.

Usage:
    python -m earnings_calendar.app          # production
    python -m earnings_calendar.app --demo   # demo mode with sample data

Environment variables:
    ALPHAVANTAGE_API_KEY  Free API key from https://www.alphavantage.co/support/#api-key
                          Enables fetching 20+ quarters of earnings history (vs 4 from Yahoo).
    DEMO_MODE=1           Run with sample data (no network calls).
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# Enable demo mode via flag or env var (useful when Yahoo API is unreachable)
DEMO_MODE = "--demo" in sys.argv or os.environ.get("DEMO_MODE", "") == "1"

# Alpha Vantage API key — free at https://www.alphavantage.co/support/#api-key
# Provides 20+ quarters of earnings history (Yahoo Finance only returns 4).
ALPHAVANTAGE_API_KEY = os.environ.get("ALPHAVANTAGE_API_KEY", "")

# Default and maximum number of quarters returned
DEFAULT_QUARTER_LIMIT = 4
MAX_QUARTER_LIMIT = 40

_YAHOO_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

_TICKER_RE = re.compile(r"^[A-Z]{1,5}$")


# ── Demo / sample data ──────────────────────────────────────────────


def _generate_extended_eps(base_eps, num_quarters=20):
    """Generate extended EPS data going back multiple quarters."""
    extended = list(base_eps)
    # Generate additional historical quarters from the last known values
    if len(extended) >= 2:
        last_actual = extended[-1][1]
        last_estimate = extended[-1][2]
        for i in range(len(extended), num_quarters):
            year = 2024 - (i // 4)
            quarter = 4 - (i % 4)
            period = f"{quarter}Q{year}"
            # Slightly vary EPS going back in time (gradual decline)
            decay = 0.97 ** (i - len(base_eps) + 1)
            actual = round(last_actual * decay, 2)
            estimate = round(last_estimate * decay, 2)
            surprise = round((actual - estimate) / max(abs(estimate), 0.01), 4)
            extended.append((period, actual, estimate, surprise))
    return extended


def _demo_data(ticker: str) -> dict:
    """Return realistic sample data so the UI can be exercised offline."""
    today = datetime.utcnow()
    samples = {
        "AAPL": {
            "companyName": "Apple Inc.",
            "upcomingDelta": 30,
            "eps": [
                ("4Q2024", 2.18, 2.11, 0.0332),
                ("3Q2024", 1.40, 1.35, 0.0370),
                ("2Q2024", 1.53, 1.50, 0.0200),
                ("1Q2024", 2.18, 2.10, 0.0381),
                ("4Q2023", 2.10, 2.09, 0.0048),
                ("3Q2023", 1.46, 1.39, 0.0504),
                ("2Q2023", 1.26, 1.19, 0.0588),
                ("1Q2023", 1.88, 1.94, -0.0309),
            ],
            "qRevenue": [
                ("4Q2024", 124_300_000_000, 36_330_000_000),
                ("3Q2024", 94_930_000_000, 23_640_000_000),
                ("2Q2024", 85_780_000_000, 21_450_000_000),
                ("1Q2024", 119_580_000_000, 33_920_000_000),
            ],
            "yRevenue": [
                ("2024", 391_035_000_000, 101_560_000_000),
                ("2023", 383_285_000_000, 96_995_000_000),
                ("2022", 394_328_000_000, 99_803_000_000),
                ("2021", 365_817_000_000, 94_680_000_000),
            ],
        },
        "MSFT": {
            "companyName": "Microsoft Corporation",
            "upcomingDelta": 45,
            "eps": [
                ("2Q2025", 3.23, 3.11, 0.0386),
                ("1Q2025", 3.30, 3.10, 0.0645),
                ("4Q2024", 2.95, 2.93, 0.0068),
                ("3Q2024", 2.94, 2.82, 0.0426),
                ("2Q2024", 2.93, 2.78, 0.0540),
                ("1Q2024", 2.94, 2.82, 0.0426),
                ("4Q2023", 2.69, 2.55, 0.0549),
                ("3Q2023", 2.45, 2.35, 0.0426),
            ],
            "qRevenue": [
                ("2Q2025", 69_600_000_000, 24_100_000_000),
                ("1Q2025", 65_600_000_000, 24_700_000_000),
                ("4Q2024", 64_700_000_000, 22_000_000_000),
                ("3Q2024", 61_900_000_000, 21_900_000_000),
            ],
            "yRevenue": [
                ("2024", 245_122_000_000, 88_136_000_000),
                ("2023", 211_915_000_000, 72_361_000_000),
                ("2022", 198_270_000_000, 72_738_000_000),
                ("2021", 168_088_000_000, 61_271_000_000),
            ],
        },
        "GOOGL": {
            "companyName": "Alphabet Inc.",
            "upcomingDelta": 60,
            "eps": [
                ("4Q2024", 2.15, 2.05, 0.0488),
                ("3Q2024", 2.12, 1.85, 0.1459),
                ("2Q2024", 1.89, 1.85, 0.0216),
                ("1Q2024", 1.89, 1.51, 0.2517),
                ("4Q2023", 1.64, 1.59, 0.0314),
                ("3Q2023", 1.55, 1.45, 0.0690),
                ("2Q2023", 1.44, 1.34, 0.0746),
                ("1Q2023", 1.17, 1.07, 0.0935),
            ],
            "qRevenue": [
                ("4Q2024", 96_469_000_000, 30_972_000_000),
                ("3Q2024", 88_268_000_000, 26_301_000_000),
                ("2Q2024", 84_742_000_000, 23_619_000_000),
                ("1Q2024", 80_539_000_000, 23_662_000_000),
            ],
            "yRevenue": [
                ("2024", 350_018_000_000, 100_554_000_000),
                ("2023", 307_394_000_000, 73_795_000_000),
                ("2022", 282_836_000_000, 59_972_000_000),
                ("2021", 257_637_000_000, 76_033_000_000),
            ],
        },
    }

    info = samples.get(ticker)
    if info is None:
        # Generate plausible placeholder for any ticker
        info = {
            "companyName": f"{ticker} Corp.",
            "upcomingDelta": 25,
            "eps": [
                ("4Q2024", 1.20, 1.15, 0.0435),
                ("3Q2024", 1.05, 1.00, 0.0500),
                ("2Q2024", 0.98, 0.95, 0.0316),
                ("1Q2024", 0.88, 0.90, -0.0222),
            ],
            "qRevenue": [
                ("4Q2024", 12_000_000_000, 2_000_000_000),
                ("3Q2024", 11_500_000_000, 1_800_000_000),
                ("2Q2024", 11_000_000_000, 1_600_000_000),
                ("1Q2024", 10_500_000_000, 1_500_000_000),
            ],
            "yRevenue": [
                ("2024", 45_000_000_000, 6_900_000_000),
                ("2023", 42_000_000_000, 6_200_000_000),
                ("2022", 39_000_000_000, 5_500_000_000),
                ("2021", 36_000_000_000, 4_800_000_000),
            ],
        }

    # Extend EPS data to support higher limits in demo mode
    info["eps"] = _generate_extended_eps(info["eps"], num_quarters=20)

    upcoming_date = (today + timedelta(days=info["upcomingDelta"])).strftime(
        "%Y-%m-%d"
    )

    history = []
    base_date = today - timedelta(days=30)
    for i, (period, actual, estimate, surprise) in enumerate(info["eps"]):
        rd = (base_date - timedelta(days=90 * i)).strftime("%Y-%m-%d")
        history.append(
            {
                "period": period,
                "quarter": None,
                "reportDate": rd,
                "epsActual": actual,
                "epsEstimate": estimate,
                "surprisePct": round(surprise * 100, 2),
            }
        )

    quarterly = [
        {"period": p, "revenue": r, "earnings": e}
        for p, r, e in info["qRevenue"]
    ]
    yearly = [
        {"period": p, "revenue": r, "earnings": e}
        for p, r, e in info["yRevenue"]
    ]

    return {
        "ticker": ticker,
        "companyName": info["companyName"],
        "upcomingEarningsDates": [upcoming_date],
        "earningsHistory": history,
        "quarterlyFinancials": quarterly,
        "yearlyFinancials": yearly,
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


# ── Alpha Vantage fetcher ────────────────────────────────────────────


def _fetch_alphavantage_earnings(ticker: str, api_key: str) -> dict | None:
    """Fetch earnings data from Alpha Vantage (free API, 20+ quarters).

    Returns parsed earnings dict or None on failure.
    API docs: https://www.alphavantage.co/documentation/#earnings
    """
    url = (
        "https://www.alphavantage.co/query"
        f"?function=EARNINGS&symbol={ticker}&apikey={api_key}"
    )
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except (requests.exceptions.RequestException, ValueError):
        return None

    # Alpha Vantage returns {"Note": ...} when rate-limited
    if "Note" in data or "Information" in data:
        return None

    quarterly = data.get("quarterlyEarnings", [])
    annual = data.get("annualEarnings", [])

    if not quarterly:
        return None

    history = []
    for q in quarterly:
        fiscal_end = q.get("fiscalDateEnding", "")
        reported_date = q.get("reportedDate")
        reported_eps = q.get("reportedEPS")
        estimated_eps = q.get("estimatedEPS")
        surprise_pct = q.get("surprisePercentage")

        eps_actual = _safe_float(reported_eps)
        eps_estimate = _safe_float(estimated_eps)
        surprise = _safe_float(surprise_pct)

        history.append(
            {
                "period": fiscal_end,
                "quarter": None,
                "reportDate": reported_date or fiscal_end,
                "epsActual": eps_actual,
                "epsEstimate": eps_estimate,
                "surprisePct": round(surprise, 2) if surprise is not None else None,
            }
        )

    yearly_earnings = []
    for y in annual:
        yearly_earnings.append(
            {
                "period": y.get("fiscalDateEnding", ""),
                "reportedEPS": _safe_float(y.get("reportedEPS")),
            }
        )

    return {
        "earningsHistory": history,
        "yearlyEarnings": yearly_earnings,
    }


def _safe_float(val):
    """Convert a value to float, returning None if not possible."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if f != f else f  # NaN check
    except (ValueError, TypeError):
        return None


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


@app.route("/api/earnings")
def api_earnings():
    """API endpoint to fetch earnings data for a stock ticker.

    Query parameters:
        ticker  — Stock ticker symbol (required, 1-5 letters).
        limit   — Max quarters of earnings history to return (default 4, max 40).
                   Set to a higher value when ALPHAVANTAGE_API_KEY is configured.
    """
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

    # Parse limit parameter
    try:
        limit = int(request.args.get("limit", DEFAULT_QUARTER_LIMIT))
        limit = max(1, min(limit, MAX_QUARTER_LIMIT))
    except (ValueError, TypeError):
        limit = DEFAULT_QUARTER_LIMIT

    # Demo mode — return sample data
    if DEMO_MODE:
        data = _demo_data(ticker)
        data["earningsHistory"] = data["earningsHistory"][:limit]
        data["limit"] = limit
        data["maxLimit"] = MAX_QUARTER_LIMIT
        data["source"] = "demo"
        return jsonify(data)

    try:
        # Always fetch Yahoo for upcoming dates and company info
        raw = _fetch_yahoo_data(ticker)
        parsed = _parse_earnings(raw)
        if "error" in parsed:
            return jsonify(parsed), 404

        source = "yahoo"

        # If Alpha Vantage key is set and user wants more than 4 quarters,
        # fetch extended history from Alpha Vantage
        if ALPHAVANTAGE_API_KEY and limit > 4:
            av_data = _fetch_alphavantage_earnings(
                ticker, ALPHAVANTAGE_API_KEY
            )
            if av_data and av_data.get("earningsHistory"):
                parsed["earningsHistory"] = av_data["earningsHistory"]
                source = "alphavantage"

        # Apply the limit
        parsed["earningsHistory"] = parsed["earningsHistory"][:limit]
        parsed["limit"] = limit
        parsed["maxLimit"] = MAX_QUARTER_LIMIT if ALPHAVANTAGE_API_KEY else 4
        parsed["source"] = source

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
