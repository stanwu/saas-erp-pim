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
from app.models import Supplier, User

router = APIRouter(prefix="/suppliers", tags=["suppliers"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


@router.get("")
def list_suppliers(
    request: Request,
    page: int = 1,
    q: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    per_page = settings.page_size
    stmt = select(Supplier)
    if q:
        stmt = stmt.where(Supplier.name.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    total_pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, total_pages))
    suppliers = db.scalars(
        stmt.order_by(Supplier.name).offset((page - 1) * per_page).limit(per_page)
    ).all()
    return templates.TemplateResponse(
        request,
        "suppliers/list.html",
        tmpl_ctx(request, current_user, suppliers=suppliers, q=q, page=page, total_pages=total_pages, total=total),
    )


@router.get("/new")
def new_supplier_page(
    request: Request,
    current_user: User = Depends(require_admin),
):
    return templates.TemplateResponse(
        request,
        "suppliers/form.html",
        tmpl_ctx(request, current_user, supplier=None, error=None),
    )


@router.post("/new")
async def create_supplier(
    request: Request,
    name: str = Form(...),
    contact_person: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    is_active: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    clean_name = name.strip()
    supplier = Supplier(
        name=clean_name,
        contact_person=contact_person.strip() or None,
        email=email.strip() or None,
        phone=phone.strip() or None,
        is_active=bool(is_active),
    )
    db.add(supplier)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "suppliers/form.html",
            tmpl_ctx(request, current_user, supplier=None, error="Supplier already exists."),
            status_code=400,
        )
    flash(request, f"Supplier '{clean_name}' created.", "success")
    return RedirectResponse(url="/suppliers", status_code=303)


@router.get("/{supplier_id}/edit")
def edit_supplier_page(
    supplier_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        return RedirectResponse(url="/suppliers", status_code=303)
    return templates.TemplateResponse(
        request,
        "suppliers/form.html",
        tmpl_ctx(request, current_user, supplier=supplier, error=None),
    )


@router.post("/{supplier_id}/edit")
async def edit_supplier(
    supplier_id: int,
    request: Request,
    name: str = Form(...),
    contact_person: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    is_active: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        return RedirectResponse(url="/suppliers", status_code=303)

    supplier.name = name.strip()
    supplier.contact_person = contact_person.strip() or None
    supplier.email = email.strip() or None
    supplier.phone = phone.strip() or None
    supplier.is_active = bool(is_active)
    db.commit()
    flash(request, f"Supplier '{supplier.name}' updated.", "success")
    return RedirectResponse(url="/suppliers", status_code=303)
