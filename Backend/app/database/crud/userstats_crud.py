from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.models import UserStats
from app.database.schemas import UserStatsCreate


async def UserStatsCreate(db: AsyncSession, userstats_in: UserStatsCreate , user_id : int):

    db_userstats = UserStats(
        user_id = user_id,
        user_credi = userstats_in.user_credi,
        create_image = userstats_in.create_image,
        render_image = userstats_in.render_image   
    )      
    
    
    db.add(db_userstats)
    await db.commit()
    await db.refresh(db_userstats)
    return db_userstats


async def update_user_stats(db: AsyncSession, user_id: int, userstats_in: dict):
    result = await db.execute(select(UserStats).where(UserStats.user_id == user_id))
    db_userstats = result.scalars().first()
    
    if not db_userstats:
        return None
    
    for key, value in userstats_in.items():
        if hasattr(db_userstats, key):
            setattr(db_userstats, key, value)
    
    await db.commit()
    await db.refresh(db_userstats)
    return db_userstats