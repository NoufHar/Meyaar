from collections import Counter

from sqlalchemy import text

from src.quality.db import get_engine
from src.quality.quality_registry import get_applicable_quality_definitions

SUPPORTED_LAYERS={"roads","buildings"}
MISSING_GEOMETRY_RULE={"roads":"RD005","buildings":"BLD004"}

def _total_features(layer_name:str)->int:
    if layer_name not in SUPPORTED_LAYERS:
        raise ValueError("Unsupported layer.")
    with get_engine().connect() as conn:
        return int(conn.execute(text(f"SELECT COUNT(*) FROM public.{layer_name}")).scalar() or 0)

def _get_findings(run_id:str,layer_name:str|None=None)->list[dict]:
    query="""
        SELECT result_id,run_id::text,layer_name,feature_id,rule_id,
               error_type,severity,details,detected_at
        FROM public.validation_results
        WHERE run_id=:run_id
    """
    params={"run_id":run_id}
    if layer_name:
        query+=" AND layer_name=:layer_name"
        params["layer_name"]=layer_name
    query+=" ORDER BY result_id"
    with get_engine().connect() as conn:
        rows=conn.execute(text(query),params).mappings().all()
    return [dict(row) for row in rows]

def _geometry_completeness(layer_name:str,findings:list[dict],total_features:int,definition:dict)->dict:
    rule_id=MISSING_GEOMETRY_RULE[layer_name]
    missing_ids={
        row["feature_id"] for row in findings
        if row["rule_id"]==rule_id and row["feature_id"] is not None
    }
    missing=len(missing_ids)
    valid=max(total_features-missing,0)
    value=round(valid/total_features*100,2) if total_features else 0.0
    threshold=definition["threshold"]
    return {
        "rule_id":rule_id,
        "name":definition["name"],
        "quality_element":definition["quality_element"],
        "sub_element":definition["sub_element"],
        "measure":definition["measure"],
        "value":value,
        "unit":"percent",
        "threshold":threshold,
        "threshold_source":definition["threshold_source"],
        "status":"pass" if threshold is not None and value>=threshold else "fail",
        "total_features":total_features,
        "valid_features":valid,
        "missing_features":missing,
        "note":definition.get("note")
    }

def calculate_quality_results(run_id:str,layer_name:str)->dict:
    if layer_name not in SUPPORTED_LAYERS:
        raise ValueError("layer_name must be roads or buildings.")

    findings=_get_findings(run_id,layer_name)
    total_features=_total_features(layer_name)
    counts=Counter(row["rule_id"] for row in findings)
    definitions=get_applicable_quality_definitions(layer_name)
    results=[]

    for rule_id,definition in definitions.items():
        if definition["measure"]=="geometry_completeness":
            results.append(_geometry_completeness(layer_name,findings,total_features,definition))
            continue

        count=counts.get(rule_id,0)
        threshold=definition["threshold"]
        status="not_evaluated" if threshold is None else ("pass" if count<=threshold else "fail")
        results.append({
            "rule_id":rule_id,
            "name":definition["name"],
            "quality_element":definition["quality_element"],
            "sub_element":definition["sub_element"],
            "measure":definition["measure"],
            "value":count,
            "unit":"count",
            "threshold":threshold,
            "threshold_source":definition["threshold_source"],
            "status":status,
            "note":definition.get("note")
        })

    order={rule_id:i for i,rule_id in enumerate(definitions)}
    results.sort(key=lambda item:order[item["rule_id"]])
    status_counts=Counter(item["status"] for item in results)

    return {
        "run_id":run_id,
        "layer_name":layer_name,
        "total_features":total_features,
        "total_findings":len(findings),
        "summary":{
            "pass":status_counts.get("pass",0),
            "fail":status_counts.get("fail",0),
            "not_evaluated":status_counts.get("not_evaluated",0)
        },
        "quality_results":results
    }
