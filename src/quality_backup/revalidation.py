from sqlalchemy import text

from src.quality.db import get_engine
from src.quality.quality_evaluator import calculate_quality_results
from src.validation.validation_tools import run_rules_for_layer

def _findings_for_run(run_id:str)->list[dict]:
    with get_engine().connect() as conn:
        rows=conn.execute(text("""
            SELECT layer_name,feature_id,rule_id,error_type,severity,details
            FROM public.validation_results
            WHERE run_id=:run_id
            ORDER BY result_id
        """),{"run_id":run_id}).mappings().all()
    return [dict(row) for row in rows]

def _normalize(value)->str:
    return " ".join(str(value or "").split())

def _key(finding:dict)->tuple:
    return (
        finding.get("rule_id"),
        finding.get("feature_id"),
        _normalize(finding.get("details"))
    )

def compare_runs(before_run_id:str,after_run_id:str)->dict:
    before=_findings_for_run(before_run_id)
    after=_findings_for_run(after_run_id)
    before_map={_key(item):item for item in before}
    after_map={_key(item):item for item in after}

    resolved=[{**finding,"revalidation_status":"resolved"} for key,finding in before_map.items() if key not in after_map]
    still_present=[{**after_map[key],"revalidation_status":"still_present"} for key in before_map if key in after_map]
    new_issues=[{**finding,"revalidation_status":"new_issue"} for key,finding in after_map.items() if key not in before_map]

    return {
        "before_run_id":before_run_id,
        "after_run_id":after_run_id,
        "resolved":resolved,
        "still_present":still_present,
        "new_issues":new_issues,
        "summary":{
            "before":len(before),"after":len(after),
            "resolved":len(resolved),"still_present":len(still_present),
            "new_issues":len(new_issues)
        }
    }

def revalidate(before_run_id:str,layer_name:str,error_limit:int=500)->dict:
    validation=run_rules_for_layer(
        engine=get_engine(),layer_name=layer_name,error_limit=error_limit
    )
    if validation.get("status")!="success":
        return {"status":"failed","validation":validation}

    after_run_id=validation["run_id"]
    comparison=compare_runs(before_run_id,after_run_id)
    quality=calculate_quality_results(after_run_id,layer_name)

    return {
        "status":"success",
        "before_run_id":before_run_id,
        "after_run_id":after_run_id,
        "layer_name":layer_name,
        "validation":validation,
        "quality":quality,
        "comparison":comparison
    }

def get_revalidation_results(before_run_id:str,after_run_id:str)->dict:
    return compare_runs(before_run_id,after_run_id)
