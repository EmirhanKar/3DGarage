import os
import uuid
import httpx
from PIL import Image
from typing import Optional
from app.core.config import BACKEND_PUBLIC_URL

class LocalStorageService:
    """
    Yerel ve bulut (S3/R2) geçişine uyumlu merkezi dosya depolama servisi.
    Görselleri, 3D GLB modellerini ve küçük önizleme (thumbnail) dosyalarını yönetir.
    """

    @staticmethod
    def sanitize_path(path: str) -> str:
        return path.replace("\\", "/")

    @classmethod
    def save_bytes(cls, content: bytes, subfolder: str, filename: str) -> str:
        upload_dir = os.path.join("uploads", subfolder)
        os.makedirs(upload_dir, exist_ok=True)
        full_path = os.path.join(upload_dir, filename)
        with open(full_path, "wb") as f:
            f.write(content)
        return cls.sanitize_path(full_path)

    @classmethod
    async def download_and_save(cls, url: str, subfolder: str, filename: str) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return cls.save_bytes(resp.content, subfolder, filename)

    @classmethod
    def create_thumbnail(cls, source_path: str, thumb_subfolder: str, thumb_filename: str, size=(400, 400)) -> str:
        thumb_dir = os.path.join("uploads", thumb_subfolder)
        os.makedirs(thumb_dir, exist_ok=True)
        thumb_path = os.path.join(thumb_dir, thumb_filename)

        try:
            with Image.open(source_path) as img:
                img = img.convert("RGB")
                img.thumbnail(size)
                img.save(thumb_path, "JPEG", quality=85)
        except Exception:
            import shutil
            shutil.copy2(source_path, thumb_path)

        return cls.sanitize_path(thumb_path)

    @classmethod
    def build_public_url(cls, relative_path: Optional[str]) -> Optional[str]:
        if not relative_path:
            return None
        if relative_path.startswith("http://") or relative_path.startswith("https://"):
            return relative_path
        clean_path = relative_path.lstrip("/")
        base = (BACKEND_PUBLIC_URL or "http://localhost:8000").rstrip("/")
        return f"{base}/{clean_path}"
