from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.exceptions import UnauthorizedException
from app.dependencies.auth import get_token_from_header
from app.utils.rate_limiter import rate_limit_auth_link
from app.schemas.auth import LinkSessionRequest
from app.schemas.envelope import ResponseEnvelope
from app.schemas.user import UserResponse
from app.services.auth_service import auth_service

router = APIRouter(tags=["Authentication"])

@router.post(
    "/auth/link-session",
    response_model=ResponseEnvelope[UserResponse],
    dependencies=[Depends(rate_limit_auth_link)]
)
def link_session(
    request: Request,
    body: LinkSessionRequest,
    db: Session = Depends(get_db)
) -> ResponseEnvelope[UserResponse]:
    """
    Link all anonymous documents and conversations created under an anonymous session 
    to the authenticated user account verified by the Firebase ID token.
    """
    token = get_token_from_header(request)
    if not token:
        raise UnauthorizedException("Authentication token is missing from the request header.")
        
    user = auth_service.link_anonymous_session(
        db=db,
        id_token=token,
        session_id=body.session_id
    )
    
    return ResponseEnvelope(
        success=True,
        message="Anonymous session successfully linked to authenticated user account.",
        data=UserResponse.model_validate(user)
    )
