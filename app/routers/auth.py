from fastapi import APIRouter, Depends, HTTPException, status, Request as FastAPIRequest
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.profile import EmployeeProfile
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse, MeResponse, ProfileBrief
from app.services.auth_service import auth_service, get_current_user
from app.services.audit_service import audit_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: FastAPIRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower(), User.is_active == True).first()
    if not user or not auth_service.verify_password(payload.password, user.password_hash):
        audit_service.log_event(
            db=db,
            action="LOGIN_FAILED",
            details={"email": payload.email},
            ip_address=request.client.host if request.client else None,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_service.create_access_token(user_id=user.id, role=user.role.value)

    audit_service.log_event(
        db=db,
        action="LOGIN_SUCCESS",
        actor_id=user.id,
        target_type="user",
        target_id=str(user.id),
        details={"email": user.email, "role": user.role.value},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post("/logout")
def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    audit_service.log_event(
        db=db,
        action="LOGOUT",
        actor_id=current_user.id,
        target_type="user",
        target_id=str(current_user.id),
    )
    db.commit()
    return {"message": "Successfully logged out"}
