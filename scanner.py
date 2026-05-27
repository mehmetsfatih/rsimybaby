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
INTERVAL = "15"  # Bybit'te 15 dakika sadece "15" olarak ifade edilir
BASE_URL = "https://api.bybit.com"


def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(
        url,
        json={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"},
        timeout=10,
    )


def get_futures_symbols():
    # Bybit V5 API - Linear (USDT Perps) Sembollerini Çeker
    url = f"{BASE_URL}/v5/market/instruments-info"
    params = {"category": "linear"}
    
    r = requests.get(url, params=params, timeout=15)
    data = r.json()
    
    symbols = []
    if data.get("retCode") == 0:
        for s in data["result"]["list"]:
            # Sadece USDT paritelerini ve aktif olarak trade edilenleri al
            if s.get("quoteCoin") == "USDT" and s.get("status") == "Trading":
                symbols.append(s["symbol"])
    return symbols


def get_klines(symbol, interval=INTERVAL, limit=100):
    # Bybit V5 API - Kline (Mum) Verisi Çeker
    url = f"{BASE_URL}/v5/market/kline"
    params = {
        "category": "linear",
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    
    r = requests.get(url, params=params, timeout=10)
    data = r.json()
    
    # Bybit veriyi sondan başa (en yeni en başta) gönderir. 
    # RSI hesaplaması için eskiden yeniye sıralamamız lazım, bu yüzden ters çeviriyoruz.
    klines = data["result"]["list"]
    klines.reverse()
    
    # Bybit kline yapısı: [startTime, open, high, low, close, volume, turnover]
    # İndeks 4 kapanış fiyatıdır.
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
    # [-2] alıyoruz çünkü [-1] henüz kapanmamış olan şu anki aktif mumdur.
    return float(rsi.iloc[-2])


def main():
    print(f"[{datetime.utcnow():%Y-%m-%d %H:%M:%S} UTC] Bybit Taraması başlıyor")
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
            
            # Bybit API limitlerine takılmamak için kısa bir bekleme (Saniyede max 120 istek sınırı vardır)
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
