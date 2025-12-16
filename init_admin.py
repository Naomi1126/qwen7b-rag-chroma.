from database import SessionLocal, init_db
from models import User
from auth import get_password_hash

EMAIL = "admin@comarket.com"
PASSWORD = "1234"
NAME = "Administrador"

def main():
    init_db()
    db = SessionLocal()
    u = db.query(User).filter(User.email == EMAIL).first()

    if not u:
        u = User(email=EMAIL, name=NAME)
        db.add(u)

    # Siempre PBKDF2 
    u.password_hash = get_password_hash(PASSWORD)
    db.commit()
    print("OK admin listo:", EMAIL)

if __name__ == "__main__":
    main()
