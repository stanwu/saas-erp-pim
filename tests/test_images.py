import os
import re
from io import BytesIO
from pathlib import Path

TEST_DB = Path(__file__).resolve().parent / "test_erp_pim.db"
os.environ["ERP_PIM_DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["ERP_PIM_SECRET_KEY"] = "test-secret"
os.environ["ERP_PIM_CSRF_SECRET"] = "test-csrf-secret"
os.environ["ERP_PIM_SEED_DEMO_DATA"] = "false"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.main import app  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Product, ProductImage  # noqa: E402


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


def test_upload_product_image_success():
    with TestClient(app) as client:
        _login_admin(client)

        csrf_token = _get_csrf(client, "/products/new")
        response = client.post(
            "/products/new",
            data={
                "sku": "SKU-IMG-1",
                "name": "Image Product",
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
                "is_active": "on",
                "csrf_token": csrf_token,
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

        db = SessionLocal()
        try:
            product = db.scalar(select(Product).where(Product.sku == "SKU-IMG-1"))
            assert product is not None
            product_id = product.id
        finally:
            db.close()

        csrf_token = _get_csrf(client, f"/images/products/{product_id}")
        upload_response = client.post(
            f"/images/products/{product_id}/upload",
            data={"alt_text": "Front view", "is_primary": "on", "csrf_token": csrf_token},
            files={"image_file": ("test.png", BytesIO(b"fake-image-bytes"), "image/png")},
            follow_redirects=False,
        )
        assert upload_response.status_code == 303

        db = SessionLocal()
        try:
            images = db.scalars(select(ProductImage).where(ProductImage.product_id == product_id)).all()
            assert len(images) == 1
            assert images[0].alt_text == "Front view"
            assert images[0].is_primary is True
        finally:
            db.close()
