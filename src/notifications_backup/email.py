import os
from pathlib import Path

import resend
from dotenv import load_dotenv

load_dotenv()

resend.api_key=os.getenv("RESEND_API_KEY")
RESEND_FROM=os.getenv(
    "RESEND_FROM",
    "Meyaar <onboarding@resend.dev>",
)


def send_analysis_email(
    to_email:str,
    filename:str,
    report_path:str|None=None,
    audio_path:str|None=None,
):
    attachments=[]

    for file_path in [report_path,audio_path]:
        if not file_path:
            continue

        path=Path(file_path)

        if path.exists():
            attachments.append({
                "filename":path.name,
                "content":list(path.read_bytes()),
            })

    return resend.Emails.send({
        "from":RESEND_FROM,
        "to":[to_email],
        "subject":f"نتائج تحليل معيار - {filename}",
        "html":f"""
        <div dir="rtl" style="font-family:Arial,sans-serif">
            <h2>مرحبًا،</h2>

            <p>
                اكتمل تحليل الملف
                <strong>{filename}</strong>
                بنجاح عبر منصة معيار.
            </p>

            <p>
                تم إرفاق نتائج التحليل المتاحة مع هذه الرسالة.
            </p>

            <p>
                يمكنك أيضًا الرجوع إلى التحليل لاحقًا
                من سجل التحليلات في حسابك على منصة معيار.
            </p>

            <p>
                مع تحيات،<br>
                فريق معيار
            </p>
        </div>
        """,
        "attachments":attachments,
    })