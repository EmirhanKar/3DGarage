from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from app.database.base import Base
from dotenv import load_dotenv
import os
from sqlalchemy import text

load_dotenv()

DB_URL = os.getenv("DB_URL")
if not DB_URL:
    DB_URL = "sqlite+aiosqlite:///./3dgarage.db"

# SQLite için echo ve connect_args
connect_args = {}
if "sqlite" in DB_URL:
    connect_args = {"check_same_thread": False}

engine = create_async_engine(DB_URL, echo=False, connect_args=connect_args)
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # Mevcut veritabanlarında eksik Tripo v3 sütunlarını otomatik ekle
        cols_to_add = [
            ("mode", "VARCHAR(20) DEFAULT '3d'"),
            ("options_json", "TEXT"),
            ("modifications_json", "TEXT"),
            ("edit_task_id", "VARCHAR(100)"),
            ("model_task_id", "VARCHAR(100)"),
            ("credits_estimated", "INTEGER DEFAULT 0"),
            ("credits_consumed", "INTEGER DEFAULT 0"),
            ("is_locked", "BOOLEAN DEFAULT 0"),
        ]
        for col_name, col_type in cols_to_add:
            try:
                await conn.execute(text(f"ALTER TABLE scans ADD COLUMN {col_name} {col_type}"))
            except Exception:
                pass


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session
