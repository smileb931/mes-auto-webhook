# ============================================================
# MES Alert System — app.py
# 整合 V7.1 S1 / S2 + V6.2 三策略
# Flow: TradingView Webhook → Perplexity API → Telegram
# ============================================================

import os, json, math, requests
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# ── 金鑰設定（直接改成你的值，或用環境變數） ─────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID",   "YOUR_CHAT_ID")
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "YOUR_PERPLEXITY_KEY")
# ───────────────────────────────────────────────────────────


# 1. 時段判斷（台灣時間）
def get_time_info(tw_time_str: str):
    """
    回傳 (t_score, session_name, is_forbidden, is_next_b)
    """
    try:
        dt = datetime.fromisoformat(tw_time_str)
    except Exception:
        dt = datetime.now()

    h = dt.hour
    m = dt.minute
    hm = h * 60 + m  # 分鐘數

    # 禁止：04:00–13:30
    if (4 * 60) <= hm < (13 * 60 + 30):
        return 0, "禁止時段 04:00-13:30", True, False
    # 黃金A：13:30–14:30
    if (13 * 60 + 30) <= hm < (14 * 60 + 30):
        return 20, "黃金A 13:30-14:30", False, False
    # 一般：14:30–19:00
    if (14 * 60 + 30) <= hm < (19 * 60):
        return 5, "一般 14:30-19:00", False, False
    # 次佳A：19:00–21:30
    if (19 * 60) <= hm < (21 * 60 + 30):
        return 15, "次佳A 19:00-21:30", False, False
    # 黃金B：21:30–23:30
    if (21 * 60 + 30) <= hm < (23 * 60 + 30):
        return 20, "黃金B 21:30-23:30", False, False
    # 次佳B：23:30–01:30
    if hm >= (23 * 60 + 30) or hm < (1 * 60 + 30):
        return 10, "次佳B 23:30-01:30", True, True   # V7.1 禁 / V6.2 限制
    # 一般：01:30–04:00
    return 5, "一般 01:30-04:00", False, False


# 2. V7.1 S1 SuperTrend 翻轉
def score_s1(d: dict, t_score: int):
    """回傳 (score, direction, detail)"""
    close    = float(d.get("close", 0))
    atr5     = float(d.get("atr5", 10))
    rsi5     = float(d.get("rsi5", 50))
    macd_now = float(d.get("macd_now", 0))
    macd_p1  = float(d.get("macd_p1", 0))
    st5      = int(d.get("st5", 0))      # +1多 / -1空
    st5_p    = int(d.get("st5_p", st5))  # 上一根
    st15     = int(d.get("st15", 0))
    adx5     = float(d.get("adx5", 0))
    vwap     = float(d.get("vwap", close))

    flip_long  = st5 == 1 and st5_p == -1
    flip_short = st5 == -1 and st5_p == 1
    if not flip_long and not flip_short:
        return 0, "無", {"reason": "ST未翻轉"}

    is_long = flip_long

    flip_score = 25
    vwap_score = 15 if (is_long and close > vwap) or (not is_long and close < vwap) else 0
    rsi_score  = 15 if (is_long and 45 <= rsi5 <= 65) or (not is_long and 35 <= rsi5 <= 55) else 0
    if is_long:
        macd_score = 15 if macd_now > 0 and macd_now > macd_p1 else 0
    else:
        macd_score = 15 if macd_now < 0 and macd_now < macd_p1 else 0
    adx_score  = 10 if adx5 > 18 else 0
    st15_score = 10 if st15 == st5 else 0
    atr_ok     = 1 if atr5 < 25 else 0

    total = (flip_score + vwap_score + rsi_score + macd_score + adx_score + st15_score + t_score) * atr_ok
    direction = "多" if is_long else "空"
    detail = {
        "ST翻轉": flip_score,
        "VWAP": vwap_score,
        "RSI": rsi_score,
        "MACD": macd_score,
        "ADX": adx_score,
        "15mST": st15_score,
        "時段": t_score,
    }
    return total, direction, detail


# 3. V7.1 S2 EMA9×21 穿越
def score_s2(d: dict, t_score: int):
    close      = float(d.get("close", 0))
    atr5       = float(d.get("atr5", 10))
    rsi5       = float(d.get("rsi5", 50))
    macd_now   = float(d.get("macd_now", 0))
    st15       = int(d.get("st15", 0))
    adx5       = float(d.get("adx5", 0))
    vwap       = float(d.get("vwap", close))
    ema_cross  = str(d.get("ema_cross", "none")).lower()  # "golden"/"death"/"none"
    false_cross = int(d.get("false_cross", 0))            # 1 = 有假交叉

    if ema_cross not in ("golden", "death"):
        return 0, "無", {"reason": "EMA無穿越"}

    is_long = ema_cross == "golden"

    cross_score = 25
    vwap_score  = 20 if (is_long and close > vwap) or (not is_long and close < vwap) else 0
    rsi_score   = 15 if (is_long and 45 <= rsi5 <= 65) or (not is_long and 35 <= rsi5 <= 55) else 0
    macd_score  = 15 if (is_long and macd_now > 0) or (not is_long and macd_now < 0) else 0
    adx_score   = 10 if adx5 > 18 else 0
    st15_score  = 10 if (is_long and st15 == 1) or (not is_long and st15 == -1) else 0
    no_false    = 1 if false_cross == 0 else 0
    atr_ok      = 1 if atr5 < 25 else 0

    total = (cross_score + vwap_score + rsi_score + macd_score + adx_score + st15_score + t_score) * no_false * atr_ok
    direction = "多" if is_long else "空"
    detail = {
        "EMA叉": cross_score,
        "VWAP": vwap_score,
        "RSI": rsi_score,
        "MACD": macd_score,
        "ADX": adx_score,
        "15mST": st15_score,
        "時段": t_score,
    }
    return total, direction, detail


# 4. V6.2 評分
def score_v62(d: dict, t_score: int, is_next_b: bool):
    close    = float(d.get("close", 0))
    atr5     = float(d.get("atr5", 10))
    rsi5     = float(d.get("rsi5", 50))
    macd_now = float(d.get("macd_now", 0))
    macd_p1  = float(d.get("macd_p1", 0))
    macd_p2  = float(d.get("macd_p2", 0))
    st5      = int(d.get("st5", 0))
    st15     = int(d.get("st15", 0))
    adx5     = float(d.get("adx5", 0))
    dmp5     = float(d.get("dmp5", 0))
    dmn5     = float(d.get("dmn5", 0))
    vwap     = float(d.get("vwap", close))
    ema_cross = str(d.get("ema_cross", "none")).lower()

    # 強制觀望 A: MACD 連縮 >=3 根
    bear_shrink = (
        macd_now < 0 and macd_p1 < 0 and macd_p2 < 0
        and abs(macd_now) < abs(macd_p1) < abs(macd_p2)
    )
    bull_shrink = (
        macd_now > 0 and macd_p1 > 0 and macd_p2 > 0
        and abs(macd_now) < abs(macd_p1) < abs(macd_p2)
    )
    if bear_shrink or bull_shrink:
        return 0, "無", {"force_watch": "A-MACD連縮≥3根"}

    # B: 5m/15m ST 背離
    if st5 != st15:
        return 0, "無", {"force_watch": "B-5m15m背離"}

    # C: ATR < 6
    if atr5 < 6:
        return 0, "無", {"force_watch": "C-ATR死水<6"}

    def long_score():
        rsi  = 15 if 45 <= rsi5 <= 65 else 0
        macd = 20 if macd_now > 0 and macd_now > macd_p1 else (5 if macd_now > 0 else 0)
        cross = 10 if ema_cross == "golden" and not bull_shrink else 0
        adx   = 10 if adx5 > 25 and dmp5 > dmn5 else (5 if adx5 > 18 and dmp5 > dmn5 else 0)
        st    = 10 if st15 == 1 else 0
        return rsi + macd + cross + adx + st + t_score

    def short_score():
        rsi  = 15 if 35 <= rsi5 <= 55 else 0
        macd = 20 if macd_now < 0 and macd_now < macd_p1 else (5 if macd_now < 0 else 0)
        cross = 10 if ema_cross == "death" and not bear_shrink else 0
        adx   = 10 if adx5 > 25 and dmn5 > dmp5 else (5 if adx5 > 18 and dmn5 > dmp5 else 0)
        st    = 10 if st15 == -1 else 0
        return rsi + macd + cross + adx + st + t_score

    ls = long_score()
    ss = short_score()
    score = max(ls, ss)
    direction = "多" if ls >= ss else "空"

    threshold = 70 if is_next_b else 60
    if score < threshold or score >= 80:
        return 0, "無", {"v62_score": score, "threshold": threshold, "reason": "未達門檻或過熱"}

    return score, direction, {"long_score": ls, "short_score": ss}


# 5. Perplexity 二次確認（可關掉：直接回傳 local_result）
def call_perplexity_confirm(d: dict, local_result: dict) -> dict:
    prompt = f"""你是 MES 期貨交易 AI。以下是本地策略評分結果，請確認方向正確性並給出最終 score（0-100），只輸出 JSON。

本地評分：
觸發策略: {local_result.get('strategy')}
方向: {local_result.get('direction')}
本地分數: {local_result.get('score')}
收盤價: {d.get('close')}
ATR5: {d.get('atr5')}
RSI5: {d.get('rsi5')}
MACD當根: {d.get('macd_now')}，前根: {d.get('macd_p1')}
ST5: {d.get('st5')}，ST15: {d.get('st15')}
ADX: {d.get('adx5')}，DMP: {d.get('dmp5')}，DMN: {d.get('dmn5')}
VWAP: {d.get('vwap')}，收盤: {d.get('close')}

輸出格式（只輸出 JSON，無其他文字）：
{{"direction":"多或空","score":整數,"confirmed":true或false}}"""

    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "sonar-pro",
        "messages": [
            {"role": "system", "content": "只輸出 JSON，不輸出任何其他內容。"},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 120,
        "temperature": 0.0,
    }
    try:
        resp = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=body,
            timeout=15,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        confirmed = json.loads(content)
        final_score = max(int(local_result.get("score", 0)), int(confirmed.get("score", 0)))
        local_result["score"] = final_score
        local_result["perplexity_confirmed"] = confirmed.get("confirmed", False)
        # 如果想讓 Perplexity 改變方向，可以取消下一行註解
        # local_result["direction"] = confirmed.get("direction", local_result["direction"])
        return local_result
    except Exception:
        local_result["perplexity_confirmed"] = False
        return local_result


# 6. 計算 SL / TP（整合 V7.1 + V6.2）
def calc_sl_tp(close: float, atr5: float, direction: str, score: int, adx5: float):
    sl_mult = 0.8 if adx5 > 25 else 0.6
    tp_mult = 1.5 if score >= 70 else 1.2
    if direction == "多":
        sl = round(close - sl_mult * atr5, 2)
        tp = round(close + tp_mult * atr5, 2)
    else:
        sl = round(close + sl_mult * atr5, 2)
        tp = round(close - tp_mult * atr5, 2)
    return sl, tp


# 7. Telegram 純文字格式
def format_msg(tw_time_str: str, direction: str, close: float,
               sl: float, tp: float, score: int, strategy: str) -> str:
    try:
        dt = datetime.fromisoformat(tw_time_str)
        t  = f"{dt.year}/{dt.month}/{dt.day} {dt.hour:02d}:{dt.minute:02d}"
    except Exception:
        t = tw_time_str

    return (
        f"時間 {t}\n"
        f"進倉 {direction}\n"
        f"進倉點 {close}\n"
        f"停損 {sl}\n"
        f"停利 {tp}\n"
        f"成功率分數 {score}% {strategy}"
    )


def send_telegram(msg: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID,
                                 "text": msg, "parse_mode": ""}, timeout=10)
    return r.ok


# 8. Webhook 入口
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        d = request.get_json(force=True) or {}
        if not d:
            return jsonify({"status": "error", "msg": "empty"}), 400

        tw_time = d.get("tw_time", datetime.now().strftime("%Y-%m-%dT%H:%M"))
        t_score, session, is_forbidden, is_next_b = get_time_info(tw_time)

        # 禁止時段（04:00–13:30 絕對禁止）
        if is_forbidden and not is_next_b:
            return jsonify({"status": "skipped", "reason": f"禁止時段 {session}"}), 200

        close = float(d.get("close", 0))
        atr5  = float(d.get("atr5", 10))
        adx5  = float(d.get("adx5", 0))

        # 三策略評分
        s1_score, s1_dir, _ = score_s1(d, t_score)
        s2_score, s2_dir, _ = score_s2(d, t_score)
        v62_score, v62_dir, _ = score_v62(d, t_score, is_next_b)

        min_score = 70 if is_next_b else 55  # 次佳B門檻70，其餘55

        best_score = 0
        best_dir   = "無"
        best_strat = "無"

        if s1_score >= min_score and s1_score > best_score:
            best_score, best_dir, best_strat = s1_score, s1_dir, "S1"
        if s2_score >= min_score and s2_score > best_score:
            best_score, best_dir, best_strat = s2_score, s2_dir, "S2"
        if v62_score >= min_score and v62_score > best_score:
            best_score, best_dir, best_strat = v62_score, v62_dir, "V62"

        if best_strat == "無" or best_dir == "無":
            return jsonify({
                "status": "skipped",
                "reason": f"三策略均未達門檻 ({min_score}分)",
                "s1": s1_score, "s2": s2_score, "v62": v62_score,
            }), 200

        local_result = {"strategy": best_strat, "direction": best_dir, "score": best_score}
        final_result = call_perplexity_confirm(d, local_result)

        final_score = int(final_result.get("score", best_score))
        final_dir   = final_result.get("direction", best_dir)

        sl, tp = calc_sl_tp(close, atr5, final_dir, final_score, adx5)
        msg = format_msg(tw_time, final_dir, close, sl, tp, final_score, best_strat)
        ok  = send_telegram(msg)

        return jsonify({
            "status": "sent" if ok else "telegram_failed",
            "message": msg,
            "strategy": best_strat,
            "score": final_score,
            "s1": s1_score, "s2": s2_score, "v62": v62_score,
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
