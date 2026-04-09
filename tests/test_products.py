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


def setup_module():
    if TEST_DB.exists():
        TEST_DB.unlink()


def teardown_module():
    if TEST_DB.exists():
        TEST_DB.unlink()


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


def test_create_product_success():
    with TestClient(app) as client:
        _login_admin(client)
        csrf_token = _get_csrf(client, "/products/new")
        response = client.post(
            "/products/new",
            data={
                "sku": "SKU-TEST-1",
                "name": "Test Product",
                "short_description": "Test short",
                "description": "Full description",
                "category_id": "",
                "brand_id": "",
                "supplier_id": "",
                "unit": "pcs",
                "cost_price": "10",
                "sale_price": "15",
                "reorder_point": "2",
                "weight": "1",
                "length": "2",
                "width": "3",
                "height": "4",
                "status": "active",
                "tag_names": "demo, sample",
                "is_active": "on",
                "csrf_token": csrf_token,
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        list_response = client.get("/products")
        assert "SKU-TEST-1" in list_response.text
        assert "Test Product" in list_response.text


def test_export_products_csv():
    with TestClient(app) as client:
        _login_admin(client)
        response = client.get("/export/products.csv")
        assert response.status_code == 200
        assert "sku,name,description,category,unit,cost_price,reorder_point" in response.text
