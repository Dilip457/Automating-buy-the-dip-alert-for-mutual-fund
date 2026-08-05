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

# ── Fund comparison config ────────────────────────────────────────────────────
# Each entry compares an active fund's benchmark vs a momentum/factor index
# to show which strategy outperformed on a given day.
COMPARISONS = [
    {
        "title":  "🔄 Small Cap — Active vs Momentum Quality",
        "fund_a": {
            "label":     "Nippon Small Cap Direct Growth",
            "nse_index": "NIFTY SMLCAP 250",
        },
        "fund_b": {
            "label":     "Mirae Asset Nifty Smallcap 250 Momentum Quality 100 ETF FOF",
            "nse_index": "NIFTYSML250MQ 100",
        },
    },
    {
        "title":  "🔄 Mid Cap — Active vs Momentum",
        "fund_a": {
            "label":     "Edelweiss Midcap Direct Growth",
            "nse_index": "NIFTY MIDCAP 150",
        },
        "fund_b": {
            "label":     "Edelweiss Nifty Midcap 150 Momentum 50 Index Fund",
            "nse_index": "NIFTYM150MOMNTM50",
        },
    },
]

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
MAX_RETRIES  = 3
TIMEOUT_HOME = 30   # homepage can be slow
TIMEOUT_API  = 30   # allIndices API call

def build_nse_session() -> requests.Session:
    """
    NSE requires valid cookies before API calls.
    Visit homepage + indices page first to seed the session.
    Retries up to MAX_RETRIES times on failure.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            session = requests.Session()
            session.headers.update(NSE_HEADERS)

            print(f"  [Attempt {attempt}] Visiting NSE homepage for cookies…")
            session.get("https://www.nseindia.com", timeout=TIMEOUT_HOME)
            time.sleep(3)

            print(f"  [Attempt {attempt}] Visiting indices page…")
            session.get(
                "https://www.nseindia.com/market-data/live-equity-market",
                timeout=TIMEOUT_HOME,
            )
            time.sleep(2)

            return session

        except Exception as e:
            print(f"  ⚠️ Session attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                wait = attempt * 10   # 10s, 20s, 30s
                print(f"  Retrying in {wait}s…")
                time.sleep(wait)
            else:
                raise RuntimeError(
                    f"NSE session failed after {MAX_RETRIES} attempts: {e}"
                ) from e


# ── Fetch all index data in one API call ──────────────────────────────────────
def fetch_all_indices(session: requests.Session) -> list:
    """
    Calls NSE allIndices API — returns live quote + yearHigh + yearLow
    for every index in a single request.
    Retries up to MAX_RETRIES times on timeout/error.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"  [Attempt {attempt}] Calling allIndices API…")
            resp = session.get(
                "https://www.nseindia.com/api/allIndices",
                timeout=TIMEOUT_API,
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
            if not data:
                raise ValueError("NSE allIndices returned empty data")
            print(f"  ✅ Got data for {len(data)} indices.")
            return data

        except Exception as e:
            print(f"  ⚠️ API attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                wait = attempt * 10
                print(f"  Retrying in {wait}s…")
                time.sleep(wait)
            else:
                raise RuntimeError(
                    f"allIndices API failed after {MAX_RETRIES} attempts: {e}"
                ) from e


# ── Extract stats for one index ───────────────────────────────────────────────
def get_index_stats(all_data: list, nse_index: str) -> dict:
    target = nse_index.upper()
    entry  = next(
        (row for row in all_data if row.get("indexSymbol", "").upper() == target),
        None,
    )
    if entry is None:
        # Limit to first 30 symbols to keep error messages short (Telegram 4096-char limit)
        available = [row.get("indexSymbol") for row in all_data][:30]
        raise ValueError(
            f"'{nse_index}' not found in NSE response. "
            f"First 30 available: {available}"
        )

    current  = round(float(entry["last"]),    2)
    high_52w = round(float(entry["yearHigh"]),2)
    low_52w  = round(float(entry["yearLow"]), 2)

    # Guard against zero values (NSE returns 0 for some newer/factor indices)
    drop_pts = round(current - high_52w, 2)
    drop_pct = round(drop_pts / high_52w * 100, 2) if high_52w else 0.0
    rise_pts = round(current - low_52w,  2)
    rise_pct = round(rise_pts / low_52w  * 100, 2) if low_52w  else 0.0

    # Daily change — field name varies slightly across NSE API versions
    day_pct  = round(float(entry.get("percentChange", entry.get("pChange", 0))), 2)
    day_pts  = round(float(entry.get("change", 0)), 2)

    return dict(
        current=current, high_52w=high_52w, low_52w=low_52w,
        drop_pts=drop_pts, drop_pct=drop_pct,
        rise_pts=rise_pts, rise_pct=rise_pct,
        day_pct=day_pct, day_pts=day_pts,
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

    # ── Section 1 : Dip monitor (existing) ───────────────────────────────────
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
    ]

    # ── Section 2 : Daily return comparison (new) ─────────────────────────────
    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "📈 *DAILY RETURN COMPARISON*",
        "_(Active fund benchmark vs Momentum/Factor index — today's performance)_",
        "━━━━━━━━━━━━━━━━━━━━━━\n",
    ]

    for comp in COMPARISONS:
        lines.append(f"*{comp['title']}*")
        try:
            da = get_index_stats(all_data, comp["fund_a"]["nse_index"])
            db = get_index_stats(all_data, comp["fund_b"]["nse_index"])

            # Format daily return with explicit + for gains, - for losses
            ret_a = f"+{da['day_pct']:.2f}%" if da["day_pct"] >= 0 else f"{da['day_pct']:.2f}%"
            ret_b = f"+{db['day_pct']:.2f}%" if db["day_pct"] >= 0 else f"{db['day_pct']:.2f}%"

            # Determine today's outperformer
            if da["day_pct"] > db["day_pct"]:
                verdict = f"🏆 {comp['fund_a']['label']} outperformed today"
            elif db["day_pct"] > da["day_pct"]:
                verdict = f"🏆 {comp['fund_b']['label']} outperformed today"
            else:
                verdict = "🤝 Both funds moved equally today"

            lines += [
                f"  📌 {comp['fund_a']['label']}: `{ret_a}`",
                f"  📌 {comp['fund_b']['label']}: `{ret_b}`",
                f"  {verdict}",
                "",
            ]
        except Exception as e:
            lines += [f"  ❌ Error: {e}", ""]

    lines += [
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
