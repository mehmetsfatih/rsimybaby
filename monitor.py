"""15m USDT perpetual RSI(14) alerts; Python standard library only."""
import copy
import json
import math
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError

INTERVAL = 900_000
PERIOD = 14
STATE = Path('data/state.json')
BASE = 'https://fapi.binance.com'


def binance(path, **params):
    for attempt in range(3):
        time.sleep(0.18)
        try:
            with urlopen(BASE + path + '?' + urlencode(params), timeout=20) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code in (403, 418, 429, 451):
                raise RuntimeError(f'Binance HTTP {exc.code}: access/rate restriction; run stopped.') from None
            if exc.code < 500:
                raise RuntimeError(f'Binance HTTP {exc.code}') from None
        except (URLError, TimeoutError):
            pass
        time.sleep(2 ** attempt)
    raise RuntimeError('Binance request failed after retries')


def rsi(gain, loss):
    if gain == loss == 0:
        return 50.0  # No directional movement: no signal.
    if loss == 0:
        return 100.0
    return 100 - 100 / (1 + gain / loss)


def qualifies(value):
    return value > 90 or value < 15


def advance(previous, candles, cutoff):
    """Return new Wilder state and signals. Never mutate the input state."""
    closed = [c for c in candles if int(c[6]) < cutoff]
    closed.sort(key=lambda c: int(c[0]))
    for index, candle in enumerate(closed):
        if not math.isfinite(float(candle[4])) or float(candle[4]) <= 0:
            raise RuntimeError('Invalid closing price')
        if index and int(candle[0]) != int(closed[index - 1][0]) + INTERVAL:
            raise RuntimeError('Missing/non-contiguous candles')
    current = copy.deepcopy(previous)
    signals = []
    if current is None:
        if len(closed) < PERIOD + 1:
            return None, []
        prices = [float(c[4]) for c in closed[:PERIOD + 1]]
        changes = [b - a for a, b in zip(prices, prices[1:])]
        current = dict(last_open=int(closed[PERIOD][0]), close=prices[-1],
                       gain=sum(max(d, 0) for d in changes) / PERIOD,
                       loss=sum(max(-d, 0) for d in changes) / PERIOD)
        remaining = closed[PERIOD + 1:]
    else:
        remaining = [c for c in closed if int(c[0]) > current['last_open']]
    for candle in remaining:
        opening = int(candle[0])
        if opening != current['last_open'] + INTERVAL:
            raise RuntimeError('Missing/non-contiguous candles; progress not advanced')
        price = float(candle[4])
        if not math.isfinite(price) or price <= 0:
            raise RuntimeError('Invalid closing price')
        change = price - current['close']
        current.update(last_open=opening, close=price,
                       gain=(current['gain'] * 13 + max(change, 0)) / 14,
                       loss=(current['loss'] * 13 + max(-change, 0)) / 14)
        value = rsi(current['gain'], current['loss'])
        if qualifies(value):
            signals.append(dict(open=opening, close=price, rsi=value))
    if previous is None:
        # Historical data warms the indicator; only latest close alerts at enrollment.
        value = rsi(current['gain'], current['loss'])
        signals = [dict(open=current['last_open'], close=current['close'], rsi=value)] if qualifies(value) else []
    return current, signals


def save(state):
    STATE.parent.mkdir(exist_ok=True, parents=True)
    temporary = STATE.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    temporary.replace(STATE)


def collect(symbol, previous, cutoff):
    params = dict(symbol=symbol, interval='15m', limit=499, endTime=cutoff - 1)
    current = previous
    signals = []
    while True:
        if current is not None:
            params['startTime'] = current['last_open'] + INTERVAL
            if params['startTime'] >= cutoff:
                break
        candles = binance('/fapi/v1/klines', **params)
        if not isinstance(candles, list) or not candles:
            raise RuntimeError(f'{symbol}: missing candle response')
        updated, new = advance(current, candles, cutoff)
        if updated is None:
            return None, []
        if current is not None and updated['last_open'] == current['last_open']:
            raise RuntimeError(f'{symbol}: no progress')
        current = updated
        signals.extend(new)
        if previous is None or len(candles) < 499:
            break
    if current is not None and current['last_open'] != cutoff - INTERVAL:
        raise RuntimeError(f'{symbol}: latest closed candle unavailable; retry next run')
    return current, signals


def message(event):
    closing = datetime.fromtimestamp((event['open'] + INTERVAL) / 1000, timezone(timedelta(hours=3)))
    return (f"{'🔴' if event['rsi'] > 90 else '🟢'} {event['symbol']} | 15 dakika\n"
            f"RSI(14): {event['rsi']:.6f}\n"
            f"Kapanış fiyatı: {event['close']:.12g}\n"
            f"Mum kapanışı: {closing:%d.%m.%Y %H:%M} (Türkiye)\n"
            f"Koşul: {'RSI > 90' if event['rsi'] > 90 else 'RSI < 15'}\n"
            f"Sinyal: {event['symbol']}:{event['open']}")


def send(token, chat, text):
    payload = json.dumps(dict(chat_id=chat, text=text)).encode()
    req = Request(f'https://api.telegram.org/bot{token}/sendMessage', data=payload,
                  headers={'Content-Type': 'application/json'})
    try:
        with urlopen(req, timeout=20) as response:
            result = json.load(response)
        if not result.get('ok'):
            raise RuntimeError('Telegram rejected message; pending queue preserved')
    except (HTTPError, URLError, TimeoutError):
        # Do not print the exception: request URL contains the secret token.
        raise RuntimeError('Telegram delivery failed/uncertain; pending queue preserved') from None


def main():
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat = os.environ.get('TELEGRAM_CHAT_ID', '')
    if not token or not chat:
        raise RuntimeError('Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in GitHub Secrets')
    state = json.loads(STATE.read_text()) if STATE.exists() else dict(version=1, symbols={}, pending=[], initialized=False)
    if state.get('version') != 1:
        raise RuntimeError('Unsupported state format')
    # Deliver previous failed notifications before scanning more history.
    def flush():
        while state['pending']:
            batch = state['pending'][:8]
            send(token, chat, '\n\n'.join(message(event) for event in batch))
            del state['pending'][:len(batch)]
            save(state)
            time.sleep(3.1)  # Also respects a single group's 20 messages/minute limit.
    flush()
    now = binance('/fapi/v1/time')['serverTime']
    cutoff = now // INTERVAL * INTERVAL
    info = binance('/fapi/v1/exchangeInfo')
    symbols = sorted(s['symbol'] for s in info['symbols']
                     if s['status'] == 'TRADING' and s['quoteAsset'] == 'USDT'
                     and s['contractType'] == 'PERPETUAL'
                     and s.get('underlyingType', 'COIN') == 'COIN')
    if not symbols:
        raise RuntimeError('No eligible symbols returned')
    count = 0
    errors = []
    for symbol in symbols:
        previous = state['symbols'].get(symbol)
        try:
            current, events = collect(symbol, previous, cutoff)
        except RuntimeError as exc:
            if str(exc).startswith('Binance'):
                raise
            errors.append(f'{symbol}: {exc}')
            continue
        if current is None:
            continue
        state['symbols'][symbol] = current
        state['pending'].extend(dict(symbol=symbol, **e) for e in events)
        count += len(events)
        save(state)
    print(f'Scanned {len(symbols)} pairs; {count} qualifying closes; {len(state["pending"])} pending.')
    flush()
    if errors:
        raise RuntimeError('; '.join(errors))
    if not state['initialized']:
        send(token, chat, f'✅ RSI tarayıcı kuruldu. {len(symbols)} USDT sürekli vadeli çift; 15m RSI(14), >90 veya <15. Her uygun kapanış bildirilir.')
        state['initialized'] = True
        save(state)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'ERROR: {type(exc).__name__}: {exc}', file=sys.stderr)
        sys.exit(1)
