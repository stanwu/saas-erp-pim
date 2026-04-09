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
from app.models import AttributeOption, AttributeType, Product, ProductAttribute, ProductVariant, User, VariantAttributeValue
from app.services import generate_variant_combinations

router = APIRouter(prefix="/variants", tags=["variants"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


@router.get("")
def list_variants(
    request: Request,
    page: int = 1,
    q: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    per_page = settings.page_size
    stmt = select(ProductVariant).options(joinedload(ProductVariant.product), joinedload(ProductVariant.option_values).joinedload(VariantAttributeValue.option))
    if q:
        stmt = stmt.join(Product).where(
            ProductVariant.sku.ilike(f"%{q}%") | ProductVariant.name.ilike(f"%{q}%") | Product.name.ilike(f"%{q}%")
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    total_pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, total_pages))
    variants = db.scalars(
        stmt.order_by(ProductVariant.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    ).unique().all()
    return templates.TemplateResponse(
        request,
        "variants/list.html",
        tmpl_ctx(request, current_user, variants=variants, q=q, page=page, total_pages=total_pages, total=total),
    )


@router.get("/new")
def new_variant_page(
    request: Request,
    product_id: str = "",
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    products = db.scalars(select(Product).order_by(Product.name)).all()
    attributes = db.scalars(
        select(ProductAttribute)
        .options(joinedload(ProductAttribute.options))
        .where(
            (ProductAttribute.attribute_type == AttributeType.select) | (ProductAttribute.attribute_type == AttributeType.multiselect)
        )
        .order_by(ProductAttribute.name)
    ).unique().all()
    selected_product = db.get(Product, int(product_id)) if product_id else None
    return templates.TemplateResponse(
        request,
        "variants/form.html",
        tmpl_ctx(
            request,
            current_user,
            variant=None,
            products=products,
            attributes=attributes,
            selected_product=selected_product,
            error=None,
        ),
    )


@router.post("/new")
async def create_variant(
    request: Request,
    product_id: int = Form(...),
    sku: str = Form(...),
    name: str = Form(...),
    barcode: str = Form(""),
    price_adjustment: float = Form(0),
    is_active: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    form_data = await request.form()
    products = db.scalars(select(Product).order_by(Product.name)).all()
    attributes = db.scalars(select(ProductAttribute).options(joinedload(ProductAttribute.options)).order_by(ProductAttribute.name)).unique().all()
    variant = ProductVariant(
        product_id=product_id,
        sku=sku.strip(),
        name=name.strip(),
        barcode=barcode.strip() or None,
        price_adjustment=price_adjustment,
        is_active=bool(is_active),
    )
    selected_options = []
    raw_option_ids = []
    for value in form_data.getlist("option_ids"):
        clean_value = str(value).strip()
        if clean_value:
            raw_option_ids.append(int(clean_value))
    if raw_option_ids:
        options = db.scalars(select(AttributeOption).where(AttributeOption.id.in_(raw_option_ids))).all()
        option_map = {option.id: option for option in options}
        for option_id in raw_option_ids:
            option = option_map.get(option_id)
            if option:
                selected_options.append(option)
        variant.option_values = [VariantAttributeValue(option_id=option.id) for option in selected_options]
    db.add(variant)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "variants/form.html",
            tmpl_ctx(
                request,
                current_user,
                variant=None,
                products=products,
                attributes=attributes,
        selected_product=db.get(Product, product_id),
                error="Variant SKU already exists for this product.",
            ),
            status_code=400,
        )
    flash(request, f"Variant '{variant.name}' created.", "success")
    return RedirectResponse(url="/variants", status_code=303)


@router.post("/generate")
async def generate_variants(
    request: Request,
    product_id: int = Form(...),
    attribute_ids: list[int] = Form([]),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    product = db.scalar(select(Product).options(joinedload(Product.variants)).where(Product.id == product_id))
    if not product or not attribute_ids:
        return RedirectResponse(url=f"/variants/new?product_id={product_id}", status_code=303)

    attributes = db.scalars(
        select(ProductAttribute)
        .options(joinedload(ProductAttribute.options))
        .where(ProductAttribute.id.in_(attribute_ids))
        .order_by(ProductAttribute.name)
    ).unique().all()
    option_ids = [[option.id for option in attribute.options] for attribute in attributes if attribute.options]
    if not option_ids or len(option_ids) != len(attributes):
        flash(request, "Selected attributes must have options before generating variants.", "warning")
        return RedirectResponse(url=f"/variants/new?product_id={product_id}", status_code=303)

    existing_skus = {variant.sku for variant in product.variants}
    generated = 0
    for variant in generate_variant_combinations(db, product, option_ids):
        if variant.sku in existing_skus:
            continue
        db.add(variant)
        existing_skus.add(variant.sku)
        generated += 1
    db.commit()
    flash(request, f"{generated} variants generated for '{product.name}'.", "success")
    return RedirectResponse(url="/variants", status_code=303)
