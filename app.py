import os
import requests
import threading
from flask import Flask, request, jsonify

app = Flask(__name__)

BOT = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT = os.getenv("TELEGRAM_CHAT_ID")
PPLX = os.getenv("PERPLEXITY_API_KEY")


def tg(text):
    url = "https://api.telegram.org/bot" + BOT + "/sendMessage"
    data = {"chat_id": CHAT, "text": text}
    r = requests.post(url, json=data, timeout=30)
    return r.status_code


def ask_pplx(signal_text):
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": "Bearer " + PPLX,
        "Content-Type": "application/json"
    }
    payload = {
        "model": "sonar",
        "messages": [
            {
                "role": "system",
                "content": "你是專業的美股期貨交易分析助手。請用繁體中文，簡短分析這筆 MES 訊號的可能意義、偏多偏空方向、以及交易風險。控制在6行內。"
            },
            {
                "role": "user",
                "content": signal_text
            }
        ]
    }
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    j = r.json()
    return j["choices"][0]["message"]["content"]


def process_signal(body):
    try:
        analysis = ask_pplx(body)
    except Exception as e:
        analysis = "Perplexity 分析失敗: " + str(e)

    msg = "TradingView 訊號: " + body + "\n\nPerplexity 分析:\n" + analysis

    try:
        tg(msg)
    except Exception:
        pass


@app.route("/")
def home():
    return "OK-PPLX-ASYNC-20260327"


@app.route("/test")
def test():
    code = tg("TEST OK PPLX ASYNC 20260327")
    return jsonify({"ok": True, "code": code})


@app.route("/webhook/tradingview", methods=["POST"])
def webhook():
    body = request.get_data(as_text=True)

    if not body:
        body = "EMPTY"

    t = threading.Thread(target=process_signal, args=(body,))
    t.start()

    return jsonify({
        "ok": True,
        "accepted": True,
        "body": body
    }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
