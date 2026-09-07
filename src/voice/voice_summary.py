import json
import os
import re
import subprocess
import tempfile
import wave
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq
from gtts import gTTS

load_dotenv()

client=Groq(api_key=os.getenv("GROQ_API_KEY"))


def generate_audio_report_text(dataset,validation,quality_summary,report):
    input_type=dataset.get(
        "input_type",
        validation.get("input_type","vector"),
    )

    if input_type=="image":
        input_context="""
نوع المدخل هو صورة خريطة.

تعليمات خاصة بالصور:
- صف المدخل بأنه صورة أو صورة خريطة.
- لا تذكر عدد المعالم أو feature count.
- لا تذكر نظام الإحداثيات CRS.
- لا تذكر PostGIS أو الهندسة أو topology.
- لا تقل إن الصورة مطابقة للمعايير أو compliant.
- لا تستنتج أن الصورة اجتازت التقييم بالكامل.
- اذكر فقط الملاحظات التي ظهرت فعليًا في النتائج.
- صف عملية التقييم بأنها فحص بصري لعناصر الخريطة باستخدام نموذج الرؤية.
"""
    else:
        input_context="""
نوع المدخل هو بيانات جيومكانية Vector.

تعليمات خاصة بالـVector:
- يمكن ذكر نوع الطبقة.
- يمكن ذكر عدد المعالم إذا كان متوفرًا.
- يمكن ذكر نظام الإحداثيات إذا كان متوفرًا.
- يمكن شرح نتائج التحقق الجيومكاني الموجودة فقط.
- لا تستنتج امتثالًا رسميًا من نتائج التحقق.
"""

    prompt=f"""
حوّل تقييم Meyaar إلى تقرير صوتي عربي واضح ومهني.

الهدف:
أن يفهم المستخدم أهم محتوى التقرير بدون الحاجة إلى قراءة ملف PDF.

{input_context}

استخدم:
- dataset لمعلومات المدخل.
- validation للأرقام ونتائج التحقق ودرجات الخطورة.
- quality_summary لنتائج الجودة المحسوبة.
- validation.compliance لأدلة ومعنى حالة المطابقة عند توفرها.
- validation.revalidation لنتائج Before/After عند توفرها.
- report للتفسير والتوصيات.

غطِّ عند توفر المعلومات:
- نتيجة التقييم العامة.
- نوع المدخل.
- إجمالي الحالات التي تحتاج إلى مراجعة.
- أبعاد الجودة المتأثرة.
- أهم النتائج وأعدادها.
- معنى النتائج باختصار.
- هل تم تنفيذ تصحيح أو إعادة تحقق.
- إذا وجدت إعادة تحقق، اذكر عدد resolved وstill_present وnew_issues بصياغة عربية واضحة.
- إذا كانت حالة المطابقة not_determined فلا تصف البيانات بأنها مطابقة أو غير مطابقة رسميًا.
- أهم التوصيات.
- تنبيه مختصر بأن Meyaar لا يمثل اعتمادًا رسميًا من GeoSA.

قواعد:
- لا تخترع معلومات أو أرقام.
- لا تغير الأرقام.
- لا تعتبر النتائج مخالفات مؤكدة.
- Severity تصنيف داخلي في Meyaar.
- لا تقرأ run_id أو Rule ID.
- لا تكرر المعلومات.
- لا تستخدم أسلوب محادثة.
- لا تقل إن المدخل مطابق للمعايير أو متوافق أو اجتاز التقييم إلا إذا كانت هذه النتيجة موجودة صراحة في البيانات.
- لا تدّعي اعتمادًا أو موافقة رسمية من GeoSA.
- استخدم report فقط للتوصيات ولا تضف توصيات من عندك.
- إذا لم يتم تنفيذ تصحيح، اذكر ذلك باختصار.
- إذا لم تتم إعادة التحقق، اذكر ذلك باختصار.
- اكتب نصًا عربيًا مترابطًا ومناسبًا للاستماع.
- أرجع نصًا متصلًا مخصصًا للنطق فقط، بدون عنوان أو Markdown أو نقاط أو قوائم.

DATASET:
{json.dumps(dataset,ensure_ascii=False,default=str)}

VALIDATION:
{json.dumps(validation,ensure_ascii=False,default=str)}

QUALITY SUMMARY:
{json.dumps(quality_summary,ensure_ascii=False,default=str)}

REPORT:
{json.dumps(report,ensure_ascii=False,default=str)}
"""

    response=client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[{"role":"user","content":prompt}],
        temperature=0,
        max_completion_tokens=1200,
    )

    text=response.choices[0].message.content

    if not text:
        raise ValueError("Failed to generate audio report.")

    return text.strip()


def split_text(text,max_chars=190):
    sentences=re.split(r"(?<=[.!؟])\s+",text.strip())
    chunks=[]
    current=""

    for sentence in sentences:
        candidate=f"{current} {sentence}".strip()

        if len(candidate)<=max_chars:
            current=candidate
        else:
            if current:
                chunks.append(current)
            current=sentence

    if current:
        chunks.append(current)

    return chunks


def create_tts_chunk(text,output_path,voice="lulwa"):
    response=client.audio.speech.create(
        model="canopylabs/orpheus-arabic-saudi",
        voice=voice,
        input=text,
        response_format="wav",
    )
    response.write_to_file(output_path)


def merge_wav_files(files,output_path):
    with wave.open(str(files[0]),"rb") as first:
        channels=first.getnchannels()
        sample_width=first.getsampwidth()
        frame_rate=first.getframerate()

    with wave.open(str(output_path),"wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(sample_width)
        output.setframerate(frame_rate)

        for file in files:
            with wave.open(str(file),"rb") as wav_file:
                output.writeframes(
                    wav_file.readframes(wav_file.getnframes())
                )


def convert_wav_to_mp3(wav_path,mp3_path):
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(wav_path),
                "-codec:a",
                "libmp3lame",
                "-q:a",
                "2",
                str(mp3_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

    except FileNotFoundError:
        raise RuntimeError(
            "FFmpeg was not found. Make sure FFmpeg is installed and available in PATH."
        )

    except subprocess.CalledProcessError as error:
        raise RuntimeError(
            f"FFmpeg conversion failed: {error.stderr}"
        )


def create_gtts_audio(text,output_path):
    tts=gTTS(
        text=text,
        lang="ar",
    )
    tts.save(str(output_path))


def create_audio_summary(
    dataset,
    validation,
    quality_summary,
    report,
    output_path="outputs/MEYAAR_Summary.mp3",
    voice="lulwa",
):
    output_path=Path(output_path).with_suffix(".mp3")
    output_path.parent.mkdir(parents=True,exist_ok=True)

    wav_output_path=output_path.with_suffix(".wav")

    audio_text=generate_audio_report_text(
        dataset=dataset,
        validation=validation,
        quality_summary=quality_summary,
        report=report,
    )

    chunks=split_text(audio_text)

    if not chunks:
        raise ValueError("No audio text was generated.")

    tts_engine="orpheus"

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir=Path(temp_dir)
            wav_files=[]

            for index,chunk in enumerate(chunks,start=1):
                chunk_path=temp_dir/f"chunk_{index}.wav"

                create_tts_chunk(
                    text=chunk,
                    output_path=chunk_path,
                    voice=voice,
                )

                wav_files.append(chunk_path)

            merge_wav_files(
                files=wav_files,
                output_path=wav_output_path,
            )

        convert_wav_to_mp3(
            wav_path=wav_output_path,
            mp3_path=output_path,
        )

        wav_output_path.unlink(missing_ok=True)

    except Exception as error:
        print(f"Orpheus TTS unavailable, using gTTS: {error}")

        wav_output_path.unlink(missing_ok=True)

        create_gtts_audio(
            text=audio_text,
            output_path=output_path,
        )

        tts_engine="gtts"

    return {
        "status":"success",
        "audio_text":audio_text,
        "audio_path":str(output_path),
        "tts_engine":tts_engine,
    }