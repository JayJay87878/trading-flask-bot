import pandas as pd
from oandapyV20 import API
import oandapyV20.endpoints.instruments as instruments
from datetime import datetime, timedelta
from config import OANDA_API_KEY

# ===== Parameters =====
INSTRUMENT = "EUR_USD"
GRANULARITY = "M5"        # 5-minute candles
TOTAL_DAYS = 90           # last 90 days
MAX_CANDLES_PER_REQUEST = 5000

# ===== Initialize API client =====
client = API(access_token=OANDA_API_KEY)

# ===== Helper function to fetch candles for a date range =====
def fetch_candles(start, end):
    params = {
        "from": start.isoformat("T") + "Z",
        "to": end.isoformat("T") + "Z",
        "granularity": GRANULARITY,
    }
    r = instruments.InstrumentsCandles(instrument=INSTRUMENT, params=params)
    response = client.request(r)
    candles = [
        {
            "time": c['time'],
            "open": float(c['mid']['o']),
            "high": float(c['mid']['h']),
            "low": float(c['mid']['l']),
            "close": float(c['mid']['c']),
            "volume": c['volume']
        }
        for c in response['candles'] if c['complete']
    ]
    return candles

# ===== Main =====
all_candles = []
end_time = datetime.utcnow()
start_time = end_time - timedelta(days=TOTAL_DAYS)

# OANDA limit: 5000 candles per request. Split if needed
delta_per_request = timedelta(minutes=5 * MAX_CANDLES_PER_REQUEST)  # 5 min candles
current_start = start_time

print(f"Downloading {TOTAL_DAYS} days of {INSTRUMENT} {GRANULARITY} candles...")

while current_start < end_time:
    current_end = min(current_start + delta_per_request, end_time)
    print(f"Fetching from {current_start} to {current_end}")
    candles = fetch_candles(current_start, current_end)
    all_candles.extend(candles)
    current_start = current_end

# ===== Save to CSV =====
df = pd.DataFrame(all_candles)
csv_filename = f"{INSTRUMENT}_{GRANULARITY}_{TOTAL_DAYS}days.csv"
df.to_csv(csv_filename, index=False)
print(f"✅ Saved {len(df)} candles to {csv_filename}")
