from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.localization import LocalizedRoute
from app.models.session import AuthSession
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.schemas.common import MessageResponse
from app.services.audit_service import audit_service
from app.services.auth_service import (
    DUMMY_PASSWORD_HASH,
    auth_service,
    get_current_user,
    login_limiter,
    security,
)

router = APIRouter(route_class=LocalizedRoute, prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    key = login_limiter.check(request.client.host if request.client else "unknown")
    failed = False
    try:
        return authenticate_login(payload, db)
    except HTTPException as exc:
        failed = exc.status_code == 401
        raise
    finally:
        login_limiter.finish(key, failed=failed)


def authenticate_login(payload: LoginRequest, db: Session) -> TokenResponse:
    user = (
        db.query(User).filter(User.email == payload.email.lower(), User.is_active.is_(True)).first()
    )
    valid = auth_service.verify_password(
        payload.password, user.password_hash if user else DUMMY_PASSWORD_HASH
    )
    if settings.ENVIRONMENT == "production" and payload.password == "Password123!":
        valid = False
    if not user or not valid:
        audit_service.log_event(
            db, action="LOGIN_FAILED", details={"reason": "invalid_credentials"}
        )
        db.commit()
        raise HTTPException(
            401, "Incorrect email or password", headers={"WWW-Authenticate": "Bearer"}
        )
    if not user.password_hash.startswith("pbkdf2_sha256$"):
        user.password_hash = auth_service.hash_password(payload.password)
    token = auth_service.create_access_token(user.id, db)
    audit_service.log_event(
        db, action="LOGIN_SUCCESS", actor_id=user.id, target_type="user", target_id=str(user.id)
    )
    db.commit()
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", response_model=MessageResponse)
def logout(
    current_user: User = Depends(get_current_user),
    credentials=Depends(security),
    db: Session = Depends(get_db),
):
    payload = auth_service.decode_token(credentials.credentials)
    db.query(AuthSession).filter(
        AuthSession.id == payload["jti"], AuthSession.user_id == current_user.id
    ).update({"revoked_at": datetime.now(timezone.utc)}, synchronize_session=False)
    audit_service.log_event(
        db,
        action="LOGOUT",
        actor_id=current_user.id,
        target_type="user",
        target_id=str(current_user.id),
    )
    db.commit()
    return {"message": "Successfully logged out"}
