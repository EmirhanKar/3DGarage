#kullanıcıların kredi ve işlem sayılarını tutmak için oluşturulan tablo

from sqlalchemy import Column, ForeignKey, Integer, String 
from app.database.base import Base
from sqlalchemy.orm import relationship

class UserStats(Base):
    __tablename__ = "user_stats"
    userstats_id = Column(Integer, primary_key=True)
    user_id = Column(Integer,ForeignKey("users.user_id"), unique=True)
    user_credi = Column(Integer, default=0)
    create_image = Column(Integer, default=0)
    render_image = Column(Integer, default=0)
    

    user = relationship("User", back_populates="userstats")     

