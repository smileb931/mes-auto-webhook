from flask import Flask, request, jsonify
import requests
import os
from datetime import datetime

app = Flask(__name__)

# ═══════════════════════════════════════════════════════════
# 環境變數配置（在 Render.com 設定）
# ═══════════════════════════════════════════════════════════
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
PERPLEXITY_API_KEY = os.environ.get('PERPLEXITY_API_KEY')

# ═══════════════════════════════════════════════════════════
# 健康檢查端點（Render.com 用來確認服務運行）
# ═══════════════════════════════════════════════════════════
@app.route('/')
def home():
    return jsonify({
        'status': 'online',
        'service': 'MES Trading Bot',
        'version': 'v5.0',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

# ═══════════════════════════════════════════════════════════
# TradingView Webhook 接收端點
# ═══════════════════════════════════════════════════════════
@app.route('/tradingview-webhook', methods=['POST'])
def tradingview_webhook():
    try:
        # 1. 接收 TradingView 數據
        data = request.json
        
        # 提取訊號數據
        signal = data.get('signal', '')
        price = data.get('price', 0)
        direction = data.get('direction', '')
        score = data.get('score', 0)
        position = data.get('position', 0)
        winrate = data.get('winrate', 0)
        risk = data.get('risk', 0)
        advice = data.get('advice', '')
        timestamp = data.get('time', '')
        
        print(f"[INFO] 收到訊號: {signal} | 價格: {price} | 方向: {direction}")
        
        # 2. 調用 Perplexity API 進行深度分析
        perplexity_analysis = analyze_with_perplexity(
            signal, price, direction, score, winrate
        )
        
        # 3. 組合完整訊息（極簡版 A 格式）
        message = f"""⚡ MES 閃電訊號 {signal}
價格：{price:,.2f}
時間：{timestamp.split()[-1] if timestamp else 'N/A'}

{advice}
方向：{direction}
倉位：{position}（{'滿倉' if position == 1.0 else '半倉' if position == 0.5 else '觀察'})
勝率：{winrate}%
風險：{risk}/100

━━━━━━━━━━
AI 深度分析：
{perplexity_analysis}"""
        
        # 4. 發送到 Telegram
        send_to_telegram(message)
        
        print(f"[SUCCESS] 訊號已發送到 Telegram")
        
        return jsonify({
            'status': 'success',
            'message': 'Alert processed and sent to Telegram'
        }), 200
        
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# ═══════════════════════════════════════════════════════════
# Perplexity API 分析函數
# ═══════════════════════════════════════════════════════════
def analyze_with_perplexity(signal, price, direction, score, winrate):
    """調用 Perplexity API 進行市場分析"""
    try:
        url = "https://api.perplexity.ai/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # 構建分析提示詞
        prompt = f"""作為專業的期貨交易分析師，請分析以下 MES 期貨訊號：

訊號等級：{signal}
當前價格：{price}
交易方向：{direction}
綜合評分：{score}/100
預期勝率：{winrate}%

請提供：
1. 技術面分析（簡短）
2. 風險評估（簡短）
3. 進場建議（明確）

請用繁體中文回答，限制在 150 字內。"""
        
        payload = {
            "model": "llama-3.1-sonar-small-128k-online",
            "messages": [
                {
                    "role": "system",
                    "content": "你是一位專業的期貨交易分析師，擅長技術分析和風險管理。回答簡潔明確。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 300,
            "temperature": 0.2,
            "top_p": 0.9
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        analysis = result['choices'][0]['message']['content']
        
        return analysis.strip()
        
    except requests.exceptions.Timeout:
        return "⚠️ API 請求超時，請稍後再試"
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Perplexity API 錯誤: {str(e)}")
        return "⚠️ AI 分析暫時無法使用"
    except Exception as e:
        print(f"[ERROR] 未知錯誤: {str(e)}")
        return "⚠️ 分析過程發生錯誤"

# ═══════════════════════════════════════════════════════════
# Telegram 發送函數
# ═══════════════════════════════════════════════════════════
def send_to_telegram(message):
    """發送訊息到 Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Telegram 發送失敗: {str(e)}")
        return False

# ═══════════════════════════════════════════════════════════
# 測試端點（可選）
# ═══════════════════════════════════════════════════════════
@app.route('/test', methods=['POST'])
def test():
    """測試 Webhook 和 API 是否正常"""
    test_data = {
        "signal": "#S級",
        "price": 6467.00,
        "direction": "多",
        "score": 87,
        "position": 1.0,
        "winrate": 75,
        "risk": 25,
        "advice": "✅ 強烈建議進場",
        "time": "2026-03-27 23:31:00"
    }
    
    return tradingview_webhook()

# ═══════════════════════════════════════════════════════════
# 啟動服務器
# ═══════════════════════════════════════════════════════════
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
