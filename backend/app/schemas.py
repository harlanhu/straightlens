from typing import Literal
from pydantic import BaseModel

class JobAccepted(BaseModel):
    id: str
    status: Literal['queued']

class JobView(BaseModel):
    id: str
    status: Literal['queued','running','succeeded','failed']
    stage: str
    stages: list[str] = []
    outcome: str | None = None
    reason_code: str | None = None
    message: str
    width: int | None = None
    height: int | None = None
    output_width: int | None = None
    output_height: int | None = None
    elapsed_seconds: float | None = None
    download_url: str | None = None
    original_preview_url: str | None = None
    result_preview_url: str | None = None
    original_image_url: str | None = None
    result_image_url: str | None = None
    kind: Literal['correction','reverse'] = 'correction'
    parent_id: str | None = None
    reference_basis: str | None = None
    covered_fraction: float | None = None
    uncropped_download_url: str | None = None
    uncropped_width: int | None = None
    uncropped_height: int | None = None
    can_reverse: bool = False
    transform_version: int | None = None
    upload_preview_url: str | None = None
    upload_image_url: str | None = None
