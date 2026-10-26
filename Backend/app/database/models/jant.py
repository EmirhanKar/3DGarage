#jant tablosu, jant modellerini ve kategorilerini tutmak için oluşturuldu.
from app.database.base import Base
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship 


class Jant(Base):
    __tablename__ = 'jant'

    jant_id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String, index=True)
    category = Column(String, index=True)
    image_url = Column(String)
    
    modifications = relationship("Modification", back_populates="jant", cascade="all, delete-orphan")    
    
