"""
Daily Market Dip Monitor — FINAL
Data   : NSE India official API (allIndices endpoint)
         Returns yearHigh / yearLow directly — same data as nseindia.com
Notify : Multiple Telegram chats / channels (comma-separated TELEGRAM_CHAT_IDS)
"""

import os
import time
import requests
import pytz
from datetime import datetime

# ── Index config ──────────────────────────────────────────────────────────────
# nse_index must match the "indexSymbol" field in NSE's allIndices API exactly
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

DIP_LEVELS = [
    (5,  "🟡 Minor dip  — Consider small lump sum (~1x SIP)"),
    (10, "🟠 Medium dip — Good opportunity (~2–3x SIP)"),
    (15, "🔴 Deep dip   — Strong buy signal (~5x SIP)"),
    (20, "🚨 Crash zone — Max lump sum if available!"),
]

NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://www.nseindia.com/",
}


# ── NSE session ───────────────────────────────────────────────────────────────
def build_nse_session() -> requests.Session:
    """
    NSE requires valid cookies before API calls.
    Visit homepage + indices page first to seed the session.
    """
    session = requests.Session()
    session.headers.update(NSE_HEADERS)

    print("  Visiting NSE homepage for cookies…")
    session.get("https://www.nseindia.com", timeout=15)
    time.sleep(2)

    print("  Visiting indices page…")
    session.get("https://www.nseindia.com/market-data/live-equity-market", timeout=15)
    time.sleep(1)

    return session


# ── Fetch all index data in one API call ──────────────────────────────────────
def fetch_all_indices(session: requests.Session) -> list:
    """
    Calls NSE allIndices API — returns live quote + yearHigh + yearLow
    for every index in a single request.
    """
    resp = session.get("https://www.nseindia.com/api/allIndices", timeout=20)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    if not data:
        raise ValueError("NSE allIndices returned empty data")
    return data


# ── Extract stats for one index ───────────────────────────────────────────────
def get_index_stats(all_data: list, nse_index: str) -> dict:
    target = nse_index.upper()
    entry  = next(
        (row for row in all_data if row.get("indexSymbol", "").upper() == target),
        None,
    )
    if entry is None:
        available = [row.get("indexSymbol") for row in all_data]
        raise ValueError(
            f"'{nse_index}' not found in NSE response.\n"
            f"Available symbols: {available}"
        )

    current  = round(float(entry["last"]),    2)
    high_52w = round(float(entry["yearHigh"]),2)
    low_52w  = round(float(entry["yearLow"]), 2)
    drop_pts = round(current - high_52w, 2)
    drop_pct = round(drop_pts / high_52w * 100, 2)
    rise_pts = round(current - low_52w,  2)
    rise_pct = round(rise_pts / low_52w  * 100, 2)

    return dict(
        current=current, high_52w=high_52w, low_52w=low_52w,
        drop_pts=drop_pts, drop_pct=drop_pct,
        rise_pts=rise_pts, rise_pct=rise_pct,
    )


# ── Buy signal ────────────────────────────────────────────────────────────────
def get_signal(drop_pct: float) -> str:
    signal = "🟢 Near 52W high — Stick to regular SIP"
    for threshold, msg in DIP_LEVELS:
        if abs(drop_pct) >= threshold:
            signal = msg
    return signal


# ── Build Telegram message ────────────────────────────────────────────────────
def build_message() -> str:
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist).strftime("%d %b %Y  |  %I:%M %p IST")

    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━",
        "📊 *DAILY DIP MONITOR*",
        f"🗓 {now}",
        "━━━━━━━━━━━━━━━━━━━━━━\n",
    ]

    try:
        session  = build_nse_session()
        all_data = fetch_all_indices(session)
    except Exception as e:
        lines.append(f"❌ NSE connection failed: {e}")
        return "\n".join(lines)

    for name, meta in INDICES.items():
        try:
            d = get_index_stats(all_data, meta["nse_index"])
            lines += [
                f"*{name}*",
                f"  Fund  : {meta['fund']}",
                f"  Now   : `{d['current']:,.2f}`",
                f"  52W ↑ : `{d['high_52w']:,.2f}`  ({d['drop_pts']:+,.2f} pts  |  {d['drop_pct']:+.2f}%)",
                f"  52W ↓ : `{d['low_52w']:,.2f}`  (+{d['rise_pts']:,.2f} pts  |  +{d['rise_pct']:.2f}%)",
                f"  💡 {get_signal(d['drop_pct'])}",
                "",
            ]
        except Exception as e:
            lines += [f"*{name}*", f"  ❌ Error: {e}", ""]

    lines += [
        "━━━━━━━━━━━━━━━━━━━━━━",
        "*Dip Guide*",
        "🟢 < 5%   → Regular SIP only",
        "🟡 5–9%   → Small lump sum",
        "🟠 10–14% → Medium lump sum",
        "🔴 15–19% → Large lump sum",
        "🚨 20%+   → Max lump sum",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "_Data via NSE India (official). Not financial advice._",
    ]
    return "\n".join(lines)


# ── Send to multiple Telegram chats/channels ──────────────────────────────────
def send_telegram(message: str, bot_token: str, chat_ids: list) -> bool:
    url     = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    success = False
    for chat_id in chat_ids:
        chat_id = chat_id.strip()
        if not chat_id:
            continue
        try:
            resp = requests.post(
                url,
                json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
                timeout=15,
            )
            if resp.status_code == 200:
                print(f"✅ Sent to {chat_id}")
                success = True
            else:
                print(f"❌ Failed for {chat_id}: {resp.text}")
        except Exception as e:
            print(f"❌ Error for {chat_id}: {e}")
    return success


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    BOT_TOKEN    = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    CHAT_IDS_RAW = os.environ.get("TELEGRAM_CHAT_IDS", "")

    if not BOT_TOKEN or not CHAT_IDS_RAW:
        print("ERROR: Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_IDS env vars.")
        exit(1)

    CHAT_IDS = [c.strip() for c in CHAT_IDS_RAW.split(",") if c.strip()]

    print("Fetching data from NSE India…")
    message = build_message()
    print(message)

    print(f"\nSending to {len(CHAT_IDS)} chat(s)…")
    if send_telegram(message, BOT_TOKEN, CHAT_IDS):
        print("✅ Done!")
    else:
        print("❌ All sends failed.")
        exit(1)
