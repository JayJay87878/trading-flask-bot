# smc_trading_bot.py
"""
Integrated Smart Money Concept (SMC) Trading Bot
- Receives TradingView webhook data
- Updates candle history (multi-timeframe)
- Detects structure, POIs, FVGs, OBs, BBs
- Generates trade signals
- Plots chart + sends Telegram alert with RR, confluence, and trend table
"""

from flask import Flask, request, jsonify
from smc_engine import SMCEngine
from smc_visual_alerts import send_signal_telegram, plot_signal_chart, generate_trend_table, print_trend_table
import threading

# -----------------------------
# Flask Webhook Setup
# -----------------------------
app = Flask(__name__)

# Dictionary to maintain engines per symbol
engines = {}

# Telegram config (imported from smc_visual_alerts or redefine here)
from smc_visual_alerts import TELEGRAM_TOKEN, CHAT_ID, Bot
bot = Bot(token=TELEGRAM_TOKEN)

# -----------------------------
# Webhook Endpoint
# -----------------------------
@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Receives TradingView webhook POST requests in JSON format
    Example payload:
    {
        "symbol": "EURUSD",
        "timeframe": "M15",
        "candles": [
            {"time": "...", "open":..., "high":..., "low":..., "close":..., "volume":...},
            ...
        ]
    }
    """
    data = request.get_json()
    if not data or 'symbol' not in data or 'candles' not in data:
        return jsonify({"error": "Invalid payload"}), 400

    symbol = data['symbol']
    tf = data.get('timeframe', 'M15')
    candles = data['candles']

    # Create engine if new symbol
    if symbol not in engines:
        engines[symbol] = SMCEngine(symbol=symbol)
    
    engine = engines[symbol]
    engine.add_candles(tf, candles)
    engine.detect_fvgs(tf)
    engine.validate_pois()
    signal = engine.generate_signal()

    if signal:
        # Send Telegram alert in a separate thread to avoid blocking
        threading.Thread(target=send_signal_telegram, args=(signal, engine)).start()
        return jsonify({"status": "signal_sent", "symbol": symbol}), 200
    else:
        return jsonify({"status": "no_signal", "symbol": symbol}), 200

# -----------------------------
# Run Flask App
# -----------------------------
if __name__ == '__main__':
    print("SMC Trading Bot is running...")
    app.run(host='0.0.0.0', port=5000)
