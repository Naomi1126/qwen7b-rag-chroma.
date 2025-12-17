from database import SessionLocal
from models import Area

BASE_AREAS = [
    ("general", "General"),
    ("logistica", "Logística"),
    ("sistemas", "Sistemas"),
    ("ventas", "Ventas"),
    ("finanzas", "Finanzas"),
]

db = SessionLocal()

for slug, name in BASE_AREAS:
    exists = db.query(Area).filter(Area.slug == slug).first()
    if not exists:
        db.add(Area(slug=slug, name=name))

db.commit()
print(" Áreas inicializadas")
