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