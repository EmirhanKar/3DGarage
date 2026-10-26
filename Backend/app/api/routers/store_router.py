# app/api/routers/store_router.py — YENİ DOSYA

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone, timedelta
from typing import List
from pydantic import BaseModel
from typing import Optional

from app.database.db import get_session
from app.database.models import UserStats, Subscription, User
from app.api import get_current_user

router = APIRouter(prefix="/store")


# ─────────────────────────────────────────
# PAKET TANIMLARI (DB'ye gerek yok, sabit)
# ─────────────────────────────────────────

PACKAGES = [
    {
        "package_id": "credits_50",
        "name": "50 Kredi",
        "description": "Tekli Projeler İçin İdeal",
        "credits": 50,
        "bonus_credits": 0,
        "price": 29.99,
        "currency": "TRY",
        "type": "credits",
        "is_featured": False,
    },
    {
        "package_id": "credits_250",
        "name": "250 Kredi",
        "description": "Tasarım Tutkunlarına",
        "credits": 250,
        "bonus_credits": 50,
        "price": 99.99,
        "currency": "TRY",
        "type": "credits",
        "is_featured": True,  # En İyi Fırsat
    },
    {
        "package_id": "weekly_unlimited",
        "name": "Haftalık Sınırsız",
        "description": "Sıra Beklemeden Hızlı Render, Premium Jantlar, Sınırsız Renk Paleti",
        "credits": 9999,  # Sınırsız yerine yüksek bir sayı
        "bonus_credits": 0,
        "price": 199.99,
        "currency": "TRY",
        "type": "subscription",
        "duration_days": 7,
        "is_featured": True,  # En Çok Tercih Edilen
    },
]


# ─────────────────────────────────────────
# ŞEMALAR
# ─────────────────────────────────────────

class PackageResponse(BaseModel):
    package_id: str
    name: str
    description: str
    credits: int
    bonus_credits: int
    price: float
    currency: str
    type: str
    is_featured: bool
    duration_days: Optional[int] = None


class PurchaseResponse(BaseModel):
    message: str
    package_name: str
    credits_added: int
    current_credits: int
    subscription_tier: Optional[str] = None
    subscription_end: Optional[datetime] = None


# ─────────────────────────────────────────
# ENDPOINTler
# ─────────────────────────────────────────

@router.get("/packages", response_model=List[PackageResponse], tags=["Store"])
async def get_packages(current_user: User = Depends(get_current_user)):
    """Mağazadaki tüm paketleri listeler."""
    return PACKAGES


@router.post("/purchase/{package_id}", response_model=PurchaseResponse, tags=["Store"])
async def purchase_package(
    package_id: str,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Paketi satın al (şimdilik ödeme yok, direkt kredi ekler).
    Gerçek ödeme entegrasyonu sonradan buraya eklenecek.
    """

    # Paketi bul
    package = next((p for p in PACKAGES if p["package_id"] == package_id), None)
    if not package:
        raise HTTPException(status_code=404, detail="Paket bulunamadı.")

    # Kullanıcının stats kaydını al
    result = await db.execute(select(UserStats).where(UserStats.user_id == current_user.user_id))
    user_stats = result.scalar_one_or_none()

    if not user_stats:
        raise HTTPException(status_code=404, detail="Kullanıcı istatistikleri bulunamadı.")

    credits_to_add = package["credits"] + package["bonus_credits"]
    subscription_tier = None
    subscription_end = None

    if package["type"] == "credits":
        # Kredileri ekle
        user_stats.user_credi += credits_to_add

    elif package["type"] == "subscription":
        # Aboneliği güncelle
        result = await db.execute(
            select(Subscription).where(Subscription.user_id == current_user.user_id)
            .order_by(Subscription.subscription_id.desc())
        )
        subscription = result.scalar_one_or_none()

        end_date = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=package["duration_days"])

        if subscription:
            subscription.tier = "premium"
            subscription.start_date = datetime.now(timezone.utc).replace(tzinfo=None)
            subscription.end_date = end_date
        else:
            new_sub = Subscription(
                user_id=current_user.user_id,
                tier="premium",
                start_date=datetime.now(timezone.utc).replace(tzinfo=None),
                end_date=end_date
            )
            db.add(new_sub)

        # Abonelikte de kredi ekle
        user_stats.user_credi += credits_to_add
        subscription_tier = "premium"
        subscription_end = end_date

    await db.commit()
    await db.refresh(user_stats)

    return PurchaseResponse(
        message="Satın alma başarılı!",
        package_name=package["name"],
        credits_added=credits_to_add,
        current_credits=user_stats.user_credi,
        subscription_tier=subscription_tier,
        subscription_end=subscription_end,
    )


@router.get("/my-credits", tags=["Store"])
async def get_my_credits(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Kullanıcının mevcut kredi ve abonelik bilgisini getirir."""
    stats_result = await db.execute(select(UserStats).where(UserStats.user_id == current_user.user_id))
    user_stats = stats_result.scalar_one_or_none()

    sub_result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == current_user.user_id)
        .order_by(Subscription.subscription_id.desc())
    )
    subscription = sub_result.scalar_one_or_none()

    # Abonelik süresi dolmuş mu?
    is_premium = False
    sub_end = None
    if subscription and subscription.end_date:
        sub_end = subscription.end_date
        is_premium = subscription.end_date > datetime.now(timezone.utc).replace(tzinfo=None)

    return {
        "credits": user_stats.user_credi if user_stats else 0,
        "is_premium": is_premium,
        "subscription_tier": subscription.tier if subscription else "free",
        "subscription_end": sub_end,
    }


# ─────────────────────────────────────────
# REFERRAL (DAVET) - 50 KREDİ
# ─────────────────────────────────────────

@router.post("/referral", status_code=status.HTTP_200_OK, tags=["Store"])
async def referral_bonus(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Arkadaş davet eden kullanıcıya 1 defalık 50 kredi ekler."""

    # Daha önce kullanmış mı?
    if current_user.referral_used:
        raise HTTPException(status_code=400, detail="Davet bonusunu zaten kullandınız!")

    result = await db.execute(select(UserStats).where(UserStats.user_id == current_user.user_id))
    user_stats = result.scalar_one_or_none()

    if not user_stats:
        raise HTTPException(status_code=404, detail="Kullanıcı istatistikleri bulunamadı.")

    user_stats.user_credi += 50
    current_user.referral_used = True
    await db.commit()
    await db.refresh(user_stats)

    return {
        "message": "Davet bonusu eklendi!",
        "credits_added": 50,
        "current_credits": user_stats.user_credi,
    }