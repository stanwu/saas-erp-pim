import math
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.dependencies import flash, get_current_user, require_admin, tmpl_ctx, validate_csrf
from app.models import ListingStatus, Product, ProductChannelListing, SalesChannel, SalesChannelType, User

router = APIRouter(prefix="/channels", tags=["channels"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


CHANNEL_SETUP_GUIDES = {
    SalesChannelType.shopify: {
        "title": "Shopify custom app token",
        "summary": "Recommended for non-technical staff. Ask the store owner to create or open the store app settings, then paste the shop URL and Admin API access token.",
        "steps": [
            "Open your Shopify admin and go to the app setup page for your store.",
            "Create or open the app that will manage products for this store.",
            "Enable product-related permissions, then copy the Admin API access token.",
            "Paste the shop URL and token into the form below and save.",
        ],
        "fields": ["account_label", "store_url", "access_token", "requested_scopes"],
        "store_url_label": "Shop URL",
        "store_url_example": "https://your-shop.myshopify.com",
        "api_key_label": "Admin API access token",
        "api_key_help": "Paste the Admin API access token from your Shopify custom app.",
    },
    SalesChannelType.woocommerce: {
        "title": "WooCommerce REST API keys",
        "summary": "Usually the easiest setup path. The store admin creates a Consumer Key and Consumer Secret for this site.",
        "steps": [
            "Open WooCommerce > Settings > Advanced > REST API.",
            "Create a key with Read/Write permission for the store account.",
            "Copy the Consumer Key and Consumer Secret shown by WooCommerce.",
            "Paste the shop URL and keys below and save.",
        ],
        "fields": ["account_label", "store_url", "api_key", "api_secret"],
        "store_url_label": "Store URL",
        "store_url_example": "https://shop.example.com",
        "api_key_label": "Consumer Key",
        "api_secret_label": "Consumer Secret",
        "api_key_help": "Create these from WooCommerce > Settings > Advanced > REST API.",
    },
    SalesChannelType.amazon: {
        "title": "Amazon SP-API OAuth setup",
        "summary": "Preferred for marketplace integrations. Your operator can prepare the app credentials and callback URL here before the authorization step.",
        "steps": [
            "Register or open the application in Amazon Selling Partner developer settings.",
            "Copy the Client ID and Client Secret from Amazon.",
            "Paste the callback URL shown on this page into Amazon's redirect URL settings.",
            "After Amazon redirects back, this screen will capture the returned code for your team.",
        ],
        "fields": ["account_label", "client_id", "client_secret", "oauth_redirect_uri", "requested_scopes"],
        "store_url_label": "Seller Central URL",
        "store_url_example": "https://sellercentral.amazon.com",
        "client_id_label": "LWA Client ID",
        "client_secret_label": "LWA Client Secret",
    },
    SalesChannelType.ebay: {
        "title": "eBay OAuth app setup",
        "summary": "Recommended when you want one login-based connection rather than handling tokens by hand.",
        "steps": [
            "Open your eBay Developer account and create or open the application.",
            "Copy the App ID / Client ID and Client Secret.",
            "Register the callback URL from this page in eBay developer settings.",
            "After the user authorizes the app, return here so the code can be captured.",
        ],
        "fields": ["account_label", "client_id", "client_secret", "oauth_redirect_uri", "requested_scopes"],
        "store_url_label": "Seller Hub URL",
        "store_url_example": "https://www.ebay.com/sh/ovw",
        "client_id_label": "App ID / Client ID",
        "client_secret_label": "Cert ID / Client Secret",
    },
    SalesChannelType.google_shopping: {
        "title": "Google Merchant Center OAuth setup",
        "summary": "Prepare the Merchant Center account and OAuth app details so your team can later exchange the returned authorization code.",
        "steps": [
            "Open your Google Merchant Center and Google Cloud project settings.",
            "Create or open the OAuth application used for product feed access.",
            "Paste the callback URL from this page into your Google OAuth redirect settings.",
            "Save the client credentials here before authorizing.",
        ],
        "fields": ["account_label", "client_id", "client_secret", "oauth_redirect_uri", "requested_scopes"],
        "store_url_label": "Merchant Center URL",
        "store_url_example": "https://merchants.google.com",
        "client_id_label": "OAuth Client ID",
        "client_secret_label": "OAuth Client Secret",
    },
    SalesChannelType.shopee: {
        "title": "Shopee Open Platform OAuth setup",
        "summary": "Shopee usually uses app-based authorization. Keep the shop name and callback settings here so the operator can follow the platform guide.",
        "steps": [
            "Open the Shopee Open Platform console.",
            "Create or open the app for this shop.",
            "Register the callback URL shown on this page.",
            "Save the app credentials and proceed with the authorization step.",
        ],
        "fields": ["account_label", "store_url", "client_id", "client_secret", "oauth_redirect_uri"],
        "store_url_label": "Shop URL",
        "store_url_example": "https://shopee.tw/shop/12345678",
        "client_id_label": "Partner ID / Client ID",
        "client_secret_label": "Partner Key / Client Secret",
    },
    SalesChannelType.lazada: {
        "title": "Lazada Open Platform OAuth setup",
        "summary": "Lazada typically uses app authorization. Save the account URL, app key, and callback URL here so the operator can proceed step by step.",
        "steps": [
            "Open Lazada Open Platform and create or open the app.",
            "Register the callback URL shown on this page.",
            "Save the app credentials below.",
            "After Lazada redirects back, this page will capture the authorization code.",
        ],
        "fields": ["account_label", "store_url", "client_id", "client_secret", "oauth_redirect_uri"],
        "store_url_label": "Seller Center URL",
        "store_url_example": "https://sellercenter.lazada.com",
        "client_id_label": "App Key / Client ID",
        "client_secret_label": "App Secret / Client Secret",
    },
    SalesChannelType.tiktok_shop: {
        "title": "TikTok Shop app authorization",
        "summary": "TikTok Shop usually connects through app authorization. Save the shop URL and app credentials here first.",
        "steps": [
            "Open TikTok Shop Partner Center.",
            "Create or open the application for this shop.",
            "Add the callback URL from this page into the app settings.",
            "Save the app credentials and continue with authorization.",
        ],
        "fields": ["account_label", "store_url", "client_id", "client_secret", "oauth_redirect_uri"],
        "store_url_label": "Seller Center URL",
        "store_url_example": "https://seller.tiktokglobalshop.com",
        "client_id_label": "App Key / Client ID",
        "client_secret_label": "App Secret / Client Secret",
    },
}


def _default_channel_guide(channel: SalesChannel, request: Request) -> dict:
    guide = CHANNEL_SETUP_GUIDES.get(channel.channel_type)
    callback_url = f"{request.base_url}channels/{channel.id}/oauth/callback".rstrip("/")
    if guide:
        return {
            **guide,
            "callback_url": channel.oauth_redirect_uri or callback_url,
        }
    return {
        "title": f"{channel.name} connection",
        "summary": "Use the fields below to store the store URL, app credentials, and any token information your marketplace gives you.",
        "steps": [
            "Open the marketplace's developer or seller portal.",
            "Create an app or API credential for product publishing.",
            "Paste the credentials below and save.",
        ],
        "fields": ["account_label", "store_url", "client_id", "client_secret", "api_key", "api_secret", "access_token", "requested_scopes"],
        "callback_url": channel.oauth_redirect_uri or callback_url,
        "store_url_label": "Store URL",
        "store_url_example": "https://example.com",
        "api_key_label": "API Key",
        "api_secret_label": "API Secret",
        "client_id_label": "Client ID",
        "client_secret_label": "Client Secret",
    }


def _status_badge(status: str) -> str:
    return {
        "ready": "success",
        "oauth_code_received": "info",
        "credentials_saved": "primary",
        "needs_attention": "danger",
        "not_connected": "secondary",
    }.get(status, "secondary")


@router.get("")
def list_channels(
    request: Request,
    page: int = 1,
    q: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    per_page = settings.page_size
    stmt = select(SalesChannel)
    if q:
        stmt = stmt.where(SalesChannel.name.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    total_pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, total_pages))
    channels = db.scalars(
        stmt.order_by(SalesChannel.name).offset((page - 1) * per_page).limit(per_page)
    ).all()
    return templates.TemplateResponse(
        request,
        "channels/list.html",
        tmpl_ctx(
            request,
            current_user,
            channels=channels,
            q=q,
            page=page,
            total_pages=total_pages,
            total=total,
            status_badge=_status_badge,
        ),
    )


@router.get("/{channel_id}/connect")
def connect_channel_page(
    channel_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    channel = db.get(SalesChannel, channel_id)
    if not channel:
        return RedirectResponse(url="/channels", status_code=303)
    guide = _default_channel_guide(channel, request)
    return templates.TemplateResponse(
        request,
        "channels/connect.html",
        tmpl_ctx(request, current_user, channel=channel, guide=guide, status_badge=_status_badge, error=None),
    )


@router.post("/{channel_id}/connect")
async def connect_channel(
    channel_id: int,
    request: Request,
    account_label: str = Form(""),
    store_url: str = Form(""),
    requested_scopes: str = Form(""),
    api_key: str = Form(""),
    api_secret: str = Form(""),
    access_token: str = Form(""),
    refresh_token: str = Form(""),
    client_id: str = Form(""),
    client_secret: str = Form(""),
    oauth_redirect_uri: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    _ = current_user
    channel = db.get(SalesChannel, channel_id)
    if not channel:
        return RedirectResponse(url="/channels", status_code=303)

    channel.account_label = account_label.strip() or None
    channel.store_url = store_url.strip() or None
    channel.requested_scopes = requested_scopes.strip() or None
    channel.api_key = api_key.strip() or None
    channel.api_secret = api_secret.strip() or None
    channel.access_token = access_token.strip() or None
    channel.refresh_token = refresh_token.strip() or None
    channel.client_id = client_id.strip() or None
    channel.client_secret = client_secret.strip() or None
    channel.oauth_redirect_uri = oauth_redirect_uri.strip() or f"{request.base_url}channels/{channel.id}/oauth/callback".rstrip("/")

    has_live_token = bool(channel.access_token or channel.refresh_token)
    has_credentials = bool(channel.api_key or channel.client_id or channel.client_secret)
    channel.setup_status = "ready" if has_live_token else "credentials_saved" if has_credentials else "not_connected"
    if channel.setup_status == "ready":
        channel.connected_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    flash(request, f"Channel '{channel.name}' connection details saved.", "success")
    return RedirectResponse(url=f"/channels/{channel.id}/connect", status_code=303)


@router.get("/{channel_id}/oauth/callback")
def channel_oauth_callback(
    channel_id: int,
    request: Request,
    code: str = "",
    state: str = "",
    spapi_oauth_code: str = "",
    selling_partner_id: str = "",
    db: Session = Depends(get_db),
):
    channel = db.get(SalesChannel, channel_id)
    if not channel:
        return RedirectResponse(url="/channels", status_code=303)
    returned_code = spapi_oauth_code.strip() or code.strip()
    if returned_code:
        channel.last_oauth_code = returned_code
        channel.account_label = channel.account_label or selling_partner_id.strip() or None
        channel.setup_status = "oauth_code_received"
        channel.last_connection_error = None
        db.commit()
        flash(request, f"OAuth code received for '{channel.name}'.", "success")
    else:
        channel.setup_status = "needs_attention"
        channel.last_connection_error = "OAuth callback did not include an authorization code."
        db.commit()
        flash(request, f"OAuth callback for '{channel.name}' needs review.", "warning")
    return RedirectResponse(url=f"/channels/{channel.id}/connect", status_code=303)


@router.get("/{product_id}/listings")
def product_listings_page(
    product_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    product = db.scalar(
        select(Product)
        .options(joinedload(Product.channel_listings).joinedload(ProductChannelListing.channel))
        .where(Product.id == product_id)
    )
    if not product:
        return RedirectResponse(url="/products", status_code=303)
    channels = db.scalars(select(SalesChannel).where(SalesChannel.is_active == True).order_by(SalesChannel.name)).all()  # noqa: E712
    return templates.TemplateResponse(
        request,
        "channels/listings.html",
        tmpl_ctx(
            request,
            current_user,
            product=product,
            channels=[channel for channel in channels if channel.setup_status in {"credentials_saved", "oauth_code_received", "ready"}],
            statuses=ListingStatus,
            error=None,
        ),
    )


@router.post("/{product_id}/listings/new")
async def create_product_listing(
    product_id: int,
    request: Request,
    channel_id: int = Form(...),
    external_product_id: str = Form(""),
    external_url: str = Form(""),
    listing_status: str = Form(ListingStatus.draft.value),
    title_override: str = Form(""),
    description_override: str = Form(""),
    price_override: str = Form(""),
    sync_enabled: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    _ = current_user
    listing = ProductChannelListing(
        product_id=product_id,
        channel_id=channel_id,
        external_product_id=external_product_id.strip() or None,
        external_url=external_url.strip() or None,
        listing_status=ListingStatus(listing_status),
        title_override=title_override.strip() or None,
        description_override=description_override.strip() or None,
        price_override=float(price_override) if price_override.strip() else None,
        sync_enabled=bool(sync_enabled),
    )
    db.add(listing)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        flash(request, "Listing already exists for this channel.", "warning")
    else:
        flash(request, "Channel listing created.", "success")
    return RedirectResponse(url=f"/channels/{product_id}/listings", status_code=303)


@router.post("/listings/{listing_id}/edit")
async def edit_product_listing(
    listing_id: int,
    request: Request,
    external_product_id: str = Form(""),
    external_url: str = Form(""),
    listing_status: str = Form(ListingStatus.draft.value),
    title_override: str = Form(""),
    description_override: str = Form(""),
    price_override: str = Form(""),
    sync_enabled: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
    _ = current_user
    listing = db.get(ProductChannelListing, listing_id)
    if not listing:
        return RedirectResponse(url="/products", status_code=303)
    listing.external_product_id = external_product_id.strip() or None
    listing.external_url = external_url.strip() or None
    listing.listing_status = ListingStatus(listing_status)
    listing.title_override = title_override.strip() or None
    listing.description_override = description_override.strip() or None
    listing.price_override = float(price_override) if price_override.strip() else None
    listing.sync_enabled = bool(sync_enabled)
    db.commit()
    flash(request, "Channel listing updated.", "success")
    return RedirectResponse(url=f"/channels/{listing.product_id}/listings", status_code=303)
