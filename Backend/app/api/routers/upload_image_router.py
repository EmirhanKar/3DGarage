from datetime import datetime, timezone, timedelta
from sqlalchemy import select, update, or_, and_, func
from sqlalchemy.inspection import inspect
from fastapi import APIRouter, Depends, Form, HTTPException, status, UploadFile, File, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.database.db import get_session
from app.database.schemas import ScanResponse, ScanCreate
from app.database.schemas.scan_schemas import (
    ClaimResponse, ProgressRequest, FailRequest,
    Processed3DInfo, Processed2DInfo, ModificationBrief, ScanImageBrief
)
from app.database.crud import scanCreate, scanImageCreate, get_user_scans, scan_crud
from app.database.models import Scans, Processed3D, Processed2D, User, UserStats, Modification, Jant, Colors
from app.core.config import (
    PROCESSING_LEASE_SECONDS, MAX_JOB_ATTEMPTS, RETRY_COOLDOWN_SECONDS,
    ENABLE_CAR_PRECHECK, CREDIT_COST_2D_EDIT, CREDIT_COST_3D_SINGLE_BASE,
    CREDIT_COST_3D_MULTIVIEW_BASE, calculate_scan_credits
)
from typing import List, Optional, Dict, Any
from PIL import Image
import os
import uuid
import re
import json
import logging
from app.api.deps import get_current_user, get_worker_api_key, get_admin_api_key
from app.services.car_detection import detect_car as run_car_detection
from app.services.storage import LocalStorageService
from app.services.tripo_service import tripo_service, TripoAPIError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scans")

# ── KREDİ MALİYETLERİ (Geriye Dönük Uyumluluk) ──
CREDIT_COST_2D = 15
CREDIT_COST_3D = 45

# ── KABUL EDİLEN FORMATLAR ──
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}

PHOTO_COUNTS = {
    "2d": 1,
    "3d": 2,          # Çoklu görünüm için en az 2 görsel
    "3d_single": 1,   # Tek fotoğraftan 3D model
    "single": 1,      # Tek fotoğraftan 3D model alias
    "multiview": 2,   # Çoklu görünüm alias
}


def sanitize_error_detail(detail: Optional[str]) -> Optional[str]:
    """Hata detayındaki dosya yollarını, token/şifreleri ve stack trace'leri temizler."""
    if not detail:
        return None
    lines = detail.strip().splitlines()
    if len(lines) > 2 and any("Traceback" in l or "File \"" in l for l in lines):
        detail = " ".join([l.strip() for l in lines[-2:]])
    else:
        detail = " ".join([l.strip() for l in lines])

    detail = re.sub(r'[A-Za-z]:\\[^ \t\n\r"\'<>]+', '[PATH]', detail)
    detail = re.sub(r'/(?:[a-zA-Z0-9_\.\-]+/)+[a-zA-Z0-9_\.\-]+', '[PATH]', detail)
    detail = re.sub(r'(token|key|secret|password)=[^&\s"\']+', r'\1=[REDACTED]', detail, flags=re.IGNORECASE)
    return detail[:1000]


# ══════════════════════════════════════════════════════════════════════════════
# YENİ TRIPO v3 ENTEGRASYONLU UÇ NOKTALAR (/prepare, /confirm_3d, /retry_edit)
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/prepare", status_code=status.HTTP_201_CREATED, response_model=ScanResponse)
async def prepare_scan(
    files: List[UploadFile] = File(...),
    car_name: str = Form(...),
    description: Optional[str] = Form(None),
    mode: str = Form("3d"),                # "2d" veya "3d"
    method: str = Form("3d_single"),       # "2d", "3d_single", "3d" (multiview)
    options_json: Optional[str] = Form(None),       # 3D Kalite seçenekleri JSON
    modifications_json: Optional[str] = Form(None), # Seçilen modifikasyonlar JSON
    skip_car_precheck: bool = Form(False),
    db: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user)
):
    """
    Kullanıcının fotoğrafını, mod seçimini (2D/3D), 3D kalite seçeneklerini ve
    seçtiği modifikasyonları (renk, jant, spoiler) alır.
    - 2D Düzenleme gerekiyorsa önce Tripo image-to-image görevini başlatır (pending_edit).
    - Modifikasyon seçilmemiş doğrudan 3D ise hemen Tripo image-to-model görevini başlatır (generating_3d).
    - Krediyi atomik işlemle kontrol eder ve düşer.
    """
    # 1. Metod ve Mod Doğrulama
    if mode not in ("2d", "3d"):
        raise HTTPException(status_code=400, detail="Geçersiz mod: '2d' veya '3d' olmalıdır.")

    if method not in PHOTO_COUNTS:
        raise HTTPException(status_code=400, detail=f"Geçersiz metod: '{method}'.")

    min_expected = PHOTO_COUNTS[method]
    if method in ("3d", "multiview") and len(files) < min_expected:
        raise HTTPException(status_code=400, detail=f"Çoklu açı 3D için en az {min_expected} fotoğraf gereklidir.")
    elif method in ("2d", "3d_single", "single") and len(files) < 1:
        raise HTTPException(status_code=400, detail="Lütfen en az bir fotoğraf yükleyin.")

    # 2. Dosya Format ve Boyut Kontrolü (Max 20 MB)
    MAX_FILE_SIZE = 20 * 1024 * 1024
    file_bytes_list: List[bytes] = []
    first_file_bytes: Optional[bytes] = None

    for idx, file in enumerate(files):
        content_type = file.content_type or ""
        filename = file.filename or ""
        ext = filename.lower().split(".")[-1] if "." in filename else ""

        if not (content_type in ALLOWED_CONTENT_TYPES or ext in {"jpg", "jpeg", "png", "webp", "heic", "heif"}):
            raise HTTPException(status_code=400, detail=f"'{filename}' desteklenmeyen formatta (JPEG, PNG, WEBP kabul edilir).")

        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"'{filename}' çok büyük ({len(content) // (1024*1024)} MB). Maksimum 20 MB.")

        file_bytes_list.append(content)
        if idx == 0:
            first_file_bytes = content

    # 3. Araç Ön Kontrolü (MobileNet Pre-check)
    if ENABLE_CAR_PRECHECK and not skip_car_precheck and first_file_bytes:
        try:
            detect_res = run_car_detection(first_file_bytes)
            if not detect_res.get("is_car", True):
                raise HTTPException(
                    status_code=400,
                    detail="Yüklenen fotoğrafta araç tespit edilemedi. Lütfen net bir araba fotoğrafı yükleyin."
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("Car precheck warning: %s", e)

    # 4. JSON Ayrıştırma ve Modifikasyon Kontrolü
    options: Dict[str, Any] = {}
    if options_json:
        try:
            options = json.loads(options_json)
        except Exception:
            pass

    mods: Dict[str, Any] = {}
    if modifications_json:
        try:
            mods = json.loads(modifications_json)
        except Exception:
            pass

    body_color = mods.get("body_color") or mods.get("color_hex") or mods.get("color")
    rim_name = mods.get("rim_name") or mods.get("rim_id")
    if str(rim_name).lower() in ("none", "null", "0", ""):
        rim_name = None
    spoiler_name = mods.get("spoiler_name") or mods.get("spoiler_id")
    if str(spoiler_name).lower() in ("none", "null", "0", ""):
        spoiler_name = None
    extra_prompt = mods.get("extra_prompt")
    has_modifications = bool(body_color or rim_name or spoiler_name or extra_prompt)

    # 5. Kredi Hesaplama ve Atomik Düşüm
    estimated_credits = calculate_scan_credits(mode=mode, method=method, options=options, has_modifications=has_modifications)

    # İlk aşamada harcanacak kredi:
    # 2D modunda tüm kredi (15) peşin düşülür.
    # 3D modunda modifikasyon varsa önce 2D düzenleme kredisi (15) düşülür. 3D modeli onayladığında geri kalanı düşülür.
    # 3D modunda modifikasyon seçilmemişse direkt 3D üretileceği için tüm 3D kredisi peşin düşülür.
    if mode == "2d":
        initial_cost = CREDIT_COST_2D_EDIT
    else:
        initial_cost = CREDIT_COST_2D_EDIT if has_modifications else estimated_credits

    user_stats = await db.get(UserStats, current_user.user_id, with_for_update=True)
    if not user_stats or user_stats.user_credi < initial_cost:
        raise HTTPException(
            status_code=402,
            detail=f"Yetersiz kredi! Gerekli: {initial_cost}, Mevcut: {user_stats.user_credi if user_stats else 0}"
        )

    user_stats.user_credi -= initial_cost
    user_stats.create_image += 1

    # 6. Tarama Kaydını Veritabanında Oluştur
    initial_status = "pending_edit" if (has_modifications or mode == "2d") else "generating_3d"
    new_scan = Scans(
        user_id=current_user.user_id,
        method=method,
        mode=mode,
        status=initial_status,
        car_name=car_name,
        description=description,
        options_json=options_json,
        modifications_json=modifications_json,
        credits_estimated=estimated_credits,
        credits_consumed=initial_cost,
        progress_percent=20 if initial_status == "pending_edit" else 50,
        progress_stage="Görseller hazırlanıyor...",
    )
    db.add(new_scan)
    await db.flush()  # new_scan.scan_id üretilir

    # 7. Dosyaları Yerel Depolamaya Kaydet
    scan_folder = f"images_{mode}/scan_{new_scan.scan_id}"
    thumb_folder = f"thumbnails/{current_user.user_id}"

    first_image_path = None
    uploaded_file_tokens: List[str] = []

    for idx, content in enumerate(file_bytes_list):
        filename = f"{idx:04d}_{uuid.uuid4().hex[:8]}.jpg"
        saved_path = LocalStorageService.save_bytes(content, scan_folder, filename)
        await scanImageCreate(db, new_scan.scan_id, saved_path)

        if idx == 0:
            first_image_path = saved_path

    # Thumbnail oluştur
    thumb_filename = f"thumb_{new_scan.scan_id}.jpg"
    thumb_path = LocalStorageService.create_thumbnail(first_image_path, thumb_folder, thumb_filename)

    # Processed kayıtları
    p2d = Processed2D(scan_id=new_scan.scan_id, thumbnail_url=thumb_path)
    db.add(p2d)
    if mode == "3d":
        p3d = Processed3D(scan_id=new_scan.scan_id, thumbnail_url=thumb_path)
        db.add(p3d)

    # 8. Tripo API Görevini Başlat
    try:
        # Ana araç görselini Tripo'ya yükle
        car_token = await tripo_service.upload_file(file_bytes_list[0], filename="car_input.jpg")

        if has_modifications or mode == "2d":
            # 2D Image-to-Image Akışı
            ref_tokens: List[str] = []
            has_rims = False
            has_spoiler = False

            # Jant referans görseli kontrolü
            if rim_name:
                rim_file_path = os.path.join("uploads", "catalog", "rims", f"{rim_name}.png")
                if not os.path.exists(rim_file_path):
                    rim_file_path = os.path.join("uploads", "catalog", "rims", f"{rim_name}")
                if os.path.exists(rim_file_path):
                    with open(rim_file_path, "rb") as rf:
                        rim_token = await tripo_service.upload_file(rf.read(), filename="rim_ref.png")
                        ref_tokens.append(rim_token)
                        has_rims = True

            # Rüzgarlık / Spoiler referans görseli kontrolü
            if spoiler_name:
                spoiler_file_path = os.path.join("uploads", "catalog", "spoilers", f"{spoiler_name}.png")
                if not os.path.exists(spoiler_file_path):
                    spoiler_file_path = os.path.join("uploads", "catalog", "spoilers", f"{spoiler_name}")
                if os.path.exists(spoiler_file_path):
                    with open(spoiler_file_path, "rb") as sf:
                        sp_token = await tripo_service.upload_file(sf.read(), filename="spoiler_ref.png")
                        ref_tokens.append(sp_token)
                        has_spoiler = True

            # Prompt oluştur
            prompt = tripo_service.build_modification_prompt(
                body_color=body_color,
                has_rims=has_rims,
                rim_index=2 if has_rims else 0,
                has_spoiler=has_spoiler,
                spoiler_index=(3 if has_rims and has_spoiler else 2 if has_spoiler else 0),
                extra_prompt=extra_prompt
            )

            # Image to image görevi
            task_id = await tripo_service.image_to_image(
                car_image=car_token,
                prompt=prompt,
                reference_images=ref_tokens,
                model="chat_image_2.5_sunburst"
            )
            new_scan.edit_task_id = task_id
            new_scan.status = "pending_edit"
            new_scan.progress_stage = "2D modifikasyon yapay zekası çalışıyor..."
            logger.info("Scan #%d: 2D edit task created: %s", new_scan.scan_id, task_id)

        else:
            # Doğrudan 3D Üretim Akışı (Modifikasyonsuz)
            if method == "3d" and len(file_bytes_list) >= 2:
                # Çoklu görünüm
                views = []
                keys = ["front", "left", "back", "right"]
                for i, c in enumerate(file_bytes_list[:4]):
                    t = await tripo_service.upload_file(c, filename=f"view_{keys[i]}.jpg")
                    views.append({keys[i]: t})
                task_id = await tripo_service.multiview_to_model(views=views, options=options)
            else:
                # Tek görselden 3D
                task_id = await tripo_service.image_to_model(image_input=car_token, options=options)

            new_scan.model_task_id = task_id
            new_scan.status = "generating_3d"
            new_scan.progress_stage = "3D model rekonstrüksiyonu başladı..."
            logger.info("Scan #%d: 3D model task created: %s", new_scan.scan_id, task_id)

    except TripoAPIError as te:
        # Hata durumunda harcanan krediyi derhal iade et!
        user_stats.user_credi += initial_cost
        new_scan.status = "failed"
        new_scan.credits_consumed = 0
        new_scan.error_code = str(te.code)
        new_scan.error_hint = te.user_friendly_tr
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Tripo servisi başlatılamadı: {te.user_friendly_tr}")
    except Exception as ex:
        user_stats.user_credi += initial_cost
        new_scan.status = "failed"
        new_scan.credits_consumed = 0
        new_scan.error_code = "INIT_FAILED"
        new_scan.error_hint = "Bağlantı hatası oluştu, krediniz iade edildi."
        await db.commit()
        raise HTTPException(status_code=500, detail=f"İşlem başlatılırken hata: {str(ex)}")

    await db.commit()
    return await build_scan_response(new_scan, db)


@router.post("/{scan_id}/confirm_3d", response_model=ScanResponse)
async def confirm_3d_generation(
    scan_id: int,
    db: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user)
):
    """
    Kullanıcı üretilen 2D modifiye görseli beğendiğinde ("Beğendim, 3D üret"),
    kalan 3D üretim kredisini atomik olarak düşer ve Tripo image-to-model görevini başlatır.
    """
    scan_res = await db.execute(
        select(Scans).where(Scans.scan_id == scan_id).with_for_update()
    )
    scan = scan_res.scalar_one_or_none()

    if not scan:
        raise HTTPException(status_code=404, detail="Tarama bulunamadı.")
    if scan.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Bu taramaya erişim yetkiniz yok.")

    if scan.status not in ("awaiting_confirmation", "edit_ready"):
        raise HTTPException(
            status_code=400,
            detail=f"Tarama onay bekler durumda değil (Mevcut durum: {scan.status})."
        )

    # Çift istek / yarış durumu koruması (Idempotency Lock)
    if scan.is_locked:
        raise HTTPException(status_code=409, detail="Bu tarama için işlem şu anda devam ediyor.")
    scan.is_locked = True
    await db.flush()

    # Kalan 3D kredi maliyeti
    remaining_cost = max(0, scan.credits_estimated - scan.credits_consumed)

    user_stats = await db.get(UserStats, current_user.user_id, with_for_update=True)
    if not user_stats or user_stats.user_credi < remaining_cost:
        scan.is_locked = False
        await db.commit()
        raise HTTPException(
            status_code=402,
            detail=f"Yetersiz kredi. 3D model için gerekli kalan: {remaining_cost}, Mevcut: {user_stats.user_credi if user_stats else 0}"
        )

    user_stats.user_credi -= remaining_cost
    scan.credits_consumed += remaining_cost

    # 3D Model Üretim Görevini Başlat
    options: Dict[str, Any] = {}
    if scan.options_json:
        try:
            options = json.loads(scan.options_json)
        except Exception:
            pass

    try:
        # Tripo image-to-model: Girdi olarak onaylanan 2D edit_task_id'si gönderilir
        input_ref = scan.edit_task_id
        if not input_ref:
            # Fallback: Processed2D görselini yükle
            p2d_res = await db.execute(select(Processed2D).where(Processed2D.scan_id == scan.scan_id))
            p2d = p2d_res.scalar_one_or_none()
            if p2d and p2d.image_url and os.path.exists(p2d.image_url):
                with open(p2d.image_url, "rb") as f:
                    input_ref = await tripo_service.upload_file(f.read(), filename="edited_car.png")

        task_id = await tripo_service.image_to_model(image_input=input_ref, options=options)
        scan.model_task_id = task_id
        scan.status = "generating_3d"
        scan.progress_percent = 50
        scan.progress_stage = "3D model rekonstrüksiyonu başladı..."
        scan.is_locked = False
        logger.info("Scan #%d: 3D generation confirmed and started, task_id=%s", scan.scan_id, task_id)

    except TripoAPIError as te:
        # Kalan krediyi iade et
        user_stats.user_credi += remaining_cost
        scan.credits_consumed -= remaining_cost
        scan.is_locked = False
        scan.error_code = str(te.code)
        scan.error_hint = te.user_friendly_tr
        await db.commit()
        raise HTTPException(status_code=500, detail=f"3D üretim başlatılamadı: {te.user_friendly_tr}")
    except Exception as e:
        user_stats.user_credi += remaining_cost
        scan.credits_consumed -= remaining_cost
        scan.is_locked = False
        scan.error_code = "CONFIRM_FAILED"
        scan.error_hint = "Bağlantı hatası, krediniz iade edildi."
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Hata: {str(e)}")

    await db.commit()
    return await build_scan_response(scan, db)


@router.post("/{scan_id}/retry_edit", response_model=ScanResponse)
async def retry_edit(
    scan_id: int,
    modifications_json: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user)
):
    """
    Kullanıcı 2D önizlemeyi beğenmediğinde seçimlerini değiştirerek veya
    aynı ayarlarla yeniden 2D düzenleme yapılmasını ister.
    """
    scan_res = await db.execute(select(Scans).where(Scans.scan_id == scan_id).with_for_update())
    scan = scan_res.scalar_one_or_none()

    if not scan or scan.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Tarama bulunamadı.")

    if scan.status not in ("awaiting_confirmation", "edit_ready", "failed"):
        raise HTTPException(status_code=400, detail="Bu tarama tekrar düzenlemeye uygun durumda değil.")

    # 2D Düzenleme için ek kredi kontrolü
    cost = CREDIT_COST_2D_EDIT
    user_stats = await db.get(UserStats, current_user.user_id, with_for_update=True)
    if not user_stats or user_stats.user_credi < cost:
        raise HTTPException(status_code=402, detail=f"Yetersiz kredi. Düzenleme için gerekli: {cost}")

    user_stats.user_credi -= cost
    scan.credits_consumed += cost

    if modifications_json:
        scan.modifications_json = modifications_json

    mods: Dict[str, Any] = {}
    if scan.modifications_json:
        try:
            mods = json.loads(scan.modifications_json)
        except Exception:
            pass

    # İlk orijinal görseli bul
    imgs_res = await db.execute(select(Scans).where(Scans.scan_id == scan_id).options(selectinload(Scans.images)))
    scan_with_imgs = imgs_res.scalar_one()
    if not scan_with_imgs.images or not os.path.exists(scan_with_imgs.images[0].image_url):
        raise HTTPException(status_code=400, detail="Orijinal araç görseli bulunamadı.")

    try:
        with open(scan_with_imgs.images[0].image_url, "rb") as f:
            car_token = await tripo_service.upload_file(f.read(), filename="car_original.jpg")

        ref_tokens: List[str] = []
        has_rims = False
        has_spoiler = False
        rim_name = mods.get("rim_name") or mods.get("rim_id")
        spoiler_name = mods.get("spoiler_name") or mods.get("spoiler_id")

        if rim_name:
            rim_path = os.path.join("uploads", "catalog", "rims", f"{rim_name}.png")
            if os.path.exists(rim_path):
                with open(rim_path, "rb") as rf:
                    ref_tokens.append(await tripo_service.upload_file(rf.read(), filename="rim.png"))
                    has_rims = True

        if spoiler_name:
            sp_path = os.path.join("uploads", "catalog", "spoilers", f"{spoiler_name}.png")
            if os.path.exists(sp_path):
                with open(sp_path, "rb") as sf:
                    ref_tokens.append(await tripo_service.upload_file(sf.read(), filename="spoiler.png"))
                    has_spoiler = True

        prompt = tripo_service.build_modification_prompt(
            body_color=mods.get("body_color") or mods.get("color_hex") or mods.get("color"),
            has_rims=has_rims,
            rim_index=2 if has_rims else 0,
            has_spoiler=has_spoiler,
            spoiler_index=(3 if has_rims and has_spoiler else 2 if has_spoiler else 0),
            extra_prompt=mods.get("extra_prompt")
        )

        task_id = await tripo_service.image_to_image(car_image=car_token, prompt=prompt, reference_images=ref_tokens)
        scan.edit_task_id = task_id
        scan.status = "pending_edit"
        scan.progress_percent = 20
        scan.progress_stage = "Yeniden düzenleme başlatıldı..."
        scan.error_code = None
        scan.error_hint = None

    except Exception as e:
        user_stats.user_credi += cost
        scan.credits_consumed -= cost
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Tekrar deneme başarısız: {str(e)}")

    await db.commit()
    return await build_scan_response(scan, db)


# ══════════════════════════════════════════════════════════════════════════════
# GÜNCEL VE SENKRONİZE SCAN DETAYI (GET /scans/{id})
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/{scan_id}", response_model=ScanResponse)
async def get_scan_detail(
    scan_id: int,
    db: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user)
):
    """
    Taramanın durumunu döndürür. Arka planda Tripo görevi devam ediyorsa
    Tripo'dan sorgulayarak durumu günceller, tamamlandıysa GLB / 2D görseli indirir.
    """
    result = await db.execute(
        select(Scans)
        .where(Scans.scan_id == scan_id)
        .options(
            selectinload(Scans.processed_3d),
            selectinload(Scans.processed_2d),
            selectinload(Scans.images),
            selectinload(Scans.modifications).selectinload(Modification.jant),
            selectinload(Scans.modifications).selectinload(Modification.colors)
        )
    )
    scan = result.scalar_one_or_none()

    if not scan:
        raise HTTPException(status_code=404, detail="Tarama bulunamadı!")
    if scan.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Bu veriye erişim yetkiniz yok.")

    # 1. 2D Düzenleme Sorgulaması (pending_edit)
    if scan.status == "pending_edit" and scan.edit_task_id:
        try:
            task = await tripo_service.get_task(scan.edit_task_id)
            task_status = task.get("status")

            if task_status == "success":
                output = task.get("output", {})
                img_url = output.get("rendered_image_url") or output.get("image") or output.get("rendered_image")
                if img_url:
                    saved_path = await LocalStorageService.download_and_save(
                        img_url,
                        f"images_2d/scan_{scan.scan_id}",
                        f"edit_{uuid.uuid4().hex[:8]}.png"
                    )
                    thumb_path = LocalStorageService.create_thumbnail(
                        saved_path,
                        f"thumbnails/{scan.user_id}",
                        f"thumb_edit_{scan.scan_id}.jpg"
                    )

                    if scan.processed_2d:
                        scan.processed_2d.image_url = saved_path
                        scan.processed_2d.thumbnail_url = thumb_path
                    else:
                        p2d = Processed2D(scan_id=scan.scan_id, image_url=saved_path, thumbnail_url=thumb_path)
                        db.add(p2d)

                if scan.mode == "2d":
                    scan.status = "completed"
                    scan.progress_percent = 100
                    scan.progress_stage = "2D modifikasyon tamamlandı!"
                else:
                    # 3D akışında kullanıcı onayına sunulur
                    scan.status = "awaiting_confirmation"
                    scan.progress_percent = 50
                    scan.progress_stage = "2D önizleme hazır. 3D üretim için onay bekleniyor."

                await db.commit()

            elif task_status in ("running", "queued"):
                prog = task.get("progress", 30)
                scan.progress_percent = prog
                scan.progress_stage = "Yapay zeka görseli işliyor..."
                await db.commit()

            elif task_status in ("failed", "cancelled"):
                scan.status = "failed"
                scan.progress_stage = "2D düzenleme başarısız oldu."
                scan.error_code = str(task.get("code", "TASK_FAILED"))
                scan.error_hint = "Görsel işleme tamamlanamadı. Harcanan krediniz iade edilmiştir."

                # Atomik Kredi İadesi
                user_stats = await db.get(UserStats, scan.user_id)
                if user_stats and scan.credits_consumed > 0:
                    user_stats.user_credi += scan.credits_consumed
                    scan.credits_consumed = 0

                await db.commit()

        except Exception as e:
            logger.warning("Error syncing edit_task #%s: %s", scan.edit_task_id, e)

    # 2. 3D Model Üretimi Sorgulaması (generating_3d)
    elif scan.status == "generating_3d" and scan.model_task_id:
        try:
            task = await tripo_service.get_task(scan.model_task_id)
            task_status = task.get("status")

            if task_status == "success":
                output = task.get("output", {})
                model_url = output.get("model_url") or output.get("model")
                rendered_img = output.get("rendered_image_url") or output.get("rendered_image")

                if model_url:
                    saved_glb = await LocalStorageService.download_and_save(
                        model_url,
                        f"images_3d/scan_{scan.scan_id}",
                        f"model_{uuid.uuid4().hex[:8]}.glb"
                    )
                    thumb_path = None
                    if rendered_img:
                        saved_img = await LocalStorageService.download_and_save(
                            rendered_img,
                            f"thumbnails/{scan.user_id}",
                            f"thumb_3d_{scan.scan_id}.png"
                        )
                        thumb_path = saved_img

                    if scan.processed_3d:
                        scan.processed_3d.model_url = saved_glb
                        if thumb_path:
                            scan.processed_3d.thumbnail_url = thumb_path
                    else:
                        p3d = Processed3D(scan_id=scan.scan_id, model_url=saved_glb, thumbnail_url=thumb_path)
                        db.add(p3d)

                scan.status = "completed"
                scan.progress_percent = 100
                scan.progress_stage = "3D model üretimi tamamlandı!"
                await db.commit()

            elif task_status in ("running", "queued"):
                prog = 50 + int(task.get("progress", 0) * 0.5)
                scan.progress_percent = prog
                scan.progress_stage = "3D mesh ve dokular oluşturuluyor..."
                await db.commit()

            elif task_status in ("failed", "cancelled"):
                scan.status = "failed"
                scan.progress_stage = "3D model üretimi başarısız oldu."
                scan.error_code = str(task.get("code", "TASK_FAILED"))
                scan.error_hint = "3D rekonstrüksiyon başarısız. 3D modelleme kredisi iade edildi."

                # 3D aşamasında harcanan krediyi iade et
                user_stats = await db.get(UserStats, scan.user_id)
                if user_stats and scan.credits_consumed > 0:
                    refund_amt = scan.credits_consumed - (CREDIT_COST_2D_EDIT if scan.edit_task_id else 0)
                    if refund_amt > 0:
                        user_stats.user_credi += refund_amt
                        scan.credits_consumed -= refund_amt

                await db.commit()

        except Exception as e:
            logger.warning("Error syncing model_task #%s: %s", scan.model_task_id, e)

    return await build_scan_response(scan, db)


# ══════════════════════════════════════════════════════════════════════════════
# ESKİ VE STANDART UÇ NOKTALAR (TAM GERİYE DÖNÜK UYUMLULUK KORUNUR)
# ══════════════════════════════════════════════════════════════════════════════

async def expire_dead_leases(db: AsyncSession) -> int:
    """Kirası dolmuş eski işçi kayıtlarını sonlandırır."""
    lease_cutoff = func.now() - timedelta(seconds=PROCESSING_LEASE_SECONDS)
    stmt = (
        update(Scans)
        .where(Scans.method.in_(["3d", "3d_single"]))
        .where(Scans.status == "processing")
        .where(Scans.status_updated_at < lease_cutoff)
        .where(Scans.retry_count >= MAX_JOB_ATTEMPTS)
        .values(
            status="failed",
            status_updated_at=func.now(),
            claim_token=None,
            error_code="LEASE_EXPIRED",
            error_hint="İşlem zaman aşımına uğradı."
        )
    )
    res = await db.execute(stmt)
    await db.commit()
    return res.rowcount


@router.post("/upload_image", status_code=status.HTTP_201_CREATED, response_model=ScanResponse)
async def upload_image(
    files: List[UploadFile] = File(...),
    car_name: str = Form(...),
    description: str = Form(None),
    method: str = Form(...),
    db: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user)
):
    """Eski mobil istemci uyumluluğu için mevcut upload_image rotası."""
    # Yönlendirme: Yeni prepare mantığına bağla
    mode = "2d" if method == "2d" else "3d"
    return await prepare_scan(
        files=files,
        car_name=car_name,
        description=description,
        mode=mode,
        method=method,
        options_json=None,
        modifications_json=None,
        skip_car_precheck=False,
        db=db,
        current_user=current_user
    )


@router.get("/garage", response_model=List[ScanResponse])
async def get_my_scans(
    db: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user)
):
    scans = await get_user_scans(db, user_id=current_user.user_id)
    return [await build_scan_response(s, db) for s in scans]


@router.get("/garage/{scan_id}", response_model=ScanResponse)
async def get_scan_details(
    scan_id: int,
    db: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user)
):
    return await get_scan_detail(scan_id=scan_id, db=db, current_user=current_user)


async def build_scan_response(scan: Scans, db: Optional[AsyncSession] = None) -> ScanResponse:
    if db is not None:
        try:
            result = await db.execute(
                select(Scans)
                .where(Scans.scan_id == scan.scan_id)
                .options(
                    selectinload(Scans.processed_3d),
                    selectinload(Scans.processed_2d),
                    selectinload(Scans.images),
                    selectinload(Scans.modifications).selectinload(Modification.jant),
                    selectinload(Scans.modifications).selectinload(Modification.colors),
                )
            )
            loaded = result.scalar_one_or_none()
            if loaded:
                scan = loaded
        except Exception:
            pass

    ins = inspect(scan)
    unloaded = ins.unloaded if ins is not None else set()

    p3d = scan.processed_3d if "processed_3d" not in unloaded else None
    p2d = scan.processed_2d if "processed_2d" not in unloaded else None
    mods = scan.modifications if "modifications" not in unloaded else []
    imgs = scan.images if "images" not in unloaded else []

    res = ScanResponse(
        scan_id=scan.scan_id,
        method=scan.method,
        status=scan.status,
        created_at=scan.created_at,
        car_name=scan.car_name,
        description=scan.description,
        is_shared=scan.is_shared,
        mode=scan.mode,
        options_json=scan.options_json,
        modifications_json=scan.modifications_json,
        edit_task_id=scan.edit_task_id,
        model_task_id=scan.model_task_id,
        credits_estimated=scan.credits_estimated,
        credits_consumed=scan.credits_consumed,
        progress_percent=scan.progress_percent,
        progress_stage=scan.progress_stage,
        error_code=scan.error_code,
        error_hint=scan.error_hint,
        processed_3d=Processed3DInfo.model_validate(p3d, from_attributes=True) if p3d else None,
        processed_2d=Processed2DInfo.model_validate(p2d, from_attributes=True) if p2d else None,
        modifications=[ModificationBrief.model_validate(m, from_attributes=True) for m in mods] if mods else [],
        images=[ScanImageBrief.model_validate(i, from_attributes=True) for i in imgs] if imgs else []
    )
    if scan.progress_percent is not None and scan.progress_percent > 0:
        res.progress = scan.progress_percent
    elif scan.status in ("completed", "done"):
        res.progress = 100
    elif scan.status == "awaiting_confirmation":
        res.progress = 50
    elif scan.status == "generating_3d":
        res.progress = 75
    elif scan.status == "pending_edit":
        res.progress = 25
    return res


@router.delete("/{scan_id}")
async def delete_scan(
    scan_id: int,
    db: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user)
):
    result = await db.execute(select(Scans).where(Scans.scan_id == scan_id))
    scan = result.scalar_one_or_none()

    if not scan or scan.user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Silinecek kayıt bulunamadı veya yetkiniz yok.")

    await db.delete(scan)
    await db.commit()
    return {"message": f"{scan_id} numaralı tarama silindi."}


@router.post("/detect_car", status_code=status.HTTP_200_OK)
async def detect_car_endpoint(
    image: UploadFile = File(...),
    current_user=Depends(get_current_user)
):
    content_type = image.content_type or ""
    filename = image.filename or ""
    ext = filename.lower().split(".")[-1] if "." in filename else ""

    if not (content_type in ALLOWED_CONTENT_TYPES or ext in {"jpg", "jpeg", "png", "webp", "heic", "heif"}):
        raise HTTPException(status_code=400, detail=f"'{filename}' desteklenmiyor. JPEG, PNG, WEBP kabul edilir.")

    try:
        content = await image.read()
        return run_car_detection(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Araç tespiti hatası: {str(e)}")


# Eski worker uyumluluk rotaları (Dahili modifikasyon / modelleme)
@router.get("/pending_3d", response_model=List[ScanResponse])
async def get_pending_3d_scans(db: AsyncSession = Depends(get_session), _auth: str = Depends(get_worker_api_key)):
    query = select(Scans).where(Scans.status == "generating_3d")
    result = await db.execute(query)
    scans = result.scalars().all()
    return [await build_scan_response(s, db) for s in scans]


@router.post("/claim_3d/{scan_id}", response_model=ClaimResponse)
async def claim_3d_scan(scan_id: int, worker_id: str = "worker-default", db: AsyncSession = Depends(get_session), _auth: str = Depends(get_worker_api_key)):
    return ClaimResponse(status="claimed", scan_id=scan_id, claim_token=str(uuid.uuid4()), retry_count=1, max_attempts=MAX_JOB_ATTEMPTS)


@router.post("/progress/{scan_id}")
async def report_3d_progress(scan_id: int, body: ProgressRequest, db: AsyncSession = Depends(get_session), _auth: str = Depends(get_worker_api_key)):
    await db.execute(update(Scans).where(Scans.scan_id == scan_id).values(progress_percent=body.percent, progress_stage=body.stage))
    await db.commit()
    return {"status": "ok", "scan_id": scan_id}


@router.post("/fail/{scan_id}")
async def report_3d_failure(scan_id: int, body: FailRequest, db: AsyncSession = Depends(get_session), _auth: str = Depends(get_worker_api_key)):
    await db.execute(update(Scans).where(Scans.scan_id == scan_id).values(status="failed", error_code=body.error_code, error_hint=body.hint))
    await db.commit()
    return {"status": "ok", "scan_status": "failed"}


@router.put("/complete/3d/{scan_id}", tags=["Admin/Modeller"])
@router.post("/complete/3d/{scan_id}", tags=["Admin/Modeller"])
async def complete_3d_model(scan_id: int, request: Request, db: AsyncSession = Depends(get_session), _auth: str = Depends(get_worker_api_key)):
    contents = await request.body()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Dosya boş!")
    saved_path = LocalStorageService.save_bytes(contents, f"images_3d/scan_{scan_id}", f"model_{uuid.uuid4().hex[:8]}.glb")
    await db.execute(update(Processed3D).where(Processed3D.scan_id == scan_id).values(model_url=saved_path))
    await db.execute(update(Scans).where(Scans.scan_id == scan_id).values(status="completed", progress_percent=100))
    await db.commit()
    return {"status": "success", "message": "3D model yüklendi!", "model_url": saved_path}


@router.post("/complete/2d/{scan_id}", tags=["Admin/Modeller"])
async def complete_2d_model(scan_id: int, image_file: UploadFile = File(...), db: AsyncSession = Depends(get_session)):
    content = await image_file.read()
    saved_path = LocalStorageService.save_bytes(content, f"images_2d/scan_{scan_id}", f"result_{uuid.uuid4().hex[:8]}.png")
    thumb_path = LocalStorageService.create_thumbnail(saved_path, f"thumbnails/scan_{scan_id}", f"thumb_{scan_id}.jpg")
    await db.execute(update(Processed2D).where(Processed2D.scan_id == scan_id).values(image_url=saved_path, thumbnail_url=thumb_path))
    await db.execute(update(Scans).where(Scans.scan_id == scan_id).values(status="completed", progress_percent=100))
    await db.commit()
    return {"status": "success", "message": "2D görsel yüklendi!", "image_url": saved_path}
