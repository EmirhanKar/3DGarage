# app/database/models/scans.py
# Tarama ve 3D/2D üretim süreci bilgilerini tutan ana tablo

from datetime import datetime, timezone
from typing import Optional
from app.database.base import Base
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Boolean, func
from sqlalchemy.orm import relationship

class Scans(Base):
    __tablename__ = 'scans'

    scan_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), index=True, nullable=False)
    method = Column(String, index=True, nullable=False)  # "2d", "3d", "3d_single"
    status = Column(String, index=True, default="pending")  # pending_edit, edit_ready, awaiting_confirmation, generating_3d, completed, failed
    car_name = Column(String, index=True) 
    description = Column(String, index=True, nullable=True)
    is_shared = Column(Boolean, default=False, nullable=False, server_default="0")  # Keşfette paylaşıldı mı?
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # ── Tripo v3 & Yeni Akış Alanları ──
    mode = Column(String(20), default="3d", nullable=True)  # "2d" veya "3d"
    options_json = Column(String(2000), nullable=True)  # Kalite seçenekleri (texture_quality, geometry_quality, pbr vb.)
    modifications_json = Column(String(2000), nullable=True)  # Seçilen modifikasyonlar (renk, jant, spoiler vb.)
    edit_task_id = Column(String(100), nullable=True, index=True)  # Tripo image-to-image görev kimliği
    model_task_id = Column(String(100), nullable=True, index=True)  # Tripo image-to-model / multiview görev kimliği
    credits_estimated = Column(Integer, default=0, server_default="0", nullable=False)  # Tahmini toplam kredi
    credits_consumed = Column(Integer, default=0, server_default="0", nullable=False)  # Fiilen harcanan kredi
    is_locked = Column(Boolean, default=False, server_default="0", nullable=False)  # Çift istek kilit bayrağı

    # 3D Kira (Lease), Sahiplik Çiti (Claim Token), İlerleme ve Hata Alanları
    status_updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=True
    )
    claimed_by = Column(String(100), nullable=True)
    claim_token = Column(String(36), nullable=True, index=True)
    retry_count = Column(Integer, default=0, server_default="0", nullable=False)
    failed_step = Column(String(100), nullable=True)
    error_code = Column(String(100), nullable=True)
    error_detail = Column(String(1000), nullable=True)
    error_hint = Column(String(500), nullable=True)
    progress_stage = Column(String(100), nullable=True)
    progress_percent = Column(Integer, default=0, server_default="0", nullable=True)
    next_attempt_at = Column(DateTime, nullable=True)

    images = relationship("ScanImage", back_populates="scan", cascade="all, delete-orphan")
    processed_3d = relationship("Processed3D", back_populates="scan", cascade="all, delete-orphan", uselist=False)
    processed_2d = relationship("Processed2D", back_populates="scan", cascade="all, delete-orphan", uselist=False)
    modifications = relationship("Modification", back_populates="scan", cascade="all, delete-orphan")
    likes = relationship("Like", back_populates="scan", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="scan", cascade="all, delete-orphan")
