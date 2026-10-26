import os
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

# ── 3D Worker & Kira Yapılandırması ──
PROCESSING_LEASE_SECONDS: int = int(os.getenv("PROCESSING_LEASE_SECONDS", "600"))  # 10 dakika
MAX_JOB_ATTEMPTS: int = int(os.getenv("MAX_JOB_ATTEMPTS", "3"))
RETRY_COOLDOWN_SECONDS: int = int(os.getenv("RETRY_COOLDOWN_SECONDS", "30"))
DEAD_LEASE_CHECK_INTERVAL_SECONDS: int = int(os.getenv("DEAD_LEASE_CHECK_INTERVAL_SECONDS", "60"))

# ── Tripo 3D API v3 Yapılandırması ──
TRIPO_API_KEY: str = os.getenv("TRIPO_API_KEY", "")
TRIPO_BASE_URL: str = os.getenv("TRIPO_BASE_URL", "https://openapi.tripo3d.com/v3").rstrip("/")
TRIPO_WEBHOOK_SECRET: str = os.getenv("TRIPO_WEBHOOK_SECRET", "")

# ── Sunucu & Depolama ──
BACKEND_PUBLIC_URL: str = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000").rstrip("/")
ENABLE_CAR_PRECHECK: bool = os.getenv("ENABLE_CAR_PRECHECK", "false").lower() in ("true", "1", "yes")

# ── Kredi Maliyet Matrisi ──
CREDIT_COST_2D_EDIT: int = 15
CREDIT_COST_3D_SINGLE_BASE: int = 30
CREDIT_COST_3D_MULTIVIEW_BASE: int = 60

CREDIT_SURCHARGE_TEXTURE_DETAILED: int = 15
CREDIT_SURCHARGE_TEXTURE_EXTREME: int = 25
CREDIT_SURCHARGE_GEOMETRY_DETAILED: int = 15
CREDIT_SURCHARGE_PBR: int = 10


def calculate_scan_credits(
    mode: str,
    method: str,
    options: Dict[str, Any],
    has_modifications: bool = True
) -> int:
    """
    Kullanıcının seçtiği mod, yöntem ve 3D kalite seçeneklerine göre
    harcanacak toplam tahmini kredi miktarını hesaplar.
    """
    if mode == "2d":
        return CREDIT_COST_2D_EDIT

    # 3D Modu
    total = CREDIT_COST_3D_SINGLE_BASE if method in ("single", "3d_single") else CREDIT_COST_3D_MULTIVIEW_BASE

    # Modifikasyon varsa (renk, jant, spoiler vb.) 2D image-to-image düzenleme maliyeti de eklenir
    if has_modifications:
        total += CREDIT_COST_2D_EDIT

    # Kalite eklentileri
    texture_q = options.get("texture_quality", "standard")
    if texture_q == "detailed":
        total += CREDIT_SURCHARGE_TEXTURE_DETAILED
    elif texture_q == "extreme":
        total += CREDIT_SURCHARGE_TEXTURE_EXTREME

    geometry_q = options.get("geometry_quality", "standard")
    if geometry_q == "detailed":
        total += CREDIT_SURCHARGE_GEOMETRY_DETAILED

    if options.get("pbr") is True:
        total += CREDIT_SURCHARGE_PBR

    return total
