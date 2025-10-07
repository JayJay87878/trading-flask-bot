import pandas as pd
from oandapyV20 import API
import oandapyV20.endpoints.instruments as instruments
from datetime import datetime, timedelta
from config import OANDA_API_KEY
import os

# ===== Parameters =====
INSTRUMENTS = ["EUR_USD", "GBP_USD", "USD_JPY", "XAU_USD", "GBP_JPY", "AUD_JPY", "NZD_JPY", "CAD_JPY"]  # add your trading pairs here
GRANULARITY = "M5"
TOTAL_DAYS = 90
MAX_CANDLES_PER_REQUEST = 5000
OUTPUT_FOLDER = "historical_data"

# ===== Initialize API client =====
client = API(access_token=OANDA_API_KEY)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ===== Helper function to fetch candles =====
def fetch_candles(instrument, start, end):
    params = {
        "from": start.isoformat("T") + "Z",
        "to": end.isoformat("T") + "Z",
        "granularity": GRANULARITY,
    }
    r = instruments.InstrumentsCandles(instrument=instrument, params=params)
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

# ===== Main loop for all instruments =====
for instr in INSTRUMENTS:
    print(f"\nDownloading {instr} candles...")
    all_candles = []
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=TOTAL_DAYS)
    delta_per_request = timedelta(minutes=5 * MAX_CANDLES_PER_REQUEST)
    current_start = start_time

    while current_start < end_time:
        current_end = min(current_start + delta_per_request, end_time)
        print(f"{instr}: Fetching from {current_start} to {current_end}")
        candles = fetch_candles(instr, current_start, current_end)
        all_candles.extend(candles)
        current_start = current_end

    # Save to CSV
    df = pd.DataFrame(all_candles)
    csv_filename = os.path.join(OUTPUT_FOLDER, f"{instr}_{GRANULARITY}_{TOTAL_DAYS}days.csv")
    df.to_csv(csv_filename, index=False)
    print(f"✅ Saved {len(df)} candles to {csv_filename}")
