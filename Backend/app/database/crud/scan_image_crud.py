from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.models import ScanImage
from app.database.schemas import ScanImageCreate

async def scanImageCreate(db: AsyncSession, scan_id: int , image_url: str, label: str = None, modification_id: int = None):
    db_scan_image = ScanImage(
        scan_id=scan_id,
        image_url=image_url,
        modification_id=modification_id
    )
    
    db.add(db_scan_image)
    await db.commit()
    return db_scan_image

async def scanImageUpdate(db: AsyncSession, scanimage_id: int, modification_id: int = None):
    result = await db.execute(select(ScanImage).where(ScanImage.scanimage_id == scanimage_id))
    db_scan_image = result.scalars().first()
    
    if not db_scan_image:
        return None
    if modification_id is not None:
        db_scan_image.modification_id = modification_id
    
    await db.commit()
    await db.refresh(db_scan_image)
    return db_scan_image


async def scanImageRead(db: AsyncSession, scanimage_id: int):
    result = await db.execute(select(ScanImage).where(ScanImage.scanimage_id == scanimage_id))
    return result.scalars().first()

