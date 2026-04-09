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


def _get_csrf(client: TestClient) -> str:
    response = client.get("/login")
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


def test_login_page_loads():
    with TestClient(app) as client:
        response = client.get("/login")
        assert response.status_code == 200
        assert "ERP PIM" in response.text


def test_dashboard_requires_login():
    with TestClient(app) as client:
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 303


def test_dashboard_after_login():
    with TestClient(app) as client:
        _login_admin(client)
        response = client.get("/")
        assert response.status_code == 200
        assert "Recent Products" in response.text
