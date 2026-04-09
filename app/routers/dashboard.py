from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user, tmpl_ctx
from app.models import Brand, Category, Product, ProductStatus, Supplier, User

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


@router.get("/")
def dashboard(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stats = {
        "products": db.scalar(select(func.count(Product.id))) or 0,
        "active_products": db.scalar(select(func.count(Product.id)).where(Product.status == ProductStatus.active)) or 0,
        "categories": db.scalar(select(func.count(Category.id))) or 0,
        "brands": db.scalar(select(func.count(Brand.id))) or 0,
        "suppliers": db.scalar(select(func.count(Supplier.id))) or 0,
    }
    recent_products = db.scalars(select(Product).order_by(Product.created_at.desc()).limit(8)).all()
    return templates.TemplateResponse(
        request,
        "dashboard/index.html",
        tmpl_ctx(request, current_user, stats=stats, recent_products=recent_products),
    )
