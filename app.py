import os
import re
import json
import requests
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# Render 環境變數（在 Render Dashboard > Environment 設定）
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"


def send_telegram(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram token 未設定")
        return
    try:
        requests.post(TELEGRAM_URL, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text
        }, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")


def parse_signal(raw: str) -> dict:
    result = {
        "type": "unknown",
        "direction": "",
        "price": "",
        "stop_loss": "",
        "take_profit": "",
        "score": "",
        "time": datetime.now().strftime("%Y/%m/%d %H:%M")
    }

    # 判斷進場 or 出場
    if "進倉點" in raw:
        result["type"] = "entry"
    elif "出場點" in raw:
        result["type"] = "exit"

    # 方向
    if "多" in raw:
        result["direction"] = "多"
    elif "空" in raw:
        result["direction"] = "空"

    # 提取所有數字（過濾非價格）
    numbers = [float(n) for n in re.findall(r'\d+\.?\d*', raw) if float(n) > 100]

    if result["type"] == "entry":
        result["price"]      = str(round(numbers[0], 2)) if len(numbers) > 0 else ""
        result["stop_loss"]  = str(round(numbers[1], 2)) if len(numbers) > 1 else ""
        result["take_profit"]= str(round(numbers[2], 2)) if len(numbers) > 2 else ""

    if result["type"] == "exit":
        result["price"] = str(round(numbers[0], 2)) if len(numbers) > 0 else ""

    # 分數
    m = re.search(r'分數\s*(\d+)', raw)
    if m:
        result["score"] = m.group(1)

    return result


def build_entry_msg(s: dict) -> str:
    direction = s.get("direction", "")
    score     = s.get("score", "80")
    rate      = "68%" if direction == "多" else "58%"
    return (
        f"時間 {s['time']}\n"
        f"進倉 {direction}\n"
        f"進倉點 {s['price']}\n"
        f"停損 {s['stop_loss']}\n"
        f"停利 {s['take_profit']}\n"
        f"成功率分數 {rate} {score}分"
    )


def build_exit_msg(s: dict) -> str:
    return (
        f"時間 {s['time']}\n"
        f"出場點 {s['price']}"
    )


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        raw = request.data.decode("utf-8")
        print(f"收到: {raw}")

        signal = parse_signal(raw)

        if signal["type"] == "entry":
            send_telegram(build_entry_msg(signal))
        elif signal["type"] == "exit":
            send_telegram(build_exit_msg(signal))
        else:
            send_telegram(f"時間 {signal['time']}\n{raw[:200]}")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "V8.7 running"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
