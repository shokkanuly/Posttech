"""Password verification and revocable bearer sessions; roles always come from User."""

import hashlib
import secrets
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.enums import UserRole
from app.models.session import AuthSession
from app.models.user import User

security = HTTPBearer(auto_error=False)


def unauthenticated(message="Could not validate authentication credentials"):
    return HTTPException(401, message, headers={"WWW-Authenticate": "Bearer"})


class LoginLimiter:
    """Bounded single-process limiter. A shared gateway is needed for multiple workers."""

    def __init__(self):
        self.failures: dict[str, deque[float]] = {}
        self.inflight: dict[str, int] = {}
        self.lock = threading.Lock()

    def check(self, address: str):
        key = hashlib.sha256(address.encode()).hexdigest()
        now = time.monotonic()
        with self.lock:
            self.failures = {k: q for k, q in self.failures.items() if q and q[-1] > now - 60}
            queue = self.failures.get(key, deque())
            while queue and queue[0] <= now - 60:
                queue.popleft()
            tracked = self.failures.keys() | self.inflight.keys()
            if len(queue) + self.inflight.get(key, 0) >= 5 or (
                key not in tracked and len(tracked) >= 10000
            ):
                raise HTTPException(
                    429,
                    "Too many failed or concurrent login attempts; retry in one minute",
                    headers={"Retry-After": "60"},
                )
            self.inflight[key] = self.inflight.get(key, 0) + 1
        return key

    def finish(self, key: str, failed: bool):
        with self.lock:
            count = self.inflight.get(key, 0)
            if count <= 1:
                self.inflight.pop(key, None)
            else:
                self.inflight[key] = count - 1
            if failed:
                self.failures.setdefault(key, deque(maxlen=5)).append(time.monotonic())


login_limiter = LoginLimiter()


class AuthService:
    @staticmethod
    def hash_password(password: str) -> str:
        salt = secrets.token_hex(16)
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600000)
        return f"pbkdf2_sha256$600000${salt}${key.hex()}"

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        try:
            parts = hashed_password.split("$")
            if len(parts) == 2:  # Retain existing accounts; upgrade on a successful login.
                salt, key_hex = parts
                iterations = 100000
            else:
                algorithm, rounds, salt, key_hex = parts
                if algorithm != "pbkdf2_sha256":
                    return False
                iterations = int(rounds)
                if not 100000 <= iterations <= 1000000:
                    return False
            key = hashlib.pbkdf2_hmac("sha256", plain_password.encode(), salt.encode(), iterations)
            return secrets.compare_digest(key.hex(), key_hex)
        except (ValueError, TypeError):
            return False

    @staticmethod
    def create_access_token(
        user_id: int, db: Session, expires_delta: Optional[timedelta] = None
    ) -> str:
        now = datetime.now(timezone.utc)
        expires = now + (
            expires_delta
            if expires_delta is not None
            else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        jti = secrets.token_hex(32)
        db.add(AuthSession(id=jti, user_id=user_id, expires_at=expires))
        db.flush()
        return jwt.encode(
            {"sub": str(user_id), "jti": jti, "exp": expires, "iat": now},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )

    @staticmethod
    def decode_token(token: str) -> dict:
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
                options={"require": ["sub", "jti", "exp", "iat"]},
            )
            subject = payload["sub"]
            if (
                not isinstance(subject, str)
                or not subject.isdecimal()
                or len(subject) > 19
                or not 0 < int(subject) < 2**63
            ):
                raise unauthenticated("Invalid token subject")
            if not isinstance(payload["jti"], str) or len(payload["jti"]) != 64:
                raise unauthenticated("Invalid session identifier")
            return payload
        except jwt.PyJWTError:
            raise unauthenticated() from None


auth_service = AuthService()
DUMMY_PASSWORD_HASH = auth_service.hash_password(secrets.token_urlsafe(32))


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise unauthenticated("Authentication credentials were not provided")
    payload = auth_service.decode_token(credentials.credentials)
    active_session = (
        db.query(AuthSession)
        .filter(
            AuthSession.id == payload["jti"],
            AuthSession.user_id == int(payload["sub"]),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(timezone.utc),
        )
        .first()
    )
    if not active_session:
        raise unauthenticated("Session expired or revoked")
    user = (
        db.query(User).filter(User.id == active_session.user_id, User.is_active.is_(True)).first()
    )
    if not user:
        raise unauthenticated("User not found or account is deactivated")
    return user


def require_role(*allowed_roles: UserRole):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(403, "Access denied for this role")
        return current_user

    return role_checker
