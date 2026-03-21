"""
Shared FastAPI dependencies.

require_auth  — raises HTTP 401 if request has no valid access_token_cookie
optional_auth — returns user or None; never raises
"""
from typing import Optional

import jwt
from fastapi import Cookie, Depends
from sqlalchemy.orm import Session

from backend.config import JWT_SECRET_KEY as SECRET_KEY
from backend.core.security import get_current_user
from backend.database import get_db
from backend.models.user import User

# Reuses the existing robust implementation: reads access_token_cookie,
# decodes JWT, fetches user from DB, raises 401 on any failure.
require_auth = get_current_user


async def optional_auth(
    access_token_cookie: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Returns the authenticated user, or None if unauthenticated. Never raises."""
    if not access_token_cookie:
        return None
    try:
        payload = jwt.decode(access_token_cookie, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            return None
        return db.get(User, int(user_id))
    except Exception:
        return None
