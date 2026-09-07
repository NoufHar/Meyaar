from src.api.result_adapter import build_reporting_input
from src.notifications.email import send_analysis_email
from src.quality import calculate_quality_results,evaluate_conformance,get_geosa_evidence
from src.reporting.report_generator import create_pdf,generate_report_content
from src.voice.voice_summary import create_audio_summary


def build_quality_context(result:dict)->tuple[dict|None,list[dict],dict|None]:
    if result.get("input_type")!="vector":
        return None,[],result.get("revalidation")

    layer_name=result.get("layer_type")
    run_id=str(result.get("run_id",""))

    if layer_name not in {"roads","buildings"} or not run_id:
        return None,[],result.get("revalidation")

    quality=calculate_quality_results(run_id,layer_name)
    compliance=[]

    for item in quality.get("quality_results",[]):
        evidence=None

        if item.get("status")=="fail":
            try:
                evidence=get_geosa_evidence(item["rule_id"],top_k=2)
            except Exception as error:
                evidence={
                    "status":"unavailable",
                    "rule_id":item.get("rule_id"),
                    "evidence":[],
                    "error":str(error),
                }

        conformance=evaluate_conformance(item,evidence)
        conformance["evidence_status"]=(evidence or {}).get("status","not_requested")
        compliance.append(conformance)

    return quality,compliance,result.get("revalidation")


def prepare_reporting_context(result:dict)->tuple[dict,dict]:
    dataset,validation=build_reporting_input(result)
    quality,compliance,revalidation=build_quality_context(result)
    validation["quality"]=quality
    validation["compliance"]=compliance
    validation["revalidation"]=revalidation
    validation["remediation"]=result.get("remediation")
    return dataset,validation


def generate_report(result:dict)->dict:
    dataset,validation=prepare_reporting_context(result)
    report=generate_report_content(dataset,validation)
    report_path=create_pdf(
        dataset=dataset,
        validation=validation,
        report=report,
        output_path=f"outputs/{result['run_id']}_report.pdf",
    )
    return {
        "dataset":dataset,
        "validation":validation,
        "report":report,
        "report_path":str(report_path),
    }


def generate_voice_summary(report_result:dict)->dict:
    validation=report_result["validation"]
    quality_summary=validation.get("quality") or {
        "total_findings":validation.get("total_findings",0)
    }
    return create_audio_summary(
        dataset=report_result["dataset"],
        validation=validation,
        quality_summary=quality_summary,
        report=report_result["report"],
        output_path=f"outputs/{validation['run_id']}_summary.mp3",
    )


def send_results_email(
    to_email:str,
    filename:str,
    report_result:dict,
    audio_result:dict,
):
    validation=report_result["validation"]
    return send_analysis_email(
        to_email=to_email,
        filename=filename,
        report_path=report_result["report_path"],
        audio_path=str(audio_result["audio_path"]),
        quality_summary=validation.get("quality"),
        revalidation=validation.get("revalidation"),
    )


def generate_all_outputs(result:dict,user_email:str)->dict:
    report_result=generate_report(result)
    audio_result=generate_voice_summary(report_result)
    email_status="sent"
    email_error=None

    try:
        send_results_email(
            to_email=user_email,
            filename=result["filename"],
            report_result=report_result,
            audio_result=audio_result,
        )
    except Exception as error:
        email_status="failed"
        email_error=str(error)
        print(f"Email notification failed: {error}")

    return {
        "report":report_result["report"],
        "report_path":report_result["report_path"],
        "audio_path":str(audio_result["audio_path"]),
        "audio_text":audio_result["audio_text"],
        "tts_engine":audio_result.get("tts_engine"),
        "quality":report_result["validation"].get("quality"),
        "compliance":report_result["validation"].get("compliance",[]),
        "revalidation":report_result["validation"].get("revalidation"),
        "email_status":email_status,
        "email_error":email_error,
    }
