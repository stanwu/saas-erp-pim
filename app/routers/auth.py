from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import flash, tmpl_ctx, validate_csrf
from app.models import User
from app.security import verify_password

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


@router.get("/login")
def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request, "auth/login.html", tmpl_ctx(request, None, error=None))


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    user = db.scalar(select(User).where(User.username == username.strip()))
    if not user or not verify_password(password, user.password_hash) or not user.is_active:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            tmpl_ctx(request, None, error="Invalid username or password."),
            status_code=400,
        )
    request.session["user_id"] = user.id
    flash(request, f"Welcome back, {user.username}!", "success")
    return RedirectResponse(url="/", status_code=303)


@router.post("/logout")
async def logout(
    request: Request,
    _: None = Depends(validate_csrf),
):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
