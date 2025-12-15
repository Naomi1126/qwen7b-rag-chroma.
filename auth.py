# auth.py
import os
import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database import SessionLocal
from models import User

# ==========================
# JWT
# ==========================
SECRET_KEY = os.getenv("SECRET_KEY", "CAMBIA_ESTO_POR_UNA_LLAVE_LARGA_Y_SECRETA")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 8)))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

# ==========================
# Password hashing (PBKDF2)
# ==========================
# Formato guardado en DB:
#   pbkdf2_sha256$<iterations>$<salt_b64>$<dk_b64>
PBKDF2_ITERATIONS = int(os.getenv("PBKDF2_ITERATIONS", "210000"))  # valor típico/seguro


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64d(txt: str) -> bytes:
    pad = "=" * (-len(txt) % 4)
    return base64.urlsafe_b64decode((txt + pad).encode("utf-8"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_password_hash(password: str) -> str:
    if not isinstance(password, str) or not password:
        raise ValueError("password inválido")
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS, dklen=32)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${_b64e(salt)}${_b64e(dk)}"


def verify_password(plain_password: str, password_hash: str) -> bool:
    if not plain_password or not password_hash:
        return False

    # Aceptamos SOLO nuestro formato pbkdf2 para evitar estados raros
    # (si tienes hashes viejos con bcrypt, hay que migrarlos / resetear password)
    try:
        scheme, iters_s, salt_b64, dk_b64 = password_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iters = int(iters_s)
        salt = _b64d(salt_b64)
        dk_expected = _b64d(dk_b64)
        dk = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iters, dklen=len(dk_expected))
        return hmac.compare_digest(dk, dk_expected)
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar el token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: Optional[str] = payload.get("sub")
        if not email:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
    return user
