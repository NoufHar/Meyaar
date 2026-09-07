from getpass import getpass

from sqlalchemy import select

from src.auth.security import hash_password
from src.database.database import SessionLocal
from src.database.models import User


def main():
    name=input("Admin name: ").strip()
    email=input("Admin email: ").strip().lower()
    password=getpass("Admin password: ")

    if len(password)<8:
        print("Password must be at least 8 characters.")
        return

    db=SessionLocal()

    try:
        user=db.scalar(
            select(User).where(User.email==email)
        )

        if user:
            user.name=name or user.name
            user.password_hash=hash_password(password)
            user.role="admin"
            user.is_active=True
            print("Existing user updated to admin.")

        else:
            user=User(
                name=name,
                email=email,
                password_hash=hash_password(password),
                role="admin",
                is_active=True,
            )

            db.add(user)
            print("Admin created.")

        db.commit()

    finally:
        db.close()


if __name__=="__main__":
    main()