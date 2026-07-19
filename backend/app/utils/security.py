from uuid import UUID
from typing import Optional
from app.core.exceptions import ForbiddenException

def check_resource_ownership(
    resource_user_id: Optional[UUID],
    resource_session_id: Optional[str],
    current_user_id: Optional[UUID],
    current_session_id: Optional[str]
) -> None:
    """
    Utility function to verify if the active request user or session is allowed
    to access a database resource (e.g. Document, Conversation).
    Raises ForbiddenException if access is not permitted.
    """
    # 1. If the resource is owned by a registered user
    if resource_user_id is not None:
        if current_user_id is None:
            raise ForbiddenException("Access denied. This resource requires authentication.")
        if resource_user_id != current_user_id:
            raise ForbiddenException("Access denied. You do not have permission to access this resource.")
        return

    # 2. If the resource belongs to an anonymous session
    if resource_session_id is not None:
        if current_session_id is None:
            raise ForbiddenException("Access denied. Session header (X-Session-Id) is missing.")
        if resource_session_id != current_session_id:
            raise ForbiddenException("Access denied. You do not own this session's resources.")
        return

    # 3. Fallback for orphaned resources
    raise ForbiddenException("Access denied. Resource does not have valid ownership attributes.")
