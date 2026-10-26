# app/core/security.py — token süresi 30 dakikadan 7 güne çıkarıldı

import bcrypt
import os
from datetime import datetime, timedelta, timezone
import jwt
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("MY_TOKEN")


def create_access_token(data: dict):
    to_encode = data.copy()
    # 7 gün — kullanıcı her açtığında login olmasın
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, TOKEN, algorithm="HS256")
    return encoded_jwt


def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(pwd_bytes, salt)
    return hashed_password.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_byte = plain_password.encode('utf-8')
    hashed_byte = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_byte, hashed_byte)