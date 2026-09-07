"""
Meyaar Tools
------------
Central access point for Meyaar's main capabilities.

This module exposes the functions that can be registered as tools
for the Multi-Agent / LangGraph system.

Supported workflows:
- Vector validation: Roads and Buildings
- Map image validation
- Quality assessment
- GeoSA evidence retrieval and conformance evaluation
- Fix recommendation and application
- Revalidation
- Report, voice summary, and email generation
"""

from src.api.vector_pipeline import process_vector_upload
from src.vision.vision_pipeline import run_vision_pipeline

# Quality analysis and finding inspection
from src.quality import (
    get_finding_details,
    get_analysis_summary,
    analyze_findings,
    get_quality_definition,
    calculate_quality_results,

    # GeoSA evidence and conformance evaluation
    get_geosa_evidence,
    evaluate_conformance,

    # Fix and remediation
    get_fix_definition,
    get_fix_options,
    apply_fix,

    # Revalidation after applying fixes
    revalidate,
    get_revalidation_results,
)

# Final output generation
from src.reporting.final_outputs import (
    generate_report,
    generate_voice_summary,
    send_results_email,
)


def run_vector_validation(
    filename:str,
    content:bytes,
    layer_name:str|None=None,
)->dict:
    """
    Validate vector geospatial data.

    Supports Roads and Buildings.
    If layer_name is not provided, Meyaar attempts to detect
    the layer type automatically.

    The vector pipeline handles:
    file loading -> layer detection -> PostGIS insertion ->
    validation -> findings.
    """
    return process_vector_upload(
        filename=filename,
        content=content,
        requested_layer=layer_name,
    )


def run_vision_validation(
    filename:str,
    content:bytes,
)->dict:
    """
    Validate a map image using Meyaar's vision pipeline.

    The vision model analyzes map elements and returns
    structured findings as a dictionary.
    """
    result=run_vision_pipeline(filename,content)
    return result.model_dump()


# Registry used by the agent system.
# The teammate can register these functions as LangGraph/LLM tools
# and assign each tool to the appropriate agent.
MEYAAR_TOOLS={
    # Data validation
    "run_vector_validation":run_vector_validation,
    "run_vision_validation":run_vision_validation,

    # Finding and quality analysis
    "get_finding_details":get_finding_details,
    "get_analysis_summary":get_analysis_summary,
    "analyze_findings":analyze_findings,
    "get_quality_definition":get_quality_definition,
    "calculate_quality_results":calculate_quality_results,

    # GeoSA grounding and conformance
    "get_geosa_evidence":get_geosa_evidence,
    "evaluate_conformance":evaluate_conformance,

    # Remediation
    "get_fix_definition":get_fix_definition,
    "get_fix_options":get_fix_options,
    "apply_fix":apply_fix,

    # Revalidation
    "revalidate":revalidate,
    "get_revalidation_results":get_revalidation_results,

    # Final outputs
    "generate_report":generate_report,
    "generate_voice_summary":generate_voice_summary,
    "send_results_email":send_results_email,
}