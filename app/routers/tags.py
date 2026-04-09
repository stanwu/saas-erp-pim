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
from app.models import Tag, User
from app.services import ensure_unique_slug

router = APIRouter(prefix="/tags", tags=["tags"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


@router.get("")
def list_tags(
    request: Request,
    page: int = 1,
    q: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    per_page = settings.page_size
    stmt = select(Tag)
    if q:
        stmt = stmt.where(Tag.name.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    total_pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, total_pages))
    tags = db.scalars(
        stmt.order_by(Tag.name).offset((page - 1) * per_page).limit(per_page)
    ).all()
    return templates.TemplateResponse(
        request,
        "tags/list.html",
        tmpl_ctx(request, current_user, tags=tags, q=q, page=page, total_pages=total_pages, total=total),
    )


@router.get("/new")
def new_tag_page(
    request: Request,
    current_user: User = Depends(require_admin),
):
    return templates.TemplateResponse(
        request,
        "tags/form.html",
        tmpl_ctx(request, current_user, tag=None, error=None),
    )


@router.post("/new")
async def create_tag(
    request: Request,
    name: str = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    clean_name = name.strip()
    tag = Tag(name=clean_name, slug=ensure_unique_slug(db, Tag, clean_name))
    db.add(tag)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "tags/form.html",
            tmpl_ctx(request, current_user, tag=None, error="Tag already exists."),
            status_code=400,
        )
    flash(request, f"Tag '{clean_name}' created.", "success")
    return RedirectResponse(url="/tags", status_code=303)


@router.get("/{tag_id}/edit")
def edit_tag_page(
    tag_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    tag = db.get(Tag, tag_id)
    if not tag:
        return RedirectResponse(url="/tags", status_code=303)
    return templates.TemplateResponse(
        request,
        "tags/form.html",
        tmpl_ctx(request, current_user, tag=tag, error=None),
    )


@router.post("/{tag_id}/edit")
async def edit_tag(
    tag_id: int,
    request: Request,
    name: str = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    tag = db.get(Tag, tag_id)
    if not tag:
        return RedirectResponse(url="/tags", status_code=303)
    tag.name = name.strip()
    tag.slug = ensure_unique_slug(db, Tag, tag.name, current_id=tag.id)
    db.commit()
    flash(request, f"Tag '{tag.name}' updated.", "success")
    return RedirectResponse(url="/tags", status_code=303)
