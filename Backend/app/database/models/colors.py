from app.database.base import Base
from sqlalchemy import Column, Integer, String , ForeignKey
from sqlalchemy.orm import relationship

class Colors(Base):
    __tablename__ = "colors"

    color_id = Column(Integer, primary_key=True, index=True)
    color_code = Column(String, index=True)
    

    modifications = relationship("Modification", back_populates="colors")