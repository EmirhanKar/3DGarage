# app/api/routers/modification_router.py
# ──────────────────────────────────────
# Modifikasyon endpoint'leri.
# Akış: Fotoğraf yükle → 3D model oluşsun → SONRA modifikasyon seç (her birinin ayrı kredi maliyeti var)

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.database.db import get_session
from app.database.models import Scans, User, Modification, Processed3D, UserStats
from app.database.models.jant import Jant
from app.database.models.colors import Colors
from app.api import get_current_user

router = APIRouter(prefix="/modifications")


# ─────────────────────────────────────────
# KREDİ MALİYETLERİ (modifikasyon başına)
# ─────────────────────────────────────────

MODIFICATION_CREDIT_COSTS = {
    "jant": 30,       # Jant değiştirme
    "renk": 20,       # Renk değiştirme
    # İleride eklenecekler:
    # "spoiler": 25,
    # "body_kit": 40,
    # "cam_filmi": 15,
}


# ─────────────────────────────────────────
# ŞEMALAR
# ─────────────────────────────────────────

class ModificationCreate(BaseModel):
    scan_id: int
    jant_id: Optional[int] = None
    color_id: Optional[int] = None
    paint_location: Optional[str] = None  # Boya yeri


class ModificationUpdate(BaseModel):
    jant_id: Optional[int] = None
    color_id: Optional[int] = None
    paint_location: Optional[str] = None  # Boya yeri


class ModificationResponse(BaseModel):
    modification_id: int
    scan_id: int
    user_id: int
    jant_id: Optional[int] = None
    color_id: Optional[int] = None
    paint_location: Optional[str] = None
    last_step: str
    credit_cost: int = 0  # Bu modifikasyonun toplam kredi maliyeti

    class Config:
        from_attributes = True


class DraftResponse(BaseModel):
    scan_id: int
    car_name: str
    last_step: str           # Ne kadar ilerledi
    step_label: str          # Flutter'a gösterilecek yazı
    created_at: datetime
    method: str

    class Config:
        from_attributes = True


class ModificationCostsResponse(BaseModel):
    """Her modifikasyon tipi için kredi maliyetleri."""
    costs: dict
    currency: str = "user_credits"


# ─────────────────────────────────────────
# YARDIMCI FONKSİYONLAR
# ─────────────────────────────────────────

def get_step_label(last_step: str) -> str:
    labels = {
        "method_selected": "Yöntem Seçildi, Fotoğraf Bekleniyor",
        "photo_uploaded": "Fotoğraf Yüklendi, 3D Model Bekleniyor",
        "model_ready": "3D Model Hazır, Modifikasyon Bekleniyor",
        "plugin_selected": "Modifikasyon Seçildi, Render Bekleniyor",
        "completed": "Tamamlandı",
    }
    return labels.get(last_step, "Devam Et")


def calculate_modification_cost(jant_id: Optional[int], color_id: Optional[int]) -> int:
    """Seçilen modifikasyonların toplam kredi maliyetini hesaplar."""
    total = 0
    if jant_id is not None:
        total += MODIFICATION_CREDIT_COSTS.get("jant", 30)
    if color_id is not None:
        total += MODIFICATION_CREDIT_COSTS.get("renk", 20)
    return total


# ─────────────────────────────────────────
# ENDPOINTler
# ─────────────────────────────────────────

@router.get("/costs", response_model=ModificationCostsResponse, tags=["Modifications"])
async def get_modification_costs(
    current_user: User = Depends(get_current_user)
):
    """
    Her modifikasyon tipi için kredi maliyetlerini döndürür.
    Flutter bu endpoint'i çağırarak kullanıcıya fiyatları gösterir.
    """
    return ModificationCostsResponse(
        costs=MODIFICATION_CREDIT_COSTS,
        currency="user_credits"
    )


@router.post("", response_model=ModificationResponse, status_code=status.HTTP_201_CREATED, tags=["Modifications"])
async def create_modification(
    mod_in: ModificationCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Tamamlanmış bir 3D model üzerine modifikasyon uygular.
    
    Akış:
    1. Scan'in 3D modelinin hazır olduğunu doğrula (status == completed)
    2. Seçilen modifikasyonların kredi maliyetini hesapla
    3. Kullanıcının yeterli kredisi var mı kontrol et
    4. Krediyi düş
    5. Modifikasyon kaydını oluştur
    """
    # ── 1. Scan var mı ve bu kullanıcıya mı ait? ──
    scan_result = await db.execute(
        select(Scans)
        .where(Scans.scan_id == mod_in.scan_id)
        .options(selectinload(Scans.processed_3d))
    )
    scan = scan_result.scalar_one_or_none()
    
    if not scan or scan.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Tarama bulunamadı.")

    # ── 2. Scan metodu ve durum kontrolü ──
    # Hem 2D hem 3D desteklenir. 
    # Henüz tamamlanmamış (pending) taramalarda da başlangıç modifikasyonu seçilebilir.
    proc = scan.processed_3d if scan.method in ["3d", "3d_single"] else None

    # ── 3. En az bir modifikasyon seçilmiş mi? ──
    if mod_in.jant_id is None and mod_in.color_id is None:
        raise HTTPException(
            status_code=400,
            detail="En az bir modifikasyon seçmelisiniz (jant veya renk)."
        )

    # ── 4. Jant geçerli mi? ──
    if mod_in.jant_id is not None:
        jant = await db.get(Jant, mod_in.jant_id)
        if not jant:
            raise HTTPException(status_code=404, detail="Jant bulunamadı.")

    # ── 5. Renk geçerli mi? ──
    if mod_in.color_id is not None:
        color = await db.get(Colors, mod_in.color_id)
        if not color:
            raise HTTPException(status_code=404, detail="Renk bulunamadı.")

    # ── 6. Kredi maliyetini hesapla ──
    cost = calculate_modification_cost(mod_in.jant_id, mod_in.color_id)

    # ── 7. Kullanıcının yeterli kredisi var mı? ──
    stats_result = await db.execute(
        select(UserStats).where(UserStats.user_id == current_user.user_id)
    )
    user_stats = stats_result.scalar_one_or_none()

    if not user_stats or user_stats.user_credi < cost:
        mevcut = user_stats.user_credi if user_stats else 0
        raise HTTPException(
            status_code=402,
            detail=f"Yetersiz kredi. Bu modifikasyon {cost} kredi gerektiriyor. "
                   f"Mevcut krediniz: {mevcut}"
        )

    # ── 8. Krediyi düş ──
    user_stats.user_credi -= cost

    # ── 9. Modifikasyon kaydı oluştur veya güncelle ──
    result = await db.execute(
        select(Modification).where(
            Modification.scan_id == mod_in.scan_id,
            Modification.user_id == current_user.user_id
        )
    )
    existing_mod = result.scalar_one_or_none()

    if existing_mod:
        existing_mod.jant_id = mod_in.jant_id
        existing_mod.color_id = mod_in.color_id
        existing_mod.paint_location = mod_in.paint_location
        existing_mod.last_step = "plugin_selected"
        new_mod = existing_mod
    else:
        new_mod = Modification(
            scan_id=mod_in.scan_id,
            user_id=current_user.user_id,
            jant_id=mod_in.jant_id,
            color_id=mod_in.color_id,
            paint_location=mod_in.paint_location,
            last_step="plugin_selected"
        )
        db.add(new_mod)

    # ── 10. Scan durumunu güncelle ──
    scan.status = "plugin_selected"
    await db.commit()
    await db.refresh(new_mod)


    return ModificationResponse(
        modification_id=new_mod.modification_id,
        scan_id=new_mod.scan_id,
        user_id=new_mod.user_id,
        jant_id=new_mod.jant_id,
        color_id=new_mod.color_id,
        paint_location=new_mod.paint_location,
        last_step=new_mod.last_step,
        credit_cost=cost
    )


@router.patch("/{modification_id}", response_model=ModificationResponse, tags=["Modifications"])
async def update_modification(
    modification_id: int,
    mod_in: ModificationUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Mevcut modifikasyonu güncelle (jant veya renk değiştir).
    Yeni eklenen modifikasyon tiplerinden kredi alır, kaldırılandan almaz.
    """
    result = await db.execute(
        select(Modification).where(
            Modification.modification_id == modification_id,
            Modification.user_id == current_user.user_id
        )
    )
    mod = result.scalar_one_or_none()
    if not mod:
        raise HTTPException(status_code=404, detail="Modifikasyon bulunamadı.")

    # Yeni eklenen modifikasyonlar için ek kredi hesapla
    extra_cost = 0

    if mod_in.jant_id is not None:
        jant = await db.get(Jant, mod_in.jant_id)
        if not jant:
            raise HTTPException(status_code=404, detail="Jant bulunamadı.")
        # Eğer daha önce jant seçilmemişse, yeni jant ekleniyor → kredi al
        if mod.jant_id is None:
            extra_cost += MODIFICATION_CREDIT_COSTS.get("jant", 30)
        mod.jant_id = mod_in.jant_id

    if mod_in.color_id is not None:
        color = await db.get(Colors, mod_in.color_id)
        if not color:
            raise HTTPException(status_code=404, detail="Renk bulunamadı.")
        # Eğer daha önce renk seçilmemişse, yeni renk ekleniyor → kredi al
        if mod.color_id is None:
            extra_cost += MODIFICATION_CREDIT_COSTS.get("renk", 20)
        mod.color_id = mod_in.color_id

    if mod_in.paint_location is not None:
        mod.paint_location = mod_in.paint_location

    # Ek kredi gerekliyse kontrol et ve düş
    if extra_cost > 0:
        stats_result = await db.execute(
            select(UserStats).where(UserStats.user_id == current_user.user_id)
        )
        user_stats = stats_result.scalar_one_or_none()

        if not user_stats or user_stats.user_credi < extra_cost:
            mevcut = user_stats.user_credi if user_stats else 0
            raise HTTPException(
                status_code=402,
                detail=f"Yetersiz kredi. Ek modifikasyon {extra_cost} kredi gerektiriyor. "
                       f"Mevcut krediniz: {mevcut}"
            )
        user_stats.user_credi -= extra_cost

    await db.commit()
    await db.refresh(mod)


    return ModificationResponse(
        modification_id=mod.modification_id,
        scan_id=mod.scan_id,
        user_id=mod.user_id,
        jant_id=mod.jant_id,
        color_id=mod.color_id,
        paint_location=mod.paint_location,
        last_step=mod.last_step,
        credit_cost=extra_cost
    )


@router.get("/drafts", response_model=List[DraftResponse], tags=["Modifications"])
async def get_drafts(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Kullanıcının taslak araçlarını getirir.
    status 'completed' olmayanlar taslak sayılır.
    """
    result = await db.execute(
        select(Scans)
        .where(
            Scans.user_id == current_user.user_id,
            Scans.status != "completed"
        )
        .order_by(Scans.created_at.desc())
    )
    scans = result.scalars().all()

    drafts = []
    for scan in scans:
        # Bu scan'e ait modifikasyon var mı?
        mod_result = await db.execute(
            select(Modification).where(Modification.scan_id == scan.scan_id)
        )
        mod = mod_result.scalar_one_or_none()

        last_step = mod.last_step if mod else scan.status
        drafts.append(DraftResponse(
            scan_id=scan.scan_id,
            car_name=scan.car_name,
            last_step=last_step,
            step_label=get_step_label(last_step),
            created_at=scan.created_at,
            method=scan.method
        ))

    return drafts


@router.get("/{scan_id}", response_model=ModificationResponse, tags=["Modifications"])
async def get_modification(
    scan_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Bir scan'e ait modifikasyonu getirir."""
    result = await db.execute(
        select(Modification).where(
            Modification.scan_id == scan_id,
            Modification.user_id == current_user.user_id
        )
    )
    mod = result.scalar_one_or_none()
    if not mod:
        raise HTTPException(status_code=404, detail="Modifikasyon bulunamadı.")
    
    # Mevcut kredi maliyetini hesapla
    cost = calculate_modification_cost(mod.jant_id, mod.color_id)
    
    return ModificationResponse(
        modification_id=mod.modification_id,
        scan_id=mod.scan_id,
        user_id=mod.user_id,
        jant_id=mod.jant_id,
        color_id=mod.color_id,
        paint_location=mod.paint_location,
        last_step=mod.last_step,
        credit_cost=cost
    )


@router.delete("/{modification_id}", tags=["Modifications"])
async def delete_modification(
    modification_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Modifikasyonu siler."""
    result = await db.execute(
        select(Modification).where(
            Modification.modification_id == modification_id,
            Modification.user_id == current_user.user_id
        )
    )
    mod = result.scalar_one_or_none()
    if not mod:
        raise HTTPException(status_code=404, detail="Modifikasyon bulunamadı.")

    await db.delete(mod)
    await db.commit()
    return {"message": "Modifikasyon silindi."}