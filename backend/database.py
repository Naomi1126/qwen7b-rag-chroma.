import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base

# Base de datos persistente en 
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:////data/comarket.db"  )


# Fallback para desarrollo local sin /data
if not os.path.exists("/data") and DATABASE_URL.startswith("sqlite:////data"):
    DATABASE_URL = "sqlite:///./app.db"
    print("[DB]   Directorio /data no existe. Usando SQLite local: ./app.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """
    Crea las tablas definidas en models.Base (User, Area, user_areas).
    Se llama automáticamente al arrancar la app.
    """
    Base.metadata.create_all(bind=engine)
    db_path = DATABASE_URL.replace("sqlite:///", "")
    print(f"[DB] Base de datos inicializada: {db_path}")