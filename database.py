from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base  # <- sin punto

SQLALCHEMY_DATABASE_URL = "sqlite:///./app.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},  # necesario para SQLite + FastAPI
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """
    Crea las tablas definidas en models.Base (User, Area, user_areas).
    Debes llamar a init_db() al arrancar la app (por ejemplo en app.py).
    """
    Base.metadata.create_all(bind=engine)
