from io import BytesIO

import numpy as np
from PIL import Image

from src.quality import compliance_score, compliance_score_from_summary, inspect_image_quality


def test_compliance_score_uses_severity_weights():
    assert compliance_score([], 10) == 100.0
    assert compliance_score([{"severity": "high"}], 10) == 93.0


def test_summary_score_uses_all_findings():
    summary = [{"severity": "medium", "errors_found": 2}]
    assert compliance_score_from_summary(summary, 10) == 92.0


def test_uniform_image_is_flagged():
    stream = BytesIO()
    Image.fromarray(np.full((32, 32, 3), 120, dtype=np.uint8)).save(stream, "PNG")
    result = inspect_image_quality(stream.getvalue())
    assert any(issue["error_type"] == "empty_or_uniform_image" for issue in result["issues"])
