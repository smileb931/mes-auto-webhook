@app.route("/test-ai", methods=["GET"])
def test_ai():
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
    })
