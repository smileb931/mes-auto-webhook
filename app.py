from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

@app.route("/")
def home():
    return "MES webhook server is running"

@app.route("/webhook/tradingview", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    msg = f"收到 TradingView 訊號: {data}"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg
    }
    requests.post(url, json=payload, timeout=20)

    return jsonify({"ok": True, "data": data})
