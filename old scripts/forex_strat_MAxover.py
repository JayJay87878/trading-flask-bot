import pandas as pd
from oandapyV20 import API
import oandapyV20.endpoints.pricing as pricing
from config import OANDA_API_KEY, OANDA_ACCOUNT_ID, OANDA_API_URL

# ===== Connect to OANDA =====
client = API(access_token=OANDA_API_KEY)

# ===== Function to fetch recent EUR/USD prices =====
def fetch_prices(instrument="EUR_USD", count=50, granularity="M5"):
    import oandapyV20.endpoints.instruments as instruments
    r = instruments.InstrumentsCandles(instrument=instrument,
                                       params={"count": count,
                                               "granularity": granularity})
    response = client.request(r)
    data = response['candles']
    # Extract close prices and timestamps
    prices = [float(candle['mid']['c']) for candle in data if candle['complete']]
    times = [candle['time'] for candle in data if candle['complete']]
    df = pd.DataFrame({"time": times, "close": prices})
    return df

# ===== Function to compute moving averages =====
def compute_ma(df, short_window=5, long_window=20):
    df['MA_short'] = df['close'].rolling(window=short_window).mean()
    df['MA_long'] = df['close'].rolling(window=long_window).mean()
    return df

# ===== Function to generate signals =====
def generate_signals(df):
    signals = []
    for i in range(1, len(df)):
        if df['MA_short'][i] > df['MA_long'][i] and df['MA_short'][i-1] <= df['MA_long'][i-1]:
            signals.append((df['time'][i], "BUY"))
        elif df['MA_short'][i] < df['MA_long'][i] and df['MA_short'][i-1] >= df['MA_long'][i-1]:
            signals.append((df['time'][i], "SELL"))
    return signals

# ===== Main =====
if __name__ == "__main__":
    df = fetch_prices()
    df = compute_ma(df)
    signals = generate_signals(df)

    print("Recent Signals:")
    for time, signal in signals[-5:]:
        print(time, signal)

from oandapyV20.endpoints.orders import OrderCreate

def place_order(signal, units=1000, instrument="EUR_USD"):
    """
    Place a market order based on the signal.
    units: positive for buy, negative for sell
    """
    # Determine units: Buy = positive, Sell = negative
    if signal == "SELL":
        units = -units

    order_data = {
        "order": {
            "units": str(units),
            "instrument": instrument,
            "timeInForce": "FOK",
            "type": "MARKET",
            "positionFill": "DEFAULT"
        }
    }

    r = OrderCreate(accountID=OANDA_ACCOUNT_ID, data=order_data)
    try:
        response = client.request(r)
        print(f"✅ Order executed: {signal} {abs(units)} units")
        return response
    except Exception as e:
        print("❌ Order failed:", e)
        return None

# Execute last signal (demo account)
if signals:
    last_time, last_signal = signals[-1]
    print(f"\nExecuting last signal: {last_signal} at {last_time}")
    place_order(last_signal)

import time

while True:
    df = fetch_prices()
    df = compute_ma(df)
    signals = generate_signals(df)

    if signals:
        last_time, last_signal = signals[-1]
        print(f"{last_time} - Signal: {last_signal}")
        place_order(last_signal)

    time.sleep(300)  # Wait 5 minutes
