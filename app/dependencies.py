from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from fastapi import Depends, Form, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User, UserRole


def _csrf_subject(request: Request) -> str:
    return str(request.session.get("user_id", "anonymous"))


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})

    user = db.get(User, user_id)
    if not user or not user.is_active:
        request.session.clear()
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def generate_csrf_token(request: Request) -> str:
    settings = get_settings()
    serializer = URLSafeTimedSerializer(settings.csrf_secret)
    return serializer.dumps(_csrf_subject(request))


def validate_csrf(request: Request, csrf_token: str = Form(...)) -> None:
    settings = get_settings()
    serializer = URLSafeTimedSerializer(settings.csrf_secret)
    try:
        subject = serializer.loads(csrf_token, max_age=3600)
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")
    if subject != _csrf_subject(request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")


def flash(request: Request, message: str, category: str = "success") -> None:
    messages = request.session.get("_flash", [])
    messages.append({"message": message, "category": category})
    request.session["_flash"] = messages


def get_flashed_messages(request: Request) -> list[dict]:
    return request.session.pop("_flash", [])


def tmpl_ctx(request: Request, current_user=None, **kwargs) -> dict:
    return {
        "request": request,
        "current_user": current_user,
        "flash_messages": get_flashed_messages(request),
        "csrf_token": generate_csrf_token(request),
        **kwargs,
    }
