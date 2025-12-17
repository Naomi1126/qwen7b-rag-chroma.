from database import SessionLocal
from models import User, Area
from auth import get_password_hash

ADMIN_EMAIL = "admin@comarket.com"
ADMIN_PASSWORD = "1234"

db = SessionLocal()

admin = db.query(User).filter(User.email == ADMIN_EMAIL).first()
if not admin:
    admin = User(
        email=ADMIN_EMAIL,
        name="Administrador",
        password_hash=get_password_hash(ADMIN_PASSWORD),
        is_admin=True,
    )
    db.add(admin)
    db.commit()

all_areas = db.query(Area).all()
admin.areas = all_areas
admin.is_admin = True
db.commit()

print(" Admin asegurado con todas las áreas")

