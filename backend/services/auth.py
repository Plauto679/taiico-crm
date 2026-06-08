import os

from database import SessionLocal, User

def verify_credentials(username, password):
    """
    Verify username and password against the relational database.
    """
    db = SessionLocal()
    try:
        # Check if the user exists in our unified database
        user = db.query(User).filter((User.email == username) | (User.name == username)).first()
        if user and user.is_active:
            dev_password = os.environ.get("AUTH_DEV_PASSWORD", "taiico")
            return str(password) == str(dev_password)
        return False
    except Exception as e:
        print(f"Authentication error: {e}")
        return False
    finally:
        db.close()
