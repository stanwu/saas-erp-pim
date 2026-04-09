from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.dependencies import flash, get_current_user, require_admin, tmpl_ctx, validate_csrf
from app.models import Product, ProductImage, ProductVariant, User
from app.services import delete_product_upload, save_product_upload, set_primary_product_image

router = APIRouter(prefix="/images", tags=["images"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


def _load_product_images(db: Session, product_id: int) -> Product | None:
    return db.scalar(
        select(Product)
        .options(joinedload(Product.images), joinedload(Product.variants))
        .where(Product.id == product_id)
    )


@router.get("/products/{product_id}")
def manage_product_images(
    product_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    product = _load_product_images(db, product_id)
    if not product:
        return RedirectResponse(url="/products", status_code=303)
    return templates.TemplateResponse(
        request,
        "images/manage.html",
        tmpl_ctx(request, current_user, product=product, error=None),
    )


@router.post("/products/{product_id}/upload")
async def upload_product_image(
    product_id: int,
    request: Request,
    image_file: UploadFile = File(...),
    alt_text: str = Form(""),
    variant_id: str = Form(""),
    is_primary: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    _ = current_user
    product = _load_product_images(db, product_id)
    if not product:
        return RedirectResponse(url="/products", status_code=303)
    content = await image_file.read()
    if not content:
        flash(request, "Image upload failed.", "warning")
        return RedirectResponse(url=f"/images/products/{product_id}", status_code=303)

    path_value = save_product_upload(product_id, image_file.filename or "upload.bin", content)
    sort_order = max((image.sort_order for image in product.images), default=0) + 1
    image = ProductImage(
        product_id=product_id,
        variant_id=int(variant_id) if variant_id else None,
        path=path_value,
        alt_text=alt_text.strip() or None,
        sort_order=sort_order,
        is_primary=bool(is_primary) or len(product.images) == 0,
    )
    db.add(image)
    db.flush()
    if image.is_primary:
        set_primary_product_image(product, image)
    db.commit()
    flash(request, "Image uploaded.", "success")
    return RedirectResponse(url=f"/images/products/{product_id}", status_code=303)


@router.post("/{image_id}/edit")
async def edit_product_image(
    image_id: int,
    request: Request,
    alt_text: str = Form(""),
    sort_order: int = Form(0),
    variant_id: str = Form(""),
    is_primary: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    _ = current_user
    image = db.scalar(select(ProductImage).options(joinedload(ProductImage.product)).where(ProductImage.id == image_id))
    if not image or not image.product:
        return RedirectResponse(url="/products", status_code=303)
    image.alt_text = alt_text.strip() or None
    image.sort_order = sort_order
    image.variant_id = int(variant_id) if variant_id else None
    if is_primary:
        set_primary_product_image(image.product, image)
    db.commit()
    flash(request, "Image updated.", "success")
    return RedirectResponse(url=f"/images/products/{image.product_id}", status_code=303)


@router.post("/{image_id}/delete")
async def delete_image(
    image_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    _ = current_user
    image = db.scalar(select(ProductImage).options(joinedload(ProductImage.product)).where(ProductImage.id == image_id))
    if not image or not image.product:
        return RedirectResponse(url="/products", status_code=303)
    product_id = image.product_id
    delete_product_upload(image.path)
    db.delete(image)
    db.commit()
    flash(request, "Image deleted.", "success")
    return RedirectResponse(url=f"/images/products/{product_id}", status_code=303)
