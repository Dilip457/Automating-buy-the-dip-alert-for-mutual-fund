"""
Daily Market Dip Monitor — FINAL
Data   : NSE India public bhavcopy archives (accurate 52W H/L)
Notify : Multiple Telegram chats / channels
"""

import os
import csv
import io
import requests
import pytz
from datetime import date, timedelta, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Index config ──────────────────────────────────────────────────────────────
INDICES = {
    "🏦 Nifty 50": {
        "nse_name": "Nifty 50",
        "fund":     "Large Cap Index",
    },
    "📈 Nifty Midcap 150": {
        "nse_name": "Nifty Midcap 150",
        "fund":     "Edelweiss Mid Cap",
    },
    "🚀 Nifty Smallcap 250": {
        "nse_name": "Nifty Smlcap 250",
        "fund":     "Nippon Small Cap",
    },
}

DIP_LEVELS = [
    (5,  "🟡 Minor dip  — Consider small lump sum (~1x SIP)"),
    (10, "🟠 Medium dip — Good opportunity (~2–3x SIP)"),
    (15, "🔴 Deep dip   — Strong buy signal (~5x SIP)"),
    (20, "🚨 Crash zone — Max lump sum if available!"),
]

ARCHIVE_URL = "https://archives.nseindia.com/content/indices/ind_close_all_{}.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}


# ── NSE bhavcopy: download one day ────────────────────────────────────────────
def fetch_one_day(target_date: date) -> dict:
    """Returns {index_name: {high, low, close}} or {} if holiday/error."""
    url = ARCHIVE_URL.format(target_date.strftime("%d%m%Y"))
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return {}
        reader = csv.DictReader(io.StringIO(resp.text))
        result = {}
        for row in reader:
            name = (row.get("Index Name") or "").strip()
            try:
                result[name] = {
                    "high":  float(row["High Index Value"]),
                    "low":   float(row["Low Index Value"]),
                    "close": float(row["Closing Index Value"]),
                }
            except (ValueError, KeyError, TypeError):
                pass
        return result
    except Exception:
        return {}


# ── NSE bhavcopy: parallel download of full year ──────────────────────────────
def download_52w_history() -> dict:
    """Downloads ~260 daily CSVs in parallel. Returns {date: {name: ohlc}}."""
    end   = date.today()
    start = end - timedelta(days=375)

    weekdays = []
    d = start
    while d <= end:
        if d.weekday() < 5:
            weekdays.append(d)
        d += timedelta(days=1)

    print(f"  Downloading {len(weekdays)} candidate days in parallel…")
    history = {}

    with ThreadPoolExecutor(max_workers=20) as ex:
        futures = {ex.submit(fetch_one_day, d): d for d in weekdays}
        for f in as_completed(futures):
            day = f.result()
            if day:
                history[futures[f]] = day

    print(f"  Got data for {len(history)} actual trading days.")
    return history


# ── Flexible index name matching ───────────────────────────────────────────────
def find_row(day_data: dict, target: str):
    if target in day_data:
        return day_data[target]
    tl = target.lower()
    for k, v in day_data.items():
        if k.lower() == tl:
            return v
    for k, v in day_data.items():
        if tl in k.lower():
            return v
    return None


# ── Compute 52W stats ─────────────────────────────────────────────────────────
def compute_stats(history: dict, nse_name: str) -> dict:
    sorted_dates = sorted(history.keys())[-252:]
    highs, lows  = [], []
    current      = None

    for d in sorted_dates:
        row = find_row(history.get(d, {}), nse_name)
        if row:
            highs.append(row["high"])
            lows.append(row["low"])
            current = row["close"]

    if not current or not highs or not lows:
        raise ValueError(f"No data for '{nse_name}'")

    current  = round(current,    2)
    high_52w = round(max(highs), 2)
    low_52w  = round(min(lows),  2)
    drop_pts = round(current - high_52w, 2)
    drop_pct = round(drop_pts / high_52w * 100, 2)
    rise_pts = round(current - low_52w,  2)
    rise_pct = round(rise_pts / low_52w  * 100, 2)

    return dict(current=current, high_52w=high_52w, low_52w=low_52w,
                drop_pts=drop_pts, drop_pct=drop_pct,
                rise_pts=rise_pts, rise_pct=rise_pct)


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
        history = download_52w_history()
    except Exception as e:
        lines.append(f"❌ Failed to download NSE data: {e}")
        return "\n".join(lines)

    for name, meta in INDICES.items():
        try:
            d = compute_stats(history, meta["nse_name"])
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
        "_Data via NSE India. Not financial advice._",
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

    print("Fetching 52W data from NSE India archives…")
    message = build_message()
    print(message)

    print(f"\nSending to {len(CHAT_IDS)} chat(s)…")
    if send_telegram(message, BOT_TOKEN, CHAT_IDS):
        print("✅ Done!")
    else:
        print("❌ All sends failed.")
        exit(1)
