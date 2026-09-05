import os
from pathlib import Path

import requests
from dotenv import load_dotenv


# =========================================================
# Environment
# =========================================================

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def _check_token():
    """Make sure Telegram bot token exists."""
    if not BOT_TOKEN:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN is missing from .env"
        )


# =========================================================
# Get Chat ID
# =========================================================

def get_chat_id():
    """
    Get the latest chat ID from Telegram.

    This is mainly useful during the initial setup.
    After TELEGRAM_CHAT_ID is saved in .env,
    Meyaar will use the saved ID directly.
    """

    _check_token()

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"

    response = requests.get(
        url,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    if not data.get("result"):
        raise ValueError(
            "No Telegram messages found. "
            "Open the Meyaar bot, press Start, send Hi, "
            "then try again."
        )

    latest_update = data["result"][-1]

    message = (
        latest_update.get("message")
        or latest_update.get("edited_message")
    )

    if not message:
        raise ValueError(
            "Could not find a Telegram message containing a chat ID."
        )

    return str(message["chat"]["id"])


# =========================================================
# Resolve Chat ID
# =========================================================

def _resolve_chat_id(chat_id=None):
    """
    Priority:
    1. Explicit chat_id
    2. TELEGRAM_CHAT_ID from .env
    3. getUpdates fallback
    """

    if chat_id:
        return str(chat_id)

    if CHAT_ID:
        return str(CHAT_ID)

    return get_chat_id()


# =========================================================
# Send Text Message
# =========================================================

def send_message(message, chat_id=None):
    """Send a text message from Meyaar to Telegram."""

    _check_token()

    chat_id = _resolve_chat_id(chat_id)

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    response = requests.post(
        url,
        data={
            "chat_id": chat_id,
            "text": message,
        },
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# Send Audio Summary
# =========================================================

def send_voice(
    audio_path,
    chat_id=None,
    caption="Meyaar Analysis Summary",
):
    """
    Send Meyaar's generated MP3 audio summary to Telegram.
    """

    _check_token()

    chat_id = _resolve_chat_id(chat_id)

    audio_path = Path(audio_path)

    if not audio_path.exists():
        raise FileNotFoundError(
            f"Audio file not found: {audio_path}"
        )

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendAudio"

    with audio_path.open("rb") as audio_file:

        response = requests.post(
            url,
            data={
                "chat_id": chat_id,
                "caption": caption,
            },
            files={
                "audio": (
                    audio_path.name,
                    audio_file,
                    "audio/mpeg",
                )
            },
            timeout=60,
        )

    response.raise_for_status()

    return response.json()


# =========================================================
# Test
# =========================================================

if __name__ == "__main__":

    chat_id = _resolve_chat_id()

    print(f"Telegram chat_id: {chat_id}")

    send_voice(
        "outputs/MEYAAR_Buildings_Audio.mp3",
        chat_id=chat_id,
        caption="Meyaar Buildings Analysis Summary",
    )

    print("Audio summary sent successfully.")