import osimport os
import timeimport time
import requestsimport requests
from datetime import datetimefrom datetime import datetime
import pytzimport pytz

# ── Telegram ──────────────────────────────────────────────────────────────────
def send_telegram(message: str, bot_token: str, chat_ids: list[str]) -> bool:
    """
    Send message to multiple Telegram chats/groups/channels.
    Returns True if at least one send succeeds.
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    success = False

    for chat_id in chat_ids:
        chat_id = chat_id.strip()

        if not chat_id:
            continue

        try:
            resp = requests.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                },
                timeout=15,
            )

            if resp.status_code == 200:
                print(f"✅ Sent to {chat_id}")
                success = True
            else:
                print(f"❌ Telegram error for {chat_id}")
                print(resp.text)

        except Exception as e:
            print(f"❌ Failed for {chat_id}: {e}")

    return success


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    # comma-separated IDs
    CHAT_IDS_RAW = os.environ.get("TELEGRAM_CHAT_IDS", "")

    if not BOT_TOKEN or not CHAT_IDS_RAW:
        print("ERROR: Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_IDS env vars.")
        exit(1)

    # Convert comma-separated string into list
    CHAT_IDS = [cid.strip() for cid in CHAT_IDS_RAW.split(",") if cid.strip()]

    print("Fetching index data from NSE India…")
    message = build_message()
    print(message)

    print("\nSending to Telegram chats…")

    if send_telegram(message, BOT_TOKEN, CHAT_IDS):
        print("✅ Alert sent successfully!")
    else:
        print("❌ Failed to send to all chats.")
        exit(1)
