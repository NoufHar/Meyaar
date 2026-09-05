import os

import requests
from dotenv import load_dotenv


load_dotenv()

ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v23.0")


def upload_audio(audio_path: str) -> str:
    url = f"https://graph.facebook.com/{API_VERSION}/{PHONE_NUMBER_ID}/media"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }

    with open(audio_path, "rb") as audio_file:
        files = {
            "file": (
                os.path.basename(audio_path),
                audio_file,
                "audio/mpeg",
            )
        }

        data = {
            "messaging_product": "whatsapp",
            "type": "audio/mpeg",
        }

        response = requests.post(
            url,
            headers=headers,
            files=files,
            data=data,
            timeout=60,
        )

    print("UPLOAD STATUS:", response.status_code)
    print("UPLOAD RESPONSE:", response.text)

    response.raise_for_status()

    return response.json()["id"]


def send_audio(phone_number: str, media_id: str):
    url = f"https://graph.facebook.com/{API_VERSION}/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "audio",
        "audio": {
            "id": media_id
        },
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=60,
    )

    print("SEND STATUS:", response.status_code)
    print("SEND RESPONSE:", response.text)

    response.raise_for_status()

    return response.json()


def send_audio_summary(audio_path: str, phone_number: str):
    media_id = upload_audio(audio_path)

    return send_audio(
        phone_number=phone_number,
        media_id=media_id,
    )


def send_template(phone_number: str):
    url = f"https://graph.facebook.com/{API_VERSION}/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "template",
        "template": {
            "name": "meyaar_summary_ready",
            "language": {
                "code": "en"
            },
        },
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=60,
    )

    print("TEMPLATE STATUS:", response.status_code)
    print("TEMPLATE RESPONSE:", response.text)

    response.raise_for_status()

    return response.json()