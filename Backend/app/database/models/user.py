#kullanıcı bilgilerini tutmak için oluşturulan tablo

from sqlalchemy import Boolean, Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
import datetime

from app.database.base import Base

class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True)
    name = Column(String)
    surname = Column(String)
    profil_image_url = Column(String, default="")
    email = Column(String, unique=True)
    password = Column(String)
    phone_number = Column(String, default="")
    is_admin = Column(Boolean,default=False)
    referral_used = Column(Boolean, default=False)
    game_score = Column(Integer, default=0)
    game_score_updated_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    game_score_car_racing = Column(Integer, default=0)
    game_score_car_racing_updated_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    game_score_fly_bird = Column(Integer, default=0)
    game_score_fly_bird_updated_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    
    likes = relationship("Like", back_populates="user")
    comments = relationship("Comment", back_populates="user")
    userstats = relationship("UserStats", back_populates="user", uselist=False) 
    subscriptions = relationship("Subscription", back_populates="user")
    modifications = relationship("Modification", back_populates="user")