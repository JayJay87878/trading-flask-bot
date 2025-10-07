# smc_visual_alerts.py
"""
Enhanced Visualization + Telegram Alerts
- Plots candlestick charts with POIs: FVG, OB, BB, Liquidity
- Marks Entry, Stop Loss, Take Profit
- Shows Confluence Score
- Sends chart + details via Telegram
"""

import matplotlib.pyplot as plt
from smc_engine import SMCEngine, Signal, POI
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from telegram import Bot
from io import BytesIO

# -----------------------------
# Telegram Configuration
# -----------------------------
TELEGRAM_TOKEN = "YOUR_BOT_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"  # numeric ID or @username
bot = Bot(token=TELEGRAM_TOKEN)

# -----------------------------
# Colors for POI types
# -----------------------------
POI_COLORS = {
    "FVG": "blue",
    "OB": "purple",
    "BB": "orange",
    "Liquidity": "cyan"
}

# -----------------------------
# Plot Signal Chart
# -----------------------------
def plot_signal_chart(engine: SMCEngine, signal: Signal, tf='M15'):
    candles = engine.candles.get(tf, [])
    if not candles:
        print("No candles available for plotting")
        return

    fig, ax = plt.subplots(figsize=(14,7))

    # Plot candlesticks
    for c in candles:
        color = 'green' if c.close >= c.open else 'red'
        ax.plot([c.timestamp, c.timestamp], [c.low, c.high], color='black', linewidth=0.8)
        ax.add_patch(Rectangle(
            (mdates.date2num(c.timestamp)-0.0005, min(c.open, c.close)),
            0.001, abs(c.close - c.open),
            color=color
        ))

    # Plot POIs
    for poi in engine.pois:
        if not poi.validated:
            continue
        color = POI_COLORS.get(poi.poi_type, 'gray')
        ax.axhspan(poi.start, poi.end, alpha=0.25, color=color)
        ax.text(candles[-1].timestamp, (poi.start+poi.end)/2, f"{poi.poi_type}", color=color, fontsize=9)

    # Plot Entry / SL / TP
    ax.axhline(signal.entry, color='green', linestyle='--', linewidth=1.5, label='Entry')
    ax.axhline(signal.stop, color='red', linestyle='--', linewidth=1.5, label='Stop Loss')
    ax.axhline(signal.target, color='blue', linestyle='--', linewidth=1.5, label='Take Profit')

    # Add Confluence Score
    ax.text(candles[-1].timestamp, max(c.high for c in candles), f"Confluence Score: {signal.confluence_score}", fontsize=10, color='black')

    ax.set_title(f"{signal.symbol} - Signal Visualization")
    ax.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    return fig

# -----------------------------
# Multi-TF Trend Table
# -----------------------------
def generate_trend_table(engine: SMCEngine):
    table = {}
    for tf, candles in engine.candles.items():
        direction = engine.detect_structure(tf)['direction']
        confidence = min(100, len(candles)*10)
        table[tf] = {'direction': direction, 'confidence': confidence}
    return table

def print_trend_table(table):
    print("\nMulti-TF Trend Confidence:")
    print("TF\tDirection\tConfidence")
    for tf, data in table.items():
        print(f"{tf}\t{data['direction']}\t{data['confidence']}%")

# -----------------------------
# Telegram Alert
# -----------------------------
def send_signal_telegram(signal: Signal, engine: SMCEngine):
    trend_table = generate_trend_table(engine)
    print_trend_table(trend_table)

    # Plot chart
    fig = plot_signal_chart(engine, signal)
    buf = BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)

    # Message
    msg = f"{signal.symbol} Signal\n"
    msg += f"Direction: {signal.direction}\n"
    msg += f"Entry: {signal.entry}\nStop: {signal.stop}\nTP: {signal.target}\nRR: {signal.rr:.2f}\n"
    msg += f"Confluence Score: {signal.confluence_score}\n"
    msg += "Confluence Details:\n"
    for k,v in signal.confluence.items():
        msg += f" - {k}: {'Yes' if v else 'No'}\n"

    bot.send_photo(chat_id=CHAT_ID, photo=buf, caption=msg)
    plt.close(fig)

# -----------------------------
# Example Usage
# -----------------------------
if __name__ == "__main__":
    from smc_engine import SMCEngine

    # Example engine & payload
    example_payload = [
        {"time": "2025-10-07T16:00:00", "open": 1.0760, "high": 1.0770, "low": 1.0755, "close": 1.0765, "volume": 1000},
        {"time": "2025-10-07T16:15:00", "open": 1.0765, "high": 1.0775, "low": 1.0760, "close": 1.0772, "volume": 1200},
        {"time": "2025-10-07T16:30:00", "open": 1.0772, "high": 1.0780, "low": 1.0768, "close": 1.0775, "volume": 1100}
    ]
    engine = SMCEngine(symbol="EURUSD")
    engine.add_candles('M15', example_payload)
    engine.detect_fvgs('M15')
    engine.detect_order_blocks('M15')
    engine.detect_liquidity_pools('M15')
    engine.validate_pois()
    signal = engine.generate_signal()
    if signal:
        send_signal_telegram(signal, engine)
