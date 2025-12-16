import os
import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple

from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database import SessionLocal
from models import User

# JWT
SECRET_KEY = os.getenv("SECRET_KEY", "CAMBIA_ESTO_POR_UNA_LLAVE_LARGA_Y_SECRETA")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 8)))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

# Password hashing (PBKDF2)

PBKDF2_ITERATIONS = int(os.getenv("PBKDF2_ITERATIONS", "210000"))

PBKDF2_PREFIX = "pbkdf2_sha256$"

# Legacy bcrypt support
try:
    from passlib.context import CryptContext
    _bcrypt_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
except Exception:
    _bcrypt_ctx = None


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
    """
    Hash principal: PBKDF2-SHA256 (formato propio)
    """
    if not isinstance(password, str) or not password:
        raise ValueError("password inválido")
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS, dklen=32
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${_b64e(salt)}${_b64e(dk)}"


def _verify_pbkdf2(plain_password: str, password_hash: str) -> bool:
    try:
        scheme, iters_s, salt_b64, dk_b64 = password_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iters = int(iters_s)
        salt = _b64d(salt_b64)
        dk_expected = _b64d(dk_b64)
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt,
            iters,
            dklen=len(dk_expected),
        )
        return hmac.compare_digest(dk, dk_expected)
    except Exception:
        return False


def _looks_like_bcrypt(password_hash: str) -> bool:
    
    return isinstance(password_hash, str) and password_hash.startswith("$2")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """
    Verifica PBKDF2 (nuevo) o bcrypt (legacy).
    """
    if not plain_password or not password_hash:
        return False

    if password_hash.startswith(PBKDF2_PREFIX):
        return _verify_pbkdf2(plain_password, password_hash)

    if _looks_like_bcrypt(password_hash) and _bcrypt_ctx is not None:
        try:
            return _bcrypt_ctx.verify(plain_password, password_hash)
        except Exception:
            return False

    return False


def verify_and_migrate_password(db: Session, user: User, plain_password: str) -> bool:
    """
    - Verifica la password
    - Si el hash era bcrypt y fue correcto, lo migra a PBKDF2.
    """
    if not user or not user.password_hash:
        return False

    ph = user.password_hash

    # 1) PBKDF2
    if ph.startswith(PBKDF2_PREFIX):
        return _verify_pbkdf2(plain_password, ph)

    # 2) bcrypt legacy 
    if _looks_like_bcrypt(ph) and _bcrypt_ctx is not None:
        try:
            ok = _bcrypt_ctx.verify(plain_password, ph)
        except Exception:
            ok = False

        if ok:
            user.password_hash = get_password_hash(plain_password)
            db.commit()
        return ok

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
