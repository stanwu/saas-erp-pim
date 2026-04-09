import math

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.dependencies import flash, get_current_user, require_admin, tmpl_ctx, validate_csrf
from app.models import Brand, Category, Product, ProductAttribute, ProductAttributeValue, ProductChannelListing, ProductImage, ProductStatus, ProductVariant, Supplier, User, VariantAttributeValue
from app.services import build_product_attribute_value_map, sync_product_attribute_values, sync_product_tags

router = APIRouter(prefix="/products", tags=["products"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


def _load_product_with_relations(db: Session, product_id: int) -> Product | None:
    return db.scalar(
        select(Product)
        .options(
            joinedload(Product.category),
            joinedload(Product.brand),
            joinedload(Product.supplier),
            joinedload(Product.tags),
            joinedload(Product.images),
            joinedload(Product.attribute_values).joinedload(ProductAttributeValue.attribute),
            joinedload(Product.variants).joinedload(ProductVariant.option_values).joinedload(VariantAttributeValue.option),
            joinedload(Product.channel_listings).joinedload(ProductChannelListing.channel),
        )
        .where(Product.id == product_id)
    )


@router.get("")
def list_products(
    request: Request,
    page: int = 1,
    q: str = "",
    category_id: str = "",
    brand_id: str = "",
    status: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    per_page = settings.page_size
    stmt = select(Product).options(joinedload(Product.category), joinedload(Product.brand))
    if q:
        stmt = stmt.where(
            or_(
                Product.sku.ilike(f"%{q}%"),
                Product.name.ilike(f"%{q}%"),
                Product.barcode.ilike(f"%{q}%"),
            )
        )
    if category_id:
        stmt = stmt.where(Product.category_id == int(category_id))
    if brand_id:
        stmt = stmt.where(Product.brand_id == int(brand_id))
    if status:
        stmt = stmt.where(Product.status == ProductStatus(status))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    total_pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, total_pages))
    products = db.scalars(
        stmt.order_by(Product.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    ).all()
    categories = db.scalars(select(Category).order_by(Category.name)).all()
    brands = db.scalars(select(Brand).order_by(Brand.name)).all()
    return templates.TemplateResponse(
        request,
        "products/list.html",
        tmpl_ctx(
            request,
            current_user,
            products=products,
            categories=categories,
            brands=brands,
            statuses=ProductStatus,
            q=q,
            category_id=category_id,
            brand_id=brand_id,
            status=status,
            page=page,
            total_pages=total_pages,
            total=total,
        ),
    )


@router.get("/new")
def new_product_page(
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    categories = db.scalars(select(Category).order_by(Category.name)).all()
    brands = db.scalars(select(Brand).order_by(Brand.name)).all()
    suppliers = db.scalars(select(Supplier).order_by(Supplier.name)).all()
    attributes = db.scalars(select(ProductAttribute).options(joinedload(ProductAttribute.options)).order_by(ProductAttribute.name)).unique().all()
    return templates.TemplateResponse(
        request,
        "products/form.html",
        tmpl_ctx(
            request,
            current_user,
            product=None,
            categories=categories,
            brands=brands,
            suppliers=suppliers,
            attributes=attributes,
            attribute_values={},
            statuses=ProductStatus,
            selected_tags="",
            error=None,
        ),
    )


@router.post("/new")
async def create_product(
    request: Request,
    sku: str = Form(...),
    name: str = Form(...),
    short_description: str = Form(""),
    description: str = Form(""),
    seo_title: str = Form(""),
    seo_description: str = Form(""),
    seo_keywords: str = Form(""),
    barcode: str = Form(""),
    category_id: str = Form(""),
    brand_id: str = Form(""),
    supplier_id: str = Form(""),
    unit: str = Form("pcs"),
    cost_price: float = Form(0),
    sale_price: float = Form(0),
    reorder_point: int = Form(0),
    weight: float = Form(0),
    length: float = Form(0),
    width: float = Form(0),
    height: float = Form(0),
    status: str = Form(ProductStatus.draft.value),
    tag_names: str = Form(""),
    is_active: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    form_data = await request.form()
    categories = db.scalars(select(Category).order_by(Category.name)).all()
    brands = db.scalars(select(Brand).order_by(Brand.name)).all()
    suppliers = db.scalars(select(Supplier).order_by(Supplier.name)).all()
    attributes = db.scalars(select(ProductAttribute).options(joinedload(ProductAttribute.options)).order_by(ProductAttribute.name)).unique().all()
    product = Product(
        sku=sku.strip(),
        name=name.strip(),
        short_description=short_description.strip() or None,
        description=description.strip() or None,
        seo_title=seo_title.strip() or None,
        seo_description=seo_description.strip() or None,
        seo_keywords=seo_keywords.strip() or None,
        barcode=barcode.strip() or None,
        category_id=int(category_id) if category_id else None,
        brand_id=int(brand_id) if brand_id else None,
        supplier_id=int(supplier_id) if supplier_id else None,
        unit=unit.strip() or "pcs",
        cost_price=cost_price,
        sale_price=sale_price,
        reorder_point=reorder_point,
        weight=weight,
        length=length,
        width=width,
        height=height,
        status=ProductStatus(status),
        is_active=bool(is_active),
    )
    db.add(product)
    try:
        db.flush()
        sync_product_tags(db, product, tag_names)
        sync_product_attribute_values(db, product, attributes, form_data)
        db.commit()
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "products/form.html",
            tmpl_ctx(
                request,
                current_user,
                product=None,
                categories=categories,
                brands=brands,
                suppliers=suppliers,
                attributes=attributes,
                attribute_values={attribute.id: form_data.get(f"attribute_{attribute.id}", "") for attribute in attributes},
                statuses=ProductStatus,
                selected_tags=tag_names,
                error="SKU already exists.",
            ),
            status_code=400,
        )
    flash(request, f"Product '{product.name}' created.", "success")
    return RedirectResponse(url="/products", status_code=303)


@router.get("/{product_id}")
def product_detail(
    product_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    product = _load_product_with_relations(db, product_id)
    if not product:
        return RedirectResponse(url="/products", status_code=303)
    return templates.TemplateResponse(
        request,
        "products/detail.html",
        tmpl_ctx(request, current_user, product=product),
    )


@router.get("/{product_id}/edit")
def edit_product_page(
    product_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    product = _load_product_with_relations(db, product_id)
    if not product:
        return RedirectResponse(url="/products", status_code=303)
    categories = db.scalars(select(Category).order_by(Category.name)).all()
    brands = db.scalars(select(Brand).order_by(Brand.name)).all()
    suppliers = db.scalars(select(Supplier).order_by(Supplier.name)).all()
    attributes = db.scalars(select(ProductAttribute).options(joinedload(ProductAttribute.options)).order_by(ProductAttribute.name)).unique().all()
    selected_tags = ", ".join(tag.name for tag in product.tags)
    attribute_values = build_product_attribute_value_map(product)
    return templates.TemplateResponse(
        request,
        "products/form.html",
        tmpl_ctx(
            request,
            current_user,
            product=product,
            categories=categories,
            brands=brands,
            suppliers=suppliers,
            attributes=attributes,
            attribute_values=attribute_values,
            statuses=ProductStatus,
            selected_tags=selected_tags,
            error=None,
        ),
    )


@router.post("/{product_id}/edit")
async def edit_product(
    product_id: int,
    request: Request,
    name: str = Form(...),
    short_description: str = Form(""),
    description: str = Form(""),
    seo_title: str = Form(""),
    seo_description: str = Form(""),
    seo_keywords: str = Form(""),
    barcode: str = Form(""),
    category_id: str = Form(""),
    brand_id: str = Form(""),
    supplier_id: str = Form(""),
    unit: str = Form("pcs"),
    cost_price: float = Form(0),
    sale_price: float = Form(0),
    reorder_point: int = Form(0),
    weight: float = Form(0),
    length: float = Form(0),
    width: float = Form(0),
    height: float = Form(0),
    status: str = Form(ProductStatus.draft.value),
    tag_names: str = Form(""),
    is_active: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    form_data = await request.form()
    product = db.get(Product, product_id)
    if not product:
        return RedirectResponse(url="/products", status_code=303)

    product.name = name.strip()
    product.short_description = short_description.strip() or None
    product.description = description.strip() or None
    product.seo_title = seo_title.strip() or None
    product.seo_description = seo_description.strip() or None
    product.seo_keywords = seo_keywords.strip() or None
    product.barcode = barcode.strip() or None
    product.category_id = int(category_id) if category_id else None
    product.brand_id = int(brand_id) if brand_id else None
    product.supplier_id = int(supplier_id) if supplier_id else None
    product.unit = unit.strip() or "pcs"
    product.cost_price = cost_price
    product.sale_price = sale_price
    product.reorder_point = reorder_point
    product.weight = weight
    product.length = length
    product.width = width
    product.height = height
    product.status = ProductStatus(status)
    product.is_active = bool(is_active)
    attributes = db.scalars(select(ProductAttribute).options(joinedload(ProductAttribute.options)).order_by(ProductAttribute.name)).unique().all()
    sync_product_tags(db, product, tag_names)
    sync_product_attribute_values(db, product, attributes, form_data)
    db.commit()
    flash(request, f"Product '{product.name}' updated.", "success")
    return RedirectResponse(url=f"/products/{product_id}", status_code=303)


@router.post("/{product_id}/toggle")
async def toggle_product(
    product_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    product = db.get(Product, product_id)
    if product:
        product.is_active = not product.is_active
        db.commit()
        status = "activated" if product.is_active else "deactivated"
        flash(request, f"Product '{product.name}' {status}.", "success")
    return RedirectResponse(url="/products", status_code=303)
