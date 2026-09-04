from src.reporting.report_generator import generate_report_content
from src.voice.voice_summary import create_audio_summary


dataset = {
    "file_name": "buildings_dataset.geojson",
    "layer_type": "buildings",
    "feature_count": 0,
    "crs": "EPSG:4326",
}

validation = {
    "status": "success",
    "layer_name": "buildings",
    "run_id": "test-buildings-run",
    "total_findings": 39100,
    "summary": [
        {
            "rule_id": "BLD001",
            "finding_type": "Building Overlap",
            "severity": "high",
            "findings": 39048,
        },
        {
            "rule_id": "BLD003",
            "finding_type": "Invalid Geometry",
            "severity": "high",
            "findings": 52,
        },
    ],
}

quality_summary = [
    {
        "dimension": "Logical Consistency",
        "findings": 39100,
        "status": "Needs Review",
    }
]

report = generate_report_content(
    dataset=dataset,
    validation=validation,
)

create_audio_summary(
    dataset=dataset,
    validation=validation,
    quality_summary=quality_summary,
    report=report,
    output_path="outputs/MEYAAR_Buildings_Audio.wav",
    voice="lulwa",
)