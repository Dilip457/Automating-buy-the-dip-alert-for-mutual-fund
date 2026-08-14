"""
Daily Market Dip Monitor — FINAL
Data   : NSE India official API (allIndices endpoint)
         Returns yearHigh / yearLow directly — same data as nseindia.com
         mfapi.in for actual mutual fund NAV daily returns
Notify : Multiple Telegram chats / channels (comma-separated TELEGRAM_CHAT_IDS)
Output : Infographic PNG sent via Telegram sendPhoto
         Falls back to plain-text sendMessage if Pillow is not installed.
"""

import os
import io
import time
import calendar
import requests
import pytz
from datetime import datetime

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("WARNING: Pillow not installed — falling back to text messages.")

# ── Index config ──────────────────────────────────────────────────────────────
INDICES = {
    "Nifty 50": {
        "nse_index": "NIFTY 50",
        "fund":      "Large Cap Index",
    },
    "Nifty Midcap 150": {
        "nse_index": "NIFTY MIDCAP 150",
        "fund":      "Edelweiss Mid Cap",
    },
    "Nifty Smallcap 250": {
        "nse_index": "NIFTY SMLCAP 250",
        "fund":      "Nippon Small Cap",
    },
}

# ── Fund comparison config ────────────────────────────────────────────────────
COMPARISONS = [
    {
        "title":  "Small Cap — Active vs Momentum",
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
        "title":  "Mid Cap — Active vs Momentum",
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

# ── Infographic palette (GitHub-dark inspired) ────────────────────────────────
C_BG      = (13,  17,  23)
C_CARD    = (22,  27,  34)
C_CARD2   = (30,  37,  46)
C_BORDER  = (48,  54,  61)
C_BLUE    = (88,  166, 255)
C_TEXT    = (230, 237, 243)
C_SUBTEXT = (139, 148, 158)
C_GREEN   = (63,  185, 80)
C_YELLOW  = (210, 153, 34)
C_ORANGE  = (240, 136, 62)
C_RED     = (248, 81,  73)
C_GOLD    = (255, 200, 0)

IMG_W = 900
PAD   = 32


# ── Month-end detection ───────────────────────────────────────────────────────
def is_last_day_of_month() -> bool:
    """Return True if today (IST) is the last calendar day of the current month."""
    ist   = pytz.timezone("Asia/Kolkata")
    today = datetime.now(ist).date()
    return today.day == calendar.monthrange(today.year, today.month)[1]


# ── Signal helpers ────────────────────────────────────────────────────────────
def _signal_color(drop_pct: float) -> tuple:
    a = abs(drop_pct)
    if a >= 15: return C_RED
    if a >= 10: return C_ORANGE
    if a >= 5:  return C_YELLOW
    return C_GREEN


def _signal_text(drop_pct: float) -> str:
    a = abs(drop_pct)
    if a >= 20: return "CRASH ZONE"
    if a >= 15: return "DEEP DIP"
    if a >= 10: return "MEDIUM DIP"
    if a >= 5:  return "MINOR DIP"
    return "NEAR PEAK"


# ── Font loader ───────────────────────────────────────────────────────────────
def _find_font(size: int, bold: bool = False):
    """Load a TrueType font with OS-aware fallbacks."""
    if not PIL_AVAILABLE:
        return None
    if bold:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/calibrib.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibri.ttf",
        ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def _text_w(draw, text: str, font) -> int:
    """Return pixel width of text."""
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]
    except Exception:
        return len(text) * 8  # rough fallback


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


# ── Shared NAV fetch (with retry) ─────────────────────────────────────────────
def _fetch_nav_data(amfi_code: int, label: str) -> list:
    """
    Fetch full NAV history from mfapi.in with retry / back-off.
    Returns the 'data' list (reverse-chronological, most recent first).
    Each entry: {"date": "DD-MM-YYYY", "nav": "123.456"}
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"  [Attempt {attempt}] Fetching NAV for '{label}' (code {amfi_code})…")
            resp = requests.get(f"{MFAPI_BASE}/{amfi_code}", timeout=30)
            resp.raise_for_status()
            data = resp.json().get("data", [])
            if len(data) < 2:
                raise ValueError(
                    f"Not enough NAV history for '{label}' (code {amfi_code})"
                )
            return data
        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError) as e:
            print(f"  ⚠️ NAV fetch attempt {attempt} failed (network): {e}")
            if attempt < MAX_RETRIES:
                wait = attempt * 10
                print(f"  Retrying in {wait}s…")
                time.sleep(wait)
            else:
                raise RuntimeError(
                    f"mfapi.in timed out for '{label}' after {MAX_RETRIES} attempts: {e}"
                ) from e
        except Exception as e:
            raise RuntimeError(
                f"Failed to fetch NAV for '{label}' (code {amfi_code}): {e}"
            ) from e


# ── Daily NAV return ──────────────────────────────────────────────────────────
def get_fund_daily_return(amfi_code: int, label: str) -> float:
    """Returns daily NAV return %: (nav_today - nav_prev) / nav_prev * 100"""
    data      = _fetch_nav_data(amfi_code, label)
    nav_today = float(data[0]["nav"])
    nav_prev  = float(data[1]["nav"])
    if nav_prev == 0:
        raise ValueError(f"Previous NAV is zero for '{label}'")
    return round((nav_today - nav_prev) / nav_prev * 100, 2)


# ── Monthly NAV return (month-end only) ───────────────────────────────────────
def get_fund_monthly_return(amfi_code: int, label: str) -> tuple:
    """
    Returns (monthly_return_pct, month_label).
    Base = last trading-day NAV of the previous calendar month.
    mfapi.in date format: "DD-MM-YYYY", data is reverse-chronological.
    """
    ist   = pytz.timezone("Asia/Kolkata")
    today = datetime.now(ist).date()

    if today.month == 1:
        prev_month, prev_year = 12, today.year - 1
    else:
        prev_month, prev_year = today.month - 1, today.year

    data      = _fetch_nav_data(amfi_code, label)
    nav_today = float(data[0]["nav"])

    nav_base = base_date_str = None
    for entry in data[1:]:
        entry_date = datetime.strptime(entry["date"], "%d-%m-%Y").date()
        if entry_date.year == prev_year and entry_date.month == prev_month:
            nav_base      = float(entry["nav"])
            base_date_str = entry["date"]
            break
        if (entry_date.year, entry_date.month) < (prev_year, prev_month):
            nav_base      = float(entry["nav"])
            base_date_str = entry["date"]
            break

    if nav_base is None:
        raise ValueError(
            f"Could not find previous-month NAV for '{label}' "
            f"(looking for {prev_month:02d}-{prev_year})"
        )
    if nav_base == 0:
        raise ValueError(f"Previous-month NAV is zero for '{label}'")

    month_label = datetime(prev_year, prev_month, 1).strftime("%b %Y")
    monthly_ret = round((nav_today - nav_base) / nav_base * 100, 2)
    print(
        f"  ✅ Monthly return for '{label}': base {nav_base} "
        f"({base_date_str}) → today {nav_today} = {monthly_ret:+.2f}%"
    )
    return monthly_ret, month_label


# ── Collect all report data ───────────────────────────────────────────────────
def collect_report_data() -> dict:
    """
    Fetch all data and return a structured dict used by both the
    infographic renderer and the text-message fallback.
    """
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)

    report = {
        "date":       now.strftime("%d %b %Y  ·  %I:%M %p IST"),
        "indices":    [],
        "daily":      [],
        "monthly":    None,
        "month_label": None,
        "nse_error":  None,
    }

    # NSE data
    try:
        session  = build_nse_session()
        all_data = fetch_all_indices(session)
    except Exception as e:
        report["nse_error"] = str(e)
        return report

    # Index stats
    for name, meta in INDICES.items():
        try:
            d = get_index_stats(all_data, meta["nse_index"])
            report["indices"].append({
                "name":         name,
                "fund":         meta["fund"],
                "current":      d["current"],
                "drop_pct":     d["drop_pct"],
                "high_52w":     d["high_52w"],
                "signal_text":  _signal_text(d["drop_pct"]),
                "signal_color": _signal_color(d["drop_pct"]),
                "error":        None,
            })
        except Exception as e:
            report["indices"].append({"name": name, "error": str(e)})

    # Daily fund returns
    for comp in COMPARISONS:
        try:
            ret_a = get_fund_daily_return(comp["fund_a"]["amfi_code"], comp["fund_a"]["label"])
            ret_b = get_fund_daily_return(comp["fund_b"]["amfi_code"], comp["fund_b"]["label"])
            report["daily"].append({
                "title":  comp["title"],
                "fund_a": {"short_label": comp["fund_a"]["short_label"],
                           "ret": ret_a, "winner": ret_a > ret_b},
                "fund_b": {"short_label": comp["fund_b"]["short_label"],
                           "ret": ret_b, "winner": ret_b > ret_a},
                "error":  None,
            })
        except Exception as e:
            report["daily"].append({"title": comp["title"], "error": str(e)})

    # Monthly returns (month-end only)
    if is_last_day_of_month():
        print("📅 Month-end detected — collecting monthly returns…")
        monthly = []
        for comp in COMPARISONS:
            try:
                mret_a, month_lbl = get_fund_monthly_return(
                    comp["fund_a"]["amfi_code"], comp["fund_a"]["label"])
                mret_b, _         = get_fund_monthly_return(
                    comp["fund_b"]["amfi_code"], comp["fund_b"]["label"])
                monthly.append({
                    "title":  comp["title"],
                    "fund_a": {"short_label": comp["fund_a"]["short_label"],
                               "ret": mret_a, "winner": mret_a > mret_b},
                    "fund_b": {"short_label": comp["fund_b"]["short_label"],
                               "ret": mret_b, "winner": mret_b > mret_a},
                    "error":  None,
                })
                report["month_label"] = month_lbl
            except Exception as e:
                monthly.append({"title": comp["title"], "error": str(e)})
        report["monthly"] = monthly

    return report


# ── Infographic renderer ──────────────────────────────────────────────────────
def render_infographic(report: dict) -> bytes:
    """Render the report dict as a PNG infographic and return raw bytes."""

    # ── Pre-load fonts ────────────────────────────────────────────────────────
    f_title   = _find_font(30, bold=True)
    f_date    = _find_font(15)
    f_section = _find_font(12)
    f_idx_name = _find_font(13, bold=True)
    f_idx_val  = _find_font(20, bold=True)
    f_idx_pct  = _find_font(16, bold=True)
    f_idx_sub  = _find_font(11)
    f_comp_ttl = _find_font(14, bold=True)
    f_fund_lbl = _find_font(13)
    f_fund_ret = _find_font(14, bold=True)
    f_footer   = _find_font(11)

    # ── Layout constants ──────────────────────────────────────────────────────
    INNER_W    = IMG_W - 2 * PAD
    CARD_GAP   = 12
    CARD_W     = (INNER_W - 2 * CARD_GAP) // 3
    CARD_H     = 132
    ROW_H      = 24   # height per fund row
    COMP_TITLE_H = 26

    has_monthly = report.get("monthly") is not None

    def _comp_block_h(comps):
        h = 0
        for c in comps:
            h += COMP_TITLE_H + (55 if c.get("error") else 2 * ROW_H + 10)
        return h

    # ── Calculate total image height ──────────────────────────────────────────
    total_h = (
        100 +                                          # header
        16 +                                           # divider + gap
        22 + CARD_H + 20 +                             # index label + cards + gap
        16 +                                           # divider + gap
        22 + _comp_block_h(report.get("daily", [])) +  # daily label + blocks
        10 +                                           # gap
        16 +                                           # divider + gap
        (22 + _comp_block_h(report.get("monthly", [])) + 10 + 16
         if has_monthly else 0) +
        40 +                                           # footer
        PAD                                            # bottom padding
    )

    img  = Image.new("RGB", (IMG_W, total_h), C_BG)
    draw = ImageDraw.Draw(img)

    y = 0  # running cursor

    # ── Header ────────────────────────────────────────────────────────────────
    draw.rectangle([0, 0, IMG_W, 100], fill=C_CARD)
    draw.rectangle([0, 0, 5, 100], fill=C_BLUE)          # left accent bar
    draw.text((PAD + 10, 18), "DAILY DIP MONITOR",
              font=f_title, fill=C_BLUE)
    draw.text((PAD + 10, 62), report.get("date", ""),
              font=f_date, fill=C_SUBTEXT)
    y = 100

    # ── Divider ───────────────────────────────────────────────────────────────
    def _divider(yy):
        draw.line([(0, yy), (IMG_W, yy)], fill=C_BORDER, width=1)
        return yy + 15

    y = _divider(y)

    # ── NSE error (early exit) ────────────────────────────────────────────────
    if report.get("nse_error"):
        draw.text((PAD, y), f"NSE Error: {report['nse_error'][:80]}",
                  font=f_fund_lbl, fill=C_RED)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf.read()

    # ── Section label helper ──────────────────────────────────────────────────
    def _section_label(yy, text):
        draw.text((PAD, yy), text, font=f_section, fill=C_SUBTEXT)
        return yy + 22

    # ── Index cards ───────────────────────────────────────────────────────────
    y = _section_label(y, "INDEX STATUS")

    for i, idx in enumerate(report.get("indices", [])):
        cx = PAD + i * (CARD_W + CARD_GAP)
        cy = y

        # Card background + border
        draw.rounded_rectangle(
            [cx, cy, cx + CARD_W, cy + CARD_H],
            radius=8, fill=C_CARD, outline=C_BORDER, width=1,
        )

        if idx.get("error"):
            draw.text((cx + 12, cy + 12), idx.get("name", "?"),
                      font=f_idx_name, fill=C_TEXT)
            draw.text((cx + 12, cy + 38), "Data unavailable",
                      font=f_idx_sub, fill=C_RED)
        else:
            sig_col = idx["signal_color"]

            # Colored left accent bar inside card
            draw.rounded_rectangle(
                [cx + 1, cy + 1, cx + 5, cy + CARD_H - 1],
                radius=4, fill=sig_col,
            )

            # Index name
            draw.text((cx + 14, cy + 10), idx["name"],
                      font=f_idx_name, fill=C_TEXT)

            # Current value
            val_str = f"{idx['current']:,.2f}"
            draw.text((cx + 14, cy + 30), val_str,
                      font=f_idx_val, fill=C_TEXT)

            # Drop %
            drop_str = f"{idx['drop_pct']:+.2f}%"
            draw.text((cx + 14, cy + 62), drop_str,
                      font=f_idx_pct, fill=sig_col)
            draw.text((cx + 14, cy + 84), "from 52W high",
                      font=f_idx_sub, fill=C_SUBTEXT)

            # Signal text
            draw.text((cx + 14, cy + 106), idx["signal_text"],
                      font=f_idx_sub, fill=sig_col)

    y += CARD_H + 20
    y = _divider(y)

    # ── Comparison block renderer ─────────────────────────────────────────────
    def _draw_comparisons(yy, comps, bg_toggle=False):
        for ci, comp in enumerate(comps):
            # Alternating card background
            block_h = (COMP_TITLE_H + 55 if comp.get("error")
                       else COMP_TITLE_H + 2 * ROW_H + 10)
            bg = C_CARD2 if ci % 2 == 0 else C_CARD
            draw.rounded_rectangle(
                [PAD, yy, IMG_W - PAD, yy + block_h],
                radius=6, fill=bg, outline=C_BORDER, width=1,
            )

            # Title
            draw.text((PAD + 12, yy + 6), comp["title"],
                      font=f_comp_ttl, fill=C_TEXT)
            yy += COMP_TITLE_H

            if comp.get("error"):
                draw.text((PAD + 12, yy + 4),
                          f"Error: {comp['error'][:70]}",
                          font=f_footer, fill=C_RED)
                yy += 55
            else:
                for fund_key in ("fund_a", "fund_b"):
                    fund    = comp[fund_key]
                    ret_str = f"{fund['ret']:+.2f}%"
                    lbl_col = C_TEXT
                    ret_col = C_GOLD if fund["winner"] else C_TEXT

                    # Fund label (left)
                    draw.text((PAD + 20, yy + 4), fund["short_label"],
                              font=f_fund_lbl, fill=lbl_col)

                    # Return value (right-aligned)
                    rw = _text_w(draw, ret_str, f_fund_ret)
                    star_offset = 22 if fund["winner"] else 0
                    draw.text(
                        (IMG_W - PAD - rw - star_offset - 12, yy + 4),
                        ret_str, font=f_fund_ret, fill=ret_col,
                    )

                    # Winner star
                    if fund["winner"]:
                        draw.text(
                            (IMG_W - PAD - star_offset + 4, yy + 4),
                            "★", font=f_fund_ret, fill=C_GOLD,
                        )

                    yy += ROW_H
                yy += 10  # gap after each comparison block

        return yy

    # ── Daily returns ─────────────────────────────────────────────────────────
    y = _section_label(y, "TODAY'S FUND RETURNS  —  Active vs Momentum")
    y = _draw_comparisons(y, report.get("daily", []))
    y += 10
    y = _divider(y)

    # ── Monthly returns (month-end only) ──────────────────────────────────────
    if has_monthly:
        month_lbl = report.get("month_label", "")
        y = _section_label(y, f"MONTHLY RETURNS  ({month_lbl} → today)")
        y = _draw_comparisons(y, report.get("monthly", []))
        y += 10
        y = _divider(y)

    # ── Footer ────────────────────────────────────────────────────────────────
    draw.text((PAD, y),
              "Source: NSE India  ·  AMFI via mfapi.in",
              font=f_footer, fill=C_SUBTEXT)
    draw.text((PAD, y + 16),
              "Not financial advice.",
              font=f_footer, fill=C_SUBTEXT)

    # ── Encode to PNG bytes ───────────────────────────────────────────────────
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()


# ── Text-message fallback (used when Pillow is unavailable) ──────────────────
def build_text_message(report: dict) -> str:
    lines = [
        "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
        "📊 *DAILY DIP MONITOR*",
        f"_🗓 {report.get('date', '')}_",
        "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n",
    ]

    if report.get("nse_error"):
        lines.append(f"❌ NSE connection failed: {report['nse_error']}")
        return "\n".join(lines)

    for idx in report.get("indices", []):
        if idx.get("error"):
            lines += [f"*{idx['name']}*", f"  ❌ {idx['error']}", ""]
        else:
            trend = "📉" if idx["drop_pct"] < 0 else "📈"
            lines += [
                f"*{idx['name']}*  _· {idx['fund']}_",
                f"  `{idx['current']:>12,.2f}`  {trend} `{idx['drop_pct']:+.2f}%` from 52W high",
                f"  {idx['signal_text']}",
                "",
            ]

    lines += [
        "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
        "💹 *TODAY'S FUND RETURNS*",
        "_Active vs Momentum — who won today?_",
        "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n",
    ]

    for comp in report.get("daily", []):
        lines.append(f"*🔄 {comp['title']}*")
        if comp.get("error"):
            lines += [f"  ❌ {comp['error']}", ""]
        else:
            fa, fb = comp["fund_a"], comp["fund_b"]
            lines += [
                f"  ▸ {fa['short_label']}  `{fa['ret']:+.2f}%`{'  🏆' if fa['winner'] else ''}",
                f"  ▸ {fb['short_label']}  `{fb['ret']:+.2f}%`{'  🏆' if fb['winner'] else ''}",
                "",
            ]

    if report.get("monthly"):
        lines += [
            "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
            f"📅 *MONTHLY RETURNS*  _({report.get('month_label', '')} → today)_",
            "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n",
        ]
        for comp in report["monthly"]:
            lines.append(f"*🔄 {comp['title']}*")
            if comp.get("error"):
                lines += [f"  ❌ {comp['error']}", ""]
            else:
                fa, fb = comp["fund_a"], comp["fund_b"]
                lines += [
                    f"  ▸ {fa['short_label']}  `{fa['ret']:+.2f}%`{'  🏆' if fa['winner'] else ''}",
                    f"  ▸ {fb['short_label']}  `{fb['ret']:+.2f}%`{'  🏆' if fb['winner'] else ''}",
                    "",
                ]

    lines += [
        "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
        "_Source: NSE India · AMFI via mfapi.in_",
        "_Not financial advice._",
    ]
    return "\n".join(lines)


# ── Telegram: send photo ──────────────────────────────────────────────────────
def send_telegram_photo(image_bytes: bytes, bot_token: str, chat_ids: list) -> bool:
    url     = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    success = False
    for chat_id in chat_ids:
        chat_id = chat_id.strip()
        if not chat_id:
            continue
        try:
            resp = requests.post(
                url,
                data={"chat_id": chat_id},
                files={"photo": ("dip_monitor.png", image_bytes, "image/png")},
                timeout=30,
            )
            if resp.status_code == 200:
                print(f"✅ Photo sent to {chat_id}")
                success = True
            else:
                print(f"❌ Photo failed for {chat_id}: {resp.text}")
        except Exception as e:
            print(f"❌ Photo error for {chat_id}: {e}")
    return success


# ── Telegram: send text (fallback) ───────────────────────────────────────────
def send_telegram_text(message: str, bot_token: str, chat_ids: list) -> bool:
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
                print(f"✅ Text sent to {chat_id}")
                success = True
            else:
                print(f"❌ Text failed for {chat_id}: {resp.text}")
        except Exception as e:
            print(f"❌ Text error for {chat_id}: {e}")
    return success


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    BOT_TOKEN    = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    CHAT_IDS_RAW = os.environ.get("TELEGRAM_CHAT_IDS", "")

    if not BOT_TOKEN or not CHAT_IDS_RAW:
        print("ERROR: Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_IDS env vars.")
        exit(1)

    CHAT_IDS = [c.strip() for c in CHAT_IDS_RAW.split(",") if c.strip()]

    print("Fetching data…")
    report = collect_report_data()

    if PIL_AVAILABLE:
        print("Rendering infographic…")
        try:
            image_bytes = render_infographic(report)
            print(f"Sending infographic to {len(CHAT_IDS)} chat(s)…")
            ok = send_telegram_photo(image_bytes, BOT_TOKEN, CHAT_IDS)
        except Exception as e:
            print(f"⚠️ Infographic render failed ({e}), falling back to text…")
            ok = send_telegram_text(build_text_message(report), BOT_TOKEN, CHAT_IDS)
    else:
        print(f"Sending text to {len(CHAT_IDS)} chat(s)…")
        ok = send_telegram_text(build_text_message(report), BOT_TOKEN, CHAT_IDS)

    if ok:
        print("✅ Done!")
    else:
        print("❌ All sends failed.")
        exit(1)
