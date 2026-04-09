from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Brand, Category, Product, ProductStatus, Supplier
from app.services import ensure_unique_slug


BRANDS = [
    ("Acme Tools", "https://acme.example.com", "Industrial hardware and tooling brand."),
    ("Northwind Home", "https://northwind.example.com", "Home and lifestyle goods."),
]

CATEGORIES = [
    ("General", "General merchandise"),
    ("Electronics", "Electronic devices and accessories"),
    ("Furniture", "Furniture and fixtures"),
]

SUPPLIERS = [
    ("Global Source Ltd.", "Amy Lin", "amy@example.com", "+886-2-1234-5678"),
    ("Delta Manufacturing", "Mark Chen", "mark@example.com", "+886-2-8765-4321"),
]

PRODUCTS = [
    ("SKU-1001", "Cordless Drill", "18V cordless drill", "Compact drill with two batteries", 89.0, 129.0),
    ("SKU-1002", "Standing Desk", "Height-adjustable desk", "Electric standing desk with memory presets", 220.0, 399.0),
]


def seed_demo_data(db: Session) -> None:
    for name, description in CATEGORIES:
        if not db.scalar(select(Category).where(Category.name == name)):
            db.add(Category(name=name, description=description, slug=ensure_unique_slug(db, Category, name)))

    for name, website, description in BRANDS:
        if not db.scalar(select(Brand).where(Brand.name == name)):
            db.add(Brand(name=name, website=website, description=description, slug=ensure_unique_slug(db, Brand, name)))

    for name, contact_person, email, phone in SUPPLIERS:
        if not db.scalar(select(Supplier).where(Supplier.name == name)):
            db.add(Supplier(name=name, contact_person=contact_person, email=email, phone=phone))

    db.commit()

    default_category = db.scalar(select(Category).where(Category.name == "General"))
    first_brand = db.scalar(select(Brand).where(Brand.name == "Acme Tools"))
    first_supplier = db.scalar(select(Supplier).where(Supplier.name == "Global Source Ltd."))
    for sku, name, short_description, description, cost_price, sale_price in PRODUCTS:
        if not db.scalar(select(Product).where(Product.sku == sku)):
            db.add(
                Product(
                    sku=sku,
                    name=name,
                    short_description=short_description,
                    description=description,
                    category_id=default_category.id if default_category else None,
                    brand_id=first_brand.id if first_brand else None,
                    supplier_id=first_supplier.id if first_supplier else None,
                    cost_price=cost_price,
                    sale_price=sale_price,
                    reorder_point=5,
                    status=ProductStatus.active,
                    is_active=True,
                )
            )

    db.commit()


def should_seed_demo_data(db: Session) -> bool:
    return (db.scalar(select(func.count(Product.id))) or 0) == 0
