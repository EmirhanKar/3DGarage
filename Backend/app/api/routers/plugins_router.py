from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import os
import uuid
 
from app.database.db import get_session
from app.database.models import Jant, Colors
from app.api import get_current_user
from app.database.schemas.plugins_schemas import (
    JantResponse, ColorResponse,
    JantCreate, ColorCreate
)
 
router = APIRouter(prefix="/plugins")
 
 
# ─────────────────────────────────────────
# JANT ENDPOINTLERİ
# ─────────────────────────────────────────
 
@router.get("/jants", response_model=List[JantResponse], tags=["Plugins"])
async def get_all_jants(
    category: str = None,  # Opsiyonel filtre: ?category=sport
    db: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user)
):
    """Tüm jantları listeler. category parametresiyle filtrelenebilir."""
    query = select(Jant)
    if category:
        query = query.where(Jant.category == category)
    result = await db.execute(query)
    return result.scalars().all()
 
 
@router.get("/jants/{jant_id}", response_model=JantResponse, tags=["Plugins"])
async def get_jant_detail(
    jant_id: int,
    db: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user)
):
    """Tek bir jantın detayını getirir."""
    result = await db.execute(select(Jant).where(Jant.jant_id == jant_id))
    jant = result.scalar_one_or_none()
    if not jant:
        raise HTTPException(status_code=404, detail="Jant bulunamadı.")
    return jant
 
 
@router.post("/jants", response_model=JantResponse, status_code=status.HTTP_201_CREATED, tags=["Admin/Plugins"])
async def create_jant(
    model_name: str,
    category: str,
    image: UploadFile = File(None),  # Fotoğraf opsiyonel
    db: AsyncSession = Depends(get_session),
):
    """Admin: Yeni jant ekler. Fotoğraf yüklemesi opsiyoneldir."""
    image_url = None
 
    if image:
        if image.content_type not in ["image/jpeg", "image/png", "image/webp"]:
            raise HTTPException(status_code=400, detail="Sadece JPEG, PNG veya WEBP kabul edilir.")
 
        upload_dir = os.path.join("uploads", "plugins", "jants")
        os.makedirs(upload_dir, exist_ok=True)
 
        extension = image.filename.split(".")[-1]
        filename = f"jant_{uuid.uuid4()}.{extension}"
        full_path = os.path.join(upload_dir, filename).replace("\\", "/")
 
        content = await image.read()
        with open(full_path, "wb") as f:
            f.write(content)
 
        image_url = full_path
 
    new_jant = Jant(model_name=model_name, category=category, image_url=image_url)
    db.add(new_jant)
    await db.commit()
    await db.refresh(new_jant)
    return new_jant
 
 
@router.delete("/jants/{jant_id}", tags=["Admin/Plugins"])
async def delete_jant(jant_id: int, db: AsyncSession = Depends(get_session)):
    """Admin: Jant siler."""
    result = await db.execute(select(Jant).where(Jant.jant_id == jant_id))
    jant = result.scalar_one_or_none()
    if not jant:
        raise HTTPException(status_code=404, detail="Jant bulunamadı.")
    await db.delete(jant)
    await db.commit()
    return {"message": f"{jant_id} numaralı jant silindi."}
 
 
# ─────────────────────────────────────────
# RENK ENDPOINTLERİ
# ─────────────────────────────────────────
 
@router.get("/colors", response_model=List[ColorResponse], tags=["Plugins"])
async def get_all_colors(
    db: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user)
):
    """Tüm renkleri listeler."""
    result = await db.execute(select(Colors))
    return result.scalars().all()
 
 
@router.get("/colors/{color_id}", response_model=ColorResponse, tags=["Plugins"])
async def get_color_detail(
    color_id: int,
    db: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user)
):
    """Tek bir rengin detayını getirir."""
    result = await db.execute(select(Colors).where(Colors.color_id == color_id))
    color = result.scalar_one_or_none()
    if not color:
        raise HTTPException(status_code=404, detail="Renk bulunamadı.")
    return color
 
 
@router.post("/colors", response_model=ColorResponse, status_code=status.HTTP_201_CREATED, tags=["Admin/Plugins"])
async def create_color(
    color_in: ColorCreate,
    db: AsyncSession = Depends(get_session)
):
    """Admin: Yeni renk ekler. color_code hex formatında olmalı örn: #FF5733"""
    new_color = Colors(color_code=color_in.color_code)
    db.add(new_color)
    await db.commit()
    await db.refresh(new_color)
    return new_color
 
 
@router.delete("/colors/{color_id}", tags=["Admin/Plugins"])
async def delete_color(color_id: int, db: AsyncSession = Depends(get_session)):
    """Admin: Renk siler."""
    result = await db.execute(select(Colors).where(Colors.color_id == color_id))
    color = result.scalar_one_or_none()
    if not color:
        raise HTTPException(status_code=404, detail="Renk bulunamadı.")
    await db.delete(color)
    await db.commit()
    return {"message": f"{color_id} numaralı renk silindi."}