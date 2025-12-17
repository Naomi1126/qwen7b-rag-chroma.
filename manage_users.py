"""
Uso:
  python manage_users.py list-users
  python manage_users.py list-areas
  python manage_users.py create-area --slug logistica --name "Logística"
  python manage_users.py assign-areas --email admin@comarket.com --areas general,sistemas,logistica
  python manage_users.py grant-all --email admin@comarket.com
"""

import argparse
from typing import List

from database import SessionLocal, init_db
from models import User, Area


def get_or_create_area(db, slug: str, name: str | None = None) -> Area:
    area = db.query(Area).filter(Area.slug == slug).first()
    if area:
        return area

    area = Area(
        slug=slug,
        name=name or slug.capitalize()
    )
    db.add(area)
    db.commit()
    db.refresh(area)
    print(f" Área creada: {slug}")
    return area


def list_users(db):
    users = db.query(User).all()
    if not users:
        print("No hay usuarios.")
        return

    for u in users:
        areas = [a.slug for a in u.areas]
        print(f"- {u.email} | admin={u.is_admin} | areas={areas}")


def list_areas(db):
    areas = db.query(Area).all()
    if not areas:
        print("No hay áreas.")
        return

    for a in areas:
        print(f"- {a.slug} ({a.name})")


def assign_areas(db, email: str, area_slugs: List[str]):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        print(f" Usuario no encontrado: {email}")
        return

    areas = []
    for slug in area_slugs:
        area = get_or_create_area(db, slug)
        areas.append(area)

    user.areas = areas
    db.commit()

    print(f" Áreas asignadas a {email}: {[a.slug for a in areas]}")


def grant_all_areas(db, email: str):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        print(f" Usuario no encontrado: {email}")
        return

    areas = db.query(Area).all()
    if not areas:
        print(" No hay áreas creadas aún.")
        return

    user.areas = areas
    user.is_admin = True
    db.commit()

    print(f"{email} ahora es admin y tiene acceso a TODAS las áreas.")


def main():
    init_db()

    parser = argparse.ArgumentParser(description="Administración de usuarios y áreas")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list-users")
    sub.add_parser("list-areas")

    p_create = sub.add_parser("create-area")
    p_create.add_argument("--slug", required=True)
    p_create.add_argument("--name")

    p_assign = sub.add_parser("assign-areas")
    p_assign.add_argument("--email", required=True)
    p_assign.add_argument("--areas", required=True, help="general,sistemas,logistica")

    p_admin = sub.add_parser("grant-all")
    p_admin.add_argument("--email", required=True)

    args = parser.parse_args()
    db = SessionLocal()

    try:
        if args.cmd == "list-users":
            list_users(db)

        elif args.cmd == "list-areas":
            list_areas(db)

        elif args.cmd == "create-area":
            get_or_create_area(db, args.slug, args.name)

        elif args.cmd == "assign-areas":
            slugs = [s.strip() for s in args.areas.split(",") if s.strip()]
            assign_areas(db, args.email, slugs)

        elif args.cmd == "grant-all":
            grant_all_areas(db, args.email)

    finally:
        db.close()


if __name__ == "__main__":
    main()
