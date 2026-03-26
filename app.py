import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    }
    r = requests.post(url, json=payload, timeout=30)
    return r.status_code, r.text


@app.route("/", methods=["GET"])
def home():
    return "DEBUG VERSION 20260327"


@app.route("/test", methods=["GET"])
def test():
    tg_status, tg_text = send_telegram_message("DEBUG TEST OK")
    return jsonify({
        "ok": True,
        "version": "DEBUG VERSION 20260327",
        "telegram_status": tg_status,
        "telegram_response": tg_text
    }), 200


@app.route("/webhook/tradingview", methods=["POST"])
def tradingview_webhook():
    raw_text = request.get_data(as_text=True)

    if not raw_text:
        raw_text = "EMPTY BODY"

    tg_status, tg_text = send_telegram_message(
        f"DEBUG WEBHOOK OK
內容：{raw_text}"
    )

    return jsonify({
        "ok": True,
        "version": "DEBUG VERSION 20260327",
        "received": raw_text,
        "telegram_status": tg_status,
        "telegram_response": tg_text
    }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
