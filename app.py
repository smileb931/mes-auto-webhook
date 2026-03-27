from flask import Flask, request, jsonify
import requests
import os
import logging

app = Flask(__name__)

# 配置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 從環境變數獲取設定
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
PERPLEXITY_API_KEY = os.environ.get('PERPLEXITY_API_KEY')

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "service": "MES Auto Trading Webhook",
        "endpoints": {
            "health": "/health",
            "webhook": "/tradingview-webhook"
        }
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

@app.route('/tradingview-webhook', methods=['POST'])
def tradingview_webhook():
    try:
        # 獲取 TradingView 傳來的資料
        data = request.get_json()
        logger.info(f"Received TradingView alert: {data}")
        
        if not data:
            logger.error("No JSON data received")
            return jsonify({"status": "error", "message": "No data received"}), 400
        
        # 提取訊號資訊
        signal = data.get('signal', '未知訊號')
        price = data.get('price', 0)
        direction = data.get('direction', '未知')
        score = data.get('score', 0)
        position = data.get('position', 0)
        winrate = data.get('winrate', 0)
        risk = data.get('risk', 0)
        advice = data.get('advice', '無建議')
        time = data.get('time', '未知時間')
        
        # 呼叫 Perplexity AI 進行市場分析
        logger.info("Calling Perplexity API...")
        perplexity_analysis = call_perplexity_api(signal, price, direction, score)
        
        # 組合 Telegram 訊息
        telegram_message = f"""
⚡ MES 閃電訊號 {signal}
價格：{price:,.2f}
時間：{time}

{advice}
方向：{direction}
倉位：{position}（{'滿倉' if position >= 1.0 else '半倉' if position >= 0.5 else '輕倉'}）
勝率：{winrate}%
風險：{risk}/100

━━━━━━━━━━
🤖 AI 深度分析：
{perplexity_analysis}
"""
        
        # 發送到 Telegram
        logger.info("Sending Telegram message...")
        send_telegram_message(telegram_message)
        
        return jsonify({
            "status": "success",
            "message": "Alert processed and sent to Telegram",
            "data": data
        })
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

def call_perplexity_api(signal, price, direction, score):
    """呼叫 Perplexity AI 進行市場分析"""
    try:
        url = "https://api.perplexity.ai/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }
        
        prompt = f"""
你是專業的期貨市場分析師。根據以下 MES 期貨訊號，提供精簡的市場分析（最多100字）：

訊號：{signal}
價格：{price}
方向：{direction}
評分：{score}/100

請分析：
1. 當前市場趨勢
2. 進場時機評估
3. 風險提醒

用繁體中文回答，直接給出分析內容，不要前言。
"""
        
        payload = {
            "model": "llama-3.1-sonar-small-128k-online",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 200,
            "temperature": 0.2
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            analysis = result['choices'][0]['message']['content']
            logger.info(f"Perplexity response: {analysis}")
            return analysis
        else:
            logger.error(f"Perplexity API error: {response.status_code} - {response.text}")
            return "AI 分析暫時無法使用，請依據技術指標自行判斷。"
            
    except Exception as e:
        logger.error(f"Error calling Perplexity API: {str(e)}")
        return "AI 分析服務連線失敗，請稍後再試。"

def send_telegram_message(message):
    """發送訊息到 Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            logger.info("Message sent successfully!")
        else:
            logger.error(f"Telegram API error: {response.status_code} - {response.text}")
            
    except Exception as e:
        logger.error(f"Error sending Telegram message: {str(e)}")

if __name__ == '__main__':
    # 啟動前檢查環境變數
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set!")
    if not TELEGRAM_CHAT_ID:
        logger.error("TELEGRAM_CHAT_ID not set!")
    if not PERPLEXITY_API_KEY:
        logger.error("PERPLEXITY_API_KEY not set!")
    
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
