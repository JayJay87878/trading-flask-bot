from flask import Flask, request, jsonify
import logging

app = Flask(__name__)

# Enable logging
logging.basicConfig(level=logging.INFO)

@app.route('/')
def index():
    return "Flask bot is running!"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No JSON received"}), 400
    
    # Log the incoming payload
    logging.info(f"Received webhook: {data}")
    
    # Example: parse TradingView alert
    symbol = data.get("symbol")
    signal = data.get("signal")
    timeframe = data.get("timeframe")
    
    # Placeholder: call your strategy functions here
    # e.g., analyze_signal(symbol, signal, timeframe)
    
    # Respond back
    return jsonify({"status": "success", "received": data})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
