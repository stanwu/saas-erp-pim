import re
from pathlib import Path
from uuid import uuid4
from itertools import product

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AttributeOption, Product, ProductAttribute, ProductAttributeValue, ProductImage, ProductVariant, Tag, VariantAttributeValue


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "item"


def ensure_unique_slug(db: Session, model, value: str, current_id: int | None = None) -> str:
    base_slug = slugify(value)
    slug = base_slug
    index = 2
    while True:
        existing = db.scalar(select(model).where(model.slug == slug))
        if not existing or existing.id == current_id:
            return slug
        slug = f"{base_slug}-{index}"
        index += 1


def parse_tag_names(raw_tags: str) -> list[str]:
    tags = []
    for value in raw_tags.split(","):
        name = value.strip()
        if name and name not in tags:
            tags.append(name)
    return tags


def sync_product_tags(db: Session, product: Product, raw_tags: str) -> None:
    tags = []
    for name in parse_tag_names(raw_tags):
        slug = ensure_unique_slug(db, Tag, name)
        tag = db.scalar(select(Tag).where(Tag.name == name))
        if not tag:
            tag = Tag(name=name, slug=slug)
            db.add(tag)
            db.flush()
        tags.append(tag)
    product.tags = tags


def build_product_attribute_value_map(product: Product | None) -> dict[int, str]:
    if not product:
        return {}
    return {
        value.attribute_id: value.value or ""
        for value in product.attribute_values
    }


def sync_product_attribute_values(
    db: Session,
    product: Product,
    attributes: list[ProductAttribute],
    form_data,
) -> None:
    existing = {value.attribute_id: value for value in product.attribute_values}
    keep_ids = set()
    for attribute in attributes:
        field_name = f"attribute_{attribute.id}"
        raw_value = form_data.get(field_name, "")
        if isinstance(raw_value, list):
            clean_value = ",".join(item.strip() for item in raw_value if item.strip())
        else:
            clean_value = str(raw_value).strip()

        if attribute.attribute_type == attribute.attribute_type.boolean:
            clean_value = "true" if form_data.get(field_name) else ""

        if clean_value:
            if attribute.id in existing:
                existing[attribute.id].value = clean_value
            else:
                db.add(ProductAttributeValue(product=product, attribute_id=attribute.id, value=clean_value))
            keep_ids.add(attribute.id)

    for attribute_id, value in existing.items():
        if attribute_id not in keep_ids:
            db.delete(value)


def generate_variant_sku(base_sku: str, options: list[str]) -> str:
    suffix = "-".join(option.strip().upper().replace(" ", "-") for option in options if option.strip())
    return f"{base_sku}-{suffix}" if suffix else base_sku


def generate_variant_combinations(db: Session, product_obj: Product, option_ids: list[list[int]]) -> list[ProductVariant]:
    variants = []
    for option_group in product(*option_ids):
        options = db.scalars(select(AttributeOption).where(AttributeOption.id.in_(option_group))).all()
        option_values = [option.value for option in options]
        ordered_options = []
        for option_id in option_group:
            for option in options:
                if option.id == option_id:
                    ordered_options.append(option)
                    break
        sku = generate_variant_sku(product_obj.sku, option_values)
        variant = ProductVariant(product=product_obj, sku=sku, name=" / ".join(option_values))
        variant.option_values = [VariantAttributeValue(option_id=option.id) for option in ordered_options]
        variants.append(variant)
    return variants


def save_product_upload(product_id: int, filename: str, content: bytes) -> str:
    settings = get_settings()
    suffix = Path(filename).suffix.lower() or ".bin"
    safe_name = f"product-{product_id}-{uuid4().hex}{suffix}"
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / safe_name
    file_path.write_bytes(content)
    return f"/static/uploads/{safe_name}"


def delete_product_upload(path_value: str | None) -> None:
    if not path_value or not path_value.startswith("/static/uploads/"):
        return
    relative_name = path_value.removeprefix("/static/uploads/")
    file_path = Path(get_settings().upload_dir) / relative_name
    if file_path.exists():
        file_path.unlink()


def set_primary_product_image(product: Product, target_image: ProductImage) -> None:
    for image in product.images:
        image.is_primary = image.id == target_image.id
