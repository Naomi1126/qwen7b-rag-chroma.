# models.py
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Table
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

# Tabla intermedia para la relación muchos-a-muchos entre usuarios y áreas
user_area_table = Table(
    "user_areas",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("area_id", Integer, ForeignKey("areas.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)

    # Relación many-to-many con Area
    areas = relationship("Area", secondary=user_area_table, back_populates="users")


class Area(Base):
    __tablename__ = "areas"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, index=True)  # "logistica", "ventas"
    name = Column(String)  # "Logística", "Ventas"

    users = relationship("User", secondary=user_area_table, back_populates="areas")
