import uuid
from sqlalchemy.orm import Session
from app.models.user import User

def get_user_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    """Fetch user by primary key ID."""
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_firebase_uid(db: Session, firebase_uid: str) -> User | None:
    """Fetch user by Firebase unique identifier."""
    return db.query(User).filter(User.firebase_uid == firebase_uid).first()

def create_user(db: Session, firebase_uid: str | None, email: str | None, display_name: str | None) -> User:
    """Create a new user record in database."""
    user = User(
        id=uuid.uuid4(),
        firebase_uid=firebase_uid,
        email=email,
        display_name=display_name
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
