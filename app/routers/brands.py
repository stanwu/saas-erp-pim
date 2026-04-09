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
from app.models import Brand, User
from app.services import ensure_unique_slug

router = APIRouter(prefix="/brands", tags=["brands"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


@router.get("")
def list_brands(
    request: Request,
    page: int = 1,
    q: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    per_page = settings.page_size
    stmt = select(Brand)
    if q:
        stmt = stmt.where(Brand.name.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    total_pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, total_pages))
    brands = db.scalars(
        stmt.order_by(Brand.name).offset((page - 1) * per_page).limit(per_page)
    ).all()
    return templates.TemplateResponse(
        request,
        "brands/list.html",
        tmpl_ctx(request, current_user, brands=brands, q=q, page=page, total_pages=total_pages, total=total),
    )


@router.get("/new")
def new_brand_page(
    request: Request,
    current_user: User = Depends(require_admin),
):
    return templates.TemplateResponse(
        request,
        "brands/form.html",
        tmpl_ctx(request, current_user, brand=None, error=None),
    )


@router.post("/new")
async def create_brand(
    request: Request,
    name: str = Form(...),
    website: str = Form(""),
    description: str = Form(""),
    is_active: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    clean_name = name.strip()
    brand = Brand(
        name=clean_name,
        slug=ensure_unique_slug(db, Brand, clean_name),
        website=website.strip() or None,
        description=description.strip() or None,
        is_active=bool(is_active),
    )
    db.add(brand)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "brands/form.html",
            tmpl_ctx(request, current_user, brand=None, error="Brand already exists."),
            status_code=400,
        )
    flash(request, f"Brand '{clean_name}' created.", "success")
    return RedirectResponse(url="/brands", status_code=303)


@router.get("/{brand_id}/edit")
def edit_brand_page(
    brand_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    brand = db.get(Brand, brand_id)
    if not brand:
        return RedirectResponse(url="/brands", status_code=303)
    return templates.TemplateResponse(
        request,
        "brands/form.html",
        tmpl_ctx(request, current_user, brand=brand, error=None),
    )


@router.post("/{brand_id}/edit")
async def edit_brand(
    brand_id: int,
    request: Request,
    name: str = Form(...),
    website: str = Form(""),
    description: str = Form(""),
    is_active: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    brand = db.get(Brand, brand_id)
    if not brand:
        return RedirectResponse(url="/brands", status_code=303)

    brand.name = name.strip()
    brand.slug = ensure_unique_slug(db, Brand, brand.name, current_id=brand.id)
    brand.website = website.strip() or None
    brand.description = description.strip() or None
    brand.is_active = bool(is_active)
    db.commit()
    flash(request, f"Brand '{brand.name}' updated.", "success")
    return RedirectResponse(url="/brands", status_code=303)
