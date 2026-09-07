from typing import Any,Literal
from pydantic import BaseModel


class ImageInspectionResponse(BaseModel):
    filename:str
    size_bytes:int
    format:str
    width:int
    height:int
    mode:str
    status:Literal["accepted"]="accepted"


class MapElementResult(BaseModel):
    element:str
    present:bool
    confidence:float|None=None
    location:list[float]|None=None


class VisionIssue(BaseModel):
    error_type:str
    severity:str
    message:str
    confidence:float|None=None


class VisionAnalysisResponse(BaseModel):
    filename:str
    status:Literal["completed"]="completed"
    elements:list[MapElementResult]
    issues:list[VisionIssue]


class VectorProcessingResponse(BaseModel):
    filename:str
    status:Literal["completed"]
    layer_name:Literal["roads","buildings"]
    run_id:str
    insertion:dict[str,Any]
    validation:dict[str,Any]
    analysis:dict[str,Any]
    map_data:dict[str,Any]


class UnifiedFinding(BaseModel):
    finding_id:str
    source_type:Literal["vector","image"]
    rule_id:str|None=None
    feature_id:str|None=None
    error_type:str
    severity:str
    status:str|None=None
    message:str
    recommendation:str|None=None
    confidence:float|None=None
    location:dict[str,Any]|None=None
    measurements:list[dict[str,Any]]=[]


class UnifiedInspectionResponse(BaseModel):
    filename:str
    input_type:Literal["vector","image"]
    status:str
    run_id:str|None=None
    layer_type:str|None=None
    findings:list[UnifiedFinding]
    visualization:dict[str,Any]|None=None
    report:dict[str,Any]|None=None
    report_path:str|None=None
    audio_path:str|None=None
    audio_text:str|None=None
    tts_engine:str|None=None
    email_status:str|None=None
    email_error:str|None=None
    analysis_id:int|None=None