from datetime import datetime, timezone

from sqlalchemy import select

from fastapi import APIRouter, Depends, HTTPException ,status , UploadFile, File 
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.db import get_session
from app.database.schemas import UserCreate , UserResponse , UserLogin , UserToken , UserUpdate , UserStatsResponse
from app.database.crud import user_crud , userstats_crud
from app.database.models import User , UserStats , Subscription
from app.core import get_password_hash, verify_password , create_access_token
from app.api import get_current_user
from fastapi.security import OAuth2PasswordRequestForm
import os , uuid
from pydantic import BaseModel
from datetime import timedelta

class GameScoreInput(BaseModel):
    score: int
    game_type: str = "car_racing"

class LeaderboardResponse(BaseModel):
    username: str
    score: int

router = APIRouter(prefix="/users")

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_in: UserCreate, db: AsyncSession = Depends(get_session)):
    db_user = await db.execute(select(User).where(User.email == user_in.email))
    if db_user.scalars().first():
        raise HTTPException(status_code=400, detail="Bu e-posta zaten kayıtlı")

    hashed_password = get_password_hash(user_in.password)
    new_user = User(
        name=user_in.name,
        surname=user_in.surname,
        email=user_in.email,
        password=hashed_password,
        phone_number=user_in.phone_number or ""
    )
        
    db.add(new_user)
    await db.flush() 

    new_stats = UserStats(
        user_id=new_user.user_id, 
        user_credi=100,
        create_image=0,
        render_image=0
    )
        
    db.add(new_stats)
    
    new_subs = Subscription(
        user_id=new_user.user_id,
        tier="free",
        start_date= datetime.now(timezone.utc).replace(tzinfo=None),
        end_date=None
    )
    
    db.add(new_subs)
    
    await db.commit()
    await db.refresh(new_user)
        
    return new_user



@router.post("/login", response_model = UserToken , status_code = status.HTTP_200_OK)
async def login_user(form_data : OAuth2PasswordRequestForm = Depends(), db : AsyncSession = Depends(get_session)):
    result = await db.execute(select(User).where(User.email == form_data.username))    
    db_user = result.scalars().first()
    
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-posta veya şifre hatalı"
        )
    
    is_password_correct = verify_password(
        plain_password = form_data.password,
        hashed_password = db_user.password
    )
    
    if not is_password_correct:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED
        )    
    
    token_data = {"sub" : str(db_user.user_id)}
    
    access_token = create_access_token(data = token_data)
    return{
        "access_token": access_token,
        "token_type" : "bearer"
    }
    
    
@router.get("/me",response_model = UserResponse)
async def get_my_profil(db : AsyncSession = Depends(get_session),current_user: User = Depends(get_current_user)):
    
    result = await db.execute(select(UserStats).where(UserStats.user_id == current_user.user_id))
    user_stats = result.scalar()
    return {
        "user_id": current_user.user_id,
        "name": current_user.name,
        "surname": current_user.surname,
        "email": current_user.email,
        "profil_image_url": current_user.profil_image_url,
        "phone_number": current_user.phone_number or "",
        "user_credi": user_stats.user_credi if user_stats else 0,
        "create_image": user_stats.create_image if user_stats else 0,
        "render_image": user_stats.render_image if user_stats else 0
    }
    
    

@router.post("/me/upload-photo", response_model=UserResponse)
async def upload_profile_photo(
    photo: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # Content type kontrolü — Flutter'dan image/jpg veya None gelebilir
    ALLOWED_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic", "image/heif"}
    content_type = photo.content_type or ""
    filename = photo.filename or ""
    ext = filename.lower().split(".")[-1] if "." in filename else ""

    gecerli_mi = (
        content_type in ALLOWED_TYPES or
        ext in {"jpg", "jpeg", "png", "webp", "heic", "heif"}
    )

    if not gecerli_mi:
        raise HTTPException(
            status_code=400,
            detail=f"Desteklenmeyen format: '{content_type}'. JPEG, PNG, WEBP veya HEIC yükleyin."
        )

    # Dosyayı kaydet
    upload_dir = os.path.join("uploads", "profiles")
    os.makedirs(upload_dir, exist_ok=True)

    unique_filename = f"profile_{current_user.user_id}_{uuid.uuid4()}.jpg"
    full_path = os.path.join(upload_dir, unique_filename).replace("\\", "/")

    content = await photo.read()

    # Pillow ile JPEG'e dönüştür (HEIC dahil her format çalışır)
    try:
        import io
        from PIL import Image
        img = Image.open(io.BytesIO(content))
        img = img.convert("RGB")
        img.thumbnail((800, 800))
        img.save(full_path, "JPEG", quality=85)
    except Exception:
        
        with open(full_path, "wb") as f:
            f.write(content)

    if current_user.profil_image_url and os.path.exists(current_user.profil_image_url):
        try:
            os.remove(current_user.profil_image_url)
        except Exception:
            pass  
    current_user.profil_image_url = full_path
    await db.commit()
    await db.refresh(current_user)

    result = await db.execute(select(UserStats).where(UserStats.user_id == current_user.user_id))
    user_stats = result.scalar()

    return {
        "user_id": current_user.user_id,
        "name": current_user.name,
        "surname": current_user.surname,
        "email": current_user.email,
        "profil_image_url": current_user.profil_image_url,
        "phone_number": current_user.phone_number or "",
        "user_credi": user_stats.user_credi if user_stats else 0,
        "create_image": user_stats.create_image if user_stats else 0,
        "render_image": user_stats.render_image if user_stats else 0,
    }
    
@router.patch("/me", response_model=UserResponse)
async def update_my_profile(
    user_in: UserUpdate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    if user_in.name is not None:
        current_user.name = user_in.name
 
    if user_in.surname is not None:
        current_user.surname = user_in.surname
 
    if user_in.email is not None:
        result = await db.execute(select(User).where(User.email == user_in.email))
        existing = result.scalar_one_or_none()
        if existing and existing.user_id != current_user.user_id:
            raise HTTPException(status_code=400, detail="Bu e-posta zaten kullanımda.")
        current_user.email = user_in.email
 
    if user_in.phone_number is not None:
        current_user.phone_number = user_in.phone_number
 
    if user_in.password is not None:
        current_user.password = get_password_hash(user_in.password)
 
    await db.commit()
    await db.refresh(current_user)
 
    result = await db.execute(select(UserStats).where(UserStats.user_id == current_user.user_id))
    user_stats = result.scalar()
 
    return {
        "user_id": current_user.user_id,
        "name": current_user.name,
        "surname": current_user.surname,
        "email": current_user.email,
        "profil_image_url": current_user.profil_image_url,
        "phone_number": current_user.phone_number or "",
        "user_credi": user_stats.user_credi if user_stats else 0,
        "create_image": user_stats.create_image if user_stats else 0,
        "render_image": user_stats.render_image if user_stats else 0,
    }


@router.delete("/me", status_code=status.HTTP_200_OK)
async def delete_my_account(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Kullanıcı hesabını ve tüm ilişkili verileri kalıcı olarak siler."""
    from app.database.models import UserStats, Subscription, Modification, Scans, Comment, Like

    # İlişkili verileri sil
    await db.execute(select(UserStats).where(UserStats.user_id == current_user.user_id))
    for model_cls in [Like, Comment, Modification, Subscription, UserStats]:
        result = await db.execute(select(model_cls).where(model_cls.user_id == current_user.user_id))
        for row in result.scalars().all():
            await db.delete(row)

    # Kullanıcının scan'lerini sil
    scan_result = await db.execute(select(Scans).where(Scans.user_id == current_user.user_id))
    for scan in scan_result.scalars().all():
        await db.delete(scan)

    # Kullanıcıyı sil
    await db.delete(current_user)
    await db.commit()

    return {"message": "Hesabınız ve tüm verileriniz kalıcı olarak silindi."}

@router.post("/game/score")
async def update_game_score(
    score_in: GameScoreInput,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    now = datetime.utcnow()
    game_type = score_in.game_type
    
    if game_type == "fly_bird":
        if current_user.game_score_fly_bird_updated_at:
            diff = now.replace(tzinfo=None) - current_user.game_score_fly_bird_updated_at.replace(tzinfo=None)
            if diff.days >= 7:
                current_user.game_score_fly_bird = score_in.score
                current_user.game_score_fly_bird_updated_at = now
            else:
                if score_in.score > current_user.game_score_fly_bird:
                    current_user.game_score_fly_bird = score_in.score
                    current_user.game_score_fly_bird_updated_at = now
        else:
            current_user.game_score_fly_bird = score_in.score
            current_user.game_score_fly_bird_updated_at = now
        await db.commit()
        return {"message": "Score updated", "best_score": current_user.game_score_fly_bird}
    else:
        # Defaults to car_racing
        if current_user.game_score_car_racing_updated_at:
            diff = now.replace(tzinfo=None) - current_user.game_score_car_racing_updated_at.replace(tzinfo=None)
            if diff.days >= 7:
                current_user.game_score_car_racing = score_in.score
                current_user.game_score_car_racing_updated_at = now
            else:
                if score_in.score > current_user.game_score_car_racing:
                    current_user.game_score_car_racing = score_in.score
                    current_user.game_score_car_racing_updated_at = now
        else:
            current_user.game_score_car_racing = score_in.score
            current_user.game_score_car_racing_updated_at = now
            
        # Also update legacy game_score for fallback queries
        if current_user.game_score_updated_at:
            diff = now.replace(tzinfo=None) - current_user.game_score_updated_at.replace(tzinfo=None)
            if diff.days >= 7:
                current_user.game_score = score_in.score
                current_user.game_score_updated_at = now
            else:
                if score_in.score > current_user.game_score:
                    current_user.game_score = score_in.score
                    current_user.game_score_updated_at = now
        else:
            current_user.game_score = score_in.score
            current_user.game_score_updated_at = now
            
        await db.commit()
        return {"message": "Score updated", "best_score": current_user.game_score_car_racing}

@router.get("/game/leaderboard", response_model=list[LeaderboardResponse])
async def get_game_leaderboard(game_type: str = "car_racing", db: AsyncSession = Depends(get_session)):
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    if game_type == "fly_bird":
        query = select(User).where(User.game_score_fly_bird > 0, User.game_score_fly_bird_updated_at >= one_week_ago).order_by(User.game_score_fly_bird.desc()).limit(3)
        result = await db.execute(query)
        users = result.scalars().all()
        return [{"username": u.name or "Anonim", "score": u.game_score_fly_bird} for u in users]
    else:
        query = select(User).where(User.game_score_car_racing > 0, User.game_score_car_racing_updated_at >= one_week_ago).order_by(User.game_score_car_racing.desc()).limit(3)
        result = await db.execute(query)
        users = result.scalars().all()
        return [{"username": u.name or "Anonim", "score": u.game_score_car_racing} for u in users]
