from pathlib import Path

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, engine
from app.demo_seed import seed_demo_data, should_seed_demo_data
from app.models import Brand, Category, SalesChannel, SalesChannelType, Supplier, User, UserRole
from app.security import hash_password
from app.services import ensure_unique_slug


def init_db() -> None:
    settings = get_settings()
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _ensure_legacy_columns()


def _ensure_legacy_columns() -> None:
    inspector = inspect(engine)
    if "sales_channels" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("sales_channels")}
    required_columns = {
        "preferred_auth_method": "ALTER TABLE sales_channels ADD COLUMN preferred_auth_method VARCHAR(32) NOT NULL DEFAULT 'manual_key'",
        "setup_status": "ALTER TABLE sales_channels ADD COLUMN setup_status VARCHAR(32) NOT NULL DEFAULT 'not_connected'",
        "help_url": "ALTER TABLE sales_channels ADD COLUMN help_url VARCHAR(255)",
        "account_label": "ALTER TABLE sales_channels ADD COLUMN account_label VARCHAR(128)",
        "store_url": "ALTER TABLE sales_channels ADD COLUMN store_url VARCHAR(255)",
        "requested_scopes": "ALTER TABLE sales_channels ADD COLUMN requested_scopes TEXT",
        "api_key": "ALTER TABLE sales_channels ADD COLUMN api_key VARCHAR(255)",
        "api_secret": "ALTER TABLE sales_channels ADD COLUMN api_secret VARCHAR(255)",
        "access_token": "ALTER TABLE sales_channels ADD COLUMN access_token TEXT",
        "refresh_token": "ALTER TABLE sales_channels ADD COLUMN refresh_token TEXT",
        "client_id": "ALTER TABLE sales_channels ADD COLUMN client_id VARCHAR(255)",
        "client_secret": "ALTER TABLE sales_channels ADD COLUMN client_secret VARCHAR(255)",
        "oauth_redirect_uri": "ALTER TABLE sales_channels ADD COLUMN oauth_redirect_uri VARCHAR(255)",
        "last_oauth_code": "ALTER TABLE sales_channels ADD COLUMN last_oauth_code TEXT",
        "last_connection_error": "ALTER TABLE sales_channels ADD COLUMN last_connection_error TEXT",
        "connected_at": "ALTER TABLE sales_channels ADD COLUMN connected_at DATETIME",
    }
    with engine.begin() as conn:
        for column_name, ddl in required_columns.items():
            if column_name not in existing_columns:
                conn.execute(text(ddl))


def seed_initial_data(db: Session) -> None:
    settings = get_settings()

    if not db.scalar(select(User).where(User.username == settings.admin_username)):
        db.add(
            User(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
                role=UserRole.admin,
                is_active=True,
            )
        )

    if not db.scalar(select(Category).where(Category.name == "General")):
        db.add(Category(name="General", description="Default category", slug=ensure_unique_slug(db, Category, "General")))

    if not db.scalar(select(Brand).where(Brand.name == "Unbranded")):
        db.add(Brand(name="Unbranded", slug=ensure_unique_slug(db, Brand, "Unbranded"), description="Default brand"))

    if not db.scalar(select(Supplier).where(Supplier.name == "Default Supplier")):
        db.add(Supplier(name="Default Supplier", contact_person="System", email="supplier@example.com", phone="N/A"))

    default_channels = [
        ("Shopify", SalesChannelType.shopify, "https://www.shopify.com", "custom_token", "https://shopify.dev/docs/apps/build/authentication-authorization/access-tokens/generate-app-access-tokens-admin"),
        ("WooCommerce", SalesChannelType.woocommerce, "https://woocommerce.com", "manual_key", "https://woocommerce.com/document/woocommerce-rest-api/"),
        ("Google Shopping", SalesChannelType.google_shopping, "https://merchants.google.com", "oauth", "https://support.google.com/merchants/answer/160173"),
        ("Amazon", SalesChannelType.amazon, "https://sellercentral.amazon.com", "oauth", "https://developer-docs.amazon.com/sp-api/docs/selling-partner-appstore-authorization-workflow"),
        ("eBay", SalesChannelType.ebay, "https://www.ebay.com/sh", "oauth", "https://developer.ebay.com/api-docs/static/oauth-trad-apis.html"),
        ("Shopee", SalesChannelType.shopee, "https://shopee.tw", "oauth", "https://open.shopee.com/"),
        ("Lazada", SalesChannelType.lazada, "https://sellercenter.lazada.com", "oauth", "https://open.lazada.com/"),
        ("TikTok Shop", SalesChannelType.tiktok_shop, "https://seller.tiktokglobalshop.com", "oauth", "https://partners.tiktokshop.com/"),
    ]
    for name, channel_type, base_url, preferred_auth_method, help_url in default_channels:
        if not db.scalar(select(SalesChannel).where(SalesChannel.name == name)):
            db.add(
                SalesChannel(
                    name=name,
                    channel_type=channel_type,
                    base_url=base_url,
                    preferred_auth_method=preferred_auth_method,
                    help_url=help_url,
                    is_active=True,
                )
            )

    db.commit()

    if settings.seed_demo_data and should_seed_demo_data(db):
        seed_demo_data(db)
