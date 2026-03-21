from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash

from backend.core.limiter import limiter
from backend.core.security import create_access_token, get_current_user
from backend.database import get_db
from backend.models.user import VALID_ROLES, User

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Request / Response schemas ────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    role: str = "Engineer"


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str

    model_config = {"from_attributes": True}


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/hour")
def register(request: Request, body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email address already registered",
        )
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )
    if body.role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid role. Must be one of: {', '.join(sorted(VALID_ROLES))}",
        )
    new_user = User(
        username=body.username,
        email=body.email,
        password_hash=generate_password_hash(body.password, method="pbkdf2:sha256"),
        role=body.role,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post("/login", response_model=UserResponse)
@limiter.limit("20/hour")
def login(request: Request, body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not check_password_hash(user.password_hash, body.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token(user.id)
    response.set_cookie(
        key="access_token_cookie",
        value=token,
        httponly=True,
        max_age=43200,  # 12 hours in seconds
        samesite="lax",
    )
    return user


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token_cookie")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user
