# app/database/schemas/plugins_schemas.py — YENİ DOSYA

from pydantic import BaseModel
from typing import Optional


class JantResponse(BaseModel):
    jant_id: int
    model_name: str
    category: str
    image_url: Optional[str] = None

    class Config:
        from_attributes = True


class ColorResponse(BaseModel):
    color_id: int
    color_code: str  # Hex kodu örn: "#FF5733"

    class Config:
        from_attributes = True


# Admin tarafı — jant ve renk ekleme için
class JantCreate(BaseModel):
    model_name: str
    category: str
    image_url: Optional[str] = None


class ColorCreate(BaseModel):
    color_code: str
