# app/database/schemas/community_schemas.py — YENİ DOSYA

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


# ── Yorum Şemaları ──────────────────────────────

class CommentCreate(BaseModel):
    content: str


class CommentResponse(BaseModel):
    comment_id: int
    scan_id: int
    user_id: int
    content: str
    created_at: datetime
    user_name: str = "Kullanıcı"
    like_count: int = 0
    is_liked: bool = False

    class Config:
        from_attributes = True


# ── Keşfet Feed Şeması ──────────────────────────
# Bir aracın keşfet sayfasında görüneceği özet bilgi

class FeedItemResponse(BaseModel):
    scan_id: int
    car_name: str
    thumbnail_url: Optional[str] = None
    like_count: int = 0
    comment_count: int = 0
    is_liked: bool = False      # Giriş yapan kullanıcı beğenmiş mi?
    owner_name: str             # Aracın sahibinin adı

    class Config:
        from_attributes = True