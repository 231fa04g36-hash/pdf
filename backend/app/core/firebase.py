import os
import logging
import firebase_admin
from firebase_admin import credentials, auth
from app.core.config import settings

logger = logging.getLogger("app.firebase")

# Track if firebase runs in mock mode for local testing
_is_mock_firebase = False

def initialize_firebase() -> None:
    """
    Initializes the Firebase Admin SDK.
    Falls back to mock authentication if no project credentials or environment options exist.
    """
    global _is_mock_firebase
    
    # Enable mock mode if in development and configured as mock
    use_mock = (
        settings.ENVIRONMENT == "development" 
        and (
            not settings.FIREBASE_PROJECT_ID 
            or settings.FIREBASE_PROJECT_ID.startswith("mock-") 
            or os.getenv("USE_MOCK_AUTH") == "true"
        )
    )

    if use_mock:
        logger.warning("Firebase Admin is running in MOCK mode. Will accept mock-token formats for development.")
        _is_mock_firebase = True
        return

    try:
        if not firebase_admin._apps:
            cred_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
            if cred_path and os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                logger.info(f"Firebase Admin SDK initialized successfully via path: '{cred_path}'")
            else:
                # Initialize with ADC or default config options
                firebase_admin.initialize_app()
                logger.info("Firebase Admin SDK initialized via default application credentials.")
    except Exception as e:
        logger.warning(f"Failed to initialize real Firebase Admin SDK: {e}. Falling back to MOCK mode.")
        _is_mock_firebase = True

def verify_firebase_token(token: str) -> dict:
    """
    Verifies the Firebase ID token and returns decoded attributes.
    Never logs the raw token or details.
    """
    global _is_mock_firebase

    if not token:
        raise ValueError("Firebase token is empty")

    if _is_mock_firebase:
        # Support default developer mock token or custom parameter mappings for testing
        if token == "mock-token-for-dev":
            return {
                "uid": "firebase-test-user-123",
                "email": "developer@pdfchatbot.com",
                "name": "Dev User"
            }
        elif token.startswith("mock-token:"):
            parts = token.split(":")
            uid = parts[1] if len(parts) > 1 else "mock-uid"
            email = parts[2] if len(parts) > 2 else "mock@example.com"
            name = parts[3] if len(parts) > 3 else "Mock User"
            return {
                "uid": uid,
                "email": email,
                "name": name
            }
        else:
            raise ValueError("Invalid mock token format. Use 'mock-token-for-dev' or 'mock-token:uid:email:name'.")

    # Real verification using Admin SDK (never logs token value)
    return auth.verify_id_token(token)
