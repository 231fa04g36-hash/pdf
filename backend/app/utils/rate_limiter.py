import time
from collections import defaultdict
from fastapi import Request
from app.core.exceptions import RateLimitException

class InMemoryRateLimiter:
    """
    Thread-safe-adjacent in-memory rate limiter using sliding window.
    """
    def __init__(self, requests_limit: int = 5, window_seconds: int = 60):
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self.request_history = defaultdict(list)

    def check_rate_limit(self, ip: str) -> None:
        now = time.time()
        # Keep only timestamps within current window
        self.request_history[ip] = [t for t in self.request_history[ip] if now - t < self.window_seconds]
        
        if len(self.request_history[ip]) >= self.requests_limit:
            raise RateLimitException("Too many requests on this endpoint. Please try again later.")
            
        self.request_history[ip].append(now)

# Instantiate a rate limiter specifically for the auth linking endpoint
auth_link_limiter = InMemoryRateLimiter(requests_limit=5, window_seconds=60)

def rate_limit_auth_link(request: Request) -> None:
    """
    Dependency function to check rate limits for a incoming request by IP address.
    """
    client_ip = "unknown"
    if request.client:
        client_ip = request.client.host
    auth_link_limiter.check_rate_limit(client_ip)

# Instantiate a rate limiter specifically for the chat endpoint (e.g. 20 requests per minute)
chat_limiter = InMemoryRateLimiter(requests_limit=20, window_seconds=60)

def rate_limit_chat(
    request: Request
) -> None:
    """
    Checks rate limits for chat request by user ID or session ID.
    """
    from fastapi import Depends
    from app.dependencies.auth import get_current_user_optional, get_session_id
    from app.core.database import SessionLocal

    # Resolve dependencies manually to keep router imports simple and fast
    db = SessionLocal()
    try:
        # Get X-Session-Id header
        session_id = request.headers.get("x-session-id")
        
        # Get auth token and verify if present
        auth_header = request.headers.get("authorization")
        user_id = None
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            from app.core.firebase import verify_firebase_token
            from app.repositories import get_user_by_firebase_uid
            try:
                decoded_token = verify_firebase_token(token)
                firebase_uid = decoded_token.get("uid")
                user = get_user_by_firebase_uid(db, firebase_uid)
                if user:
                    user_id = user.id
            except Exception:
                pass

        identifier = "anonymous"
        if user_id:
            identifier = f"user_{user_id}"
        elif session_id:
            identifier = f"session_{session_id}"
        elif request.client:
            identifier = f"ip_{request.client.host}"

        chat_limiter.check_rate_limit(identifier)
    finally:
        db.close()

# Instantiate a rate limiter specifically for document upload (e.g. 5 uploads per minute)
upload_limiter = InMemoryRateLimiter(requests_limit=5, window_seconds=60)

def rate_limit_upload(request: Request) -> None:
    """
    Checks rate limits for file upload by user ID, session ID, or IP.
    """
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        session_id = request.headers.get("x-session-id")
        auth_header = request.headers.get("authorization")
        user_id = None
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            from app.core.firebase import verify_firebase_token
            from app.repositories import get_user_by_firebase_uid
            try:
                decoded_token = verify_firebase_token(token)
                firebase_uid = decoded_token.get("uid")
                user = get_user_by_firebase_uid(db, firebase_uid)
                if user:
                    user_id = user.id
            except Exception:
                pass

        identifier = "anonymous"
        if user_id:
            identifier = f"user_{user_id}"
        elif session_id:
            identifier = f"session_{session_id}"
        elif request.client:
            identifier = f"ip_{request.client.host}"

        upload_limiter.check_rate_limit(identifier)
    finally:
        db.close()


