import math

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import flash, get_current_user, require_admin, tmpl_ctx, validate_csrf
from app.models import User, UserRole
from app.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


@router.get("")
def list_users(
    request: Request,
    page: int = 1,
    q: str = "",
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    per_page = settings.page_size
    stmt = select(User)
    if q:
        stmt = stmt.where(User.username.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    total_pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, total_pages))
    users = db.scalars(stmt.order_by(User.username).offset((page - 1) * per_page).limit(per_page)).all()
    return templates.TemplateResponse(
        request,
        "users/list.html",
        tmpl_ctx(request, current_user, users=users, q=q, page=page, total_pages=total_pages, total=total),
    )


@router.get("/new")
def new_user_page(
    request: Request,
    current_user: User = Depends(require_admin),
):
    return templates.TemplateResponse(
        request,
        "users/form.html",
        tmpl_ctx(request, current_user, user_obj=None, error=None, roles=UserRole),
    )


@router.post("/new")
async def create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(UserRole.staff.value),
    is_active: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    clean_username = username.strip()
    user = User(
        username=clean_username,
        password_hash=hash_password(password),
        role=UserRole(role),
        is_active=bool(is_active),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "users/form.html",
            tmpl_ctx(request, current_user, user_obj=None, error="Username already exists.", roles=UserRole),
            status_code=400,
        )
    flash(request, f"User '{clean_username}' created.", "success")
    return RedirectResponse(url="/users", status_code=303)


@router.get("/{user_id}/edit")
def edit_user_page(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user_obj = db.get(User, user_id)
    if not user_obj:
        return RedirectResponse(url="/users", status_code=303)
    return templates.TemplateResponse(
        request,
        "users/form.html",
        tmpl_ctx(request, current_user, user_obj=user_obj, error=None, roles=UserRole),
    )


@router.post("/{user_id}/edit")
async def edit_user(
    user_id: int,
    request: Request,
    username: str = Form(...),
    password: str = Form(""),
    role: str = Form(UserRole.staff.value),
    is_active: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    user_obj = db.get(User, user_id)
    if not user_obj:
        return RedirectResponse(url="/users", status_code=303)

    user_obj.username = username.strip()
    user_obj.role = UserRole(role)
    user_obj.is_active = bool(is_active)
    if password.strip():
        user_obj.password_hash = hash_password(password)
    db.commit()
    flash(request, f"User '{user_obj.username}' updated.", "success")
    return RedirectResponse(url="/users", status_code=303)
