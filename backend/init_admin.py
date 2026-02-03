import os
from database import SessionLocal
from models import User, Area
from auth import get_password_hash

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip() or "admin@comarket.com"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "").strip() or "1234"
ADMIN_NAME = os.getenv("ADMIN_NAME", "").strip() or "Administrador"

db = SessionLocal()

admin = db.query(User).filter(User.email == ADMIN_EMAIL).first()
if not admin:
    admin = User(
        email=ADMIN_EMAIL,
        name=ADMIN_NAME,
        password_hash=get_password_hash(ADMIN_PASSWORD),
        is_admin=True,
    )
    db.add(admin)
    db.commit()

# asegurar todas las áreas
all_areas = db.query(Area).all()
admin.areas = all_areas
admin.is_admin = True
db.commit()

print("Admin asegurado con todas las áreas")
