import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")


def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    }
    r = requests.post(url, json=payload, timeout=30)
    return r.status_code, r.text


def ask_perplexity(signal_text):
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "sonar",
        "messages": [
            {
                "role": "system",
                "content": "你是專業期貨分析助手，請用繁體中文簡短分析這個 MES 訊號。"
            },
            {
                "role": "user",
                "content": signal_text
            }
        ]
    }
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"]


@app.route("/", methods=["GET"])
def home():
    return "MES webhook server is running."


@app.route("/test", methods=["GET"])
def test():
    tg_status, tg_text = send_telegram_message("Telegram 測試成功")
    return jsonify({
        "ok": True,
        "telegram_status": tg_status,
        "telegram_response": tg_text
    })


@app.route("/webhook/tradingview", methods=["POST"])
def tradingview_webhook():
    raw_text = ""

    try:
        if request.is_json:
            data = request.get_json(silent=True)
            if isinstance(data, dict):
                raw_text = str(data)
            elif data:
                raw_text = str(data)
        if not raw_text:
            raw_text = request.get_data(as_text=True).strip()
        if not raw_text:
            raw_text = "MES LONG signal"

        try:
            analysis = ask_perplexity(raw_text)
        except Exception as e:
            analysis = f"Perplexity 分析失敗：{str(e)}"

        final_msg = (
            f"TradingView 訊號
"
            f"原始內容：{raw_text}

"
            f"Perplexity 分析：
{analysis}"
        )

        tg_status, tg_text = send_telegram_message(final_msg)

        return jsonify({
            "ok": True,
            "received": raw_text,
            "analysis": analysis,
            "telegram_status": tg_status,
            "telegram_response": tg_text
        }), 200

    except Exception as e:
        error_msg = f"Webhook 處理失敗：{str(e)}"
        try:
            send_telegram_message(error_msg)
        except Exception:
            pass

        return jsonify({
            "ok": False,
            "error": error_msg
        }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
