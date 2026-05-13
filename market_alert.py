"""
Daily Market Dip Monitor - v4
Source: NSE India direct API (same data as nseindia.com) — no third-party libs
"""

import os
import time
import requests
from datetime import datetime
import pytz

# ── Index Configuration ───────────────────────────────────────────────────────
# nse_index: exact string used in NSE's indices API
INDICES = {
    "🏦 Nifty 50": {
        "nse_index": "NIFTY 50",
        "fund":      "Large Cap Index",
    },
    "📈 Nifty Midcap 150": {
        "nse_index": "NIFTY MIDCAP 150",
        "fund":      "Edelweiss Mid Cap",
    },
    "🚀 Nifty Smallcap 250": {
        "nse_index": "NIFTY SMLCAP 250",
        "fund":      "Nippon Small Cap",
    },
}

# ── Dip Level Thresholds ──────────────────────────────────────────────────────
DIP_LEVELS = [
    (5,  "🟡 Minor dip  — Consider small lump sum (~1x SIP)"),
    (10, "🟠 Medium dip — Good opportunity (~2–3x SIP)"),
    (15, "🔴 Deep dip   — Strong buy signal (~5x SIP)"),
    (20, "🚨 Crash zone — Max lump sum if available!"),
]

# ── NSE session headers (mimics a real browser visit) ────────────────────────
NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://www.nseindia.com/",
    "Origin":          "https://www.nseindia.com",
}


# ── NSE session (must visit homepage first to get cookies) ───────────────────
def _build_nse_session() -> requests.Session:
    """
    NSE requires a valid cookie before API calls.
    Visit the homepage first, then the indices page — that seeds the session.
    """
    session = requests.Session()
    session.headers.update(NSE_HEADERS)

    # Step 1: hit homepage to get initial cookies
    session.get("https://www.nseindia.com", timeout=15)
    time.sleep(1)

    # Step 2: hit the indices page (seeds more cookies, especially 'bm_sv')
    session.get("https://www.nseindia.com/market-data/live-equity-market", timeout=15)
    time.sleep(1)

    return session


# ── Fetch 52W high/low + current from NSE ─────────────────────────────────────
def get_data_from_nse(session: requests.Session, nse_index: str) -> dict:
    """
    Calls NSE's allIndices endpoint which returns live quote + 52W high/low
    for every index in one shot. Accurate, official, India-specific.
    """
    url  = "https://www.nseindia.com/api/allIndices"
    resp = session.get(url, timeout=20)
    resp.raise_for_status()

    data = resp.json().get("data", [])
    if not data:
        raise ValueError("NSE allIndices returned empty data")

    # Find our index (case-insensitive match)
    target = nse_index.upper()
    entry  = next(
        (row for row in data if row.get("indexSymbol", "").upper() == target),
        None,
    )
    if entry is None:
        # List available symbols to help debug
        available = [row.get("indexSymbol") for row in data]
        raise ValueError(
            f"Index '{nse_index}' not found in NSE response.\n"
            f"Available: {available}"
        )

    current  = round(float(entry["last"]),        2)
    high_52w = round(float(entry["yearHigh"]),     2)
    low_52w  = round(float(entry["yearLow"]),      2)

    return _compute_stats(current, high_52w, low_52w)


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

    # Build one NSE session shared across all index fetches
    print("  Initialising NSE session…")
    try:
        session = _build_nse_session()
    except Exception as e:
        raise RuntimeError(f"Failed to create NSE session: {e}") from e

    for name, meta in INDICES.items():
        try:
            d      = get_data_from_nse(session, meta["nse_index"])
            signal = get_action_signal(d["drop_pct"])
            lines += [
                f"*{name}*  _(src: NSE India)_",
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
        "_Data via NSE India (official). Not financial advice._",
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

    print("Fetching index data from NSE India…")
    message = build_message()
    print(message)

    print("\nSending to Telegram…")
    if send_telegram(message, BOT_TOKEN, CHAT_ID):
        print("✅ Alert sent!")
    else:
        print("❌ Failed to send.")
        exit(1)
