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
from app.models import Category, User
from app.services import ensure_unique_slug

router = APIRouter(prefix="/categories", tags=["categories"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


@router.get("")
def list_categories(
    request: Request,
    page: int = 1,
    q: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    per_page = settings.page_size
    stmt = select(Category)
    if q:
        stmt = stmt.where(Category.name.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    total_pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, total_pages))
    categories = db.scalars(
        stmt.order_by(Category.sort_order, Category.name).offset((page - 1) * per_page).limit(per_page)
    ).all()
    parents = db.scalars(select(Category).order_by(Category.name)).all()
    return templates.TemplateResponse(
        request,
        "categories/list.html",
        tmpl_ctx(
            request,
            current_user,
            categories=categories,
            parents=parents,
            q=q,
            page=page,
            total_pages=total_pages,
            total=total,
        ),
    )


@router.get("/new")
def new_category_page(
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    parents = db.scalars(select(Category).order_by(Category.name)).all()
    return templates.TemplateResponse(
        request,
        "categories/form.html",
        tmpl_ctx(request, current_user, category=None, parents=parents, error=None),
    )


@router.post("/new")
async def create_category(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    parent_id: str = Form(""),
    sort_order: int = Form(0),
    is_active: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    parents = db.scalars(select(Category).order_by(Category.name)).all()
    clean_name = name.strip()
    category = Category(
        name=clean_name,
        description=description.strip() or None,
        parent_id=int(parent_id) if parent_id else None,
        slug=ensure_unique_slug(db, Category, clean_name),
        sort_order=sort_order,
        is_active=bool(is_active),
    )
    db.add(category)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "categories/form.html",
            tmpl_ctx(request, current_user, category=None, parents=parents, error="Category already exists."),
            status_code=400,
        )
    flash(request, f"Category '{clean_name}' created.", "success")
    return RedirectResponse(url="/categories", status_code=303)


@router.get("/{category_id}/edit")
def edit_category_page(
    category_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    category = db.get(Category, category_id)
    if not category:
        return RedirectResponse(url="/categories", status_code=303)
    parents = db.scalars(select(Category).where(Category.id != category_id).order_by(Category.name)).all()
    return templates.TemplateResponse(
        request,
        "categories/form.html",
        tmpl_ctx(request, current_user, category=category, parents=parents, error=None),
    )


@router.post("/{category_id}/edit")
async def edit_category(
    category_id: int,
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    parent_id: str = Form(""),
    sort_order: int = Form(0),
    is_active: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    category = db.get(Category, category_id)
    if not category:
        return RedirectResponse(url="/categories", status_code=303)

    category.name = name.strip()
    category.description = description.strip() or None
    category.parent_id = int(parent_id) if parent_id else None
    category.slug = ensure_unique_slug(db, Category, category.name, current_id=category.id)
    category.sort_order = sort_order
    category.is_active = bool(is_active)
    db.commit()
    flash(request, f"Category '{category.name}' updated.", "success")
    return RedirectResponse(url="/categories", status_code=303)
