def build_reporting_input(result:dict)->tuple[dict,dict]:
    findings=result.get("findings",[])
    input_type=result["input_type"]

    dataset={
        "file_name":result["filename"],
        "input_type":input_type,
        "layer_type":result.get("layer_type") or input_type,
        "feature_count":result.get("feature_count",0),
        "crs":result.get("crs","Not Available"),
    }

    grouped={}

    for finding in findings:
        key=(
            finding.get("rule_id") or finding["error_type"],
            finding["error_type"],
            finding["severity"],
        )
        grouped[key]=grouped.get(key,0)+1

    summary=[
        {
            "rule_id":rule_id,
            "finding_type":error_type,
            "severity":severity,
            "findings":count,
        }
        for (rule_id,error_type,severity),count in grouped.items()
    ]

    validation={
        "status":"completed",
        "input_type":input_type,
        "method":"vision_model" if input_type=="image" else "postgis_rules",
        "layer_name":result.get("layer_type") or input_type,
        "run_id":result["run_id"],
        "total_findings":len(findings),
        "summary":summary,
    }

    return dataset,validation