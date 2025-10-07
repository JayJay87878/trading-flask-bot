import pandas as pd
import csv
import os
import time
from oandapyV20 import API
from oandapyV20.endpoints.orders import OrderCreate
from config import OANDA_API_KEY, OANDA_ACCOUNT_ID

# ===== Parameters =====
SHORT_MA = 5
LONG_MA = 20
TRADE_UNITS = 1000
HISTORICAL_CSV = "EUR_USD_M5_90days.csv"  # historical candles for backtesting
SLEEP_INTERVAL = 300  # seconds between live checks

# ===== Initialize OANDA client =====
client = API(access_token=OANDA_API_KEY)

# ===== Load historical data =====
df = pd.read_csv(HISTORICAL_CSV)
df['MA_short'] = df['close'].rolling(window=SHORT_MA).mean()
df['MA_long'] = df['close'].rolling(window=LONG_MA).mean()

# ===== Backtest =====
balance = 100000
position = 0
trade_log = []

for i in range(1, len(df)):
    if df['MA_short'][i] > df['MA_long'][i] and df['MA_short'][i-1] <= df['MA_long'][i-1]:
        signal = "BUY"
        if position <= 0:
            balance += position * df['close'][i]  # close short
            position = TRADE_UNITS
            balance -= position * df['close'][i]  # open long
            trade_log.append((df['time'][i], signal, df['close'][i], balance))
    elif df['MA_short'][i] < df['MA_long'][i] and df['MA_short'][i-1] >= df['MA_long'][i-1]:
        signal = "SELL"
        if position >= 0:
            balance += position * df['close'][i]  # close long
            position = -TRADE_UNITS
            balance -= position * df['close'][i]  # open short
            trade_log.append((df['time'][i], signal, df['close'][i], balance))

# Close any open position
if position != 0:
    balance += position * df['close'].iloc[-1]

print(f"Backtest complete. Virtual balance: ${balance:.2f}")
print(f"Total simulated trades: {len(trade_log)}")

# ===== Log backtest =====
with open("backtest_log.csv", "w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["Time", "Signal", "Price", "Balance"])
    writer.writerows(trade_log)

# ===== Function to place demo trade =====
def place_order(signal, units=TRADE_UNITS, instrument="EUR_USD"):
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
        print(f"✅ Demo order executed: {signal} {abs(units)} units")
        return response
    except Exception as e:
        print("❌ Demo order failed:", e)
        return None

# ===== Live Monitoring Loop =====
print("\n🚀 Starting live demo monitoring. Press Ctrl+C to stop.")
try:
    last_signal = None
    while True:
        # Fetch last 50 candles live from OANDA
        import oandapyV20.endpoints.instruments as instruments
        r = instruments.InstrumentsCandles(instrument="EUR_USD",
                                           params={"count": 50,
                                                   "granularity": "M5"})
        live_data = client.request(r)
        live_prices = [float(c['mid']['c']) for c in live_data['candles'] if c['complete']]
        times = [c['time'] for c in live_data['candles'] if c['complete']]
        live_df = pd.DataFrame({"time": times, "close": live_prices})
        live_df['MA_short'] = live_df['close'].rolling(window=SHORT_MA).mean()
        live_df['MA_long'] = live_df['close'].rolling(window=LONG_MA).mean()

        # Generate latest signal
        if len(live_df) < LONG_MA:
            print("Not enough data to generate signal yet.")
        else:
            if (live_df['MA_short'].iloc[-1] > live_df['MA_long'].iloc[-1] and
                live_df['MA_short'].iloc[-2] <= live_df['MA_long'].iloc[-2]):
                signal = "BUY"
            elif (live_df['MA_short'].iloc[-1] < live_df['MA_long'].iloc[-1] and
                  live_df['MA_short'].iloc[-2] >= live_df['MA_long'].iloc[-2]):
                signal = "SELL"
            else:
                signal = None

            # Place demo trade if new signal
            if signal and signal != last_signal:
                print(f"{live_df['time'].iloc[-1]} - New signal: {signal}")
                place_order(signal)
                last_signal = signal
            else:
                print(f"{live_df['time'].iloc[-1]} - No new signal")

        time.sleep(SLEEP_INTERVAL)

except KeyboardInterrupt:
    print("\n🛑 Live demo monitoring stopped by user.")
