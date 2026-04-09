import os
import re
from pathlib import Path

from sqlalchemy import select

TEST_DB = Path(__file__).resolve().parent / "test_erp_pim.db"
os.environ["ERP_PIM_DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["ERP_PIM_SECRET_KEY"] = "test-secret"
os.environ["ERP_PIM_CSRF_SECRET"] = "test-csrf-secret"
os.environ["ERP_PIM_SEED_DEMO_DATA"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Product, ProductAttribute, ProductAttributeValue  # noqa: E402


def _get_csrf(client: TestClient, path: str = "/login") -> str:
    response = client.get(path)
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
    return match.group(1) if match else ""


def _login_admin(client: TestClient) -> None:
    csrf_token = _get_csrf(client)
    response = client.post(
        "/login",
        data={"username": "admin", "password": "admin@12345", "csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_create_attribute_success():
    with TestClient(app) as client:
        _login_admin(client)
        csrf_token = _get_csrf(client, "/attributes/new")
        response = client.post(
            "/attributes/new",
            data={
                "name": "Color",
                "group_name": "Variants",
                "attribute_type": "select",
                "unit_label": "",
                "raw_options": "Red, Blue, Green",
                "is_required": "on",
                "csrf_token": csrf_token,
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        list_response = client.get("/attributes")
        assert "Color" in list_response.text
        assert "Variants" in list_response.text


def test_save_product_attribute_value_success():
    with TestClient(app) as client:
        _login_admin(client)

        csrf_token = _get_csrf(client, "/attributes/new")
        attribute_response = client.post(
            "/attributes/new",
            data={
                "name": "Finish",
                "group_name": "Specs",
                "attribute_type": "text",
                "unit_label": "",
                "raw_options": "",
                "csrf_token": csrf_token,
            },
            follow_redirects=False,
        )
        assert attribute_response.status_code == 303

        db = SessionLocal()
        try:
            attribute = db.scalar(select(ProductAttribute).where(ProductAttribute.name == "Finish"))
            assert attribute is not None
            attribute_id = attribute.id
        finally:
            db.close()

        csrf_token = _get_csrf(client, "/products/new")
        response = client.post(
            "/products/new",
            data={
                "sku": "SKU-ATTR-1",
                "name": "Attribute Product",
                "short_description": "",
                "description": "",
                "category_id": "",
                "brand_id": "",
                "supplier_id": "",
                "unit": "pcs",
                "cost_price": "1",
                "sale_price": "2",
                "reorder_point": "0",
                "weight": "0",
                "length": "0",
                "width": "0",
                "height": "0",
                "status": "active",
                "tag_names": "",
                f"attribute_{attribute_id}": "Blue",
                "is_active": "on",
                "csrf_token": csrf_token,
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

        db = SessionLocal()
        try:
            product = db.scalar(select(Product).where(Product.sku == "SKU-ATTR-1"))
            assert product is not None
            values = db.scalars(select(ProductAttributeValue).where(ProductAttributeValue.product_id == product.id)).all()
            assert any(value.value == "Blue" for value in values)
        finally:
            db.close()
