from fastapi import Request, Depends, Header
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.exceptions import UnauthorizedException
from app.core.firebase import verify_firebase_token
from app.repositories import get_user_by_firebase_uid, create_user
from app.models import User

def get_token_from_header(request: Request) -> str | None:
    """
    Utility to parse Bearer token from request Authorization header safely.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None
    
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
        
    return parts[1]

def get_session_id(x_session_id: str | None = Header(None, alias="X-Session-Id")) -> str | None:
    """
    Dependency to fetch X-Session-Id from incoming request headers.
    """
    return x_session_id

def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> User | None:
    """
    Verifies Bearer token if present; returns None if absent or invalid.
    Allows anonymous flow to proceed.
    """
    token = get_token_from_header(request)
    if not token:
        return None
        
    try:
        decoded_token = verify_firebase_token(token)
        firebase_uid = decoded_token.get("uid")
        if not firebase_uid:
            return None
            
        user = get_user_by_firebase_uid(db, firebase_uid)
        if not user:
            email = decoded_token.get("email")
            name = decoded_token.get("name")
            user = create_user(db, firebase_uid=firebase_uid, email=email, display_name=name)
        return user
    except Exception:
        # Fallback to None if verification fails (never log token)
        return None

def get_current_user_required(request: Request, db: Session = Depends(get_db)) -> User:
    """
    Verifies Bearer token. Raises UnauthorizedException if missing or invalid.
    """
    token = get_token_from_header(request)
    if not token:
        raise UnauthorizedException("Authentication token is missing.")
        
    try:
        decoded_token = verify_firebase_token(token)
        firebase_uid = decoded_token.get("uid")
        if not firebase_uid:
            raise UnauthorizedException("Invalid authentication credentials.")
            
        user = get_user_by_firebase_uid(db, firebase_uid)
        if not user:
            email = decoded_token.get("email")
            name = decoded_token.get("name")
            user = create_user(db, firebase_uid=firebase_uid, email=email, display_name=name)
        return user
    except Exception as e:
        raise UnauthorizedException(f"Authentication failed: {str(e)}")
