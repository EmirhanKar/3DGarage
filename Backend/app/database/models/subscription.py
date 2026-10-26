#abonelik bilgilerini tutmak için oluşturulan tablo

from datetime import datetime,timezone

from app.database.base import Base
from sqlalchemy import Date, DateTime ,ForeignKey ,Column, Integer, String
from sqlalchemy.orm import relationship

class Subscription(Base):
    __tablename__ = 'subscriptions'

    subscription_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), index=True)  
    tier = Column(String, index=True , default= "free")
    start_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    end_date = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="subscriptions")