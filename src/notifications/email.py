import html
import os
from pathlib import Path

import resend
from dotenv import load_dotenv

load_dotenv()

resend.api_key=os.getenv("RESEND_API_KEY")
RESEND_FROM=os.getenv("RESEND_FROM","Meyaar <onboarding@resend.dev>")


def _quality_html(quality_summary:dict|None)->str:
    if not quality_summary:
        return ""

    summary=quality_summary.get("summary",{})
    return f"""
    <h3>ملخص الجودة</h3>
    <p>
        نتائج ناجحة: <strong>{summary.get('pass',0)}</strong><br>
        نتائج تحتاج مراجعة: <strong>{summary.get('fail',0)}</strong><br>
        غير مقيمة: <strong>{summary.get('not_evaluated',0)}</strong>
    </p>
    """


def _revalidation_html(revalidation:dict|None)->str:
    if not revalidation:
        return "<p>لم يتم تنفيذ إعادة تحقق ضمن هذه النتيجة.</p>"

    comparison=revalidation.get("comparison",revalidation).get("summary",{})
    if not comparison:
        return "<p>تم تسجيل إعادة تحقق، ولا يتوفر ملخص مقارنة.</p>"

    return f"""
    <h3>إعادة التحقق</h3>
    <p>
        تم حلها: <strong>{comparison.get('resolved',0)}</strong><br>
        ما زالت موجودة: <strong>{comparison.get('still_present',0)}</strong><br>
        نتائج جديدة: <strong>{comparison.get('new_issues',0)}</strong>
    </p>
    """


def send_analysis_email(
    to_email:str,
    filename:str,
    report_path:str|None=None,
    audio_path:str|None=None,
    quality_summary:dict|None=None,
    revalidation:dict|None=None,
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

    safe_filename=html.escape(filename)

    return resend.Emails.send({
        "from":RESEND_FROM,
        "to":[to_email],
        "subject":f"نتائج تحليل معيار - {filename}",
        "html":f"""
        <div dir="rtl" style="font-family:Arial,sans-serif;line-height:1.8">
            <h2>اكتمل تحليل معيار</h2>
            <p>تم الانتهاء من تحليل الملف <strong>{safe_filename}</strong>.</p>
            {_quality_html(quality_summary)}
            {_revalidation_html(revalidation)}
            <p>أرفقنا التقرير والملخص الصوتي عند توفرهما.</p>
            <p style="color:#666;font-size:12px">
                نتائج Meyaar تدعم تقييم الجودة المتوافق مع متطلبات GeoSA،
                ولا تمثل اعتمادًا أو شهادة رسمية من GeoSA.
            </p>
            <p>مع تحيات،<br>فريق معيار</p>
        </div>
        """,
        "attachments":attachments,
    })
