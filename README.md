# saas-erp-pim

> **Product Information Management (PIM)** — a FastAPI-based SaaS ERP module for managing rich product data, designed as a companion to [saas-erp-ims](https://github.com/stanwu/saas-erp-ims) with full schema compatibility for cross-system integration.
>
> **Status:** Under active development (WIP). Core PIM workflows are implemented, while live marketplace publishing is still in progress.

---

## Overview

`saas-erp-pim` centralises all product master data: descriptions, specifications, attributes, variants, images, SEO fields, and pricing. It acts as the **single source of truth** for product information and feeds downstream systems such as the Inventory Management System (IMS), e-commerce platforms, and marketplaces.

---

## Features

### 🗂 Product Management
- Full product lifecycle: **Draft → Active → Archived**
- Rich fields: short description, long description, SEO title/description/keywords
- Physical dimensions: weight, length, width, height (configurable units)
- Barcode support (EAN, UPC, etc.)
- Sale price + cost price tracking
- Reorder point (IMS-compatible)
- Pagination, full-text search by SKU / name / barcode, filter by category / brand / status / tag

### 🏷 Category Management
- **Hierarchical categories** with parent–child tree structure
- Auto-generated URL slugs
- Compatible with IMS category IDs for seamless join queries

### 🏢 Brand Management
- Brand profiles with logo upload, description, and website
- Filter and search products by brand

### 🔧 Attribute System
- Define reusable **attribute groups** (e.g. "Technical Specs", "Dimensions")
- Attribute types: `text`, `number`, `boolean`, `select`, `multiselect`
- Optional unit labels (mm, W, kg, etc.)
- Required / optional flags per attribute
- Assign attribute values per product with a dynamic editor

### 🔀 Product Variants
- Generate variants from attribute option combinations (e.g. Color × Size)
- Per-variant SKU, price adjustment, barcode, and active flag
- Bulk variant generation helper

### 🖼 Image Management
- Multi-image upload per product and per variant
- Sort order editing
- Primary image designation
- Alt text for accessibility / SEO

### 🏷 Tags
- Flat tag taxonomy with slugs
- Product tag assignment from the product editor

### 🛒 Marketplace / Channel Integration
- Built-in channel records for **Shopify**, **WooCommerce**, **Google Shopping**, **Amazon**, **eBay**, **Shopee**, **Lazada**, and **TikTok Shop**
- Non-technical onboarding UX with platform-specific setup guidance
- Store URL / key / token / OAuth callback fields with platform-specific examples
- Product-level channel listings with per-channel title / description / price overrides
- OAuth callback capture page for easier operator handoff

### 👥 User Management
- Roles: `admin` / `staff`
- Admin-only access to destructive operations
- Bcrypt password hashing
- Session-based auth with CSRF protection

### 📤 Export & IMS Integration
- Export products as **IMS-compatible CSV** (sku, name, description, category, unit, cost_price, reorder_point)
- JSON export endpoint for API consumers
- CLI script `scripts/export_to_ims.py` for scheduled sync

### 🏭 Supplier Management
- Identical schema to IMS `suppliers` table
- Shared supplier master across both systems

---

## Architecture

```
saas-erp-pim/
├── app/
│   ├── main.py               # FastAPI app entry point
│   ├── config.py             # Settings (ERP_PIM_* env vars)
│   ├── database.py           # SQLAlchemy engine, Base, sessions
│   ├── models.py             # All ORM models
│   ├── security.py           # Password hashing (bcrypt)
│   ├── dependencies.py       # Auth, CSRF, flash messages
│   ├── services.py           # Business logic layer
│   ├── bootstrap.py          # DB init + initial seed
│   ├── demo_seed.py          # Demo data factory
│   ├── routers/              # One router per domain module
│   │   ├── auth.py
│   │   ├── dashboard.py
│   │   ├── products.py
│   │   ├── images.py
│   │   ├── channels.py
│   │   ├── categories.py
│   │   ├── brands.py
│   │   ├── attributes.py
│   │   ├── variants.py
│   │   ├── tags.py
│   │   ├── suppliers.py
│   │   ├── users.py
│   │   └── export.py
│   ├── static/
│   │   └── uploads/          # Product images (gitignored)
│   └── templates/            # Jinja2 HTML templates
├── scripts/
│   ├── check_sensitive_data.py
│   ├── export_to_ims.py
├── tests/
│   ├── conftest.py
│   ├── test_app.py
│   ├── test_products.py
│   ├── test_attributes.py
│   ├── test_variants.py
│   ├── test_images.py
│   └── test_channels.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .pre-commit-config.yaml
└── plan.md
```

---

## Database Schema

### IMS-Compatible Tables

| Table | Compatible with IMS | Notes |
|-------|-------------------|-------|
| `users` | ✅ Identical | Same columns and types |
| `categories` | ✅ Superset | Adds `parent_id`, `slug`, `sort_order` |
| `suppliers` | ✅ Identical | Same columns and types |
| `products` | ✅ Superset | All IMS fields present + PIM extensions |

**Primary join key: `products.sku`** — used to link PIM product data with IMS inventory records.

### PIM-Specific Tables

| Table | Purpose |
|-------|---------|
| `brands` | Brand master data |
| `product_images` | Multi-image per product/variant |
| `attribute_groups` | Logical grouping of attributes |
| `product_attributes` | Attribute definitions (type, unit, required) |
| `attribute_options` | Options for select/multiselect attributes |
| `product_attribute_values` | Attribute values assigned to products |
| `product_variants` | SKU-level variants with price adjustments |
| `variant_attribute_values` | Attribute options assigned to variants |
| `tags` | Flat tag taxonomy |
| `product_tags` | Product ↔ tag association |
| `sales_channels` | Connected marketplace / ecommerce channels |
| `product_channel_listings` | Product ↔ sales channel publishing records |

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Web Framework | FastAPI |
| ORM | SQLAlchemy 2.0 |
| Database | SQLite (dev), configurable via `DATABASE_URL` |
| Templating | Jinja2 |
| Authentication | Session-based + CSRF (itsdangerous) |
| Password Hashing | bcrypt |
| Configuration | Manual settings class + env vars |
| Testing | pytest + httpx |
| Containerisation | Docker + docker-compose |

---

## Getting Started

### Prerequisites
- Python 3.12+
- Docker (optional)

### Local Development

```bash
# Clone
git clone https://github.com/stanwu/saas-erp-pim.git
cd saas-erp-pim

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
# optional: export ERP_PIM_* env vars

# Run
uvicorn app.main:app --reload
```

Open [http://localhost:8001](http://localhost:8001) and log in with `admin` / `admin@12345`.

### Docker

```bash
docker compose up -d
```

---

## Configuration

All settings are controlled via environment variables prefixed with `ERP_PIM_`:

| Variable | Default | Description |
|----------|---------|-------------|
| `ERP_PIM_SECRET_KEY` | *(insecure default)* | Session signing key |
| `ERP_PIM_CSRF_SECRET` | *(insecure default)* | CSRF token secret |
| `ERP_PIM_DATABASE_URL` | `sqlite:///./erp_pim.db` | Database connection URL |
| `ERP_PIM_ADMIN_USERNAME` | `admin` | Bootstrap admin username |
| `ERP_PIM_ADMIN_PASSWORD` | `admin@12345` | Bootstrap admin password |
| `ERP_PIM_SEED_DEMO_DATA` | `true` | Seed demo data on first run |
| `ERP_PIM_ENV` | `development` | `development` / `production` / `staging` |
| `ERP_PIM_UPLOAD_DIR` | `app/static/uploads` | Image storage path |
| `ERP_PIM_MAX_UPLOAD_MB` | `5` | Maximum image upload size (MB) |

> ⚠️ In production, always set `ERP_PIM_SECRET_KEY` and `ERP_PIM_CSRF_SECRET` to strong random values.

---

## IMS Integration

This system is designed to work alongside [saas-erp-ims](https://github.com/stanwu/saas-erp-ims):

- **`products.sku`** is the universal join key — IMS manages stock levels, PIM manages product data
- **`categories`** and **`suppliers`** share identical schemas — no transformation required
- Export endpoint `GET /export/products.csv` outputs IMS-compatible format
- CLI script `scripts/export_to_ims.py` can be scheduled as a cron job for automated sync
- IMS runs on port `8000`, PIM runs on port `8001` to avoid conflicts

---

## Current Status

Implemented today:

- Session auth, admin/staff users, CSRF protection
- Product, category, brand, supplier, tag, attribute, and variant management
- Product image upload / primary image / sorting / deletion
- Marketplace channel onboarding UX and product channel listings
- IMS-compatible CSV export
- Basic automated tests for app flow, products, attributes, variants, images, and channels

Still intentionally incomplete:

- Live API publishing to each marketplace
- Drag-and-drop image ordering
- Bulk import / headless JSON API
- Multi-language content workflows
- Webhook sync jobs / background workers

---

## Roadmap

- [ ] REST API endpoints (JSON) for headless integration
- [ ] Bulk import from CSV
- [ ] Multi-language product descriptions
- [ ] Webhook notifications on product publish
- [ ] Image CDN integration

---

## Contributors

- [stanwu](https://github.com/stanwu) - product direction, architecture, and implementation
- Codex - AI coding assistance for implementation, refactoring, testing, and documentation updates

---

## License

[MIT](LICENSE)
