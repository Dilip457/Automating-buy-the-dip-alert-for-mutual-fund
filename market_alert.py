"""
Daily Market Dip Monitor - v3
Primary source: NSE India (via jugaad-data) — accurate 52W high/low
Fallback:       Yahoo Finance chart API
"""

import os
import requests
from datetime import date, timedelta, datetime
import pytz

# ── jugaad-data import (NSE primary source) ───────────────────────────────────
try:
    from jugaad_data.nse import index_history
    import pandas as pd
    JUGAAD_OK = True
except Exception:
    JUGAAD_OK = False

# ── Index Configuration ───────────────────────────────────────────────────────
INDICES = {
    "🏦 Nifty 50": {
        "nse_symbol": "NIFTY 50",
        "yf_ticker":  "^NSEI",
        "fund":       "Large Cap Index",
    },
    "📈 Nifty Midcap 150": {
        "nse_symbol": "NIFTY MIDCAP 150",
        "yf_ticker":  "NIFTYMIDCAP150.NS",
        "fund":       "Edelweiss Mid Cap",
    },
    "🚀 Nifty Smallcap 250": {
        "nse_symbol": "NIFTY SMLCAP 250",
        "yf_ticker":  "NIFTYSMLCAP250.NS",
        "fund":       "Nippon Small Cap",
    },
}

# ── Dip Level Thresholds ─────────────────────────────────────────────────────
DIP_LEVELS = [
    (5,  "🟡 Minor dip  — Consider small lump sum (~1x SIP)"),
    (10, "🟠 Medium dip — Good opportunity (~2–3x SIP)"),
    (15, "🔴 Deep dip   — Strong buy signal (~5x SIP)"),
    (20, "🚨 Crash zone — Max lump sum if available!"),
]

YF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


# ── Data fetching: NSE primary ────────────────────────────────────────────────
def get_data_from_nse(nse_symbol: str) -> dict:
    """Fetch 1-year OHLC history directly from NSE India via jugaad-data."""
    end   = date.today()
    start = end - timedelta(days=365)

    df = index_history(symbol=nse_symbol, from_date=start, to_date=end)
    if df is None or df.empty:
        raise ValueError(f"No NSE data for {nse_symbol}")

    # jugaad-data column names vary; normalise to uppercase
    df.columns = [c.upper().strip() for c in df.columns]

    current  = round(float(df["CLOSE"].iloc[-1]), 2)
    high_52w = round(float(df["HIGH"].max()), 2)
    low_52w  = round(float(df["LOW"].min()), 2)

    return _compute_stats(current, high_52w, low_52w)


# ── Data fetching: Yahoo Finance fallback ─────────────────────────────────────
def get_data_from_yf(yf_ticker: str) -> dict:
    """Fetch 1-year daily OHLC from Yahoo Finance v8 chart API."""
    url  = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_ticker}"
    resp = requests.get(
        url,
        params={"range": "1y", "interval": "1d", "includePrePost": "false"},
        headers=YF_HEADERS,
        timeout=20,
    )
    resp.raise_for_status()
    result = resp.json()["chart"]["result"]
    if not result:
        raise ValueError(f"No YF data for {yf_ticker}")

    q       = result[0]["indicators"]["quote"][0]
    closes  = [x for x in q["close"] if x is not None]
    highs   = [x for x in q["high"]  if x is not None]
    lows    = [x for x in q["low"]   if x is not None]

    if not closes:
        raise ValueError(f"Empty YF data for {yf_ticker}")

    return _compute_stats(
        round(closes[-1], 2),
        round(max(highs),  2),
        round(min(lows),   2),
    )


# ── Shared stats calculation ──────────────────────────────────────────────────
def _compute_stats(current: float, high_52w: float, low_52w: float) -> dict:
    drop_pts = round(current - high_52w, 2)
    drop_pct = round((drop_pts / high_52w) * 100, 2)
    rise_pts = round(current - low_52w,  2)
    rise_pct = round((rise_pts / low_52w) * 100, 2)
    return {
        "current":   current,
        "high_52w":  high_52w,
        "low_52w":   low_52w,
        "drop_pts":  drop_pts,
        "drop_pct":  drop_pct,
        "rise_pts":  rise_pts,
        "rise_pct":  rise_pct,
    }


def get_index_data(nse_symbol: str, yf_ticker: str) -> tuple[dict, str]:
    """Try NSE first, fall back to Yahoo Finance. Returns (data, source_label)."""
    if JUGAAD_OK:
        try:
            return get_data_from_nse(nse_symbol), "NSE"
        except Exception as e:
            print(f"  NSE fetch failed for {nse_symbol}: {e}. Trying Yahoo Finance…")

    return get_data_from_yf(yf_ticker), "YF"


# ── Signal ────────────────────────────────────────────────────────────────────
def get_action_signal(drop_pct: float) -> str:
    abs_drop = abs(drop_pct)
    signal   = "🟢 Near 52W high — Stick to regular SIP"
    for threshold, message in DIP_LEVELS:
        if abs_drop >= threshold:
            signal = message
    return signal


# ── Message builder ───────────────────────────────────────────────────────────
def build_message() -> str:
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist).strftime("%d %b %Y  |  %I:%M %p IST")

    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━",
        "📊 *DAILY DIP MONITOR*",
        f"🗓 {now}",
        "━━━━━━━━━━━━━━━━━━━━━━\n",
    ]

    for name, meta in INDICES.items():
        try:
            d, src = get_index_data(meta["nse_symbol"], meta["yf_ticker"])
            signal = get_action_signal(d["drop_pct"])
            lines += [
                f"*{name}*  _(src: {src})_",
                f"  Fund  : {meta['fund']}",
                f"  Now   : `{d['current']:,.2f}`",
                f"  52W ↑ : `{d['high_52w']:,.2f}`  ({d['drop_pts']:+,.2f} pts  |  {d['drop_pct']:+.2f}%)",
                f"  52W ↓ : `{d['low_52w']:,.2f}`  (+{d['rise_pts']:,.2f} pts  |  +{d['rise_pct']:.2f}%)",
                f"  💡 {signal}",
                "",
            ]
        except Exception as e:
            lines += [f"*{name}*", f"  ❌ Error: {e}", ""]

    lines += [
        "━━━━━━━━━━━━━━━━━━━━━━",
        "*Dip Guide*",
        "🟢 < 5% drop  → Regular SIP only",
        "🟡 5–9% drop  → Small lump sum",
        "🟠 10–14% drop → Medium lump sum",
        "🔴 15–19% drop → Large lump sum",
        "🚨 20%+ drop   → Max lump sum",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "_Data via NSE India / Yahoo Finance. Not financial advice._",
    ]
    return "\n".join(lines)


# ── Telegram ──────────────────────────────────────────────────────────────────
def send_telegram(message: str, bot_token: str, chat_id: str) -> bool:
    url  = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    resp = requests.post(
        url,
        json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
        timeout=15,
    )
    if resp.status_code != 200:
        print(f"Telegram error {resp.status_code}: {resp.text}")
        return False
    return True


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not BOT_TOKEN or not CHAT_ID:
        print("ERROR: Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars.")
        exit(1)

    print("Fetching index data…")
    message = build_message()
    print(message)

    print("\nSending to Telegram…")
    if send_telegram(message, BOT_TOKEN, CHAT_ID):
        print("✅ Alert sent!")
    else:
        print("❌ Failed to send.")
        exit(1)
