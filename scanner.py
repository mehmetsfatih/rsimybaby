"""
Bybit Futures 15m RSI Tarayıcı (GitHub Actions versiyonu)
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
INTERVAL = "15"  # Bybit'te 15 dakika
BASE_URL = "https://api.bybit.com"

# Cloudflare ve bot engellemelerini aşmak için Tarayıcı Kimliği
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}


def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(
        url,
        json={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"},
        timeout=10,
    )


def get_futures_symbols():
    url = f"{BASE_URL}/v5/market/instruments-info"
    params = {"category": "linear"}
    
    # headers=HEADERS eklendi
    r = requests.get(url, params=params, headers=HEADERS, timeout=15)
    
    try:
        data = r.json()
    except requests.exceptions.JSONDecodeError:
        print(f"Sembolleri çekerken engelleme: HTTP {r.status_code} - {r.text[:100]}")
        return []
        
    symbols = []
    if data.get("retCode") == 0:
        for s in data["result"]["list"]:
            if s.get("quoteCoin") == "USDT" and s.get("status") == "Trading":
                symbols.append(s["symbol"])
    return symbols


def get_klines(symbol, interval=INTERVAL, limit=100):
    url = f"{BASE_URL}/v5/market/kline"
    params = {
        "category": "linear",
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    
    # headers=HEADERS eklendi
    r = requests.get(url, params=params, headers=HEADERS, timeout=10)
    
    try:
        data = r.json()
    except requests.exceptions.JSONDecodeError:
        print(f"{symbol} mum verisi çekerken engelleme: HTTP {r.status_code}")
        return []
        
    if data.get("retCode") != 0 or not data.get("result", {}).get("list"):
        return []
        
    klines = data["result"]["list"]
    klines.reverse()
    
    return [float(k[4]) for k in klines]


def calculate_rsi(closes, period=RSI_PERIOD):
    s = pd.Series(closes)
    delta = s.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-2])


def main():
    print(f"[{datetime.utcnow():%Y-%m-%d %H:%M:%S} UTC] Bybit Taraması başlıyor")
    symbols = get_futures_symbols()
    
    if not symbols:
        print("Sembol listesi boş, tarama iptal ediliyor.")
        return
        
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
            lines.append(f"• <code>{sym}</code> — RSI: {rsi:.2f} — Fiyat: {price}")
            
    if overbought:
        if lines:
            lines.append("")
        lines.append("🔴 <b>AŞIRI ALIM (RSI &gt; 80)</b>")
        for sym, rsi, price in sorted(overbought, key=lambda x: -x[1]):
            lines.append(f"• <code>{sym}</code> — RSI: {rsi:.2f} — Fiyat: {price}")

    if lines:
        header = f"<b>📊 Bybit 15m RSI Sinyali</b>\n{datetime.utcnow():%H:%M} UTC\n\n"
        send_telegram(header + "\n".join(lines))
        print(f"Telegram'a {len(oversold) + len(overbought)} sinyal gönderildi")
    else:
        print("Sinyal yok")


if __name__ == "__main__":
    main()
