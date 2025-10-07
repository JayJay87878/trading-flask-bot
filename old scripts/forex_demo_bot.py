import pandas as pd
from oandapyV20 import API
import oandapyV20.endpoints.instruments as instruments
from oandapyV20.endpoints.orders import OrderCreate
from config import OANDA_API_KEY, OANDA_ACCOUNT_ID
import time
import csv
import os

# ===== Initialize OANDA client =====
client = API(access_token=OANDA_API_KEY)

# ===== Fetch recent EUR/USD prices =====
def fetch_prices(instrument="EUR_USD", count=50, granularity="M5"):
    r = instruments.InstrumentsCandles(instrument=instrument,
                                       params={"count": count,
                                               "granularity": granularity})
    response = client.request(r)
    data = response['candles']
    prices = [float(candle['mid']['c']) for candle in data if candle['complete']]
    times = [candle['time'] for candle in data if candle['complete']]
    df = pd.DataFrame({"time": times, "close": prices})
    return df

# ===== Compute moving averages =====
def compute_ma(df, short_window=5, long_window=20):
    df['MA_short'] = df['close'].rolling(window=short_window).mean()
    df['MA_long'] = df['close'].rolling(window=long_window).mean()
    return df

# ===== Generate buy/sell signals =====
def generate_signals(df):
    signals = []
    for i in range(1, len(df)):
        if df['MA_short'][i] > df['MA_long'][i] and df['MA_short'][i-1] <= df['MA_long'][i-1]:
            signals.append((df['time'][i], "BUY"))
        elif df['MA_short'][i] < df['MA_long'][i] and df['MA_short'][i-1] >= df['MA_long'][i-1]:
            signals.append((df['time'][i], "SELL"))
    return signals

# ===== Place market order =====
def place_order(signal, units=1000, instrument="EUR_USD"):
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

# ===== Logging function =====
def log_trade(time_stamp, signal):
    file_exists = os.path.isfile("trade_log.csv")
    with open("trade_log.csv", "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            writer.writerow(["Time", "Signal"])
        writer.writerow([time_stamp, signal])

# ===== Main loop =====
if __name__ == "__main__":
    print("🚀 Starting Demo Forex Bot. Press Ctrl+C to stop.")
    try:
        while True:
            df = fetch_prices()
            df = compute_ma(df)
            signals = generate_signals(df)

            if signals:
                last_time, last_signal = signals[-1]
                print(f"{last_time} - Signal: {last_signal}")
                place_order(last_signal)
                log_trade(last_time, last_signal)
            else:
                print("No new signals at this time.")

            time.sleep(300)  # Wait 5 minutes before next iteration

    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user.")
