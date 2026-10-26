# app/database/crud/user_crud.py — mevcut dosyayı bununla değiştir

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.models import User, UserStats
from app.database.schemas import UserCreate
from app.core import get_password_hash


async def get_user_by_email(db: AsyncSession, email: str):
    result = await db.execute(select(User).where(User.email == email))
    return result.scalars().first()


async def UserCreate(db: AsyncSession, user_in: UserCreate):
    hashed_password = get_password_hash(user_in.password)

    db_user = User(
        name=user_in.name,
        surname=user_in.surname,   # eksikti
        email=user_in.email,
        password=hashed_password
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    # Kullanıcı oluşturulunca otomatik UserStats kaydı oluştur
    db_stats = UserStats(
        user_id=db_user.user_id,
        user_credi=0,
        create_image=0,
        render_image=0
    )
    db.add(db_stats)
    await db.commit()

    return db_user


async def UserUpdate(db: AsyncSession, user_id: int, user_in: UserCreate):
    result = await db.execute(select(User).where(User.user_id == user_id))  # user_id düzeltildi
    db_user = result.scalars().first()
    if not db_user:
        return None
    db_user.name = user_in.name
    db_user.surname = user_in.surname
    db_user.email = user_in.email
    db_user.password = get_password_hash(user_in.password)
    await db.commit()
    await db.refresh(db_user)
    return db_user