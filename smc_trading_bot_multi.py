# smc_trading_bot_multi.py
"""
Integrated Multi-Symbol SMC Trading Bot
- Handles multiple trading pairs
- Receives TradingView webhook data
- Updates candle history (multi-timeframe)
- Detects structure, POIs, FVGs, OBs, BBs, Liquidity Pools
- Generates trade signals
- Plots chart + sends Telegram alert with confluence
"""

from flask import Flask, request, jsonify
from smc_engine import SMCEngine
from smc_visual_alerts import send_signal_telegram
import threading

# -----------------------------
# Flask Webhook Setup
# -----------------------------
app = Flask(__name__)

# Predefined symbols
SYMBOLS = ["EURUSD", "XAUUSD", "GBPJPY", "AUDJPY", "NZDJPY", "BTCUSD", "CADJPY", "GBPUSD", "USDJPY"]

# Dictionary to maintain engines per symbol
engines = {symbol: SMCEngine(symbol=symbol) for symbol in SYMBOLS}

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

    if symbol not in SYMBOLS:
        return jsonify({"status": "symbol_not_supported", "symbol": symbol}), 400

    engine = engines[symbol]
    engine.add_candles(tf, candles)
    engine.detect_fvgs(tf)
    engine.detect_order_blocks(tf)
    engine.detect_liquidity_pools(tf)
    engine.validate_pois()
    signal = engine.generate_signal()

    if signal:
        # Send Telegram alert in separate thread to avoid blocking
        threading.Thread(target=send_signal_telegram, args=(signal, engine)).start()
        return jsonify({"status": "signal_sent", "symbol": symbol}), 200
    else:
        return jsonify({"status": "no_signal", "symbol": symbol}), 200

# -----------------------------
# Run Flask App
# -----------------------------
if __name__ == '__main__':
    print(f"SMC Multi-Symbol Trading Bot running for symbols: {', '.join(SYMBOLS)}")
    app.run(host='0.0.0.0', port=5000)
