from neo_api_client import NeoAPI
import pyotp
import time
import datetime
import os
from flask import Flask
import threading

# 🌐 Flask app (Render ke liye)
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Trading Bot Running"

# 🔐 ENV VARIABLES
CONSUMER_KEY = os.getenv("CONSUMER_KEY")
MOBILE = os.getenv("MOBILE")
UCC = os.getenv("UCC")
MPIN = os.getenv("MPIN")
TOTP_SECRET = os.getenv("TOTP_SECRET")

# 🔁 BOT FUNCTION
def run_bot():
    print("🚀 BOT STARTED")
    try:
        client = NeoAPI(environment="prod", consumer_key=CONSUMER_KEY)

        totp = pyotp.TOTP(TOTP_SECRET).now()
        client.totp_login(mobile_number=MOBILE, ucc=UCC, totp=totp)
        client.totp_validate(mpin=MPIN)

        print("✅ Login Successful")

        watchlist = [
            {"name": "NIFTY", "token": "26000", "segment": "nse_cm"},
            {"name": "BANKNIFTY", "token": "26009", "segment": "nse_cm"},
        ]

        prices = {}
        active_trade = None
        entry_price = 0
        active_market = None

        while True:
            try:
                now = datetime.datetime.now()

                if now.hour < 9 or now.hour > 23:
                    print("⛔ Market Closed")
                    time.sleep(60)
                    continue

                for item in watchlist:
                    name = item["name"]
                    token = item["token"]
                    segment = item["segment"]

                    data = client.quotes(
                        instrument_tokens=[{
                            "instrument_token": token,
                            "exchange_segment": segment
                        }],
                        quote_type="ltp"
                    )

                    if 'data' not in data or len(data['data']) == 0:
                        continue

                    ltp_val = data['data'][0].get('last_traded_price')
                    if ltp_val is None:
                        continue

                    ltp = float(ltp_val)
                    print(f"{name} → {ltp}")

                    if name not in prices:
                        prices[name] = []

                    prices[name].append(ltp)

                    # 🔥 ENTRY
                    if active_trade is None and len(prices[name]) > 3:

                        if prices[name][-1] > prices[name][-2] > prices[name][-3]:
                            print(f"🚀 BUY {name}")
                            place_trade(client, segment, name, ltp, "B")
                            active_trade = "BUY"
                            entry_price = ltp
                            active_market = name

                        elif prices[name][-1] < prices[name][-2] < prices[name][-3]:
                            print(f"🔻 SELL {name}")
                            place_trade(client, segment, name, ltp, "S")
                            active_trade = "SELL"
                            entry_price = ltp
                            active_market = name

                    # 💰 EXIT
                    if active_market == name:

                        if active_trade == "BUY":
                            if ltp >= entry_price + 1:
                                print(f"💰 PROFIT {name}")
                                active_trade = None

                            elif ltp <= entry_price - 1:
                                print(f"❌ LOSS {name}")
                                active_trade = None

                        elif active_trade == "SELL":
                            if ltp <= entry_price - 1:
                                print(f"💰 PROFIT {name}")
                                active_trade = None

                            elif ltp >= entry_price + 1:
                                print(f"❌ LOSS {name}")
                                active_trade = None

                time.sleep(2)

            except Exception as e:
                print("❌ Loop Error:", e)
                time.sleep(5)

    except Exception as e:
        print("❌ Login Error:", e)


# 📤 ORDER FUNCTION
def place_trade(client, segment, symbol, price, side):
    try:
        client.place_order(
            exchange_segment=segment,
            product="MIS",
            price=str(price),
            order_type="MKT",
            quantity="1",
            validity="DAY",
            trading_symbol=symbol,
            transaction_type=side,
            amo="NO",
            disclosed_quantity="0",
            market_protection="0",
            pf="N",
            trigger_price="0"
        )
    except Exception as e:
        print("Order Error:", e)


# 🚀 START BOT + SERVER
if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
