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
    url = "https://api.perplexity.ai/v1/sonar"
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "sonar",
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是專業期貨交易分析助手。"
                    "請使用繁體中文，針對收到的MES交易訊號做短線市場分析。"
                    "請輸出：1. 趨勢判斷 2. 波動風險 3. 是否適合追價 4. 風險提醒。"
                    "內容簡潔，控制在150字內。"
                )
            },
            {
                "role": "user",
                "content": f"請分析這個訊號：{signal_text}"
            }
        ]
    }
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"]

@app.route("/", methods=["GET"])
def home():
    return "Webhook server is running."

@app.route("/test", methods=["GET"])
def test():
    msg = "Render 測試成功，Perplexity 分析版 webhook 啟用中。"
    tg_status, tg_text = send_telegram_message(msg)
    return jsonify({
        "ok": True,
        "telegram_status": tg_status,
        "telegram_response": tg_text
    })

@app.route("/webhook/tradingview", methods=["POST"])
def tradingview_webhook():
    raw_text = request.get_data(as_text=True).strip()

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
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
