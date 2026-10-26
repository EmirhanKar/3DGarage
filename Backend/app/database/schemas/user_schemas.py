from pydantic import BaseModel , EmailStr , Field
from typing import Optional

class UserBase(BaseModel):
    name: str
    surname : str
    email: EmailStr
    
class UserCreate(UserBase):
    password : str = Field(min_length=8)
    phone_number: str = ""
    
class UserLogin(BaseModel):
    email: EmailStr
    password: str
    
class UserToken(BaseModel):
    access_token: str
    token_type: str

    class Config:
        from_attributes = True
    
class UserResponse(UserBase):
    user_id: int
    profil_image_url: Optional[str] = None
    phone_number: Optional[str] = ""
    user_credi: int = 0
    create_image: int = 0
    render_image: int = 0
    game_score_car_racing: int = 0
    game_score_fly_bird: int = 0

    class Config:
        from_attributes = True
        
class UserUpdate(BaseModel):
    name :str = None
    surname: str = None
    email: EmailStr = None
    phone_number: str = None
    password: str = Field(default=None, min_length=8)