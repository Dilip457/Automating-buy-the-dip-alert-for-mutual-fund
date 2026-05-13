"""
Daily Market Dip Monitor
Tracks Nifty 50, Nifty Midcap 150, Nifty Smallcap 250
Compares current level vs 52-week high/low
Sends a formatted alert to Telegram
"""

import os
import requests
import yfinance as yf
from datetime import datetime
import pytz

# ── Index Configuration ───────────────────────────────────────────────────────
# Yahoo Finance tickers for NSE indices
# Verify at: https://finance.yahoo.com/quote/^NSEI
INDICES = {
    "🏦 Nifty 50":           {"ticker": "^NSEI",      "fund": "Large Cap Index"},
    "📈 Nifty Midcap 150":   {"ticker": "NIFTYMIDCAP150.NS","fund": "Edelweiss Mid Cap"},
    "🚀 Nifty Smallcap 250": {"ticker": "NIFTYSMLCAP250.NS","fund": "Nippon Small Cap"},
}

# ── Dip Level Thresholds (customize as per your strategy) ────────────────────
DIP_LEVELS = [
    (5,  "🟡 Minor dip  — Consider small lump sum (~1x SIP amount)"),
    (10, "🟠 Medium dip — Good opportunity (~2–3x SIP amount)"),
    (15, "🔴 Deep dip   — Strong buy signal (~5x SIP amount)"),
    (20, "🚨 Crash zone — Max lump sum if available!"),
]


def get_index_data(ticker_symbol: str) -> dict:
    """Fetch current price, 52W high and 52W low using yfinance."""
    ticker = yf.Ticker(ticker_symbol)

    # 1-year daily history for accurate 52W high/low
    hist = ticker.history(period="1y", interval="1d")

    if hist.empty:
        raise ValueError(f"No data returned for ticker: {ticker_symbol}")

    current   = round(hist["Close"].iloc[-1], 2)
    high_52w  = round(hist["High"].max(), 2)
    low_52w   = round(hist["Low"].min(), 2)

    drop_pts  = round(current - high_52w, 2)          # negative value
    drop_pct  = round((drop_pts / high_52w) * 100, 2) # negative %

    rise_pts  = round(current - low_52w, 2)            # positive value
    rise_pct  = round((rise_pts / low_52w) * 100, 2)  # positive %

    return {
        "current":   current,
        "high_52w":  high_52w,
        "low_52w":   low_52w,
        "drop_pts":  drop_pts,
        "drop_pct":  drop_pct,
        "rise_pts":  rise_pts,
        "rise_pct":  rise_pct,
    }


def get_action_signal(drop_pct: float) -> str:
    """Return buy action signal based on % drop from 52W high."""
    abs_drop = abs(drop_pct)
    signal = "🟢 Near 52W high — Stick to regular SIP"
    for threshold, message in DIP_LEVELS:
        if abs_drop >= threshold:
            signal = message
    return signal


def build_message() -> str:
    """Build the full Telegram alert message."""
    ist  = pytz.timezone("Asia/Kolkata")
    now  = datetime.now(ist).strftime("%d %b %Y  |  %I:%M %p IST")

    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━",
        "📊 *DAILY DIP MONITOR*",
        f"🗓 {now}",
        "━━━━━━━━━━━━━━━━━━━━━━\n",
    ]

    for name, meta in INDICES.items():
        ticker = meta["ticker"]
        fund   = meta["fund"]
        try:
            d = get_index_data(ticker)
            signal = get_action_signal(d["drop_pct"])

            lines += [
                f"*{name}*",
                f"  Fund  : {fund}",
                f"  Now   : `{d['current']:,.2f}`",
                f"  52W ↑ : `{d['high_52w']:,.2f}`  ({d['drop_pts']:+,.2f} pts  |  {d['drop_pct']:+.2f}%)",
                f"  52W ↓ : `{d['low_52w']:,.2f}`  (+{d['rise_pts']:,.2f} pts  |  +{d['rise_pct']:.2f}%)",
                f"  💡 {signal}",
                "",
            ]
        except Exception as e:
            lines += [
                f"*{name}*",
                f"  ❌ Error fetching data: {e}",
                "",
            ]

    lines += [
        "━━━━━━━━━━━━━━━━━━━━━━",
        "*Dip Guide*",
        "🟢 < 5% drop  → Regular SIP only",
        "🟡 5–9% drop  → Small lump sum",
        "🟠 10–14% drop → Medium lump sum",
        "🔴 15–19% drop → Large lump sum",
        "🚨 20%+ drop   → Max lump sum",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "_Data via Yahoo Finance. Not financial advice._",
    ]

    return "\n".join(lines)


def send_telegram(message: str, bot_token: str, chat_id: str) -> bool:
    """Send message to Telegram chat via Bot API."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id":    chat_id,
        "text":       message,
        "parse_mode": "Markdown",
    }
    resp = requests.post(url, json=payload, timeout=15)
    if resp.status_code != 200:
        print(f"Telegram error {resp.status_code}: {resp.text}")
        return False
    return True


if __name__ == "__main__":
    BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not BOT_TOKEN or not CHAT_ID:
        print("ERROR: Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env variables.")
        exit(1)

    print("Fetching index data...")
    message = build_message()
    print(message)

    print("\nSending Telegram message...")
    if send_telegram(message, BOT_TOKEN, CHAT_ID):
        print("✅ Alert sent successfully!")
    else:
        print("❌ Failed to send alert.")
        exit(1)
