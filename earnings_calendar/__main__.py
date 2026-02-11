"""Allow running as: python -m earnings_calendar"""
from earnings_calendar.app import app, DEMO_MODE

print(f"Starting Earnings Calendar (demo={DEMO_MODE})")
print("Open http://localhost:5000 in your browser")
app.run(debug=True, host="0.0.0.0", port=5000)
