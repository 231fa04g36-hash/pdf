import logging
from sqlalchemy.orm import Session
from app.repositories import get_user_by_firebase_uid, create_user
from app.core.firebase import verify_firebase_token
from app.core.exceptions import UnauthorizedException
from app.models import Document, Conversation, User

logger = logging.getLogger("app.services.auth")

class AuthService:
    """
    Handles user session linking and auth management.
    """
    def link_anonymous_session(self, db: Session, id_token: str, session_id: str) -> User:
        """
        Verify Firebase ID Token, fetch/create user, and link all anonymous resources 
        from the specified session_id to the user ID.
        """
        try:
            # Token verification (never logs token data)
            decoded_token = verify_firebase_token(id_token)
            firebase_uid = decoded_token.get("uid")
            if not firebase_uid:
                raise UnauthorizedException("Invalid credentials token. ID identifier missing.")
        except Exception as e:
            raise UnauthorizedException(f"Token verification failed: {str(e)}")

        # Fetch or create the User row
        user = get_user_by_firebase_uid(db, firebase_uid)
        if not user:
            email = decoded_token.get("email")
            name = decoded_token.get("name")
            user = create_user(db, firebase_uid=firebase_uid, email=email, display_name=name)
            logger.info("Created new user entry on session link operation.")
        else:
            logger.info("Found existing user profile for linking.")

        # Re-assign any unassigned Document/Conversation rows matching that session_id to this user_id
        # We keep session_id for audit trail as requested (don't null it out)
        documents_updated = db.query(Document).filter(
            Document.session_id == session_id,
            Document.user_id == None
        ).update({Document.user_id: user.id}, synchronize_session=False)

        conversations_updated = db.query(Conversation).filter(
            Conversation.session_id == session_id,
            Conversation.user_id == None
        ).update({Conversation.user_id: user.id}, synchronize_session=False)

        if documents_updated > 0 or conversations_updated > 0:
            db.commit()
            logger.info(
                f"Linked session '{session_id}' to user ID '{user.id}' "
                f"({documents_updated} documents, {conversations_updated} conversations)"
            )

        return user

# Instantiate singleton service instance
auth_service = AuthService()
