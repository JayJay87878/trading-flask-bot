from telegram import Bot
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# Initialize bot
telegram_bot = Bot(token=TELEGRAM_BOT_TOKEN)

def send_telegram_message(message):
    try:
        telegram_bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as e:
        print("❌ Telegram notification failed:", e)

import pandas as pd
import csv
import os
import time
from datetime import datetime, timedelta
from oandapyV20 import API
from oandapyV20.endpoints.orders import OrderCreate
from oandapyV20.endpoints import instruments as instruments_endpoint
from config import OANDA_API_KEY, OANDA_ACCOUNT_ID

# ===== Parameters =====
INSTRUMENTS = ["EUR_USD", "GBP_USD", "USD_JPY", "XAU_USD", "GBP_JPY", "AUD_JPY", "NZD_JPY", "CAD_JPY"]  # add more pairs
GRANULARITY = "M5"
TOTAL_DAYS = 90
MAX_CANDLES_PER_REQUEST = 5000
SHORT_MA = 5
LONG_MA = 20
TRADE_UNITS = 1000
SLEEP_INTERVAL = 300  # seconds
HISTORICAL_FOLDER = "historical_data"

# ===== Initialize API client =====
client = API(access_token=OANDA_API_KEY)
os.makedirs(HISTORICAL_FOLDER, exist_ok=True)
os.makedirs("backtest_logs", exist_ok=True)

# ===== Function to fetch historical candles =====
def fetch_candles(instrument, start, end):
    params = {
        "from": start.isoformat("T") + "Z",
        "to": end.isoformat("T") + "Z",
        "granularity": GRANULARITY,
    }
    r = instruments_endpoint.InstrumentsCandles(instrument=instrument, params=params)
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

# ===== Download historical candles for all instruments =====
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

    df = pd.DataFrame(all_candles)
    csv_filename = os.path.join(HISTORICAL_FOLDER, f"{instr}_{GRANULARITY}_{TOTAL_DAYS}days.csv")
    df.to_csv(csv_filename, index=False)
    print(f"✅ Saved {len(df)} candles to {csv_filename}")

if signal and signal != last_signals[instr]:
    msg = f"{live_df['time'].iloc[-1]} - {instr} new signal: {signal}"
    print(msg)
    send_telegram_message(msg)

# ===== Function to place demo orders =====
def place_order(signal, instrument, units, stop_loss_pips, take_profit_pips):
    if signal == "SELL":
        units = -units

    sl_distance = STOP_LOSS_PIPS * (0.0001 if "JPY" not in instrument else 0.01)
    tp_distance = TAKE_PROFIT_PIPS * (0.0001 if "JPY" not in instrument else 0.01)

    order_data = {
        "order": {
            "units": str(units),
            "instrument": instrument,
            "timeInForce": "FOK",
            "type": "MARKET",
            "positionFill": "DEFAULT",
            "stopLossOnFill": {"distance": str(sl_distance)},
            "takeProfitOnFill": {"distance": str(tp_distance)}
        }
    }
    r = OrderCreate(accountID=OANDA_ACCOUNT_ID, data=order_data)
    try:
        response = client.request(r)
        msg = f"✅ {instrument} {signal} order executed: {abs(units)} units | SL:{STOP_LOSS_PIPS} TP:{TAKE_PROFIT_PIPS}"
        print(msg)
        send_telegram_message(msg)
        return response
    except Exception as e:
        print(f"❌ {instrument} order failed:", e)
        send_telegram_message(f"❌ {instrument} order failed: {e}")
        return None

# ===== Backtest all instruments =====
virtual_balances = {}
last_signals = {}

for instr in INSTRUMENTS:
    file_path = os.path.join(HISTORICAL_FOLDER, f"{instr}_{GRANULARITY}_{TOTAL_DAYS}days.csv")
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
    log_file = os.path.join("backtest_logs", f"{instr}_backtest.csv")
    with open(log_file, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Time", "Signal", "Price", "Balance"])
        writer.writerows(trade_log)

print("\n✅ Multi-instrument backtesting complete:")
for instr, bal in virtual_balances.items():
    print(f"{instr}: ${bal:.2f}")

# ===== Live demo monitoring =====
print("\n🚀 Starting live demo monitoring. Press Ctrl+C to stop.")

try:
    while True:
        for instr in INSTRUMENTS:
            r = instruments_endpoint.InstrumentsCandles(instrument=instr,
                                                        params={"count": 50, "granularity": GRANULARITY})
            live_data = client.request(r)
            live_prices = [float(c['mid']['c']) for c in live_data['candles'] if c['complete']]
            times = [c['time'] for c in live_data['candles'] if c['complete']]
            live_df = pd.DataFrame({"time": times, "close": live_prices})
            live_df['MA_short'] = live_df['close'].rolling(window=SHORT_MA).mean()
            live_df['MA_long'] = live_df['close'].rolling(window=LONG_MA).mean()

            if len(live_df) < LONG_MA:
                continue

            # Generate signal
            signal = None
            if live_df['MA_short'].iloc[-1] > live_df['MA_long'].iloc[-1] and live_df['MA_short'].iloc[-2] <= live_df['MA_long'].iloc[-2]:
                signal = "BUY"
            elif live_df['MA_short'].iloc[-1] < live_df['MA_long'].iloc[-1] and live_df['MA_short'].iloc[-2] >= live_df['MA_long'].iloc[-2]:
                signal = "SELL"

            if signal and signal != last_signals[instr]:
                print(f"{live_df['time'].iloc[-1]} - {instr} new signal: {signal}")
                place_order(signal, instr)
                last_signals[instr] = signal
            else:
                print(f"{live_df['time'].iloc[-1]} - {instr} no new signal")

        time.sleep(SLEEP_INTERVAL)

except KeyboardInterrupt:
    print("\n🛑 Workflow stopped by user.")
