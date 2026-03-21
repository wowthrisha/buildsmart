from datetime import datetime, timedelta
from typing import Optional

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.config import JWT_SECRET_KEY as SECRET_KEY
from backend.database import get_db
from backend.models.user import User
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 12


def create_access_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    access_token_cookie: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not access_token_cookie:
        raise credentials_exception
    try:
        payload = jwt.decode(access_token_cookie, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )
    except jwt.InvalidTokenError:
        raise credentials_exception

    user = db.get(User, int(user_id))
    if user is None:
        raise credentials_exception
    return user
