import math

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.dependencies import flash, get_current_user, require_admin, tmpl_ctx, validate_csrf
from app.models import AttributeGroup, AttributeOption, AttributeType, ProductAttribute, User
from app.services import ensure_unique_slug

router = APIRouter(prefix="/attributes", tags=["attributes"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


def _get_or_create_group(db: Session, group_name: str) -> AttributeGroup | None:
    clean_name = group_name.strip()
    if not clean_name:
        return None
    group = db.scalar(select(AttributeGroup).where(AttributeGroup.name == clean_name))
    if group:
        return group
    group = AttributeGroup(name=clean_name, description=None, sort_order=0)
    db.add(group)
    db.flush()
    return group


def _sync_attribute_options(db: Session, attribute: ProductAttribute, raw_options: str) -> None:
    option_names = []
    for value in raw_options.split(","):
        clean_value = value.strip()
        if clean_value and clean_value not in option_names:
            option_names.append(clean_value)
    attribute.options.clear()
    for index, value in enumerate(option_names):
        attribute.options.append(AttributeOption(value=value, sort_order=index))


@router.get("")
def list_attributes(
    request: Request,
    page: int = 1,
    q: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    per_page = settings.page_size
    stmt = select(ProductAttribute).options(joinedload(ProductAttribute.group), joinedload(ProductAttribute.options))
    if q:
        stmt = stmt.where(ProductAttribute.name.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    total_pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, total_pages))
    attributes = db.scalars(
        stmt.order_by(ProductAttribute.name).offset((page - 1) * per_page).limit(per_page)
    ).unique().all()
    return templates.TemplateResponse(
        request,
        "attributes/list.html",
        tmpl_ctx(request, current_user, attributes=attributes, q=q, page=page, total_pages=total_pages, total=total),
    )


@router.get("/new")
def new_attribute_page(
    request: Request,
    current_user: User = Depends(require_admin),
):
    return templates.TemplateResponse(
        request,
        "attributes/form.html",
        tmpl_ctx(request, current_user, attribute=None, raw_options="", error=None, types=AttributeType),
    )


@router.post("/new")
async def create_attribute(
    request: Request,
    name: str = Form(...),
    group_name: str = Form(""),
    attribute_type: str = Form(AttributeType.text.value),
    unit_label: str = Form(""),
    raw_options: str = Form(""),
    is_required: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    clean_name = name.strip()
    group = _get_or_create_group(db, group_name)
    attribute = ProductAttribute(
        name=clean_name,
        slug=ensure_unique_slug(db, ProductAttribute, clean_name),
        group_id=group.id if group else None,
        attribute_type=AttributeType(attribute_type),
        unit_label=unit_label.strip() or None,
        is_required=bool(is_required),
    )
    if attribute.attribute_type in {AttributeType.select, AttributeType.multiselect}:
        _sync_attribute_options(db, attribute, raw_options)
    db.add(attribute)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "attributes/form.html",
            tmpl_ctx(request, current_user, attribute=None, raw_options=raw_options, error="Attribute already exists.", types=AttributeType),
            status_code=400,
        )
    flash(request, f"Attribute '{clean_name}' created.", "success")
    return RedirectResponse(url="/attributes", status_code=303)


@router.get("/{attribute_id}/edit")
def edit_attribute_page(
    attribute_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    attribute = db.scalar(
        select(ProductAttribute)
        .options(joinedload(ProductAttribute.group), joinedload(ProductAttribute.options))
        .where(ProductAttribute.id == attribute_id)
    )
    if not attribute:
        return RedirectResponse(url="/attributes", status_code=303)
    raw_options = ", ".join(option.value for option in attribute.options)
    return templates.TemplateResponse(
        request,
        "attributes/form.html",
        tmpl_ctx(request, current_user, attribute=attribute, raw_options=raw_options, error=None, types=AttributeType),
    )


@router.post("/{attribute_id}/edit")
async def edit_attribute(
    attribute_id: int,
    request: Request,
    name: str = Form(...),
    group_name: str = Form(""),
    attribute_type: str = Form(AttributeType.text.value),
    unit_label: str = Form(""),
    raw_options: str = Form(""),
    is_required: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    attribute = db.scalar(
        select(ProductAttribute)
        .options(joinedload(ProductAttribute.options))
        .where(ProductAttribute.id == attribute_id)
    )
    if not attribute:
        return RedirectResponse(url="/attributes", status_code=303)

    group = _get_or_create_group(db, group_name)
    attribute.name = name.strip()
    attribute.slug = ensure_unique_slug(db, ProductAttribute, attribute.name, current_id=attribute.id)
    attribute.group_id = group.id if group else None
    attribute.attribute_type = AttributeType(attribute_type)
    attribute.unit_label = unit_label.strip() or None
    attribute.is_required = bool(is_required)
    if attribute.attribute_type in {AttributeType.select, AttributeType.multiselect}:
        _sync_attribute_options(db, attribute, raw_options)
    else:
        attribute.options.clear()
    db.commit()
    flash(request, f"Attribute '{attribute.name}' updated.", "success")
    return RedirectResponse(url="/attributes", status_code=303)
