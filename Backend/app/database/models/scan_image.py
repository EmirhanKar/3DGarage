#scan image tablosu, taranan nesnenin farklı açılardan çekilen fotoğraflarını tutmak için oluşturuldu.

from app .database.base import Base
from sqlalchemy import Column, Integer, String, ForeignKey 
from sqlalchemy.orm import relationship

class ScanImage(Base):
    __tablename__ = 'scan_images'
    
    scanimage_id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scans.scan_id"))
    modification_id = Column(Integer, ForeignKey("modifications.modification_id"), nullable=True)
    image_url = Column(String , nullable=False)
    
    scan = relationship("Scans", back_populates="images")   
    modifications = relationship("Modification", back_populates="scan_images")
    