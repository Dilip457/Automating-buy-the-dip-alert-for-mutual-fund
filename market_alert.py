"""
Daily Market Dip Monitor — FINAL
Data   : NSE India official API (allIndices endpoint)
         Returns yearHigh / yearLow directly — same data as nseindia.com
         mfapi.in for actual mutual fund NAV daily returns
Notify : Multiple Telegram chats / channels (comma-separated TELEGRAM_CHAT_IDS)
"""

import os
import time
import requests
import pytz
from datetime import datetime

# ── Index config ──────────────────────────────────────────────────────────────
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
# amfi_code : AMFI scheme code — verify at https://api.mfapi.in/mf/search?q=<name>
# short_label: compact name shown in the Telegram card
COMPARISONS = [
    {
        "title":  "🔄 Small Cap — Active vs Momentum",
        "fund_a": {
            "label":       "Nippon India Small Cap Fund Direct Growth",
            "short_label": "Nippon India SC Direct",
            "amfi_code":   118778,
        },
        "fund_b": {
            "label":       "Mirae Asset Nifty Smallcap 250 Momentum Quality 100 ETF FOF Direct",
            "short_label": "Mirae SC MQ 100 Direct",
            "amfi_code":   152459,
        },
    },
    {
        "title":  "🔄 Mid Cap — Active vs Momentum",
        "fund_a": {
            "label":       "Edelweiss Mid Cap Fund Direct Growth",
            "short_label": "Edelweiss Mid Cap Direct",
            "amfi_code":   140228,
        },
        "fund_b": {
            "label":       "Edelweiss Nifty Midcap 150 Momentum 50 Index Fund Direct",
            "short_label": "Edelweiss MC Mom 50 Direct",
            "amfi_code":   150902,
        },
    },
]

MFAPI_BASE = "https://api.mfapi.in/mf"

# Dip thresholds — used only for signal logic
DIP_LEVELS = [
    (5,  "🟡", "Minor dip",  "~1x SIP"),
    (10, "🟠", "Medium dip", "~2–3x SIP"),
    (15, "🔴", "Deep dip",   "~5x SIP"),
    (20, "🚨", "Crash zone", "Max lump sum!"),
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

MAX_RETRIES  = 3
TIMEOUT_HOME = 30
TIMEOUT_API  = 30


# ── NSE session ───────────────────────────────────────────────────────────────
def build_nse_session() -> requests.Session:
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
                wait = attempt * 10
                print(f"  Retrying in {wait}s…")
                time.sleep(wait)
            else:
                raise RuntimeError(
                    f"NSE session failed after {MAX_RETRIES} attempts: {e}"
                ) from e


# ── Fetch all index data ──────────────────────────────────────────────────────
def fetch_all_indices(session: requests.Session) -> list:
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
        available = [row.get("indexSymbol") for row in all_data][:30]
        raise ValueError(
            f"'{nse_index}' not found. First 30 available: {available}"
        )

    current  = round(float(entry["last"]),     2)
    high_52w = round(float(entry["yearHigh"]), 2)
    low_52w  = round(float(entry["yearLow"]),  2)
    drop_pts = round(current - high_52w, 2)
    drop_pct = round(drop_pts / high_52w * 100, 2) if high_52w else 0.0
    rise_pts = round(current - low_52w,  2)
    rise_pct = round(rise_pts / low_52w  * 100, 2) if low_52w  else 0.0

    return dict(
        current=current, high_52w=high_52w, low_52w=low_52w,
        drop_pts=drop_pts, drop_pct=drop_pct,
        rise_pts=rise_pts, rise_pct=rise_pct,
    )


# ── Fetch actual mutual fund NAV daily return ─────────────────────────────────
def get_fund_daily_return(amfi_code: int, label: str) -> float:
    """
    Returns daily NAV return %:  (nav_today - nav_prev) / nav_prev * 100
    Source: mfapi.in (AMFI data)
    """
    resp = requests.get(f"{MFAPI_BASE}/{amfi_code}", timeout=15)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    if len(data) < 2:
        raise ValueError(f"Not enough NAV history for '{label}' (code {amfi_code})")
    nav_today = float(data[0]["nav"])
    nav_prev  = float(data[1]["nav"])
    if nav_prev == 0:
        raise ValueError(f"Previous NAV is zero for '{label}'")
    return round((nav_today - nav_prev) / nav_prev * 100, 2)


# ── Compact dip signal ────────────────────────────────────────────────────────
def get_signal(drop_pct: float) -> str:
    icon, label, action = "🟢", "Near peak", "SIP only"
    for threshold, ico, lbl, act in DIP_LEVELS:
        if abs(drop_pct) >= threshold:
            icon, label, action = ico, lbl, act
    return f"{icon} {label}  ·  {action}"


# ── Build Telegram message ────────────────────────────────────────────────────
def build_message() -> str:
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist).strftime("%d %b %Y  ·  %I:%M %p IST")

    lines = [
        "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
        "📊 *DAILY DIP MONITOR*",
        f"_🗓 {now}_",
        "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n",
    ]

    try:
        session  = build_nse_session()
        all_data = fetch_all_indices(session)
    except Exception as e:
        lines.append(f"❌ NSE connection failed: {e}")
        return "\n".join(lines)

    # ── Section 1 : Index dip cards ───────────────────────────────────────────
    for name, meta in INDICES.items():
        try:
            d = get_index_stats(all_data, meta["nse_index"])
            trend = "📉" if d["drop_pct"] < 0 else "📈"
            lines += [
                f"*{name}*  _· {meta['fund']}_",
                f"  `{d['current']:>12,.2f}`  {trend} `{d['drop_pct']:+.2f}%` from 52W high",
                f"  {get_signal(d['drop_pct'])}",
                "",
            ]
        except Exception as e:
            lines += [f"*{name}*", f"  ❌ {e}", ""]

    # ── Section 2 : Fund return comparison ───────────────────────────────────
    lines += [
        "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
        "💹 *TODAY'S FUND RETURNS*",
        "_Active vs Momentum — who won today?_",
        "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n",
    ]

    for comp in COMPARISONS:
        lines.append(f"*{comp['title']}*")
        try:
            ret_a = get_fund_daily_return(
                comp["fund_a"]["amfi_code"], comp["fund_a"]["label"]
            )
            ret_b = get_fund_daily_return(
                comp["fund_b"]["amfi_code"], comp["fund_b"]["label"]
            )

            fmt_a = f"+{ret_a:.2f}%" if ret_a >= 0 else f"{ret_a:.2f}%"
            fmt_b = f"+{ret_b:.2f}%" if ret_b >= 0 else f"{ret_b:.2f}%"

            badge_a = " 🏆" if ret_a > ret_b else ""
            badge_b = " 🏆" if ret_b > ret_a else ""

            lines += [
                f"  ▸ {comp['fund_a']['short_label']}  `{fmt_a}`{badge_a}",
                f"  ▸ {comp['fund_b']['short_label']}  `{fmt_b}`{badge_b}",
                "",
            ]
        except Exception as e:
            lines += [f"  ❌ {e}", ""]

    lines += [
        "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
        "_Source: NSE India · AMFI via mfapi.in_",
        "_Not financial advice._",
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
