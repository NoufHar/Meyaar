from typing import Literal

from pydantic import BaseModel


class ImageInspectionResponse(BaseModel):
    filename: str
    size_bytes: int
    format: str
    width: int
    height: int
    mode: str
    status: Literal["accepted"] = "accepted"


class MapElementResult(BaseModel):
    element: str
    present: bool
    confidence: float | None = None
    location: list[float] | None = None


class VisionIssue(BaseModel):
    error_type: str
    severity: str
    message: str
    confidence: float | None = None


class VisionAnalysisResponse(BaseModel):
    filename: str
    status: Literal["completed"] = "completed"
    elements: list[MapElementResult]
    issues: list[VisionIssue]