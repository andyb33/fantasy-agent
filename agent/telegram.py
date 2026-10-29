"""Send messages to your Telegram bot chat."""
import os

from .net import request


def send(text):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat = os.environ["TELEGRAM_CHAT_ID"]
    for i in range(0, len(text), 4000):  # Telegram's limit is 4096 characters
        status, body = request(f"https://api.telegram.org/bot{token}/sendMessage",
                               data={"chat_id": chat, "text": text[i:i + 4000],
                                     "disable_web_page_preview": "true"})
        if status != 200:
            raise RuntimeError(f"Telegram send failed (HTTP {status}): {body[:200]!r}")
