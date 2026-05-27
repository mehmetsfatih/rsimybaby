"""
Binance Futures 15m RSI Tarayıcı (GitHub Actions versiyonu)
Tek sefer çalışır, sinyal varsa Telegram'a yollar, çıkar.
"""

import os
import time
import requests
import pandas as pd
from datetime import datetime

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

RSI_PERIOD = 14
RSI_LOWER = 20
RSI_UPPER = 80
INTERVAL = "15m"
BASE_URL = "https://fapi.binance.com"


def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(
        url,
        json={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"},
        timeout=10,
    )


def get_futures_symbols():
    r = requests.get(f"{BASE_URL}/fapi/v1/exchangeInfo", timeout=15)
    return [
        s["symbol"] for s in r.json()["symbols"]
        if s.get("contractType") == "PERPETUAL"
        and s.get("quoteAsset") == "USDT"
        and s.get("status") == "TRADING"
    ]


def get_klines(symbol, interval=INTERVAL, limit=100):
    r = requests.get(
        f"{BASE_URL}/fapi/v1/klines",
        params={"symbol": symbol, "interval": interval, "limit": limit},
        timeout=10,
    )
    return [float(k[4]) for k in r.json()]


def calculate_rsi(closes, period=RSI_PERIOD):
    s = pd.Series(closes)
    delta = s.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-2])  # son KAPANMIŞ mum


def main():
    print(f"[{datetime.utcnow():%Y-%m-%d %H:%M:%S} UTC] Tarama başlıyor")
    symbols = get_futures_symbols()
    print(f"{len(symbols)} sembol taranacak")

    oversold, overbought = [], []
    for sym in symbols:
        try:
            closes = get_klines(sym)
            if len(closes) < RSI_PERIOD + 2:
                continue
            rsi = calculate_rsi(closes)
            price = closes[-1]
            if rsi < RSI_LOWER:
                oversold.append((sym, rsi, price))
                print(f"🟢 {sym}  RSI={rsi:.2f}")
            elif rsi > RSI_UPPER:
                overbought.append((sym, rsi, price))
                print(f"🔴 {sym}  RSI={rsi:.2f}")
            time.sleep(0.05)
        except Exception as e:
            print(f"[hata] {sym}: {e}")

    lines = []
    if oversold:
        lines.append("🟢 <b>AŞIRI SATIM (RSI &lt; 20)</b>")
        for sym, rsi, price in sorted(oversold, key=lambda x: x[1]):
            lines.append(f"• <code>{sym}</code> — RSI: {rsi:.2f} — {price}")
    if overbought:
        if lines:
            lines.append("")
        lines.append("🔴 <b>AŞIRI ALIM (RSI &gt; 80)</b>")
        for sym, rsi, price in sorted(overbought, key=lambda x: -x[1]):
            lines.append(f"• <code>{sym}</code> — RSI: {rsi:.2f} — {price}")

    if lines:
        header = f"<b>📊 15m RSI Sinyali</b>\n{datetime.utcnow():%H:%M} UTC\n\n"
        send_telegram(header + "\n".join(lines))
        print(f"Telegram'a {len(oversold) + len(overbought)} sinyal gönderildi")
    else:
        print("Sinyal yok")


if __name__ == "__main__":
    main()
