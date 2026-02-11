"""One-click launcher for the Stock Earnings Calendar."""

from earnings_calendar.app import app

if __name__ == "__main__":
    print()
    print("  ================================")
    print("  US Stock Earnings Calendar")
    print("  ================================")
    print()
    print("  Open this link in your browser:")
    print()
    print("    http://localhost:5000")
    print()
    print("  Then type a stock ticker like AAPL, MSFT, or GOOGL")
    print("  and click Search to see earnings dates on the calendar.")
    print()
    print("  Press Ctrl+C to stop the server.")
    print()
    app.run(debug=False, host="0.0.0.0", port=5000)
