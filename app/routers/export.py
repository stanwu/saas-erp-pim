import csv
from io import StringIO

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import Product, User

router = APIRouter(prefix="/export", tags=["export"])
settings = get_settings()


@router.get("/products.csv")
def export_products_csv(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = current_user
    rows = db.scalars(select(Product).options(joinedload(Product.category)).order_by(Product.sku)).all()
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["sku", "name", "description", "category", "unit", "cost_price", "reorder_point"])
    for product in rows:
        writer.writerow(
            [
                product.sku,
                product.name,
                product.description or "",
                product.category.name if product.category else "",
                product.unit,
                product.cost_price,
                product.reorder_point,
            ]
        )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=products.csv"},
    )
