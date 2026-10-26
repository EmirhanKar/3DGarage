from pydantic import BaseModel

class UserStatsBase(BaseModel):
    user_credi: int = 0
    create_image: int = 0
    render_image: int = 0

class UserStatsCreate(UserStatsBase):
    user_id: int

class UserStatsUpdate(BaseModel):
    user_credi: int | None = None
    create_image: int | None = None
    render_image: int | None = None

class UserStatsResponse(UserStatsBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True 