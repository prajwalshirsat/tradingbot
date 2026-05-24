import time
import requests
from datetime import datetime, timezone, timedelta

# =========================
# SETTINGS
# =========================

SYMBOL = "BTCUSDT"
POINT_RANGE = 300
CHECK_INTERVAL = 60

IST = timezone(timedelta(hours=5, minutes=30))

# =========================
# TELEGRAM DETAILS
# =========================

TELEGRAM_BOT_TOKEN = "8876089532:AAHayR7kZ0SHcRNwBcqOCCVIObzzLkgNA7c"
TELEGRAM_CHAT_ID = "1269772473"

# =========================
# TELEGRAM FUNCTION
# =========================

def send_telegram_message(message):

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print("Telegram message sent.")

    except Exception as e:
        print(f"Telegram error: {e}")

# =========================
# BINANCE FUNCTIONS
# =========================

def get_1h_candles():

    url = "https://api.binance.com/api/v3/klines"

    params = {
        "symbol": SYMBOL,
        "interval": "1h",
        "limit": 50
    }

    response = requests.get(url, params=params)
    response.raise_for_status()

    return response.json()

def get_current_price():

    url = "https://api.binance.com/api/v3/ticker/price"

    params = {
        "symbol": SYMBOL
    }

    response = requests.get(url, params=params)
    response.raise_for_status()

    return float(response.json()["price"])

# =========================
# CANDLE LOGIC
# =========================

def find_530_candle():

    candles = get_1h_candles()

    for candle in candles:

        open_time_utc = datetime.fromtimestamp(
            candle[0] / 1000,
            tz=timezone.utc
        )

        open_time_ist = open_time_utc.astimezone(IST)

        if open_time_ist.hour == 17 and open_time_ist.minute == 30:

            return {
                "open": float(candle[1]),
                "high": float(candle[2]),
                "low": float(candle[3]),
                "close": float(candle[4])
            }

    return None

def classify_candle(candle):

    open_price = candle["open"]
    close_price = candle["close"]

    high_price = candle["high"]
    low_price = candle["low"]

    candle_range = high_price - low_price

    body_size = abs(close_price - open_price)

    if candle_range <= 0:
        return "neutral"

    body_ratio = body_size / candle_range

    if body_ratio < 0.55:
        return "neutral"

    if close_price > open_price:
        return "strong_bullish"

    if close_price < open_price:
        return "strong_bearish"

    return "neutral"

# =========================
# MAIN BOT
# =========================

def main():

    send_telegram_message(
        f"✅ BTC One Hour Bot Started"
    )

    signal_checked = False
    alert_sent = False

    candle_type = None
    buy_level = None
    sell_level = None

    current_day = datetime.now(IST).date()

    while True:

        now = datetime.now(IST)

        # Reset daily
        if now.date() != current_day:

            current_day = now.date()

            signal_checked = False
            alert_sent = False

            candle_type = None
            buy_level = None
            sell_level = None

        # Check candle after 6:30 PM
        if now.hour == 18 and now.minute >= 30 and not signal_checked:

            try:

                candle = find_530_candle()

                if candle is None:

                    send_telegram_message(
                        "⚠️ Candle not found"
                    )

                    signal_checked = True
                    continue

                candle_type = classify_candle(candle)

                # BULLISH
                if candle_type == "strong_bullish":

                    buy_level = candle["high"] + POINT_RANGE

                    send_telegram_message(

                        f"🟢 Strong Bullish Candle\n\n"
                        f"High = {candle['high']}\n"
                        f"Buy Level = {buy_level}\n\n"
                        f"Sentiment = BUY"

                    )

                # BEARISH
                elif candle_type == "strong_bearish":

                    sell_level = candle["low"] - POINT_RANGE

                    send_telegram_message(

                        f"🔴 Strong Bearish Candle\n\n"
                        f"Low = {candle['low']}\n"
                        f"Sell Level = {sell_level}\n\n"
                        f"Sentiment = SELL"

                    )

                # NEUTRAL
                else:

                    send_telegram_message(

                        "⚪ Neutral Candle\n\n"
                        "Avoid Trading Today"

                    )

                    alert_sent = True

                signal_checked = True

            except Exception as e:

                send_telegram_message(
                    f"❌ Error = {e}"
                )

        # Monitor breakout
        if signal_checked and not alert_sent:

            try:

                current_price = get_current_price()

                # BUY BREAKOUT
                if candle_type == "strong_bullish":

                    if current_price >= buy_level:

                        send_telegram_message(

                            f"🚀 BUY BREAKOUT\n\n"
                            f"BTC crossed {buy_level}\n"
                            f"Current Price = {current_price}"

                        )

                        alert_sent = True

                # SELL BREAKDOWN
                elif candle_type == "strong_bearish":

                    if current_price <= sell_level:

                        send_telegram_message(

                            f"📉 SELL BREAKDOWN\n\n"
                            f"BTC crossed {sell_level}\n"
                            f"Current Price = {current_price}"

                        )

                        alert_sent = True

            except Exception as e:

                print(e)

        time.sleep(CHECK_INTERVAL)

# =========================
# RUN BOT
# =========================

if __name__ == "__main__":
    main()
