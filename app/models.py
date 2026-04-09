import enum
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey, Integer,
    Numeric, String, Table, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    staff = "staff"


class ProductStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class SalesChannelType(str, enum.Enum):
    shopify = "shopify"
    woocommerce = "woocommerce"
    google_shopping = "google_shopping"
    amazon = "amazon"
    ebay = "ebay"
    shopee = "shopee"
    lazada = "lazada"
    tiktok_shop = "tiktok_shop"


class ListingStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    paused = "paused"
    error = "error"


PRODUCT_STATUS_BADGE = {
    ProductStatus.draft: "secondary",
    ProductStatus.active: "success",
    ProductStatus.archived: "dark",
}


product_tags = Table(
    "product_tags",
    Base.metadata,
    Column("product_id", ForeignKey("products.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.staff, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    slug: Mapped[str] = mapped_column(String(96), unique=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    products: Mapped[list["Product"]] = relationship(back_populates="category")
    children: Mapped[list["Category"]] = relationship(back_populates="parent", cascade="all, delete-orphan")
    parent: Mapped["Category | None"] = relationship(back_populates="children", remote_side=[id])


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    contact_person: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email: Mapped[str | None] = mapped_column(String(128), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    products: Mapped[list["Product"]] = relationship(back_populates="supplier")


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    website: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    products: Mapped[list["Product"]] = relationship(back_populates="brand")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(96), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    products: Mapped[list["Product"]] = relationship(secondary=product_tags, back_populates="tags")


class SalesChannel(Base):
    __tablename__ = "sales_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    channel_type: Mapped[SalesChannelType] = mapped_column(Enum(SalesChannelType), nullable=False)
    preferred_auth_method: Mapped[str] = mapped_column(String(32), default="manual_key", nullable=False)
    setup_status: Mapped[str] = mapped_column(String(32), default="not_connected", nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    help_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    store_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requested_scopes: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    api_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    oauth_redirect_uri: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_oauth_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_connection_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    listings: Mapped[list["ProductChannelListing"]] = relationship(back_populates="channel", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    short_description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    seo_title: Mapped[str | None] = mapped_column(String(128), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    seo_keywords: Mapped[str | None] = mapped_column(String(255), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    brand_id: Mapped[int | None] = mapped_column(ForeignKey("brands.id"), nullable=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    unit: Mapped[str] = mapped_column(String(16), default="pcs", nullable=False)
    cost_price: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    sale_price: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    reorder_point: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    weight: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    length: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    width: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    height: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    status: Mapped[ProductStatus] = mapped_column(Enum(ProductStatus), default=ProductStatus.draft, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    category: Mapped["Category | None"] = relationship(back_populates="products")
    brand: Mapped["Brand | None"] = relationship(back_populates="products")
    supplier: Mapped["Supplier | None"] = relationship(back_populates="products")
    tags: Mapped[list["Tag"]] = relationship(secondary=product_tags, back_populates="products")
    images: Mapped[list["ProductImage"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    variants: Mapped[list["ProductVariant"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    attribute_values: Mapped[list["ProductAttributeValue"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    channel_listings: Mapped[list["ProductChannelListing"]] = relationship(back_populates="product", cascade="all, delete-orphan")


class AttributeGroup(Base):
    __tablename__ = "attribute_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    attributes: Mapped[list["ProductAttribute"]] = relationship(back_populates="group", cascade="all, delete-orphan")


class AttributeType(str, enum.Enum):
    text = "text"
    number = "number"
    boolean = "boolean"
    select = "select"
    multiselect = "multiselect"


class ProductAttribute(Base):
    __tablename__ = "product_attributes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("attribute_groups.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    attribute_type: Mapped[AttributeType] = mapped_column(Enum(AttributeType), default=AttributeType.text, nullable=False)
    unit_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    group: Mapped["AttributeGroup | None"] = relationship(back_populates="attributes")
    options: Mapped[list["AttributeOption"]] = relationship(back_populates="attribute", cascade="all, delete-orphan")
    product_values: Mapped[list["ProductAttributeValue"]] = relationship(back_populates="attribute", cascade="all, delete-orphan")


class AttributeOption(Base):
    __tablename__ = "attribute_options"
    __table_args__ = (UniqueConstraint("attribute_id", "value"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attribute_id: Mapped[int] = mapped_column(ForeignKey("product_attributes.id"), nullable=False)
    value: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    attribute: Mapped["ProductAttribute"] = relationship(back_populates="options")


class ProductAttributeValue(Base):
    __tablename__ = "product_attribute_values"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    attribute_id: Mapped[int] = mapped_column(ForeignKey("product_attributes.id"), nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)

    product: Mapped["Product"] = relationship(back_populates="attribute_values")
    attribute: Mapped["ProductAttribute"] = relationship(back_populates="product_values")


class ProductVariant(Base):
    __tablename__ = "product_variants"
    __table_args__ = (UniqueConstraint("product_id", "sku"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    price_adjustment: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    product: Mapped["Product"] = relationship(back_populates="variants")
    option_values: Mapped[list["VariantAttributeValue"]] = relationship(back_populates="variant", cascade="all, delete-orphan")
    images: Mapped[list["ProductImage"]] = relationship(back_populates="variant")


class ProductChannelListing(Base):
    __tablename__ = "product_channel_listings"
    __table_args__ = (UniqueConstraint("product_id", "channel_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    channel_id: Mapped[int] = mapped_column(ForeignKey("sales_channels.id"), nullable=False)
    external_product_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    external_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    listing_status: Mapped[ListingStatus] = mapped_column(Enum(ListingStatus), default=ListingStatus.draft, nullable=False)
    title_override: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description_override: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_override: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    sync_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    product: Mapped["Product"] = relationship(back_populates="channel_listings")
    channel: Mapped["SalesChannel"] = relationship(back_populates="listings")


class VariantAttributeValue(Base):
    __tablename__ = "variant_attribute_values"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("product_variants.id"), nullable=False)
    option_id: Mapped[int] = mapped_column(ForeignKey("attribute_options.id"), nullable=False)

    variant: Mapped["ProductVariant"] = relationship(back_populates="option_values")
    option: Mapped["AttributeOption"] = relationship()


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("product_variants.id"), nullable=True)
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    product: Mapped["Product"] = relationship(back_populates="images")
    variant: Mapped["ProductVariant | None"] = relationship(back_populates="images")
