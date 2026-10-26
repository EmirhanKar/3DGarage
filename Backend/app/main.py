# app/main.py — CORS ve güncel hali

import mimetypes
mimetypes.add_type("model/gltf-binary", ".glb")
mimetypes.add_type("model/gltf+json", ".gltf")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.openapi.utils import get_openapi
from fastapi.security import OAuth2PasswordBearer
from fastapi.staticfiles import StaticFiles
import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import update
from app.database.db import init_db, AsyncSessionLocal
from app.database.models import User
from app.api.routers import (
    user_router, upload_image_router,
    plugins_router, community_router,
    store_router, modification_router
)
import os


async def weekly_score_reset_task():
    while True:
        try:
            # Check last reset file
            reset_file = "uploads/last_weekly_reset.txt"
            need_reset = False
            now = datetime.now(timezone.utc)
            
            if os.path.exists(reset_file):
                try:
                    with open(reset_file, "r") as f:
                        content = f.read().strip()
                    last_reset = datetime.fromisoformat(content)
                    if last_reset.tzinfo is None:
                        last_reset = last_reset.replace(tzinfo=timezone.utc)
                    if now - last_reset >= timedelta(days=7):
                        need_reset = True
                except Exception:
                    need_reset = True
            else:
                need_reset = True
                
            if need_reset:
                # Perform global reset
                async with AsyncSessionLocal() as db:
                    q = (
                        update(User)
                        .values(
                            game_score=0,
                            game_score_car_racing=0,
                            game_score_fly_bird=0,
                            game_score_updated_at=now,
                            game_score_car_racing_updated_at=now,
                            game_score_fly_bird_updated_at=now
                        )
                    )
                    await db.execute(q)
                    await db.commit()
                # Update file
                with open(reset_file, "w") as f:
                    f.write(now.isoformat())
                print("Global weekly game scores reset successfully.")
        except Exception as e:
            print(f"Error in weekly_score_reset_task: {e}")
            
        # Sleep for 1 hour before checking again
        await asyncio.sleep(3600)


async def dead_lease_watchdog_task():
    from app.core.config import DEAD_LEASE_CHECK_INTERVAL_SECONDS
    from app.api.routers.upload_image_router import expire_dead_leases
    while True:
        try:
            await asyncio.sleep(DEAD_LEASE_CHECK_INTERVAL_SECONDS)
            async with AsyncSessionLocal() as db:
                expired = await expire_dead_leases(db)
                if expired > 0:
                    print(f"[Lifespan] {expired} dead 3D leases marked as LEASE_EXPIRED.")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Lifespan] dead_lease_watchdog error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    disable_bg = os.getenv("DISABLE_BACKGROUND_TASKS", "false").lower() in ("true", "1")
    if disable_bg:
        yield
        return

    await init_db()
    bg_task = asyncio.create_task(weekly_score_reset_task())
    watchdog_task = asyncio.create_task(dead_lease_watchdog_task())
    try:
        yield
    finally:
        watchdog_task.cancel()
        bg_task.cancel()
        try:
            await asyncio.gather(watchdog_task, bg_task, return_exceptions=True)
        except Exception:
            pass


app = FastAPI(
    title="MODIF-AI API",
    description="Araç Modifikasyonu Uygulaması Backend Servisi",
    version="1.0.0",
    lifespan=lifespan
)

# ── CORS ────────────────────────────────────────────
# Deploy'da FLUTTER_URL'yi gerçek domain ile değiştir
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,   # Production'da ["https://uygulamaniz.com"] yap
    allow_credentials=False if "*" in ALLOWED_ORIGINS else True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ────────────────────────────────────────────────────

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/login")

# Upload klasörlerini oluştur
for directory in [
    "uploads/images", "uploads/images_2d",
    "uploads/images_3d", "uploads/profiles",
    "uploads/plugins/jants", "uploads/thumbnails"
]:
    os.makedirs(directory, exist_ok=True)

# Router'lar
app.include_router(user_router.router, tags=["Kullanıcı İşlemleri"])
app.include_router(upload_image_router.router, tags=["Scans"])
app.include_router(plugins_router.router, tags=["Plugins"])
app.include_router(community_router.router, tags=["Community"])
app.include_router(store_router.router, tags=["Store"])
app.include_router(modification_router.router, tags=["Modifications"])

# Statik dosya servisi
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


@app.get("/", tags=["Sistem"])
async def root():
    return {
        "status": "online",
        "message": "MODIF-AI API'ye hoş geldiniz!",
        "docs": "/docs"
    }


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    openapi_schema["components"]["securitySchemes"] = {
        "OAuth2PasswordBearer": {
            "type": "oauth2",
            "flows": {
                "password": {
                    "tokenUrl": "users/login",
                    "scopes": {}
                }
            }
        }
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi