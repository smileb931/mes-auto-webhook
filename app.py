import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

BOT = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT = os.getenv("TELEGRAM_CHAT_ID")

def tg(text):
    url = "https://api.telegram.org/bot" + BOT + "/sendMessage"
    data = {"chat_id": CHAT, "text": text}
    r = requests.post(url, json=data, timeout=30)
    return r.status_code

@app.route("/")
def home():
    return "OK-20260327"

@app.route("/test")
def test():
    code = tg("TEST OK 20260327")
    return jsonify({"ok": True, "code": code})

@app.route("/webhook/tradingview", methods=["POST"])
def webhook():
    body = request.get_data(as_text=True)
    if not body:
        body = "EMPTY"
    code = tg("WEBHOOK OK: " + body)
    return jsonify({"ok": True, "body": body, "code": code})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
