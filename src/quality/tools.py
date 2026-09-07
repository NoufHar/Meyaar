from collections import Counter

from sqlalchemy import text

from src.quality.compliance import evaluate_conformance,get_geosa_evidence
from src.quality.db import get_engine
from src.quality.fix_registry import get_fix_definition
from src.quality.quality_evaluator import calculate_quality_results
from src.quality.quality_registry import get_quality_definition
from src.quality.remediation import apply_fix,get_finding_details,get_fix_options
from src.quality.revalidation import get_revalidation_results,revalidate

def get_analysis_summary(run_id:str,layer_name:str)->dict:
    quality=calculate_quality_results(run_id,layer_name)
    return {
        "run_id":run_id,
        "layer_name":layer_name,
        "total_features":quality["total_features"],
        "total_findings":quality["total_findings"],
        "quality_summary":quality["summary"],
        "quality_results":quality["quality_results"]
    }

def analyze_findings(run_id:str,layer_name:str)->dict:
    with get_engine().connect() as conn:
        rows=conn.execute(text("""
            SELECT rule_id,error_type,severity,COUNT(*) AS findings
            FROM public.validation_results
            WHERE run_id=:run_id AND layer_name=:layer_name
            GROUP BY rule_id,error_type,severity
            ORDER BY COUNT(*) DESC,rule_id
        """),{"run_id":run_id,"layer_name":layer_name}).mappings().all()
    groups=[dict(row) for row in rows]
    severity=Counter()
    for row in groups:
        severity[row["severity"]]+=int(row["findings"])
    return {
        "run_id":run_id,"layer_name":layer_name,
        "total_findings":sum(int(row["findings"]) for row in groups),
        "by_severity":dict(severity),"by_rule":groups
    }

__all__=[
    "get_quality_definition","calculate_quality_results","get_fix_definition",
    "get_finding_details","get_analysis_summary","analyze_findings",
    "get_geosa_evidence","evaluate_conformance","get_fix_options","apply_fix",
    "revalidate","get_revalidation_results"
]
