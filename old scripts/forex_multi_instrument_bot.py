import pandas as pd
import csv
import os
import time
from oandapyV20 import API
from oandapyV20.endpoints.orders import OrderCreate
from oandapyV20.endpoints import instruments as instruments_endpoint
from config import OANDA_API_KEY, OANDA_ACCOUNT_ID

# ===== Parameters =====
SHORT_MA = 5
LONG_MA = 20
TRADE_UNITS = 1000
SLEEP_INTERVAL = 300  # seconds
INSTRUMENTS = ["EUR_USD", "GBP_USD", "USD_JPY"]  # add more pairs
HISTORICAL_FOLDER = "historical_data"  # folder with CSVs for each instrument

# ===== Initialize OANDA client =====
client = API(access_token=OANDA_API_KEY)

# ===== Helper: place demo order =====
def place_order(signal, instrument, units=TRADE_UNITS):
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
        print(f"✅ {instrument} demo order executed: {signal} {abs(units)} units")
        return response
    except Exception as e:
        print(f"❌ {instrument} demo order failed:", e)
        return None

# ===== Load historical data & backtest =====
virtual_balances = {}
last_signals = {}

for instr in INSTRUMENTS:
    file_path = os.path.join(HISTORICAL_FOLDER, f"{instr}_M5_90days.csv")
    df = pd.read_csv(file_path)
    df['MA_short'] = df['close'].rolling(window=SHORT_MA).mean()
    df['MA_long'] = df['close'].rolling(window=LONG_MA).mean()

    balance = 100000
    position = 0
    trade_log = []

    for i in range(1, len(df)):
        if df['MA_short'][i] > df['MA_long'][i] and df['MA_short'][i-1] <= df['MA_long'][i-1]:
            signal = "BUY"
            if position <= 0:
                balance += position * df['close'][i]
                position = TRADE_UNITS
                balance -= position * df['close'][i]
                trade_log.append((df['time'][i], signal, df['close'][i], balance))
        elif df['MA_short'][i] < df['MA_long'][i] and df['MA_short'][i-1] >= df['MA_long'][i-1]:
            signal = "SELL"
            if position >= 0:
                balance += position * df['close'][i]
                position = -TRADE_UNITS
                balance -= position * df['close'][i]
                trade_log.append((df['time'][i], signal, df['close'][i], balance))
    if position != 0:
        balance += position * df['close'].iloc[-1]

    virtual_balances[instr] = balance
    last_signals[instr] = None

    # Save backtest logs
    os.makedirs("backtest_logs", exist_ok=True)
    log_file = os.path.join("backtest_logs", f"{instr}_backtest.csv")
    with open(log_file, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Time", "Signal", "Price", "Balance"])
        writer.writerows(trade_log)

print("✅ Multi-instrument backtesting complete. Virtual balances:")
for instr, bal in virtual_balances.items():
    print(f"{instr}: ${bal:.2f}")

# ===== Live monitoring loop =====
print("\n🚀 Starting live demo monitoring for multiple instruments. Press Ctrl+C to stop.")

try:
    while True:
        for instr in INSTRUMENTS:
            # Fetch last 50 candles live
            r = instruments_endpoint.InstrumentsCandles(instrument=instr,
                                                        params={"count": 50, "granularity": "M5"})
            live_data = client.request(r)
            live_prices = [float(c['mid']['c']) for c in live_data['candles'] if c['complete']]
            times = [c['time'] for c in live_data['candles'] if c['complete']]
            live_df = pd.DataFrame({"time": times, "close": live_prices})
            live_df['MA_short'] = live_df['close'].rolling(window=SHORT_MA).mean()
            live_df['MA_long'] = live_df['close'].rolling(window=LONG_MA).mean()

            if len(live_df) < LONG_MA:
                continue

            # Generate latest signal
            signal = None
            if live_df['MA_short'].iloc[-1] > live_df['MA_long'].iloc[-1] and live_df['MA_short'].iloc[-2] <= live_df['MA_long'].iloc[-2]:
                signal = "BUY"
            elif live_df['MA_short'].iloc[-1] < live_df['MA_long'].iloc[-1] and live_df['MA_short'].iloc[-2] >= live_df['MA_long'].iloc[-2]:
                signal = "SELL"

            # Place demo trade if new signal
            if signal and signal != last_signals[instr]:
                print(f"{live_df['time'].iloc[-1]} - {instr} new signal: {signal}")
                place_order(signal, instr)
                last_signals[instr] = signal
            else:
                print(f"{live_df['time'].iloc[-1]} - {instr} no new signal")

        time.sleep(SLEEP_INTERVAL)

except KeyboardInterrupt:
    print("\n🛑 Multi-instrument live demo monitoring stopped by user.")
