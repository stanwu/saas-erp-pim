from __future__ import annotations

from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    AttributeGroup,
    AttributeOption,
    AttributeType,
    Brand,
    Category,
    ListingStatus,
    Product,
    ProductAttribute,
    ProductAttributeValue,
    ProductChannelListing,
    ProductImage,
    ProductStatus,
    ProductVariant,
    SalesChannel,
    Supplier,
    Tag,
    User,
    UserRole,
    VariantAttributeValue,
)
from app.security import hash_password
from app.services import ensure_unique_slug


DEMO_SKUS = [
    "PIM-DEMO-1001",
    "PIM-DEMO-1002",
    "PIM-DEMO-1003",
    "PIM-DEMO-1004",
]

DEMO_VARIANT_SKUS = [
    "PIM-DEMO-1001-BLK",
    "PIM-DEMO-1001-SAND",
    "PIM-DEMO-1002-20L",
    "PIM-DEMO-1002-28L",
]

DEMO_USERNAMES = [
    "merch.ops",
    "marketplace.pm",
    "content.editor",
]


def _write_demo_svg(filename: str, title: str, accent: str, subtitle: str) -> str:
    settings = get_settings()
    upload_dir = Path(settings.upload_dir) / "demo"
    upload_dir.mkdir(parents=True, exist_ok=True)
    filepath = upload_dir / filename
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="900" viewBox="0 0 1200 900">
  <rect width="1200" height="900" fill="#f3f4f6"/>
  <rect x="70" y="70" width="1060" height="760" rx="36" fill="#111827"/>
  <rect x="110" y="110" width="980" height="680" rx="28" fill="{accent}" opacity="0.92"/>
  <circle cx="980" cy="220" r="140" fill="#ffffff" opacity="0.12"/>
  <circle cx="300" cy="650" r="180" fill="#ffffff" opacity="0.08"/>
  <text x="120" y="220" fill="#ffffff" font-size="72" font-family="Helvetica, Arial, sans-serif" font-weight="700">{title}</text>
  <text x="120" y="300" fill="#e5e7eb" font-size="34" font-family="Helvetica, Arial, sans-serif">{subtitle}</text>
  <rect x="120" y="380" width="360" height="300" rx="24" fill="#ffffff" opacity="0.16"/>
  <rect x="520" y="380" width="520" height="58" rx="16" fill="#ffffff" opacity="0.18"/>
  <rect x="520" y="470" width="420" height="58" rx="16" fill="#ffffff" opacity="0.14"/>
  <rect x="520" y="560" width="320" height="58" rx="16" fill="#ffffff" opacity="0.12"/>
</svg>
"""
    filepath.write_text(svg, encoding="utf-8")
    return f"/static/uploads/demo/{filename}"


def _get_or_create_category(
    db: Session,
    name: str,
    description: str,
    *,
    parent: Category | None = None,
    sort_order: int = 0,
) -> Category:
    category = db.scalar(select(Category).where(Category.name == name))
    if not category:
        category = Category(
            name=name,
            description=description,
            slug=ensure_unique_slug(db, Category, name),
            parent=parent,
            sort_order=sort_order,
            is_active=True,
        )
        db.add(category)
        db.flush()
    else:
        category.description = description
        category.parent = parent
        category.sort_order = sort_order
        category.is_active = True
    return category


def _get_or_create_brand(db: Session, name: str, website: str, description: str) -> Brand:
    brand = db.scalar(select(Brand).where(Brand.name == name))
    if not brand:
        brand = Brand(
            name=name,
            slug=ensure_unique_slug(db, Brand, name),
            website=website,
            description=description,
            is_active=True,
        )
        db.add(brand)
        db.flush()
    else:
        brand.website = website
        brand.description = description
        brand.is_active = True
    return brand


def _get_or_create_supplier(db: Session, name: str, contact_person: str, email: str, phone: str) -> Supplier:
    supplier = db.scalar(select(Supplier).where(Supplier.name == name))
    if not supplier:
        supplier = Supplier(
            name=name,
            contact_person=contact_person,
            email=email,
            phone=phone,
            is_active=True,
        )
        db.add(supplier)
        db.flush()
    else:
        supplier.contact_person = contact_person
        supplier.email = email
        supplier.phone = phone
        supplier.is_active = True
    return supplier


def _get_or_create_tag(db: Session, name: str) -> Tag:
    tag = db.scalar(select(Tag).where(Tag.name == name))
    if not tag:
        tag = Tag(name=name, slug=ensure_unique_slug(db, Tag, name))
        db.add(tag)
        db.flush()
    return tag


def _get_or_create_attribute_group(db: Session, name: str, description: str, sort_order: int) -> AttributeGroup:
    group = db.scalar(select(AttributeGroup).where(AttributeGroup.name == name))
    if not group:
        group = AttributeGroup(name=name, description=description, sort_order=sort_order)
        db.add(group)
        db.flush()
    else:
        group.description = description
        group.sort_order = sort_order
    return group


def _get_or_create_attribute(
    db: Session,
    *,
    group: AttributeGroup | None,
    name: str,
    attribute_type: AttributeType,
    unit_label: str | None = None,
    is_required: bool = False,
    options: list[str] | None = None,
) -> ProductAttribute:
    attribute = db.scalar(select(ProductAttribute).where(ProductAttribute.name == name))
    if not attribute:
        attribute = ProductAttribute(
            group=group,
            name=name,
            slug=ensure_unique_slug(db, ProductAttribute, name),
            attribute_type=attribute_type,
            unit_label=unit_label,
            is_required=is_required,
        )
        db.add(attribute)
        db.flush()
    else:
        attribute.group = group
        attribute.attribute_type = attribute_type
        attribute.unit_label = unit_label
        attribute.is_required = is_required
    if options:
        existing = {option.value: option for option in attribute.options}
        for index, value in enumerate(options):
            if value not in existing:
                db.add(AttributeOption(attribute=attribute, value=value, sort_order=index))
            else:
                existing[value].sort_order = index
        db.flush()
    return attribute


def _set_product_attribute_value(db: Session, product: Product, attribute: ProductAttribute, value: str) -> None:
    record = db.scalar(
        select(ProductAttributeValue).where(
            ProductAttributeValue.product_id == product.id,
            ProductAttributeValue.attribute_id == attribute.id,
        )
    )
    if not record:
        record = ProductAttributeValue(product=product, attribute=attribute, value=value)
        db.add(record)
    else:
        record.value = value


def _set_product_images(db: Session, product: Product, image_specs: list[tuple[str, str, int, bool]]) -> None:
    existing = db.scalars(select(ProductImage).where(ProductImage.product_id == product.id, ProductImage.variant_id.is_(None))).all()
    for image in existing:
        db.delete(image)
    db.flush()
    for path, alt_text, sort_order, is_primary in image_specs:
        db.add(
            ProductImage(
                product=product,
                path=path,
                alt_text=alt_text,
                sort_order=sort_order,
                is_primary=is_primary,
            )
        )


def _set_variant_images(db: Session, variant: ProductVariant, image_specs: list[tuple[str, str, int, bool]]) -> None:
    existing = db.scalars(select(ProductImage).where(ProductImage.variant_id == variant.id)).all()
    for image in existing:
        db.delete(image)
    db.flush()
    for path, alt_text, sort_order, is_primary in image_specs:
        db.add(
            ProductImage(
                product_id=variant.product_id,
                variant=variant,
                path=path,
                alt_text=alt_text,
                sort_order=sort_order,
                is_primary=is_primary,
            )
        )


def _set_listing(
    db: Session,
    *,
    product: Product,
    channel: SalesChannel,
    status: ListingStatus,
    title_override: str,
    description_override: str,
    price_override: float,
    external_product_id: str,
    external_url: str,
    sync_enabled: bool = True,
) -> None:
    listing = db.scalar(
        select(ProductChannelListing).where(
            ProductChannelListing.product_id == product.id,
            ProductChannelListing.channel_id == channel.id,
        )
    )
    if not listing:
        listing = ProductChannelListing(product=product, channel=channel)
        db.add(listing)
    listing.listing_status = status
    listing.title_override = title_override
    listing.description_override = description_override
    listing.price_override = price_override
    listing.external_product_id = external_product_id
    listing.external_url = external_url
    listing.sync_enabled = sync_enabled


def _set_variant_options(db: Session, variant: ProductVariant, option_values: list[str]) -> None:
    for value in db.scalars(select(VariantAttributeValue).where(VariantAttributeValue.variant_id == variant.id)).all():
        db.delete(value)
    db.flush()
    for option_value in option_values:
        option = db.scalar(select(AttributeOption).where(AttributeOption.value == option_value))
        if option:
            db.add(VariantAttributeValue(variant=variant, option=option))


def _ensure_demo_users(db: Session) -> None:
    for username, role in [
        ("merch.ops", UserRole.admin),
        ("marketplace.pm", UserRole.admin),
        ("content.editor", UserRole.staff),
    ]:
        user = db.scalar(select(User).where(User.username == username))
        if not user:
            user = User(
                username=username,
                password_hash=hash_password("demo12345"),
                role=role,
                is_active=True,
            )
            db.add(user)
        else:
            user.role = role
            user.is_active = True


def _cleanup_legacy_demo_data(db: Session) -> None:
    for username in DEMO_USERNAMES:
        user = db.scalar(select(User).where(User.username == username))
        if user:
            db.delete(user)

    for sku in DEMO_VARIANT_SKUS:
        variant = db.scalar(select(ProductVariant).where(ProductVariant.sku == sku))
        if variant:
            db.delete(variant)

    for sku in DEMO_SKUS:
        product = db.scalar(select(Product).where(Product.sku == sku))
        if product:
            db.delete(product)

    for name in [
        "New Arrival",
        "Best Seller",
        "Giftable",
        "Eco Choice",
        "Marketplace Ready",
    ]:
        tag = db.scalar(select(Tag).where(Tag.name == name))
        if tag:
            db.delete(tag)

    for name in [
        "Color",
        "Capacity",
        "Material",
        "Battery Life",
        "Water Resistant",
        "Noise Level",
    ]:
        attribute = db.scalar(select(ProductAttribute).where(ProductAttribute.name == name))
        if attribute:
            db.delete(attribute)

    for name in [
        "Appearance",
        "Technical Specs",
        "Hydration",
        "Wearables",
        "Outdoor Gear",
        "Home Comfort",
        "Aurora Labs",
        "TrailForm",
        "Luma Living",
        "PureNest",
        "Pacific Sourcing Co.",
        "Northern Ridge Supply",
        "Everhome Distribution",
    ]:
        brand = db.scalar(select(Brand).where(Brand.name == name))
        if brand:
            db.delete(brand)
        supplier = db.scalar(select(Supplier).where(Supplier.name == name))
        if supplier:
            db.delete(supplier)
        category = db.scalar(select(Category).where(Category.name == name))
        if category:
            db.delete(category)
        group = db.scalar(select(AttributeGroup).where(AttributeGroup.name == name))
        if group:
            db.delete(group)

    db.flush()


def seed_demo_data(db: Session, cleanup_legacy: bool = False) -> None:
    if cleanup_legacy:
        _cleanup_legacy_demo_data(db)

    _ensure_demo_users(db)

    wearables = _get_or_create_category(db, "Wearables", "Smart bottles, connected accessories, and portable essentials.")
    hydration = _get_or_create_category(db, "Hydration", "Drinkware, bottles, and hydration accessories.", parent=wearables, sort_order=10)
    outdoor = _get_or_create_category(db, "Outdoor Gear", "Bags, hiking accessories, and travel products.", sort_order=20)
    home = _get_or_create_category(db, "Home Comfort", "Home appliances and comfort-focused devices.", sort_order=30)

    aurora = _get_or_create_brand(db, "Aurora Labs", "https://aurora.example.com", "Connected lifestyle products with a clean, modern aesthetic.")
    trailform = _get_or_create_brand(db, "TrailForm", "https://trailform.example.com", "Outdoor carry and modular travel essentials.")
    luma = _get_or_create_brand(db, "Luma Living", "https://luma.example.com", "Home design products that balance utility and soft ambience.")
    purenest = _get_or_create_brand(db, "PureNest", "https://purenest.example.com", "Air quality and wellness devices for compact urban homes.")

    pacific = _get_or_create_supplier(db, "Pacific Sourcing Co.", "Helen Wu", "helen@pacific-sourcing.example", "+886-2-2718-3200")
    ridge = _get_or_create_supplier(db, "Northern Ridge Supply", "Daniel Cheng", "daniel@northern-ridge.example", "+886-3-312-4488")
    everhome = _get_or_create_supplier(db, "Everhome Distribution", "Iris Kao", "iris@everhome.example", "+886-4-2298-7781")

    tags = {
        "new": _get_or_create_tag(db, "New Arrival"),
        "best": _get_or_create_tag(db, "Best Seller"),
        "gift": _get_or_create_tag(db, "Giftable"),
        "eco": _get_or_create_tag(db, "Eco Choice"),
        "market": _get_or_create_tag(db, "Marketplace Ready"),
    }

    appearance = _get_or_create_attribute_group(db, "Appearance", "Visual options and merchandising-facing specs.", 10)
    technical = _get_or_create_attribute_group(db, "Technical Specs", "Key technical fields surfaced across PDPs and channels.", 20)

    color = _get_or_create_attribute(
        db,
        group=appearance,
        name="Color",
        attribute_type=AttributeType.select,
        is_required=True,
        options=["Black", "Sand", "Forest Green", "Ivory"],
    )
    capacity = _get_or_create_attribute(
        db,
        group=technical,
        name="Capacity",
        attribute_type=AttributeType.select,
        options=["18 oz", "20 L", "28 L", "45 L"],
    )
    material = _get_or_create_attribute(
        db,
        group=technical,
        name="Material",
        attribute_type=AttributeType.text,
    )
    battery_life = _get_or_create_attribute(
        db,
        group=technical,
        name="Battery Life",
        attribute_type=AttributeType.number,
        unit_label="hours",
    )
    water_resistant = _get_or_create_attribute(
        db,
        group=technical,
        name="Water Resistant",
        attribute_type=AttributeType.boolean,
    )
    noise_level = _get_or_create_attribute(
        db,
        group=technical,
        name="Noise Level",
        attribute_type=AttributeType.number,
        unit_label="dB",
    )

    db.flush()

    product_specs = [
        {
            "sku": "PIM-DEMO-1001",
            "name": "Aurora Smart Bottle",
            "short_description": "UV self-cleaning insulated bottle with hydration reminders.",
            "description": "Aurora Smart Bottle combines vacuum insulation, hydration reminders, and a clean editorial presentation for lifestyle marketplaces.",
            "seo_title": "Aurora Smart Bottle | UV-C Self-Cleaning Water Bottle",
            "seo_description": "Premium insulated smart bottle with UV-C cleaning, hydration reminders, and app-ready marketplace content.",
            "seo_keywords": "smart bottle, insulated bottle, hydration reminder, UV bottle",
            "barcode": "4710001001001",
            "category": hydration,
            "brand": aurora,
            "supplier": pacific,
            "unit": "pcs",
            "cost_price": 19.50,
            "sale_price": 49.00,
            "reorder_point": 18,
            "weight": 0.62,
            "length": 8.4,
            "width": 8.4,
            "height": 28.5,
            "status": ProductStatus.active,
            "is_active": True,
            "tags": [tags["new"], tags["gift"], tags["market"]],
            "attribute_values": {
                color: "Black",
                capacity: "18 oz",
                material: "Food-grade stainless steel",
                battery_life: "48",
                water_resistant: "true",
            },
            "images": [
                (_write_demo_svg("aurora-bottle-main.svg", "Aurora Smart Bottle", "#0f766e", "UV self-cleaning insulated bottle"), "Aurora Smart Bottle hero image", 0, True),
                (_write_demo_svg("aurora-bottle-lifestyle.svg", "Aurora Bottle Lifestyle", "#155e75", "Packaging and premium retail presentation"), "Aurora Smart Bottle packaging shot", 1, False),
            ],
        },
        {
            "sku": "PIM-DEMO-1002",
            "name": "TrailForm Modular Backpack",
            "short_description": "Weather-ready backpack with modular storage and padded laptop sleeve.",
            "description": "TrailForm Modular Backpack is built for commuting and weekend travel, with rich content fields for channels that need merchandising copy and visual variants.",
            "seo_title": "TrailForm Modular Backpack | 20L and 28L Everyday Carry",
            "seo_description": "Versatile modular backpack with laptop compartment, weather-ready fabric, and marketplace-friendly variants.",
            "seo_keywords": "modular backpack, everyday carry, travel backpack, laptop bag",
            "barcode": "4710001001002",
            "category": outdoor,
            "brand": trailform,
            "supplier": ridge,
            "unit": "pcs",
            "cost_price": 33.00,
            "sale_price": 89.00,
            "reorder_point": 12,
            "weight": 1.10,
            "length": 31.0,
            "width": 18.0,
            "height": 47.0,
            "status": ProductStatus.active,
            "is_active": True,
            "tags": [tags["best"], tags["eco"], tags["market"]],
            "attribute_values": {
                color: "Forest Green",
                capacity: "20 L",
                material: "Recycled ripstop polyester",
                water_resistant: "true",
            },
            "images": [
                (_write_demo_svg("trailform-backpack-main.svg", "TrailForm Backpack", "#365314", "Modular backpack for commute and travel"), "TrailForm backpack front view", 0, True),
                (_write_demo_svg("trailform-backpack-inside.svg", "TrailForm Interior", "#4d7c0f", "Interior organizer and laptop sleeve"), "TrailForm interior organizer", 1, False),
            ],
        },
        {
            "sku": "PIM-DEMO-1003",
            "name": "Luma Desk Lamp",
            "short_description": "Dimmable task lamp with warm-to-cool lighting presets.",
            "description": "A compact desk lamp designed for modern home offices, with structured SEO and specification fields that map cleanly into PIM workflows.",
            "seo_title": "Luma Desk Lamp | Adjustable LED Task Lighting",
            "seo_description": "Modern LED desk lamp with adjustable brightness, color temperature presets, and compact footprint.",
            "seo_keywords": "desk lamp, task lighting, led lamp, home office lighting",
            "barcode": "4710001001003",
            "category": home,
            "brand": luma,
            "supplier": everhome,
            "unit": "pcs",
            "cost_price": 22.40,
            "sale_price": 59.00,
            "reorder_point": 10,
            "weight": 1.80,
            "length": 16.0,
            "width": 16.0,
            "height": 42.0,
            "status": ProductStatus.active,
            "is_active": True,
            "tags": [tags["new"], tags["gift"]],
            "attribute_values": {
                color: "Ivory",
                material: "Powder-coated aluminum",
                battery_life: "0",
            },
            "images": [
                (_write_demo_svg("luma-lamp-main.svg", "Luma Desk Lamp", "#b45309", "Warm-to-cool lighting presets"), "Luma desk lamp angled view", 0, True),
            ],
        },
        {
            "sku": "PIM-DEMO-1004",
            "name": "PureNest Air Purifier",
            "short_description": "Compact HEPA purifier for bedrooms and small living rooms.",
            "description": "PureNest Air Purifier is a compact air care device with quiet mode performance and channel-ready product data for retailer syndication.",
            "seo_title": "PureNest Air Purifier | Compact HEPA Air Care",
            "seo_description": "Quiet HEPA purifier with compact industrial design and clean attribute mapping for ecommerce listings.",
            "seo_keywords": "air purifier, hepa purifier, bedroom purifier, quiet purifier",
            "barcode": "4710001001004",
            "category": home,
            "brand": purenest,
            "supplier": everhome,
            "unit": "pcs",
            "cost_price": 48.00,
            "sale_price": 129.00,
            "reorder_point": 8,
            "weight": 3.90,
            "length": 22.0,
            "width": 22.0,
            "height": 46.0,
            "status": ProductStatus.active,
            "is_active": True,
            "tags": [tags["best"], tags["market"]],
            "attribute_values": {
                material: "ABS housing with matte finish",
                noise_level: "28",
                water_resistant: "false",
            },
            "images": [
                (_write_demo_svg("purenest-main.svg", "PureNest Air Purifier", "#1d4ed8", "Compact HEPA air care for small spaces"), "PureNest air purifier product shot", 0, True),
            ],
        },
    ]

    products_by_sku: dict[str, Product] = {}
    for spec in product_specs:
        product = db.scalar(select(Product).where(Product.sku == spec["sku"]))
        if not product:
            product = Product(sku=spec["sku"], name=spec["name"])
            db.add(product)
            db.flush()
        product.name = spec["name"]
        product.short_description = spec["short_description"]
        product.description = spec["description"]
        product.seo_title = spec["seo_title"]
        product.seo_description = spec["seo_description"]
        product.seo_keywords = spec["seo_keywords"]
        product.barcode = spec["barcode"]
        product.category = spec["category"]
        product.brand = spec["brand"]
        product.supplier = spec["supplier"]
        product.unit = spec["unit"]
        product.cost_price = spec["cost_price"]
        product.sale_price = spec["sale_price"]
        product.reorder_point = spec["reorder_point"]
        product.weight = spec["weight"]
        product.length = spec["length"]
        product.width = spec["width"]
        product.height = spec["height"]
        product.status = spec["status"]
        product.is_active = spec["is_active"]
        product.tags = spec["tags"]
        for attribute, value in spec["attribute_values"].items():
            _set_product_attribute_value(db, product, attribute, value)
        _set_product_images(db, product, spec["images"])
        products_by_sku[product.sku] = product

    db.flush()

    variant_specs = [
        ("PIM-DEMO-1001", "PIM-DEMO-1001-BLK", "Aurora Smart Bottle / Black", "4710001001101", 0.0, ["Black"]),
        ("PIM-DEMO-1001", "PIM-DEMO-1001-SAND", "Aurora Smart Bottle / Sand", "4710001001102", 2.0, ["Sand"]),
        ("PIM-DEMO-1002", "PIM-DEMO-1002-20L", "TrailForm Modular Backpack / 20L", "4710001001201", 0.0, ["20 L"]),
        ("PIM-DEMO-1002", "PIM-DEMO-1002-28L", "TrailForm Modular Backpack / 28L", "4710001001202", 12.0, ["28 L"]),
    ]
    variants_by_sku: dict[str, ProductVariant] = {}
    for product_sku, sku, name, barcode, adjustment, options in variant_specs:
        product = products_by_sku[product_sku]
        variant = db.scalar(select(ProductVariant).where(ProductVariant.sku == sku))
        if not variant:
            variant = ProductVariant(product=product, sku=sku, name=name)
            db.add(variant)
            db.flush()
        variant.name = name
        variant.barcode = barcode
        variant.price_adjustment = adjustment
        variant.is_active = True
        _set_variant_options(db, variant, options)
        variants_by_sku[sku] = variant

    _set_variant_images(
        db,
        variants_by_sku["PIM-DEMO-1001-SAND"],
        [(_write_demo_svg("aurora-bottle-sand.svg", "Aurora Bottle Sand", "#a16207", "Variant image for sand finish"), "Aurora Smart Bottle sand finish", 0, True)],
    )
    _set_variant_images(
        db,
        variants_by_sku["PIM-DEMO-1002-28L"],
        [(_write_demo_svg("trailform-28l.svg", "TrailForm 28L", "#3f6212", "Expanded 28L carry configuration"), "TrailForm 28L variant image", 0, True)],
    )

    channel_configs = {
        "Shopify": {
            "account_label": "Aurora Direct Store",
            "store_url": "https://aurora-demo.myshopify.com",
            "requested_scopes": "read_products,write_products,read_inventory",
            "api_key": "shp_demo_key",
            "api_secret": "shp_demo_secret",
            "access_token": "shpat_demo_token",
            "setup_status": "ready",
        },
        "WooCommerce": {
            "account_label": "TrailForm EU Store",
            "store_url": "https://shop.trailform.example.com",
            "requested_scopes": "read_write",
            "api_key": "ck_demo_key",
            "api_secret": "cs_demo_secret",
            "setup_status": "credentials_saved",
        },
        "TikTok Shop": {
            "account_label": "PureNest TW TikTok Shop",
            "store_url": "https://seller.tiktokglobalshop.com",
            "requested_scopes": "product.basic,product.write",
            "client_id": "tt_demo_client",
            "client_secret": "tt_demo_secret",
            "last_oauth_code": "demo-oauth-code-1234",
            "setup_status": "oauth_code_received",
        },
    }
    for channel_name, config in channel_configs.items():
        channel = db.scalar(select(SalesChannel).where(SalesChannel.name == channel_name))
        if not channel:
            continue
        channel.account_label = config.get("account_label")
        channel.store_url = config.get("store_url")
        channel.requested_scopes = config.get("requested_scopes")
        channel.api_key = config.get("api_key")
        channel.api_secret = config.get("api_secret")
        channel.access_token = config.get("access_token")
        channel.client_id = config.get("client_id")
        channel.client_secret = config.get("client_secret")
        channel.last_oauth_code = config.get("last_oauth_code")
        channel.setup_status = config["setup_status"]

    db.flush()

    shopify = db.scalar(select(SalesChannel).where(SalesChannel.name == "Shopify"))
    woocommerce = db.scalar(select(SalesChannel).where(SalesChannel.name == "WooCommerce"))
    tiktok = db.scalar(select(SalesChannel).where(SalesChannel.name == "TikTok Shop"))

    if shopify:
        _set_listing(
            db,
            product=products_by_sku["PIM-DEMO-1001"],
            channel=shopify,
            status=ListingStatus.published,
            title_override="Aurora Smart Bottle | Shopify Hero Listing",
            description_override="Editorial Shopify-ready copy with UV self-cleaning callouts and hydration reminders.",
            price_override=49.00,
            external_product_id="gid://shopify/Product/1001",
            external_url="https://aurora-demo.myshopify.com/products/aurora-smart-bottle",
        )
    if woocommerce:
        _set_listing(
            db,
            product=products_by_sku["PIM-DEMO-1002"],
            channel=woocommerce,
            status=ListingStatus.draft,
            title_override="TrailForm Modular Backpack 20L / 28L",
            description_override="WooCommerce draft listing with configurable capacity variants and weather-ready details.",
            price_override=89.00,
            external_product_id="wc-1002",
            external_url="https://shop.trailform.example.com/product/trailform-modular-backpack/",
        )
    if tiktok:
        _set_listing(
            db,
            product=products_by_sku["PIM-DEMO-1004"],
            channel=tiktok,
            status=ListingStatus.paused,
            title_override="PureNest Air Purifier for Bedroom and Desk",
            description_override="Short-form marketplace copy tailored for TikTok Shop listing constraints.",
            price_override=119.00,
            external_product_id="tt-1004",
            external_url="https://seller.tiktokglobalshop.com/product/tt-1004",
            sync_enabled=False,
        )

    db.commit()


def should_seed_demo_data(db: Session) -> bool:
    return (db.scalar(select(func.count(Product.id))) or 0) == 0
