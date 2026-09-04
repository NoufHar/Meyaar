import json
import os
import re
import tempfile
import wave
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq


load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def generate_audio_report_text(
    dataset,
    validation,
    quality_summary,
    report,
):
    """
    Generate a spoken version of the Meyaar report.
    """

    prompt = f"""
حوّل تقييم Meyaar إلى تقرير صوتي عربي واضح ومهني.

الهدف:
أن يفهم المستخدم أهم محتوى التقرير بدون الحاجة إلى قراءة ملف PDF.

استخدم:
- dataset لمعلومات البيانات.
- validation للأرقام ونتائج القواعد ودرجات الخطورة.
- quality_summary لأبعاد الجودة.
- report للتفسير والتوصيات.

غطِّ:
- نتيجة التقييم العامة.
- نوع البيانات ونظام الإحداثيات.
- إجمالي الحالات التي تحتاج إلى مراجعة.
- أبعاد الجودة المتأثرة.
- أهم نتائج قواعد التحقق وأعدادها.
- معنى النتائج باختصار.
- هل تم تنفيذ تصحيح أو إعادة تحقق.
- أهم التوصيات.
- تنبيه مختصر بأن Meyaar لا يمثل اعتمادًا رسميًا من GeoSA.

قواعد:
- لا تخترع معلومات أو أرقام.
- لا تغير الأرقام.
- لا تعتبر النتائج أخطاء أو مخالفات مؤكدة.
- Severity تصنيف داخلي في Meyaar.
- لا تقرأ run_id أو Rule ID.
- لا تكرر المعلومات.
- لا تستخدم أسلوب محادثة.
- اكتب نصًا عربيًا مترابطًا ومناسبًا للاستماع.
- أرجع نصًا متصلًا مخصصًا للنطق فقط، بدون عنوان أو Markdown أو نقاط أو قوائم.
- استخدم report فقط للتوصيات ولا تضف توصيات من عندك.

DATASET:
{json.dumps(dataset, ensure_ascii=False, default=str)}

VALIDATION:
{json.dumps(validation, ensure_ascii=False, default=str)}

QUALITY SUMMARY:
{json.dumps(quality_summary, ensure_ascii=False, default=str)}

REPORT:
{json.dumps(report, ensure_ascii=False, default=str)}
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        temperature=0,
        max_completion_tokens=1200,
    )

    text = response.choices[0].message.content

    if not text:
        raise ValueError("Failed to generate audio report.")

    return text.strip()


def split_text(text, max_chars=190):
    """
    Split text into TTS-safe chunks.
    """

    sentences = re.split(
        r"(?<=[.!؟])\s+",
        text.strip(),
    )

    chunks = []
    current = ""

    for sentence in sentences:
        candidate = f"{current} {sentence}".strip()

        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)

            current = sentence

    if current:
        chunks.append(current)

    return chunks


def create_tts_chunk(
    text,
    output_path,
    voice="lulwa",
):
    """
    Convert one text chunk to WAV.
    """

    response = client.audio.speech.create(
        model="canopylabs/orpheus-arabic-saudi",
        voice=voice,
        input=text,
        response_format="wav",
    )

    response.write_to_file(output_path)


def merge_wav_files(files, output_path):
    """
    Merge WAV chunks.
    """

    with wave.open(str(files[0]), "rb") as first:
        channels = first.getnchannels()
        sample_width = first.getsampwidth()
        frame_rate = first.getframerate()

    with wave.open(str(output_path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(sample_width)
        output.setframerate(frame_rate)

        for file in files:
            with wave.open(str(file), "rb") as wav_file:
                output.writeframes(
                    wav_file.readframes(
                        wav_file.getnframes()
                    )
                )


def create_audio_summary(
    dataset,
    validation,
    quality_summary,
    report,
    output_path="outputs/MEYAAR_Summary.wav",
    voice="lulwa",
):
    """
    Create the final Meyaar audio report.
    """

    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    audio_text = generate_audio_report_text(
        dataset=dataset,
        validation=validation,
        quality_summary=quality_summary,
        report=report,
    )

    chunks = split_text(audio_text)

    if not chunks:
        raise ValueError(
            "No audio text was generated."
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)

        wav_files = []

        for index, chunk in enumerate(
            chunks,
            start=1,
        ):
            chunk_path = (
                temp_dir
                / f"chunk_{index}.wav"
            )

            create_tts_chunk(
                text=chunk,
                output_path=chunk_path,
                voice=voice,
            )

            wav_files.append(chunk_path)

        merge_wav_files(
            files=wav_files,
            output_path=output_path,
        )

    return {
        "status": "success",
        "audio_text": audio_text,
        "audio_path": str(output_path),
    }