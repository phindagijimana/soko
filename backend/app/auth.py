"""Authentication helpers for OTP sign-in and token-based session access.

These helpers keep auth logic out of route handlers so the API layer stays
focused on request/response orchestration.
"""


import secrets
from datetime import datetime, timedelta
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from .models import OTPCode, User
from .settings import settings


DEV_OTP_CODE = '123456'


def normalize_phone(phone: str) -> str:
    """Normalize phone input into a compact storage-friendly string."""
    return phone.strip().replace(' ', '')


def generate_otp() -> str:
    """Generate an OTP, using a fixed local code only in debug-friendly environments."""
    if settings.environment != 'production' and settings.debug:
        return DEV_OTP_CODE
    digits = ''.join(secrets.choice('0123456789') for _ in range(settings.otp_length))
    return digits


def generate_token() -> str:
    """Generate a cryptographically random bearer token."""
    return secrets.token_urlsafe(32)


def build_token_expiry() -> datetime:
    """Compute the token expiry timestamp from configuration."""
    return datetime.utcnow() + timedelta(hours=settings.auth_token_hours)


def get_current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    """Resolve the signed-in user from the Authorization header."""
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail='Missing bearer token')
    token = authorization.replace('Bearer ', '', 1).strip()
    user = db.query(User).filter(User.auth_token == token).first()
    if not user or not user.token_expires_at or user.token_expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail='Invalid or expired token')
    return user


def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail='Admin access required')
    return current_user


def mark_failed_otp_attempt(otp: OTPCode, db: Session) -> None:
    """Increment failed attempts and apply a timed lockout when needed."""
    otp.attempts += 1
    if otp.attempts >= settings.otp_max_attempts:
        otp.locked_until = datetime.utcnow() + timedelta(minutes=settings.otp_lockout_minutes)
    db.commit()


def otp_is_locked(otp: OTPCode) -> bool:
    """Return True when the OTP is temporarily locked due to repeated failures."""
    return bool(otp.locked_until and otp.locked_until > datetime.utcnow())


def get_optional_current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User | None:
    """Resolve a signed-in user when a bearer token is present, otherwise return None."""
    if not authorization or not authorization.startswith('Bearer '):
        return None
    token = authorization.replace('Bearer ', '', 1).strip()
    user = db.query(User).filter(User.auth_token == token).first()
    if not user or not user.token_expires_at or user.token_expires_at < datetime.utcnow():
        return None
    return user
