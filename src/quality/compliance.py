from src.quality.quality_registry import get_quality_definition

def _build_query(rule_id:str,definition:dict)->str:
    return (
        f"GeoSA geospatial data quality requirements related to {definition['quality_element']}, "
        f"{definition['sub_element']}, {definition['name']}, applicable to {definition['layer']} data."
    )

def get_geosa_evidence(rule_id:str,top_k:int=5)->dict:
    definition=get_quality_definition(rule_id)
    if not definition:
        return {"status":"not_found","rule_id":rule_id,"evidence":[]}

    from src.rag.retriever import retrieve_geosa_context

    results=retrieve_geosa_context(_build_query(rule_id,definition),top_k=top_k)
    return {
        "status":"success",
        "rule_id":rule_id,
        "quality_element":definition["quality_element"],
        "sub_element":definition["sub_element"],
        "evidence":results
    }

def evaluate_conformance(quality_result:dict,evidence:dict|None=None)->dict:
    rule_id=quality_result.get("rule_id")
    definition=get_quality_definition(rule_id) if rule_id else None
    if not definition:
        return {"status":"not_determined","rule_id":rule_id,"reason":"No quality definition was found."}

    source=definition.get("threshold_source")
    if source=="geosa_proxy":
        status="not_determined"
        reason=(
            "The configured metric is a GeoSA-aligned proxy. It can support quality assessment, "
            "but it does not by itself establish full GeoSA compliance."
        )
    elif source=="dataset_specification":
        status="not_determined"
        reason="The threshold comes from the dataset specification, not a verified GeoSA requirement."
    else:
        status="not_determined"
        reason="This threshold is a Meyaar operational rule, not a verified GeoSA compliance threshold."

    return {
        "status":status,
        "rule_id":rule_id,
        "quality_status":quality_result.get("status"),
        "quality_element":definition["quality_element"],
        "sub_element":definition["sub_element"],
        "threshold_source":source,
        "reason":reason,
        "evidence":(evidence or {}).get("evidence",[]) if isinstance(evidence,dict) else [],
        "disclaimer":"Meyaar provides standards-aligned quality evidence; it does not issue official GeoSA certification."
    }
