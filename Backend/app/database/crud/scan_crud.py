# app/database/crud/scan_crud.py — mevcut dosyayı bununla değiştir

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.models import Scans, Modification
from app.database.schemas import ScanCreate
from sqlalchemy.orm import selectinload


async def scanCreate(
    db: AsyncSession,
    user_id: int,
    method: str,
    car_name: str = "İsimsiz Araç",
    description: str = None
):
    new_scan = Scans(
        user_id=user_id,
        method=method,
        car_name=car_name,
        description=description,
        status="pending"
    )
    db.add(new_scan)
    await db.commit()
    await db.refresh(new_scan)
    return new_scan


async def scanUpdate(db: AsyncSession, scan_id: int, status: str):
    result = await db.execute(select(Scans).where(Scans.scan_id == scan_id))
    db_scan = result.scalars().first()
    if not db_scan:
        return None
    db_scan.status = status
    await db.commit()
    await db.refresh(db_scan)
    return db_scan


async def scanRead(db: AsyncSession, scan_id: int):
    result = await db.execute(select(Scans).where(Scans.scan_id == scan_id))
    return result.scalars().first()


async def get_user_scans(db: AsyncSession, user_id: int):
    """Sadece tamamlanmış scan'leri getirir — Garajım ekranı için."""
    query = (
        select(Scans)
        .where(Scans.user_id == user_id, Scans.status == "completed")
        .options(
            selectinload(Scans.processed_2d),
            selectinload(Scans.processed_3d),
            selectinload(Scans.images),
            selectinload(Scans.modifications).selectinload(Modification.jant),
            selectinload(Scans.modifications).selectinload(Modification.colors)
        )
        .order_by(Scans.created_at.desc())
    )
    result = await db.execute(query)
    return result.scalars().all()


async def get_scan_by_id(db: AsyncSession, scan_id: int, user_id: int):
    """Belirli bir aracı tüm detaylarıyla getirir."""
    query = (
        select(Scans)
        .where(Scans.scan_id == scan_id, Scans.user_id == user_id)
        .options(
            selectinload(Scans.processed_2d),
            selectinload(Scans.processed_3d),
            selectinload(Scans.images),
            selectinload(Scans.modifications).selectinload(Modification.jant),
            selectinload(Scans.modifications).selectinload(Modification.colors)
        )
    )
    result = await db.execute(query)
    return result.scalars().first()