import pandas as pd
import csv
import os

# ===== Parameters =====
SHORT_MA = 5
LONG_MA = 20
INITIAL_BALANCE = 100000   # virtual USD
TRADE_UNITS = 1000         # units per simulated trade
HISTORICAL_CSV = "EUR_USD_M5_90days.csv"  # downloaded CSV

# ===== Load historical data =====
df = pd.read_csv(HISTORICAL_CSV)

# Compute moving averages
df['MA_short'] = df['close'].rolling(window=SHORT_MA).mean()
df['MA_long'] = df['close'].rolling(window=LONG_MA).mean()

# ===== Backtesting =====
balance = INITIAL_BALANCE
position = 0  # positive = long, negative = short
trade_log = []

for i in range(1, len(df)):
    # Check for crossover signals
    if df['MA_short'][i] > df['MA_long'][i] and df['MA_short'][i-1] <= df['MA_long'][i-1]:
        signal = "BUY"
        if position <= 0:
            # Close short if any
            balance += position * df['close'][i]
            # Enter long
            position = TRADE_UNITS
            balance -= position * df['close'][i]
            trade_log.append((df['time'][i], signal, df['close'][i], balance))
    elif df['MA_short'][i] < df['MA_long'][i] and df['MA_short'][i-1] >= df['MA_long'][i-1]:
        signal = "SELL"
        if position >= 0:
            # Close long if any
            balance += position * df['close'][i]
            # Enter short
            position = -TRADE_UNITS
            balance -= position * df['close'][i]
            trade_log.append((df['time'][i], signal, df['close'][i], balance))

# Close any open position at last price
if position != 0:
    balance += position * df['close'].iloc[-1]

# ===== Output results =====
print(f"Final virtual balance: ${balance:.2f}")
print(f"Total trades executed: {len(trade_log)}")

# ===== Save trade log =====
file_exists = os.path.isfile("backtest_log.csv")
with open("backtest_log.csv", "w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["Time", "Signal", "Price", "Balance"])
    writer.writerows(trade_log)

print("Backtest complete. See backtest_log.csv for details.")
