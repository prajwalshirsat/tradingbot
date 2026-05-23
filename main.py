import os
import time
import requests
from datetime import datetime, timezone, timedelta

# =========================
# SETTINGS
# =========================

SYMBOL = "BTCUSDT"          # Change this if needed, example: "ETHUSDT"
POINT_RANGE = 300           # 300 points upper/lower range
CHECK_INTERVAL = 60         # Check price every 60 seconds

IST = timezone(timedelta(hours=5, minutes=30))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


# =========================
# TELEGRAM MESSAGE FUNCTION
# =========================

def send_telegram_message(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram token or chat id missing.")
        return

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
# BINANCE DATA FUNCTIONS
# =========================

def get_1h_candles():
    url = "https://api.binance.com/api/v3/klines"

    params = {
        "symbol": SYMBOL,
        "interval": "1h",
        "limit": 50
    }

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def get_current_price():
    url = "https://api.binance.com/api/v3/ticker/price"

    params = {
        "symbol": SYMBOL
    }

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()

    return float(response.json()["price"])


# =========================
# CANDLE LOGIC
# =========================

def find_530_to_630_candle():
    candles = get_1h_candles()

    for candle in candles:
        open_time_utc = datetime.fromtimestamp(candle[0] / 1000, tz=timezone.utc)
        open_time_ist = open_time_utc.astimezone(IST)

        # Binance 1h candles open at fixed UTC times.
        # This checks for the candle starting at 5:30 PM IST.
        if open_time_ist.hour == 17 and open_time_ist.minute == 30:
            return {
                "open": float(candle[1]),
                "high": float(candle[2]),
                "low": float(candle[3]),
                "close": float(candle[4]),
                "open_time": open_time_ist
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

    # If candle body is less than 55% of total candle range, treat as neutral
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
        f"✅ Trading bot started for {SYMBOL}.\n"
        f"Waiting for 5:30 PM to 6:30 PM candle analysis."
    )

    signal_checked = False
    alert_sent = False

    candle_type = None
    buy_level = None
    sell_level = None

    while True:
        now = datetime.now(IST)

        # Analyze only after 6:30 PM IST
        if now.hour == 18 and now.minute >= 30 and not signal_checked:
            try:
                candle = find_530_to_630_candle()

                if candle is None:
                    send_telegram_message("⚠️ 5:30 PM to 6:30 PM candle not found.")
                    signal_checked = True
                    time.sleep(CHECK_INTERVAL)
                    continue

                candle_type = classify_candle(candle)

                if candle_type == "strong_bullish":
                    buy_level = candle["high"] + POINT_RANGE

                    send_telegram_message(
                        f"🟢 Strong Bullish Candle Detected\n\n"
                        f"Symbol: {SYMBOL}\n"
                        f"Sentiment: BUYING SIDE\n"
                        f"Open: {candle['open']}\n"
                        f"High: {candle['high']}\n"
                        f"Low: {candle['low']}\n"
                        f"Close: {candle['close']}\n\n"
                        f"Buy Alert Level: {buy_level}"
                    )

                elif candle_type == "strong_bearish":
                    sell_level = candle["low"] - POINT_RANGE

                    send_telegram_message(
                        f"🔴 Strong Bearish Candle Detected\n\n"
                        f"Symbol: {SYMBOL}\n"
                        f"Sentiment: SELLING SIDE\n"
                        f"Open: {candle['open']}\n"
                        f"High: {candle['high']}\n"
                        f"Low: {candle['low']}\n"
                        f"Close: {candle['close']}\n\n"
                        f"Sell Alert Level: {sell_level}"
                    )

                else:
                    send_telegram_message(
                        f"⚪ Neutral Candle Detected\n\n"
                        f"Symbol: {SYMBOL}\n"
                        f"Message: Avoid trading today."
                    )
                    alert_sent = True

                signal_checked = True

            except Exception as e:
                send_telegram_message(f"❌ Error while analyzing candle: {e}")

        # After signal is generated, keep checking breakout/breakdown level
        if signal_checked and not alert_sent:
            try:
                current_price = get_current_price()

                if candle_type == "strong_bullish" and buy_level is not None:
                    if current_price >= buy_level:
                        send_telegram_message(
                            f"🚀 BUY LEVEL CROSSED\n\n"
                            f"Symbol: {SYMBOL}\n"
                            f"Buy Level: {buy_level}\n"
                            f"Current Price: {current_price}"
                        )
                        alert_sent = True

                elif candle_type == "strong_bearish" and sell_level is not None:
                    if current_price <= sell_level:
                        send_telegram_message(
                            f"📉 SELL LEVEL CROSSED\n\n"
                            f"Symbol: {SYMBOL}\n"
                            f"Sell Level: {sell_level}\n"
                            f"Current Price: {current_price}"
                        )
                        alert_sent = True

            except Exception as e:
                print(f"Price check error: {e}")

        # Reset for next day after midnight
        if now.hour == 0 and now.minute == 0:
            signal_checked = False
            alert_sent = False
            candle_type = None
            buy_level = None
            sell_level = None

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
