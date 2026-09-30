import os, time, math, requests
import pandas as pd
import numpy as np
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
API_KEY = os.getenv("TWELVE_DATA_API_KEY", "")
SYMBOL = os.getenv("SYMBOL", "XAU/USD")
RISK_USD = float(os.getenv("RISK_USD", "5"))
MIN_SCORE = int(os.getenv("MIN_SCORE", "4"))
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "60"))
ATR_SL_MULT = float(os.getenv("ATR_SL_MULT", "1.5"))
RR1 = float(os.getenv("RR1", "1.5"))
RR2 = float(os.getenv("RR2", "2.5"))

# Signal-only: no MT5 order functions are used.

def td_time_series(interval, outputsize=250):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": SYMBOL, "interval": interval, "outputsize": outputsize,
        "apikey": API_KEY, "format": "JSON"
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    if "values" not in data:
        raise RuntimeError(str(data))
    df = pd.DataFrame(data["values"])
    for c in ["open","high","low","close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    return df

def indicators(df):
    d = df.copy()
    d["ema20"] = d.close.ewm(span=20, adjust=False).mean()
    d["ema50"] = d.close.ewm(span=50, adjust=False).mean()
    delta = d.close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    d["rsi"] = 100 - (100/(1+rs))
    tr = pd.concat([
        d.high-d.low,
        (d.high-d.close.shift()).abs(),
        (d.low-d.close.shift()).abs()
    ], axis=1).max(axis=1)
    d["atr"] = tr.rolling(14).mean()
    d["prev_high20"] = d.high.shift(1).rolling(20).max()
    d["prev_low20"] = d.low.shift(1).rolling(20).min()
    return d.dropna().reset_index(drop=True)

def make_signal(df):
    d = indicators(df)
    x, p = d.iloc[-1], d.iloc[-2]
    buy = sell = 0
    buy_reasons, sell_reasons = [], []

    if x.ema20 > x.ema50: buy += 1; buy_reasons.append("EMA20 > EMA50")
    if x.ema20 < x.ema50: sell += 1; sell_reasons.append("EMA20 < EMA50")

    if 50 <= x.rsi <= 70 and x.close > x.ema20:
        buy += 1; buy_reasons.append(f"RSI {x.rsi:.1f} bullish zone")
    if 30 <= x.rsi <= 50 and x.close < x.ema20:
        sell += 1; sell_reasons.append(f"RSI {x.rsi:.1f} bearish zone")

    if x.close > x.prev_high20:
        buy += 2; buy_reasons.append("20-bar breakout")
    if x.close < x.prev_low20:
        sell += 2; sell_reasons.append("20-bar breakdown")

    # simple momentum confirmation
    if x.close > p.close and x.close > x.ema20:
        buy += 1; buy_reasons.append("bullish momentum")
    if x.close < p.close and x.close < x.ema20:
        sell += 1; sell_reasons.append("bearish momentum")

    if max(buy, sell) < MIN_SCORE or buy == sell:
        return None

    side = "BUY" if buy > sell else "SELL"
    entry = float(x.close)
    atr = float(x.atr)
    sl = entry - ATR_SL_MULT*atr if side == "BUY" else entry + ATR_SL_MULT*atr
    risk_distance = abs(entry-sl)
    tp1 = entry + RR1*risk_distance if side == "BUY" else entry - RR1*risk_distance
    tp2 = entry + RR2*risk_distance if side == "BUY" else entry - RR2*risk_distance
    reasons = buy_reasons if side == "BUY" else sell_reasons
    score = max(buy, sell)
    return dict(side=side, entry=entry, sl=sl, tp1=tp1, tp2=tp2,
                score=score, reasons=reasons, atr=atr)

def telegram_send(text):
    if not TOKEN or not CHAT_ID:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": CHAT_ID, "text": text}, timeout=20)
    r.raise_for_status()

def format_signal(sig):
    reasons = "\n".join("• " + x for x in sig["reasons"])
    return (
        "🟡 JEEBOUR GOLD SIGNAL\n\n"
        f"XAUUSD — {sig['side']} {'🟢' if sig['side']=='BUY' else '🔴'}\n\n"
        f"Entry: {sig['entry']:.2f}\n"
        f"SL: {sig['sl']:.2f}\n"
        f"TP1: {sig['tp1']:.2f}\n"
        f"TP2: {sig['tp2']:.2f}\n\n"
        f"Risk budget: ${RISK_USD:.2f}\n"
        f"Setup score: {sig['score']}\n\n"
        f"Reasons:\n{reasons}\n\n"
        "⚠️ Signal only — place the trade manually and verify price/SL before entry."
    )

def get_chat_id():
    # Optional helper: run /chatid in a private chat after the bot is started.
    if not TOKEN:
        return
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    data = requests.get(url, timeout=20).json()
    for u in data.get("result", []):
        msg = u.get("message", {})
        if msg.get("text") == "/chatid":
            cid = msg.get("chat", {}).get("id")
            if cid:
                telegram_send(f"Your Telegram chat ID is: {cid}")

def main():
    telegram_send("🟡 Jeebour Gold Bot v1 is online.\nSignal-only mode: no automatic trades.")
    last_signal_key = None
    while True:
        try:
            df = td_time_series("5min")
            sig = make_signal(df)
            if sig:
                key = f"{sig['side']}-{round(sig['entry'],2)}-{df.iloc[-1]['datetime']}"
                if key != last_signal_key:
                    telegram_send(format_signal(sig))
                    last_signal_key = key
        except Exception as e:
            print("ERROR:", e)
        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    main()
