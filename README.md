# 📊 Daily Market Dip Monitor

Tracks **Nifty 50**, **Nifty Midcap 150**, **Nifty Smallcap 250** daily and
sends a Telegram alert comparing current index level to 52-week high/low —
so you always know when to deploy a lump sum on the dip.

---

## 📁 Project Structure

```
market_dip_monitor/
├── market_alert.py              ← Main Python script
├── requirements.txt             ← Python dependencies
└── .github/
    └── workflows/
        └── market_alert.yml     ← GitHub Actions schedule
```

---

## ⚙️ Setup Guide (One-Time)

### Step 1 — Create a Telegram Bot

1. Open Telegram → search **@BotFather** → tap **Start**
2. Send `/newbot` → give it any name (e.g., `My Market Alert`)
3. Copy the **Bot Token** (looks like `123456:ABCdef...`)

### Step 2 — Get Your Telegram Chat ID

1. Search **@userinfobot** on Telegram → tap **Start**
2. It will reply with your **Chat ID** (a number like `987654321`)
3. Now **open your new bot** and send it `/start` (important — must do this!)

### Step 3 — Create GitHub Repository

1. Go to [github.com](https://github.com) → **New repository**
2. Name it: `market-dip-monitor` → set to **Private** → Create
3. Upload these files (drag & drop or use Git):
   - `market_alert.py`
   - `requirements.txt`
   - `.github/workflows/market_alert.yml`

### Step 4 — Add Secrets to GitHub

In your GitHub repo:
1. Go to **Settings → Secrets and variables → Actions**
2. Click **New repository secret** → add these two:

| Secret Name            | Value                         |
|------------------------|-------------------------------|
| `TELEGRAM_BOT_TOKEN`   | Your bot token from Step 1    |
| `TELEGRAM_CHAT_ID`     | Your chat ID from Step 2      |

### Step 5 — Test It Manually

1. Go to your repo → **Actions** tab
2. Click **Daily Market Dip Alert** → **Run workflow** → **Run workflow**
3. Check Telegram for the alert within ~60 seconds ✅

---

## 🕐 Schedule

The script auto-runs **Monday–Friday at 4:00 PM IST** (after NSE closes at 3:30 PM).

To change timing, edit the cron in `market_alert.yml`:
```
'30 10 * * 1-5'   →  10:30 AM UTC = 4:00 PM IST
```
Use https://crontab.guru to adjust.

---

## 📱 Sample Telegram Message

```
━━━━━━━━━━━━━━━━━━━━━━
📊 DAILY DIP MONITOR
🗓 12 May 2026  |  04:00 PM IST
━━━━━━━━━━━━━━━━━━━━━━

🏦 Nifty 50
  Fund  : Large Cap Index
  Now   : 24,250.00
  52W ↑ : 26,277.35  (-2,027.35 pts  |  -7.71%)
  52W ↓ : 21,964.60  (+2,285.40 pts  |  +10.41%)
  💡 🟡 Minor dip — Consider small lump sum (~1x SIP amount)

📈 Nifty Midcap 150
  Fund  : Edelweiss Mid Cap
  Now   : 19,840.00
  52W ↑ : 23,778.00  (-3,938.00 pts  |  -16.56%)
  52W ↓ : 16,700.00  (+3,140.00 pts  |  +18.80%)
  💡 🔴 Deep dip — Strong buy signal (~5x SIP amount)

🚀 Nifty Smallcap 250
  Fund  : Nippon Small Cap
  Now   : 17,350.00
  52W ↑ : 22,500.00  (-5,150.00 pts  |  -22.89%)
  52W ↓ : 15,100.00  (+2,250.00 pts  |  +14.90%)
  💡 🚨 Crash zone — Max lump sum if available!

━━━━━━━━━━━━━━━━━━━━━━
Dip Guide
🟢 < 5% drop  → Regular SIP only
🟡 5–9% drop  → Small lump sum
🟠 10–14% drop → Medium lump sum
🔴 15–19% drop → Large lump sum
🚨 20%+ drop  → Max lump sum
━━━━━━━━━━━━━━━━━━━━━━
```

---

## 🔧 Customization

**Change dip thresholds** — edit `DIP_LEVELS` in `market_alert.py`:
```python
DIP_LEVELS = [
    (5,  "🟡 Minor dip  — Consider small lump sum"),
    (10, "🟠 Medium dip — Good opportunity"),
    (15, "🔴 Deep dip   — Strong buy signal"),
    (20, "🚨 Crash zone — Max lump sum!"),
]
```

**Add more indices** — edit `INDICES` in `market_alert.py`:
```python
"💰 Nifty Next 50": {"ticker": "^NIFTYJR", "fund": "Your Fund Name"},
```

---

## ❓ Troubleshooting

| Issue | Fix |
|-------|-----|
| No message received | Make sure you sent `/start` to your bot first |
| Data fetch error | Verify ticker on finance.yahoo.com (search `^NSEI`) |
| Workflow not running | Check Actions tab → enable workflows if prompted |
| Wrong time zone | Adjust cron using https://crontab.guru |

---

## 📌 Index Tickers Used (Yahoo Finance)

| Index | Ticker | Mapped Fund |
|-------|--------|-------------|
| Nifty 50 | `^NSEI` | Large Cap / Index funds |
| Nifty Midcap 150 | `^NIFMDCP150` | Edelweiss Mid Cap |
| Nifty Smallcap 250 | `^NIFSMCP250` | Nippon Small Cap |

---

*Data sourced from Yahoo Finance via yfinance. This is not financial advice.*
