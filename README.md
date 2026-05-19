# 📊 Buy-the-Dip Alert — Mutual Fund Monitor

An automated daily alert system that monitors **Nifty 50**, **Nifty Midcap 150**, and **Nifty Smallcap 250** indices and sends a formatted message to **Telegram** every weekday after market close.

Data is sourced directly from **NSE India's official API** — the same numbers shown on [nseindia.com](https://www.nseindia.com). No third-party data providers.

---

## 💡 Strategy

Based on the "buy the dip" approach for mutual fund investing:

- Continue your regular SIP regardless of market level
- When the index drops significantly from its 52-week high, deploy additional lump sum amounts on top of your SIP
- The alert tells you exactly how far each index is from its 52-week high so you can decide

---

## 📁 Project Structure

```
your-repo/
├── market_alert.py                  ← Main script (data + Telegram)
├── requirements.txt                 ← Python dependencies
└── .github/
    └── workflows/
        └── market_alert.yml         ← GitHub Actions schedule
```

---

## ⚙️ How It Works

```
GitHub Actions (cron)
      │
      ▼
market_alert.py runs
      │
      ├─→ Visits nseindia.com (gets session cookies)
      │
      ├─→ Calls NSE allIndices API
      │         Returns: current price, yearHigh, yearLow
      │         for every NSE index in one request
      │
      ├─→ Computes drop % from 52W high for each index
      │
      └─→ Sends formatted message to Telegram
                ├─ Your personal chat
                └─ Your channel (all subscribers see it)
```

---

## 🚀 Setup Guide

### Step 1 — Create a Telegram Bot

1. Open Telegram → search **@BotFather** → tap **Start**
2. Send `/newbot`
3. Give it a name (e.g. `Market Dip Alert`) and a username (e.g. `my_dip_monitor_bot`)
4. Copy the **Bot Token** (looks like `123456789:ABCdef...`)

> ⚠️ Keep this token private. Anyone with it can use your bot.

---

### Step 2 — Get Your Personal Chat ID

1. Search **@userinfobot** on Telegram → tap **Start**
2. It replies with your **Chat ID** (a number like `########`)
3. Open your new bot and send it `/start` — this is mandatory before the bot can message you

---

### Step 3 — Create a Telegram Channel (for sharing with friends)

1. Telegram → **New Channel**
2. Name it (e.g. `Buy_Dip_Alert_MutualFund`)
3. Set visibility: **Public** (easy sharing) or **Private** (invite-only)
4. Add your bot as **Admin**:
   - Open the channel → tap name → **Administrators → Add Administrator**
   - Search your bot → add it → enable **"Post Messages"** → Done
5. Get the channel ID:
   - **Public channel**: use `@channel_username`
   - **Private channel**: forward any channel message to `@userinfobot` → it gives `-100xxxxxxxxxx`

Friends simply **join the channel** — no setup needed on their end.

---

### Step 4 — Create GitHub Repository

1. Go to [github.com](https://github.com) → **New repository**
2. Name: `Automating-buy-the-dip-alert-for-mutual-fund` (or any name)
3. Set to **Private** → Create
4. Upload these files maintaining the exact folder structure:
   - `market_alert.py` → root
   - `requirements.txt` → root
   - `.github/workflows/market_alert.yml` → create folders as you type the path

---

### Step 5 — Add Secrets to GitHub

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret Name | Value | Example |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Your bot token from Step 1 | `123456789:ABCdef...` |
| `TELEGRAM_CHAT_IDS` | Comma-separated list of chat IDs | `7######9,-1###########9` |

For `TELEGRAM_CHAT_IDS`:
- Personal chat ID: just the number (e.g. `7#######9`)
- Public channel: `@channel_username`
- Private channel: `-100xxxxxxxxxx`
- Multiple: separate with commas — `7#######9,-1############3`

---

### Step 6 — Test It

1. Go to your repo → **Actions** tab
2. Click **Daily Market Dip Alert** → **Run workflow** → **Run workflow**
3. Wait ~30 seconds → check Telegram

✅ You should receive the full market data message in your chat and channel.

---

## 📱 Sample Message

```
━━━━━━━━━━━━━━━━━━━━━━
📊 DAILY DIP MONITOR
🗓 14 May 2026  |  04:30 PM IST
━━━━━━━━━━━━━━━━━━━━━━

🏦 Nifty 50
  Fund  : Large Cap Index
  Now   : 23,412.60
  52W ↑ : 26,373.20  (-2,960.60 pts  |  -11.23%)
  52W ↓ : 22,182.55  (+1,230.05 pts  |  +5.55%)
  💡 🟠 Medium dip — Good opportunity (~2–3x SIP)

📈 Nifty Midcap 150
  Fund  : Edelweiss Mid Cap
  Now   : 22,096.50
  52W ↑ : 22,846.70  (-750.20 pts  |  -3.28%)
  52W ↓ : 19,218.00  (+2,878.50 pts  |  +14.98%)
  💡 🟢 Near 52W high — Stick to regular SIP

🚀 Nifty Smallcap 250
  Fund  : Nippon Small Cap
  Now   : 16,735.80
  52W ↑ : 18,077.35  (-1,341.55 pts  |  -7.42%)
  52W ↓ : 14,143.45  (+2,592.35 pts  |  +18.33%)
  💡 🟡 Minor dip — Consider small lump sum (~1x SIP)

━━━━━━━━━━━━━━━━━━━━━━
Dip Guide
🟢 < 5%   → Regular SIP only
🟡 5–9%   → Small lump sum
🟠 10–14% → Medium lump sum
🔴 15–19% → Large lump sum
🚨 20%+   → Max lump sum
━━━━━━━━━━━━━━━━━━━━━━
Data via NSE India (official). Not financial advice.
```

---

## 🕐 Schedule

The workflow runs automatically **Monday–Friday at 4:30 PM IST** (11:00 AM UTC).

NSE market closes at 3:30 PM IST. The 30-minute buffer ensures today's closing data is published before the script runs.

To change the schedule, edit the cron in `market_alert.yml`:

```yaml
- cron: '00 11 * * 1-5'   # 4:30 PM IST = 11:00 AM UTC
```

Use [crontab.guru](https://crontab.guru) to calculate UTC times.

> ⚠️ GitHub disables scheduled workflows after **60 days of repo inactivity**. The `keep-alive` job in `market_alert.yml` commits a small file every Monday to prevent this.

---

## 🔧 Customization

### Change dip thresholds

Edit `DIP_LEVELS` in `market_alert.py`:

```python
DIP_LEVELS = [
    (5,  "🟡 Minor dip  — Consider small lump sum (~1x SIP)"),
    (10, "🟠 Medium dip — Good opportunity (~2–3x SIP)"),
    (15, "🔴 Deep dip   — Strong buy signal (~5x SIP)"),
    (20, "🚨 Crash zone — Max lump sum if available!"),
]
```

### Add more indices

Edit `INDICES` in `market_alert.py`. The `nse_index` value must match NSE's `indexSymbol` exactly:

```python
"💰 Nifty Next 50": {
    "nse_index": "NIFTY NEXT 50",
    "fund":      "Your Fund Name",
},
```

Common NSE index symbols:

| Index | nse_index value |
|---|---|
| Nifty 50 | `NIFTY 50` |
| Nifty Midcap 150 | `NIFTY MIDCAP 150` |
| Nifty Smallcap 250 | `NIFTY SMLCAP 250` |
| Nifty Next 50 | `NIFTY NEXT 50` |
| Nifty Bank | `NIFTY BANK` |
| Nifty IT | `NIFTY IT` |

### Add more recipients

Just append to `TELEGRAM_CHAT_IDS` in GitHub Secrets (comma-separated):
```
764480409,-1003996983943,@another_channel
```

---

## ❓ Troubleshooting

| Issue | Likely Cause | Fix |
|---|---|---|
| No message received (personal) | Haven't sent `/start` to bot | Open bot → send `/start` |
| No message in channel | Bot not admin of channel | Add bot as admin with Post Messages permission |
| `NSE connection failed` | NSE blocked GitHub IP temporarily | Re-run workflow; usually resolves itself |
| Index not found error | Wrong `nse_index` symbol | Check exact symbol in NSE API response |
| Workflow not running on schedule | GitHub disabled it after 60 days | The keep-alive job prevents this automatically |

---

## 🛠 Tech Stack

| Component | Tool | Cost |
|---|---|---|
| Data source | NSE India official API | Free |
| Notifications | Telegram Bot API | Free |
| Scheduling & hosting | GitHub Actions | Free (2000 min/month) |
| Language | Python 3.11 | Free |
| Dependencies | `requests`, `pytz` | Free |

**Total cost: ₹0/month** — entirely free, forever.

---

## 📌 Indices Tracked

| Index | NSE Symbol | Mapped Fund |
|---|---|---|
| Nifty 50 | `NIFTY 50` | Large Cap / Index funds |
| Nifty Midcap 150 | `NIFTY MIDCAP 150` | Edelweiss Mid Cap |
| Nifty Smallcap 250 | `NIFTY SMLCAP 250` | Nippon Small Cap |

---

*Not financial advice. Do your own research before investing.*
