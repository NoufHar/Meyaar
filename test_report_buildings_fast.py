from src.reporting.report_generator import (
    create_pdf,
    generate_report_content,
)


dataset = {
    "file_name": "buildings_dataset.geojson",
    "layer_type": "buildings",

    # Test value only until we use the real dataset metadata
    "feature_count": 0,

    "crs": "EPSG:4326",
}


validation = {
    "status": "success",
    "layer_name": "buildings",
    "run_id": "test-buildings-run",

    # New reporting name
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


print(
    "Generating report content..."
)

report = generate_report_content(
    dataset=dataset,
    validation=validation,
)


print(
    "Creating PDF..."
)

output_path = create_pdf(
    dataset=dataset,
    validation=validation,
    report=report,
    output_path=(
        "outputs/"
        "MEYAAR_Buildings_Report.pdf"
    ),
)


print()
print(
    "Report created successfully:"
)
print(
    output_path
)