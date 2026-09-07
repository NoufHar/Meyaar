import base64
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq
from jinja2 import Environment,FileSystemLoader
from playwright.sync_api import sync_playwright

from src.reporting.charts import (
    create_findings_by_rule_chart,
    create_quality_dimension_chart,
)

load_dotenv()

BASE_DIR=Path(__file__).resolve().parent
TEMPLATE_DIR=BASE_DIR/"templates"
TEMPLATE_NAME="report_template.html"
OUTPUT_DIR=Path("outputs")

RULE_TO_DIMENSION={
    "RD001":"Logical Consistency",
    "RD002":"Logical Consistency",
    "RD003":"Logical Consistency",
    "RD004":"Logical Consistency",
    "RD005":"Completeness",

    "BLD001":"Logical Consistency",
    "BLD002":"Logical Consistency",
    "BLD003":"Logical Consistency",
    "BLD004":"Completeness",

    "GIS001":"Spatial Reference",
    "GIS002":"Spatial Validity",
    "GIS003":"Completeness",
    "GIS004":"Attribute Quality",
    "GIS005":"Attribute Quality",

    "missing_title":"Cartographic Completeness",
    "missing_legend":"Cartographic Completeness",
    "missing_scale":"Cartographic Completeness",
    "missing_north_arrow":"Cartographic Completeness",
    "element_overlap":"Visual Legibility",
    "element_clipping":"Visual Legibility",
    "text_overlap":"Visual Legibility",
    "label_overlap":"Visual Legibility",
    "illegible_text":"Visual Legibility",
}


def normalize_dataset(dataset):
    return {
        "file_name":dataset.get("file_name","Unknown Dataset"),
        "input_type":dataset.get("input_type","vector"),
        "layer_type":dataset.get("layer_type","Unknown"),
        "feature_count":dataset.get("feature_count",0),
        "crs":dataset.get("crs","Not Available"),
    }


def normalize_validation(validation):
    normalized_summary=[]

    for row in validation.get("summary",[]):
        findings=row.get(
            "findings",
            row.get("errors_found",0),
        )

        normalized_summary.append({
            "rule_id":row.get("rule_id","Unknown"),
            "finding_type":row.get(
                "finding_type",
                row.get("error_type","Unknown Finding"),
            ),
            "severity":row.get("severity","Not Specified"),
            "findings":findings,
        })

    total_findings=validation.get(
        "total_findings",
        validation.get(
            "total_errors",
            sum(row["findings"] for row in normalized_summary),
        ),
    )

    return {
        "status":validation.get("status","unknown"),
        "input_type":validation.get("input_type","vector"),
        "method":validation.get("method","postgis_rules"),
        "layer_name":validation.get("layer_name","Unknown"),
        "run_id":validation.get("run_id","unknown-run"),
        "total_findings":total_findings,
        "summary":normalized_summary,
        "quality":validation.get("quality"),
        "compliance":validation.get("compliance",[]),
        "revalidation":validation.get("revalidation"),
        "remediation":validation.get("remediation"),
    }


def image_to_data_uri(image_path):
    if not image_path:
        return None

    image_path=Path(image_path)

    if not image_path.exists():
        return None

    encoded=base64.b64encode(
        image_path.read_bytes()
    ).decode("utf-8")

    return "data:image/png;base64,"+encoded


def build_quality_summary(validation):
    dimensions={}

    for row in validation.get("summary",[]):
        dimension=RULE_TO_DIMENSION.get(
            row["rule_id"],
            "Other",
        )

        dimensions[dimension]=(
            dimensions.get(dimension,0)
            +row["findings"]
        )

    rows=[]

    for dimension,findings in dimensions.items():
        rows.append({
            "dimension":dimension,
            "findings":findings,
            "status":"Needs Review" if findings>0 else "No Findings",
        })

    return sorted(
        rows,
        key=lambda row:row["findings"],
        reverse=True,
    )


def build_rule_rows(validation):
    rows=[]

    for row in validation.get("summary",[]):
        rule_id=row["rule_id"]
        findings=row["findings"]

        rows.append({
            "rule_id":rule_id,
            "quality_dimension":RULE_TO_DIMENSION.get(
                rule_id,
                "Other",
            ),
            "finding_type":row["finding_type"],
            "severity":row["severity"],
            "findings":findings,
            "status":"Needs Review" if findings>0 else "No Findings",
        })

    return rows


def build_rule_context(validation):
    summary=validation.get("summary",[])

    if not summary:
        return "No validation findings were reported."

    lines=[]

    for row in summary:
        lines.append(
            f"- {row['rule_id']}: "
            f"{row['finding_type']} | "
            f"Severity: {row['severity']} | "
            f"Candidate Findings: {row['findings']:,}"
        )

    return "\n".join(lines)


def sanitize_report_language(report):
    replacements=[
        (r"\bcandidate errors\b","candidate findings"),
        (r"\bcandidate error\b","candidate finding"),
        (r"\bdetected errors\b","detected findings"),
        (r"\bdetected error\b","detected finding"),
        (r"\bconfirmed errors\b","confirmed findings"),
        (r"\bconfirmed error\b","confirmed finding"),
        (r"\btopology errors\b","topology findings"),
        (r"\btopology error\b","topology finding"),
        (r"\bvalidation errors\b","validation findings"),
        (r"\bvalidation error\b","validation finding"),
        (r"\bviolations\b","findings"),
        (r"\bviolation\b","finding"),
    ]

    for key,value in report.items():
        if not isinstance(value,str):
            continue

        for pattern,replacement in replacements:
            value=re.sub(
                pattern,
                replacement,
                value,
                flags=re.IGNORECASE,
            )

        report[key]=value.strip()

    return report


def clean_json_response(text):
    text=text.strip()

    if text.startswith("```json"):
        text=text[len("```json"):]

    elif text.startswith("```"):
        text=text[len("```"):]

    if text.endswith("```"):
        text=text[:-3]

    return text.strip()


def build_method_context(dataset,validation):
    if validation["input_type"]=="image":
        return """
The input is a map image.

Meyaar used a vision-based cartographic inspection process.
The supplied vision findings are the source of truth for this report.

Do not mention PostGIS, vector feature counts, topology, geometry,
spatial databases, or coordinate reference systems unless such
information was explicitly supplied and is relevant.
"""

    return """
The input is vector geospatial data.

Meyaar used deterministic geospatial validation rules implemented
with PostGIS.

The supplied validation findings are the source of truth for this report.
"""

def compact_for_llm(validation:dict)->dict:
    data=dict(validation)

    findings=data.get("findings") or data.get("errors") or []
    data["findings"]=findings[:5]
    data.pop("errors",None)

    compliance=data.get("compliance") or []
    compact_compliance=[]

    for item in compliance:
        row=dict(item)
        evidence=row.get("evidence") or []

        row["evidence"]=[
            {
                "source":e.get("source"),
                "page":e.get("page"),
                "text":str(e.get("text",""))[:500],
            }
            for e in evidence[:2]
        ]

        compact_compliance.append(row)

    data["compliance"]=compact_compliance
    return data

def generate_report_content(dataset,validation):
    dataset=normalize_dataset(dataset)
    validation=normalize_validation(validation)

    api_key=os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError("GROQ_API_KEY was not found.")

    client=Groq(api_key=api_key)

    rule_context=build_rule_context(validation)
    method_context=build_method_context(dataset,validation)

    prompt=f"""
You are writing concise explanatory text for a Meyaar
Geospatial Data Quality Assessment Report.

{method_context}

You do not perform validation.
You do not discover new findings.
You only explain the supplied results.

DATASET

{json.dumps(dataset,indent=2)}

VALIDATION

{json.dumps(compact_for_llm(validation),indent=2,default=str)}

The validation object may also contain:
- quality: deterministic quality measures calculated from Meyaar rules.
- compliance: conservative standards-alignment results and retrieved GeoSA evidence.
- remediation: fixes that were proposed or applied.
- revalidation: before/after comparison after fixes.

Use these fields only when present. Never convert a not_determined compliance status into compliant or non-compliant.

RULES WITH FINDINGS

{rule_context}

STRICT RULES

1. Use only supplied information.

2. Never invent:
   rule IDs,
   finding types,
   counts,
   severity,
   locations,
   districts,
   neighborhoods,
   hotspots,
   corridors,
   intersections,
   spatial patterns,
   map observations,
   or standards requirements.

3. Preserve numerical values exactly.

4. Use only the supplied validation findings as the source of truth.

5. Use "finding" or "candidate finding".

6. Do not call findings confirmed errors.

7. Do not use "violation" or "violations".

8. Do not infer the cause of a finding.

9. Do not infer intended geometry, connectivity,
   extent, location, boundary, or cartographic intent.

10. Mention only the current input and supplied findings.

11. Never reuse a Road rule in a Buildings report.

12. Never reuse a Buildings rule in a Roads report.

13. Severity is Meyaar's internal classification.

14. Do not claim official GeoSA certification,
    approval, compliance, endorsement, or official violation.

15. Do not invent percentages.

16. Do not claim that visual elements were manually reviewed.

17. Recommendations may recommend review,
    correction after review, and re-validation.

18. Do not claim a correction has already occurred.

19. If remediation is absent, say:
    "No corrective actions were performed on the dataset."
    If remediation is present, describe only the supplied applied/proposed actions.

20. If revalidation is absent, say:
    "No re-validation was conducted following the initial assessment."
    If revalidation is present, report the supplied resolved, still_present, and new_issues counts exactly.

20A. If compliance status is not_determined, explicitly state that the available evidence does not establish official GeoSA compliance.

21. If input_type is "image":
    - describe the input as a map image or image.
    - describe the method as vision-based cartographic inspection.
    - do not mention vector feature counts.
    - do not mention PostGIS.
    - do not discuss CRS unless genuinely available and relevant.
    - do not describe vision findings as deterministic GIS rules.

22. If input_type is "vector":
    - describe the input as a vector geospatial dataset.
    - PostGIS validation may be mentioned.
    - feature count and CRS may be mentioned if supplied.

23. Keep writing concise and professional.
24. When there are zero findings, say "no findings were reported" or "no findings were identified".
25. Do not say the input is error-free, issue-free, compliant, or free from deviations.
26. Do not include run_id in any generated report text.
27. If total_findings is 0, set recommendations to:
  "No corrective action is recommended based on the current findings. Re-validation may be performed if the input is updated."
28. Return valid JSON only.
Return exactly:

{{
    "executive_summary":"...",
    "quality_assessment_summary":"...",
    "detailed_findings":"...",
    "actions_taken":"...",
    "revalidation_improvement":"...",
    "recommendations":"...",
    "assessment_methodology":"...",
    "standards_alignment_disclaimer":"..."
}}
"""

    response=client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role":"system",
                "content":"You write concise geospatial quality reports. Return JSON only.",
            },
            {
                "role":"user",
                "content":prompt,
            },
        ],
        temperature=0.1,
    )

    text=response.choices[0].message.content
    text=clean_json_response(text)

    try:
        report=json.loads(text)
    except json.JSONDecodeError as exc:
        print("Groq response:")
        print(text)
        raise ValueError("Groq returned invalid JSON.") from exc

    required_keys=[
        "executive_summary",
        "quality_assessment_summary",
        "detailed_findings",
        "actions_taken",
        "revalidation_improvement",
        "recommendations",
        "assessment_methodology",
        "standards_alignment_disclaimer",
    ]

    for key in required_keys:
        report.setdefault(key,"")

    return sanitize_report_language(report)


def create_pdf(
    dataset,
    validation,
    report,
    output_path="outputs/MEYAAR_Report.pdf",
):
    dataset=normalize_dataset(dataset)
    validation=normalize_validation(validation)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path=Path(output_path).resolve()

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    quality_summary=build_quality_summary(validation)
    rule_rows=build_rule_rows(validation)

    safe_run_id=re.sub(
        r"[^a-zA-Z0-9_-]",
        "_",
        str(validation["run_id"]),
    )

    findings_chart_path=(
        OUTPUT_DIR
        /f"{safe_run_id}_findings.png"
    )

    quality_chart_path=(
        OUTPUT_DIR
        /f"{safe_run_id}_quality.png"
    )

    findings_chart_path=create_findings_by_rule_chart(
        validation,
        findings_chart_path,
    )

    quality_chart_path=create_quality_dimension_chart(
        validation,
        quality_chart_path,
    )

    findings_chart_uri=image_to_data_uri(
        findings_chart_path
    )

    quality_chart_uri=image_to_data_uri(
        quality_chart_path
    )

    map_snapshot_uri=None

    environment=Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=True,
    )

    template=environment.get_template(
        TEMPLATE_NAME
    )

    html=template.render(
        dataset=dataset,
        validation=validation,
        report=report,
        quality_summary=quality_summary,
        rule_rows=rule_rows,
        findings_chart_uri=findings_chart_uri,
        quality_chart_uri=quality_chart_uri,
        map_snapshot_uri=map_snapshot_uri,
    )

    with sync_playwright() as p:
        browser=p.chromium.launch()

        try:
            page=browser.new_page()

            page.set_content(
                html,
                wait_until="networkidle",
            )

            page.pdf(
                path=str(output_path),
                format="A4",
                print_background=True,
                margin={
                    "top":"12mm",
                    "right":"12mm",
                    "bottom":"12mm",
                    "left":"12mm",
                },
            )

        finally:
            browser.close()

    return str(output_path)