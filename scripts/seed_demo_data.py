"""Seed the local database with richer demo data for screenshots and README examples."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bootstrap import init_db, seed_initial_data
from app.database import SessionLocal
from app.demo_seed import seed_demo_data
from app.models import (
    AttributeGroup,
    Brand,
    Category,
    Product,
    ProductVariant,
    SalesChannel,
    Supplier,
    Tag,
    User,
)


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        seed_initial_data(db)
        seed_demo_data(db, cleanup_legacy=True)
        counts = {
            "users": db.query(User).count(),
            "categories": db.query(Category).count(),
            "brands": db.query(Brand).count(),
            "suppliers": db.query(Supplier).count(),
            "tags": db.query(Tag).count(),
            "attribute_groups": db.query(AttributeGroup).count(),
            "products": db.query(Product).count(),
            "variants": db.query(ProductVariant).count(),
            "channels": db.query(SalesChannel).count(),
        }
        print("Demo data ready:")
        for key, value in counts.items():
            print(f"  {key}: {value}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
