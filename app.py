import os
import requests
import threading
from flask import Flask, request, jsonify

app = Flask(__name__)

BOT = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT = os.getenv("TELEGRAM_CHAT_ID")
PPLX = os.getenv("PERPLEXITY_API_KEY")


def tg(text):
    """發送 Telegram 訊息"""
    url = f"https://api.telegram.org/bot{BOT}/sendMessage"
    data = {"chat_id": CHAT, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=data, timeout=30)
        return r.status_code
    except Exception as e:
        print(f"Telegram error: {e}")
        return 0


def ask_pplx(signal_text):
    """呼叫 Perplexity API 做精簡分析"""
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {PPLX}",
        "Content-Type": "application/json"
    }
    
    system_prompt = """你是 MES 閃電判斷 V4.1 交易助理。

規則:
1. 不要搜尋網路
2. 不要引用新聞
3. 只根據訊號內容判讀
4. 用繁體中文
5. 總長度控制在 4 行內

輸出格式:
- 趨勢判斷: (明確翻多/明確翻空/觀望)
- 操作建議: (進場/等待/觀察)
- 風險提示: (一句話)
- 關鍵價位: (如有)"""

    payload = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": signal_text}
        ],
        "temperature": 0.3,
        "max_tokens": 200
    }
    
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        j = r.json()
        return j["choices"][0]["message"]["content"]
    except Exception as e:
        return f"分析失敗: {str(e)}"


def process_signal(body):
    """背景處理訊號"""
    try:
        analysis = ask_pplx(body)
    except Exception as e:
        analysis = f"AI 分析異常: {str(e)}"

    # 組合 Telegram 訊息 (使用 HTML 格式)
    msg = f"""<b>⚡ MES v4.1 閃電訊號</b>

<b>原始判斷:</b>
<code>{body}</code>

<b>AI 分析:</b>
{analysis}

<i>時間: 台灣盤後</i>"""

    try:
        tg(msg)
    except Exception as e:
        print(f"Send error: {e}")


@app.route("/")
def home():
    return "MES-PPLX-V4.1-FILTER-20260327"


@app.route("/test")
def test():
    code = tg("✅ TEST OK - MES v4.1 Trend Filter Active")
    return jsonify({"ok": True, "code": code})


@app.route("/webhook/tradingview", methods=["POST"])
def webhook():
    """接收 TradingView webhook"""
    body = request.get_data(as_text=True)
    
    if not body or len(body) < 10:
        return jsonify({"error": "Empty or invalid signal"}), 400
    
    # 立即回應 200 避免 timeout
    t = threading.Thread(target=process_signal, args=(body,))
    t.start()
    
    return jsonify({
        "ok": True,
        "accepted": True,
        "length": len(body)
    }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
