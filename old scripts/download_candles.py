import pandas as pd
from oandapyV20 import API
import oandapyV20.endpoints.instruments as instruments
from config import OANDA_API_KEY, OANDA_ACCOUNT_ID

# ===== Initialize API client =====
client = API(access_token=OANDA_API_KEY)

# ===== Parameters =====
INSTRUMENT = "EUR_USD"
COUNT = 500            # number of candles
GRANULARITY = "M5"     # 5-minute candles

# ===== Fetch candles =====
r = instruments.InstrumentsCandles(instrument=INSTRUMENT,
                                   params={"count": COUNT,
                                           "granularity": GRANULARITY})
response = client.request(r)

# ===== Extract data =====
data = response['candles']
rows = []
for candle in data:
    if candle['complete']:
        rows.append({
            "time": candle['time'],
            "open": float(candle['mid']['o']),
            "high": float(candle['mid']['h']),
            "low": float(candle['mid']['l']),
            "close": float(candle['mid']['c']),
            "volume": candle['volume']
        })

# ===== Save to CSV =====
df = pd.DataFrame(rows)
df.to_csv(f"{INSTRUMENT}_{GRANULARITY}.csv", index=False)
print(f"Saved {len(df)} candles to {INSTRUMENT}_{GRANULARITY}.csv")
