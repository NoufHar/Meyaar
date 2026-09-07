from typing import Any, Literal

# Public API contracts keep validation consistent between routes and clients.

from pydantic import BaseModel, Field


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
    quality_checks: dict[str, Any] = Field(default_factory=dict)
    geotiff: dict[str, Any] | None = None
    compliance_score: float = 100.0
    model_status: str = "completed"
    analysis_id: str | None = None


class VectorProcessingResponse(BaseModel):
    filename: str
    status: Literal["completed"]
    layer_name: Literal[
        "roads",
        "buildings",
    ]
    run_id: str
    insertion: dict[str, Any]
    validation: dict[str, Any]
    analysis: dict[str, Any]
    compliance_score: float = 100.0
    layer_geojson: dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "FeatureCollection",
            "features": [],
        }
    )
    analysis_id: str | None = None


class ErrorReviewUpdate(BaseModel):
    status: Literal["new", "confirmed", "resolved", "false_positive"]
    comment: str = Field(default="", max_length=2000)


class ErrorReviewResponse(ErrorReviewUpdate):
    result_id: int
    updated_at: str | None = None


class VoiceSynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    voice: str = Field(default="lulwa", max_length=50)


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    user_id: str
    name: str
    email: str | None = None
    username: str | None = None
    must_change_password: bool = False
    role: Literal["manager", "leader", "member"] | None = None
    team_id: str | None = None
    team_name: str | None = None
    invite_code: str | None = None


class AuthResponse(BaseModel):
    token: str
    user: UserResponse


class TeamInviteRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)


class TeamCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)


class TeamJoinRequest(BaseModel):
    invite_code: str = Field(min_length=4, max_length=20)


class TeamRoleUpdate(BaseModel):
    role: Literal["leader", "member"]


class ExistingTeamMemberAddRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)
    role: Literal["leader", "member"] = "member"


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class NewUserInterpretRequest(BaseModel):
    instruction: str = Field(min_length=3, max_length=1000)


class TeamCommandBatchRequest(BaseModel):
    instruction: str = Field(min_length=3, max_length=3000)


class BatchReportRequest(BaseModel):
    analysis_ids: list[str] = Field(min_length=1, max_length=50)


class NewUserCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=254)
    role: Literal["leader", "member"] = "member"
    suggested_username: str | None = Field(default=None, max_length=50)
