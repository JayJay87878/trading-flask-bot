from flask import Flask, request, jsonify
import logging
import os
import requests

# Optional: Telegram bot setup
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # set this in Render env
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")      # set this in Render env

app = Flask(__name__)

# Enable logging
logging.basicConfig(level=logging.INFO)

def send_telegram_message(message: str):
    """Send a message via Telegram bot."""
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        try:
            response = requests.post(url, json=payload)
            if response.status_code != 200:
                logging.warning(f"Telegram send failed: {response.text}")
        except Exception as e:
            logging.error(f"Error sending Telegram message: {e}")

@app.route("/")
def index():
    return "Trading Flask Bot is running!"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if not data:
        logging.warning("No JSON received")
        return jsonify({"error": "No JSON received"}), 400

    logging.info(f"Received webhook: {data}")

    # Extract fields (example from TradingView/Zapier)
    symbol = data.get("symbol")
    signal = data.get("signal")
    timeframe = data.get("timeframe")

    # --- Placeholder for your strategy ---
    # e.g., from strategies.forex_strategy import analyze_signal
    # trade_decision = analyze_signal(symbol, signal, timeframe)

    # Optional: send Telegram notification
    send_telegram_message(f"Webhook received: {symbol} {signal} {timeframe}")

    return jsonify({"status": "success", "received": data})


if __name__ == "__main__":
    # For local testing
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
