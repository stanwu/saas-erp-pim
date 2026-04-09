import os
import re
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
from app.models import Product, ProductChannelListing, SalesChannel  # noqa: E402


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


def test_create_product_channel_listing_success():
    with TestClient(app) as client:
        _login_admin(client)

        csrf_token = _get_csrf(client, "/products/new")
        response = client.post(
            "/products/new",
            data={
                "sku": "SKU-CH-2",
                "name": "Channel Product",
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
            product = db.scalar(select(Product).where(Product.sku == "SKU-CH-2"))
            channel = db.scalar(select(SalesChannel).where(SalesChannel.name == "Shopify"))
            assert product is not None
            assert channel is not None
            product_id = product.id
            channel_id = channel.id
        finally:
            db.close()

        connect_page = client.get(f"/channels/{channel_id}/connect")
        assert connect_page.status_code == 200
        assert "Connect Shopify" in connect_page.text

        csrf_token = _get_csrf(client, f"/channels/{channel_id}/connect")
        connect_response = client.post(
            f"/channels/{channel_id}/connect",
            data={
                "account_label": "Main Shopify Store",
                "store_url": "https://example.myshopify.com",
                "requested_scopes": "read_products,write_products",
                "access_token": "shpat_test_token",
                "oauth_redirect_uri": f"http://testserver/channels/{channel_id}/oauth/callback",
                "csrf_token": csrf_token,
            },
            follow_redirects=False,
        )
        assert connect_response.status_code == 303

        oauth_response = client.get(f"/channels/{channel_id}/oauth/callback?code=test-auth-code", follow_redirects=False)
        assert oauth_response.status_code == 303

        csrf_token = _get_csrf(client, f"/channels/{product_id}/listings")
        listing_response = client.post(
            f"/channels/{product_id}/listings/new",
            data={
                "channel_id": str(channel_id),
                "external_product_id": "gid://shopify/Product/1",
                "external_url": "https://example.myshopify.com/products/channel-product",
                "listing_status": "published",
                "title_override": "Channel Product Title",
                "description_override": "Channel description",
                "price_override": "3.50",
                "sync_enabled": "on",
                "csrf_token": csrf_token,
            },
            follow_redirects=False,
        )
        assert listing_response.status_code == 303

        db = SessionLocal()
        try:
            channel = db.get(SalesChannel, channel_id)
            listing = db.scalar(select(ProductChannelListing).where(ProductChannelListing.product_id == product_id))
            assert channel is not None
            assert channel.account_label == "Main Shopify Store"
            assert channel.last_oauth_code == "test-auth-code"
            assert listing is not None
            assert listing.external_product_id == "gid://shopify/Product/1"
            assert float(listing.price_override) == 3.5
        finally:
            db.close()
