import csv
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.database import SessionLocal
from app.models import Product


def export_products_csv(output_path: Path) -> None:
    db = SessionLocal()
    try:
        products = db.scalars(select(Product).options(joinedload(Product.category)).order_by(Product.sku)).all()
        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["sku", "name", "description", "category", "unit", "cost_price", "reorder_point"])
            for product in products:
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
    finally:
        db.close()


if __name__ == "__main__":
    export_products_csv(Path("products_export.csv"))
