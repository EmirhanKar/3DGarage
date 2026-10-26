from pydantic import BaseModel
from typing import Optional

class ScanImageBase(BaseModel):
    image_url: str
    modification_id: Optional[int] = None
    
class ScanImageCreate(ScanImageBase):
    scan_id: int
    user_id: int
    
class ScanImageResponse(ScanImageBase):
    scanimage_id: int

    class Config:
        from_attributes = True
