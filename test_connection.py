import requests

# ===== Replace with your actual credentials =====
OANDA_API_KEY = "76ce8805506f97677f51d21d5fc657fa-e896d70271923708b2c04fccaf5fe287"
OANDA_ACCOUNT_ID = "101-003-37258636-001"
OANDA_API_URL = "https://api-fxpractice.oanda.com/v3"

def test_connection():
    url = f"{OANDA_API_URL}/accounts/{OANDA_ACCOUNT_ID}/summary"
    headers = {
        "Authorization": f"Bearer {OANDA_API_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        print("✅ Connection successful!")
        data = response.json()
        print(f"Account Currency: {data['account']['currency']}")
        print(f"Balance: {data['account']['balance']}")
    else:
        print("❌ Connection failed!")
        print(response.status_code, response.text)

if __name__ == "__main__":
    test_connection()
