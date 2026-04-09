import os
import re
from pathlib import Path

TEST_DB = Path(__file__).resolve().parent / "test_erp_pim.db"
os.environ["ERP_PIM_DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["ERP_PIM_SECRET_KEY"] = "test-secret"
os.environ["ERP_PIM_CSRF_SECRET"] = "test-csrf-secret"
os.environ["ERP_PIM_SEED_DEMO_DATA"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Product, ProductAttribute, ProductVariant, VariantAttributeValue  # noqa: E402


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


def test_generate_variants_success():
    with TestClient(app) as client:
        _login_admin(client)

        csrf_token = _get_csrf(client, "/products/new")
        product_response = client.post(
            "/products/new",
            data={
                "sku": "SKU-VAR-1",
                "name": "Variant Product",
                "short_description": "",
                "description": "",
                "category_id": "",
                "brand_id": "",
                "supplier_id": "",
                "unit": "pcs",
                "cost_price": "10",
                "sale_price": "12",
                "reorder_point": "1",
                "weight": "0",
                "length": "0",
                "width": "0",
                "height": "0",
                "status": "active",
                "tag_names": "",
                "is_active": "on",
                "csrf_token": csrf_token,
            },
            follow_redirects=False,
        )
        assert product_response.status_code == 303

        csrf_token = _get_csrf(client, "/attributes/new")
        attribute_response = client.post(
            "/attributes/new",
            data={
                "name": "Size",
                "group_name": "Variants",
                "attribute_type": "select",
                "unit_label": "",
                "raw_options": "S, M",
                "csrf_token": csrf_token,
            },
            follow_redirects=False,
        )
        assert attribute_response.status_code == 303

        db = SessionLocal()
        try:
            product = db.query(Product).filter(Product.sku == "SKU-VAR-1").first()
            attribute = db.query(ProductAttribute).filter(ProductAttribute.name == "Size").first()
            assert product is not None
            assert attribute is not None
            product_id = product.id
            attribute_id = attribute.id
        finally:
            db.close()

        csrf_token = _get_csrf(client, f"/variants/new?product_id={product_id}")
        response = client.post(
            "/variants/generate",
            data={"product_id": str(product_id), "attribute_ids": str(attribute_id), "csrf_token": csrf_token},
            follow_redirects=False,
        )
        assert response.status_code == 303
        list_response = client.get("/variants")
        assert "SKU-VAR-1-S" in list_response.text
        assert "SKU-VAR-1-M" in list_response.text

        db = SessionLocal()
        try:
            variants = db.query(ProductVariant).filter(ProductVariant.product_id == product_id).all()
            assert len(variants) == 2
            variant_ids = [variant.id for variant in variants]
            linked_options = db.query(VariantAttributeValue).filter(VariantAttributeValue.variant_id.in_(variant_ids)).all()
            assert len(linked_options) == 2
        finally:
            db.close()
