# 3d modeli tutmak için oluşturulan tablo
from app.database.base import Base
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

class Processed3D(Base):
    __tablename__ = "processed_3d"

    processed3d_id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scans.scan_id"), index=True, unique=True)
    model_url = Column(String, index=True)
    thumbnail_url = Column(String, index=True)

    scan = relationship("Scans", back_populates="processed_3d")