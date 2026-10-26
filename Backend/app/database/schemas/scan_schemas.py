from pydantic import BaseModel, Field, model_validator
from datetime import datetime
from typing import Optional, List, Dict, Any


class ScanBase(BaseModel):
    method: str
    status: Optional[str] = Field(default="pending")


class ScanCreate(ScanBase):
    user_id: int


class ScanImageBrief(BaseModel):
    image_url: str
    class Config:
        from_attributes = True


class JantBrief(BaseModel):
    model_name: str
    image_url: Optional[str] = None
    class Config:
        from_attributes = True


class ColorBrief(BaseModel):
    color_code: str
    class Config:
        from_attributes = True


class ModificationBrief(BaseModel):
    modification_id: int
    jant: Optional[JantBrief] = None
    colors: Optional[ColorBrief] = None
    paint_location: Optional[str] = None
    class Config:
        from_attributes = True


class Processed3DInfo(BaseModel):
    thumbnail_url: Optional[str] = None
    model_url: Optional[str] = None
    class Config:
        from_attributes = True


class Processed2DInfo(BaseModel):
    thumbnail_url: Optional[str] = None
    image_url: Optional[str] = None
    class Config:
        from_attributes = True


class ScanResponse(BaseModel):
    scan_id: int
    method: str
    status: str
    created_at: datetime
    car_name: str
    description: Optional[str] = None
    is_shared: bool = False
    thumbnail_url: Optional[str] = None
    model_url: Optional[str] = None
    image_url: Optional[str] = None
    progress: int = 0

    # Tripo v3 & Akış Alanları
    mode: Optional[str] = "3d"
    options_json: Optional[str] = None
    modifications_json: Optional[str] = None
    edit_task_id: Optional[str] = None
    model_task_id: Optional[str] = None
    credits_estimated: int = 0
    credits_consumed: int = 0

    processed_3d: Optional[Processed3DInfo] = Field(default=None, exclude=True)
    processed_2d: Optional[Processed2DInfo] = Field(default=None, exclude=True)

    modifications: List[ModificationBrief] = Field(default=[])
    images: List[ScanImageBrief] = Field(default=[])

    jant_image_url: Optional[str] = None
    renk_kodu: Optional[str] = None

    can_modify: bool = False
    has_modification: bool = False

    progress_percent: Optional[int] = None
    progress_stage: Optional[str] = None
    error_code: Optional[str] = None
    error_hint: Optional[str] = None

    class Config:
        from_attributes = True

    @model_validator(mode='after')
    def set_fields(self) -> 'ScanResponse':
        if self.processed_3d:
            if not self.thumbnail_url:
                self.thumbnail_url = self.processed_3d.thumbnail_url
            if not self.model_url:
                self.model_url = self.processed_3d.model_url
            if self.processed_3d.model_url and self.status in ("completed", "done"):
                self.can_modify = True

        if self.processed_2d:
            if not self.thumbnail_url:
                self.thumbnail_url = self.processed_2d.thumbnail_url
            if not self.image_url:
                self.image_url = self.processed_2d.image_url
            if self.processed_2d.image_url and self.status in ("completed", "done", "edit_ready", "awaiting_confirmation"):
                self.can_modify = True

        if self.modifications:
            self.has_modification = True
            mod = self.modifications[0]
            if mod.jant:
                self.jant_image_url = mod.jant.image_url
            if mod.colors:
                self.renk_kodu = mod.colors.color_code

        # İlerleme hesaplama
        if self.progress_percent is not None and self.progress_percent > 0:
            self.progress = self.progress_percent
        elif self.status in ("completed", "done"):
            self.progress = 100
        elif self.status == "awaiting_confirmation":
            self.progress = 50
        elif self.status == "generating_3d":
            self.progress = 75
        elif self.status == "pending_edit":
            self.progress = 25

        return self


# ==============================================================================
# Worker / Dahili İletişim Şemaları
# ==============================================================================

class ClaimResponse(BaseModel):
    status: str = "claimed"
    scan_id: int
    claim_token: str
    retry_count: int
    max_attempts: int


class ProgressRequest(BaseModel):
    claim_token: str
    stage: Optional[str] = None
    percent: Optional[int] = None


class FailRequest(BaseModel):
    claim_token: str
    failed_step: Optional[str] = None
    error_code: str
    detail: Optional[str] = None
    hint: Optional[str] = None
    retryable: bool = False
