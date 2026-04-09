# PIM System — Implementation Plan

## Problem Statement

Build a **Product Information Management (PIM)** system as a companion to `saas-erp-ims`.
The PIM manages rich product data (attributes, variants, images, brands, multilingual descriptions,
SEO fields, tags) while remaining **schema-compatible** with IMS so both systems can join on
`products.sku`, `categories`, and `suppliers` tables without ETL transforms.

## Coding Agent Instructions

> **Critical directive for any coding agent implementing this project:**
> Every file in `saas-erp-pim` must feel like it was written by the **same developer** who wrote
> `saas-erp-ims`. Study the patterns below and follow them exactly — same import order, same
> naming conventions, same router structure, same SQLAlchemy idioms, same template response style.
> When in doubt, open the nearest equivalent file in `saas-erp-ims` and mirror it.

---

## Coding Style Reference (extracted from saas-erp-ims)

### 1. Import Order & Grouping

Exactly three blocks, separated by blank lines. Within each block, alphabetical order:

```python
# Block 1 — stdlib (math before datetime)
import math
from datetime import datetime

# Block 2 — third-party (fastapi, sqlalchemy)
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

# Block 3 — local app (alphabetical by submodule)
from app.config import get_settings
from app.database import get_db
from app.dependencies import flash, get_current_user, require_admin, tmpl_ctx, validate_csrf
from app.models import Brand, Product, User
from app.services import some_service_fn
```

Rules:
- Never mix blocks or add blank lines within a block
- `from __future__ import annotations` only when forward references are unavoidable (e.g. `demo_seed.py`)
- No wildcard imports (`from app.models import *` is forbidden)
- Group multi-symbol imports with parentheses when ≥ 4 symbols

---

### 2. Router File Structure

Every router file must follow this exact top-of-file pattern:

```python
import math                                          # only if paginating

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError            # only if using db.commit()
from sqlalchemy.orm import Session, joinedload       # joinedload only if eager-loading

from app.config import get_settings
from app.database import get_db
from app.dependencies import flash, get_current_user, require_admin, tmpl_ctx, validate_csrf
from app.models import MyModel, User

router = APIRouter(prefix="/mymodule", tags=["mymodule"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()
```

Rules:
- `router`, `templates`, `settings` are **always module-level** — never inside functions
- `tags` on `APIRouter` matches the prefix (no `/`)
- `auth.py` and `dashboard.py` use `router = APIRouter()` (no prefix, no tags) — same as IMS

---

### 3. Handler Signatures & Conventions

#### GET (list)
```python
@router.get("")
def list_things(
    request: Request,
    page: int = 1,
    q: str = "",                          # search param if applicable
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
```
- Function name: `list_{plural}` — no suffix
- Use `def` (sync), not `async def`
- `page: int = 1` always first query param
- `current_user` before `db` — always

#### GET (new form page)
```python
@router.get("/new")
def new_thing_page(
    request: Request,
    current_user: User = Depends(require_admin),   # or get_current_user
):
```
- Function name: `new_{singular}_page` — always `_page` suffix
- Minimal deps: no `db` if not needed for the blank form

#### POST (create)
```python
@router.post("/new")
async def create_thing(
    request: Request,
    name: str = Form(...),
    optional_field: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),             # ALWAYS last
):
```
- Function name: `create_{singular}` — no suffix
- `async def` for all POST handlers
- CSRF dependency `_: None = Depends(validate_csrf)` is **always the last parameter**
- Optional string fields use `Form("")` default, not `Form(None)`

#### GET (edit form page)
```python
@router.get("/{thing_id}/edit")
def edit_thing_page(
    thing_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
```
- Function name: `edit_{singular}_page` — always `_page` suffix
- Path param (`thing_id`) is **first** parameter

#### POST (update)
```python
@router.post("/{thing_id}/edit")
async def edit_thing(
    thing_id: int,
    request: Request,
    name: str = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
```
- Function name: `edit_{singular}` — no `_page` suffix (it does the save)

#### POST (toggle/action)
```python
@router.post("/{thing_id}/toggle")
async def toggle_thing(
    thing_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    _: None = Depends(validate_csrf),
):
```

---

### 4. SQLAlchemy Idioms

```python
# ✅ CORRECT — use select() from sqlalchemy
from sqlalchemy import select, func

# Count
total = db.scalar(select(func.count(Thing.id))) or 0

# Count filtered stmt (for paginated lists with subquery)
total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

# Pagination — always this exact pattern
total_pages = max(1, math.ceil(total / per_page))
page = max(1, min(page, total_pages))
things = db.scalars(
    stmt.order_by(Thing.created_at.desc())
    .offset((page - 1) * per_page)
    .limit(per_page)
).all()

# Primary key lookup
thing = db.get(Thing, thing_id)        # ✅ not db.query(Thing).get(id)

# Single scalar
name = db.scalar(select(Thing.name).where(Thing.id == x))

# Eager loading
stmt = select(Thing).options(joinedload(Thing.relation))

# Boolean filter — noqa comment required (SQLAlchemy uses == not is)
.where(Thing.is_active == True)  # noqa: E712

# Active-only filter (standard pattern, used everywhere)
db.scalars(select(Thing).where(Thing.is_active == True).order_by(Thing.name)).all()  # noqa: E712

# ❌ WRONG — never use legacy query API
db.query(Thing).filter(Thing.id == x).first()
```

---

### 5. Template Response Pattern

```python
# ✅ CORRECT — always use tmpl_ctx(), request is first positional arg
return templates.TemplateResponse(
    request,
    "module/template.html",
    tmpl_ctx(request, current_user, things=things, page=page, total_pages=total_pages, total=total),
)

# ❌ WRONG — never pass raw dict
return templates.TemplateResponse("template.html", {"request": request, ...})
```

Rules:
- `tmpl_ctx()` is called with positional `(request, current_user)` then keyword args
- Template path always uses forward slash: `"module/template.html"`
- `current_user` can be `None` on the login page; in all other routes it must be the real user object

---

### 6. Redirect Pattern

```python
# ✅ CORRECT
return RedirectResponse(url="/things", status_code=303)

# ❌ WRONG — never use 302
return RedirectResponse(url="/things", status_code=302)
```

- Always `status_code=303` (POST/Redirect/GET pattern)
- Missing resource → silent redirect to list (no 404 raised in routers)
- After successful create/edit/delete → redirect to list with flash message

---

### 7. IntegrityError Handling

```python
db.add(thing)
try:
    db.commit()
except IntegrityError:
    db.rollback()
    return templates.TemplateResponse(
        request,
        "module/form.html",
        tmpl_ctx(request, current_user, thing=None, error="Name already exists."),
        status_code=400,
    )
flash(request, f"Thing '{name}' created.", "success")
return RedirectResponse(url="/things", status_code=303)
```

- `db.rollback()` immediately after catching `IntegrityError`
- Return the form template with `error=` message and `status_code=400`
- Flash message uses f-string with the entity name
- Flash on success, `error=` variable on failure (never flash on failure)

---

### 8. Form Field Handling

```python
# Required string — strip whitespace
name = name.strip()

# Optional string — strip and normalize to None
contact_person = contact_person.strip() or None
email = email.strip() or None

# Checkbox — HTML checkboxes submit "on" or nothing
is_active = bool(is_active)          # "on" → True, "" → False

# Numeric from form
cost_price = float(cost_price)
quantity = int(quantity)
```

---

### 9. Private Helper Functions in Routers

Prefix with underscore, placed at top of file before route handlers:

```python
def _load_thing_with_relations(db: Session, thing_id: int) -> Thing | None:
    return db.scalar(
        select(Thing)
        .options(joinedload(Thing.relation))
        .where(Thing.id == thing_id)
    )
```

---

### 10. Model Conventions

```python
# Enums — string enum inheriting (str, enum.Enum)
class ThingStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    archived = "archived"

# Badge/label dicts — UPPER_CASE module-level constants
THING_STATUS_BADGE = {
    ThingStatus.draft: "secondary",
    ThingStatus.active: "success",
    ThingStatus.archived: "dark",
}

# Model class
class Thing(Base):
    __tablename__ = "things"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships — always typed with Mapped[]
    children: Mapped[list["Child"]] = relationship(back_populates="thing", cascade="all, delete-orphan")
    parent: Mapped["Parent | None"] = relationship(back_populates="things")
```

Rules:
- `cascade="all, delete-orphan"` only on owned child relationships
- Timestamps use `default=func.now()` — never `datetime.utcnow` or Python-side defaults
- All columns declare `nullable=True/False` explicitly
- String lengths follow IMS conventions: name=64/128, description=Text, email=128, phone=32

---

### 11. Services Layer

`services.py` holds business logic that spans multiple models or requires transaction control:

```python
# ✅ Put in services.py
def create_product_with_defaults(db: Session, sku: str, name: str, ...) -> Product: ...
def generate_variant_sku(base_sku: str, options: list[str]) -> str: ...

# ✅ Put inline in router
supplier.name = name.strip()
db.commit()
```

Rules:
- Routers call service functions; they don't contain complex business logic
- Service functions receive `db: Session` as first arg
- Service functions raise `ValueError` for business rule violations (caller handles display)
- Never import from `routers/` in `services.py`

---

### 12. Config Style

```python
class Settings:
    def __init__(self) -> None:
        self.app_name = "ERP PIM"
        self.secret_key = os.getenv("ERP_PIM_SECRET_KEY", "dev-secret-key-change-in-prod")
        # ... all other settings
        self.validate_security()

    @property
    def is_production_like(self) -> bool:
        return self.environment in {"production", "staging"}

    def validate_security(self) -> None:
        if not self.is_production_like:
            return
        if self.secret_key in INSECURE_SECRET_KEYS:
            raise ValueError("ERP_PIM_SECRET_KEY must be set...")


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- Manual `__init__`, not `pydantic.BaseSettings`
- `@lru_cache` on `get_settings()` for singleton behaviour
- `validate_security()` only raises in production/staging — never blocks dev

---

### 13. Test Conventions

```python
# File header — set env vars BEFORE any app imports
import os
from pathlib import Path

TEST_DB = Path(__file__).resolve().parent / "test_erp_pim.db"
os.environ["ERP_PIM_DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["ERP_PIM_SECRET_KEY"] = "test-secret"
os.environ["ERP_PIM_CSRF_SECRET"] = "test-csrf-secret"

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app                  # noqa: E402


# Module-level setup/teardown
def setup_module():
    if TEST_DB.exists():
        TEST_DB.unlink()

def teardown_module():
    if TEST_DB.exists():
        TEST_DB.unlink()


# Shared helpers (not fixtures)
def _get_csrf(client: TestClient) -> str:
    resp = client.get("/login")
    import re
    m = re.search(r'name="csrf_token" value="([^"]+)"', resp.text)
    return m.group(1) if m else ""

def _login_admin(client: TestClient) -> None:
    csrf = _get_csrf(client)
    resp = client.post("/login", data={"username": "admin", "password": "admin@12345", "csrf_token": csrf}, follow_redirects=False)
    assert resp.status_code == 303


# Test functions
def test_verb_subject_condition():
    with TestClient(app) as client:
        _login_admin(client)
        resp = client.get("/things")
        assert resp.status_code == 200
        assert "Things" in resp.text
```

Rules:
- Env vars at module level, before imports, `# noqa: E402` on deferred imports
- `TestClient(app)` as context manager inside each test (not module-level)
- Use helper functions (`_get_csrf`, `_login_admin`), not pytest fixtures
- `setup_module` / `teardown_module` for file-scoped DB lifecycle
- Test names: `test_{verb}_{subject}_{condition}` in snake_case

---

### 14. Pre-commit Config

Match IMS exactly — only the sensitive data scanner:

```yaml
repos:
  - repo: local
    hooks:
      - id: sensitive-data-scan
        name: Scan for sensitive data and likely PII
        entry: python3 scripts/check_sensitive_data.py
        language: system
        pass_filenames: true
        types_or: [text]
```

No ruff, black, isort, or flake8 in pre-commit (they are not in IMS).

---

### 15. String & Flash Message Conventions

```python
# Flash messages — f-string with entity name, always "success" category
flash(request, f"Brand '{name}' created.", "success")
flash(request, f"Brand '{brand.name}' updated.", "success")
flash(request, f"Brand '{brand.name}' deleted.", "success")

# Auth welcome message
flash(request, f"Welcome back, {user.username}!", "success")

# Error — passed as template variable, never flashed
return templates.TemplateResponse(..., tmpl_ctx(..., error="Name already exists."), status_code=400)
```

---

### 16. Demo Seed Style

```python
# Module-level constant lists for seed data
BRANDS = [
    ("Acme Corp", "https://acme.example.com", "Leading industrial brand"),
    ...
]

# Seed function checks existence before inserting
def seed_demo_data(db: Session) -> None:
    for name, website, description in BRANDS:
        if not db.scalar(select(Brand).where(Brand.name == name)):
            db.add(Brand(name=name, website=website, description=description))
    db.commit()

def should_seed_demo_data(db: Session) -> bool:
    return db.scalar(select(func.count(Brand.id))) == 0
```

---

## Tech Stack (mirrors saas-erp-ims exactly)

| Layer | Choice |
|-------|--------|
| Framework | FastAPI |
| ORM | SQLAlchemy 2.0 (mapped_column) |
| DB | SQLite (dev) / pluggable via `DATABASE_URL` |
| Templates | Jinja2 |
| Auth | Session-based + CSRF (itsdangerous) |
| Password | bcrypt |
| Config | pydantic-settings / env vars |
| Migrations | Alembic |
| Tests | pytest + httpx |
| Container | Docker + docker-compose |
| Pre-commit | pre-commit hooks |

---

## Database Schema

### Tables Shared / Compatible with IMS

#### `users` — identical schema to IMS
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| username | String(64) unique | |
| password_hash | String(128) | bcrypt |
| role | Enum(admin, staff) | |
| is_active | Boolean | |
| created_at | DateTime | |
| updated_at | DateTime | |

#### `categories` — superset of IMS (adds hierarchy)
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| name | String(64) unique | |
| description | Text nullable | |
| parent_id | FK→categories.id nullable | tree hierarchy |
| slug | String(128) unique | URL-friendly |
| sort_order | Integer default 0 | |

*IMS join key: `categories.id` ↔ `products.category_id`*

#### `suppliers` — identical schema to IMS
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| name | String(128) unique | |
| contact_person | String(64) nullable | |
| email | String(128) nullable | |
| phone | String(32) nullable | |
| is_active | Boolean | |
| created_at | DateTime | |

---

### New PIM Tables

#### `brands`
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| name | String(128) unique | |
| description | Text nullable | |
| website | String(256) nullable | |
| logo_filename | String(256) nullable | |
| is_active | Boolean default True | |
| created_at | DateTime | |

#### `products` — superset of IMS (fully backward-compatible)
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| sku | String(64) unique index | **IMS join key** |
| name | String(128) | |
| short_description | Text nullable | |
| description | Text nullable | |
| category_id | FK→categories.id nullable | IMS-compatible |
| brand_id | FK→brands.id nullable | PIM only |
| unit | String(16) default "pcs" | IMS-compatible |
| cost_price | Numeric(12,2) default 0 | IMS-compatible |
| sale_price | Numeric(12,2) nullable | PIM only |
| reorder_point | Integer default 0 | IMS-compatible |
| barcode | String(64) nullable index | |
| weight | Numeric(10,3) nullable | |
| weight_unit | String(8) nullable | kg/g/lb/oz |
| length | Numeric(10,2) nullable | cm |
| width | Numeric(10,2) nullable | cm |
| height | Numeric(10,2) nullable | cm |
| seo_title | String(256) nullable | |
| seo_description | Text nullable | |
| seo_keywords | Text nullable | |
| status | Enum(draft,active,archived) default draft | |
| is_active | Boolean default True | IMS-compatible |
| published_at | DateTime nullable | |
| created_at | DateTime | |
| updated_at | DateTime | |

*IMS compatibility: all IMS fields present with identical types and defaults.*

#### `product_images`
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| product_id | FK→products.id | |
| variant_id | FK→product_variants.id nullable | |
| filename | String(256) | stored under `uploads/` |
| alt_text | String(256) nullable | |
| sort_order | Integer default 0 | |
| is_primary | Boolean default False | |
| created_at | DateTime | |

#### `attribute_groups`
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| name | String(64) unique | e.g. "Dimensions", "Technical Specs" |
| sort_order | Integer default 0 | |

#### `product_attributes`
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| group_id | FK→attribute_groups.id nullable | |
| name | String(64) | |
| attribute_type | Enum(text,number,boolean,select,multiselect) | |
| unit | String(32) nullable | e.g. "mm", "W" |
| is_required | Boolean default False | |
| sort_order | Integer default 0 | |

#### `attribute_options` (for select/multiselect)
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| attribute_id | FK→product_attributes.id | |
| value | String(128) | |
| sort_order | Integer default 0 | |

#### `product_attribute_values`
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| product_id | FK→products.id | |
| attribute_id | FK→product_attributes.id | |
| value_text | Text nullable | for text/number/boolean |
| option_id | FK→attribute_options.id nullable | for select |
| UniqueConstraint(product_id, attribute_id) | | |

#### `product_variants`
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| product_id | FK→products.id | |
| sku | String(64) unique index | variant-level SKU |
| name | String(128) | e.g. "Red / XL" |
| price_adjustment | Numeric(12,2) default 0 | delta from base |
| barcode | String(64) nullable | |
| is_active | Boolean default True | |
| created_at | DateTime | |

#### `variant_attribute_values`
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| variant_id | FK→product_variants.id | |
| attribute_id | FK→product_attributes.id | |
| option_id | FK→attribute_options.id | |

#### `tags`
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| name | String(64) unique | |
| slug | String(64) unique | |

#### `product_tags` (association)
| Column | Type | Notes |
|--------|------|-------|
| product_id | FK→products.id | composite PK |
| tag_id | FK→tags.id | composite PK |

---

## Application Structure

```
app/
├── __init__.py
├── main.py                 # FastAPI app, lifespan, routers
├── config.py               # Settings (env vars, ERP_PIM_* prefix)
├── database.py             # Engine, SessionLocal, Base, WAL pragma
├── models.py               # All SQLAlchemy models
├── security.py             # hash_password, verify_password
├── dependencies.py         # get_current_user, require_admin, csrf, flash, tmpl_ctx
├── services.py             # Business logic (product service, attribute service)
├── bootstrap.py            # init_db, seed_initial_data
├── demo_seed.py            # Demo data factory
├── templates.py            # Jinja2Templates instance
├── routers/
│   ├── __init__.py
│   ├── auth.py             # login / logout
│   ├── dashboard.py        # summary stats
│   ├── products.py         # CRUD + search + filter
│   ├── categories.py       # CRUD + tree view
│   ├── brands.py           # CRUD
│   ├── attributes.py       # Attribute groups + attributes + options
│   ├── variants.py         # Variant management per product
│   ├── images.py           # Image upload / reorder / delete
│   ├── tags.py             # Tag CRUD + product association
│   ├── suppliers.py        # CRUD (IMS-compatible)
│   ├── users.py            # CRUD (admin only)
│   └── export.py           # CSV / JSON export endpoints
├── static/
│   ├── styles.css
│   └── uploads/            # Product image storage (gitignored)
└── templates/
    ├── base.html
    ├── partials/
    │   ├── pagination.html
    │   ├── product_card.html
    │   ├── attribute_editor.html
    │   └── image_upload.html
    ├── auth/
    │   └── login.html
    ├── dashboard/
    │   └── index.html
    ├── products/
    │   ├── list.html
    │   ├── detail.html
    │   └── form.html
    ├── categories/
    │   ├── list.html
    │   └── form.html
    ├── brands/
    │   ├── list.html
    │   └── form.html
    ├── attributes/
    │   ├── list.html
    │   └── form.html
    ├── variants/
    │   ├── list.html
    │   └── form.html
    ├── tags/
    │   ├── list.html
    │   └── form.html
    ├── suppliers/
    │   ├── list.html
    │   └── form.html
    └── users/
        ├── list.html
        └── form.html
```

---

## Config (env var prefix: `ERP_PIM_*`)

| Env Var | Default | Notes |
|---------|---------|-------|
| ERP_PIM_SECRET_KEY | dev-secret-key-change-in-prod | session signing |
| ERP_PIM_CSRF_SECRET | csrf-secret-change-in-prod | CSRF token |
| ERP_PIM_DATABASE_URL | sqlite:///./erp_pim.db | |
| ERP_PIM_ADMIN_USERNAME | admin | |
| ERP_PIM_ADMIN_PASSWORD | admin@12345 | |
| ERP_PIM_SEED_DEMO_DATA | true | |
| ERP_PIM_ENV | development | development / production / staging |
| ERP_PIM_UPLOAD_DIR | app/static/uploads | image storage path |
| ERP_PIM_MAX_UPLOAD_MB | 5 | per-image size limit |

---

## UX Design Consistency with saas-erp-ims

All PIM templates must follow these rules extracted from the IMS design system. Deviating from these rules requires explicit justification.

### CSS Framework
- **Bootstrap 5.3.3** via CDN (identical version)
- **Bootstrap Icons 1.11.3** via CDN (identical version)
- `styles.css` extends/overrides Bootstrap; never replaces it
- No additional CSS frameworks (no Tailwind, no Bulma)

### Layout
| Element | IMS Pattern | PIM Must Match |
|---------|------------|----------------|
| Outer shell | `container-fluid > row` | ✅ same |
| Sidebar | `col-md-2 sidebar`, `bg-dark (#212529)`, `min-height: calc(100vh - 56px)` | ✅ same |
| Content area | `col-md-10 py-4 px-4` | ✅ same |
| Top navbar | `navbar-dark bg-dark px-3` — brand left, user+logout right | ✅ same |
| Body background | `#f8f9fa` | ✅ same |

### Sidebar Navigation
- Nav links: `nav-link`, active state via `{% if '/route' in request.url.path %}active{% endif %}`
- Active link style: `color: #fff; background: rgba(255,255,255,.1); border-radius: 4px`
- Admin-only section separated by `<hr class="border-secondary my-1">`
- PIM sidebar order: Dashboard → Products → Categories → Brands → Attributes → Tags → Suppliers → *(admin hr)* → Users

### Page Header Pattern
Every list/form page must use:
```html
<div class="d-flex justify-content-between align-items-center mb-3">
  <h4 class="mb-0">Page Title <span class="badge bg-secondary fs-6">{{ total }}</span></h4>
  <a href="/X/new" class="btn btn-primary btn-sm"><i class="bi bi-plus-lg"></i> New X</a>
</div>
```

### Cards
- Content panels: `.card` → `.card-header` + `.card-body`
- No shadow utilities (IMS uses no `shadow-*` except login)
- Form panels: `.card > .card-body > form`

### Tables
```html
<div class="card">
  <div class="table-responsive">
    <table class="table table-hover table-sm mb-0">
      <thead class="table-light"><tr>...</tr></thead>
      <tbody>
        {% else %}
        <tr><td colspan="N" class="text-center text-muted py-4">No X found.</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
```

### Status Badges (must be identical to IMS)
| State | Class |
|-------|-------|
| Active / Success | `badge bg-success` |
| Inactive / Default | `badge bg-secondary` |
| Draft | `badge bg-secondary` |
| Warning / Partial | `badge bg-warning` |
| Danger / Error | `badge bg-danger` |
| Info | `badge bg-info` |
| Archived | `badge bg-dark` *(PIM addition)* |

### Forms
- Grid: `<div class="row g-3">` + `col-md-N` inside `.card-body`
- Labels: `<label class="form-label">Field <span class="text-danger">*</span></label>`
- Inputs: `form-control`, selects: `form-select`, checkboxes: `form-check-input`
- Submit row: `<button type="submit" class="btn btn-primary">Save</button> <a class="btn btn-outline-secondary ms-2">Cancel</a>`
- CSRF: `<input type="hidden" name="csrf_token" value="{{ csrf_token }}">`

### Search Bar (list pages)
```html
<form method="get" class="mb-3">
  <div class="input-group input-group-sm" style="max-width:400px">
    <input type="text" name="q" class="form-control" placeholder="Search…" value="{{ q }}">
    <button class="btn btn-outline-secondary" type="submit"><i class="bi bi-search"></i></button>
    {% if q %}<a href="/X" class="btn btn-outline-danger">✕</a>{% endif %}
  </div>
</form>
```

### Detail Pages
- Back button: `<a href="/X" class="btn btn-sm btn-outline-secondary">← Back</a>`
- Info panel: `<dl class="row mb-0"><dt class="col-5">Field</dt><dd class="col-7">Value</dd></dl>`
- Two-column layout for info + related data: `<div class="row g-3"><div class="col-md-6">`

### Flash Messages
- Rendered in `base.html` above `{% block content %}`
- Categories map to Bootstrap alert variants: `success` → `alert-success`, `danger` → `alert-danger`, `warning` → `alert-warning`, `info` → `alert-info`
- Always dismissible with `alert-dismissible fade show`

### Page `<title>` Convention
- Format: `{Page} — ERP PIM` (IMS uses `— ERP IMS`)
- Login: `Login — ERP PIM`

### Icons (Bootstrap Icons only)
| Concept | Icon |
|---------|------|
| Dashboard | `bi-speedometer2` |
| Products | `bi-box-seam` |
| Categories | `bi-diagram-3` |
| Brands | `bi-award` |
| Attributes | `bi-sliders` |
| Tags | `bi-tags` |
| Suppliers | `bi-truck` |
| Users | `bi-people` |
| Images | `bi-images` |
| Variants | `bi-intersect` |
| Export | `bi-download` |
| New/Add | `bi-plus-lg` |
| Edit | `bi-pencil` |
| Delete | `bi-trash` |
| Search | `bi-search` |
| Logout | `bi-box-arrow-right` |

### Pagination
- Reuse `partials/pagination.html` macro `render_pagination(page, total_pages, base_url, extra_params)` (identical to IMS)
- Rendered below the card: `{{ render_pagination(page, total_pages, "/products", "&q=" + q if q else "") }}`

---

## AEO Design (AI Engine Optimization)

AEO makes PIM product pages discoverable and correctly interpreted by AI-powered search engines
(Perplexity, ChatGPT Search, Google AI Overviews, Bing Copilot, etc.).
This is especially important for a PIM system because product pages are primary targets for AI indexing.

### 1. Structured Data (JSON-LD)

Inject via `{% block structured_data %}{% endblock %}` in `base.html` before `</head>`.

#### Product detail page — `schema.org/Product`
```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "{{ product.name }}",
  "sku": "{{ product.sku }}",
  "description": "{{ product.description }}",
  "brand": { "@type": "Brand", "name": "{{ product.brand.name }}" },
  "category": "{{ product.category.name }}",
  "image": ["{{ primary_image_url }}"],
  "offers": {
    "@type": "Offer",
    "price": "{{ product.sale_price or product.cost_price }}",
    "priceCurrency": "USD",
    "availability": "{% if product.status == 'active' %}InStock{% else %}Discontinued{% endif %}"
  },
  "additionalProperty": [
    {% for val in product.attribute_values %}
    { "@type": "PropertyValue", "name": "{{ val.attribute.name }}", "value": "{{ val.value_text }}" }
    {% endfor %}
  ]
}
```

#### Product list page — `schema.org/ItemList`
```json
{
  "@context": "https://schema.org",
  "@type": "ItemList",
  "name": "Products",
  "numberOfItems": {{ total }},
  "itemListElement": [
    {% for p in products %}
    { "@type": "ListItem", "position": {{ loop.index }}, "url": "/products/{{ p.id }}", "name": "{{ p.name }}" }
    {% endfor %}
  ]
}
```

#### All pages — `schema.org/BreadcrumbList`
```json
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    { "@type": "ListItem", "position": 1, "name": "Home", "item": "/dashboard" },
    { "@type": "ListItem", "position": 2, "name": "{{ section }}", "item": "/{{ section_url }}" }
  ]
}
```

### 2. Meta Tags in `base.html`

```html
<meta name="description" content="{% block meta_description %}ERP PIM — Product Information Management{% endblock %}">
<link rel="canonical" href="{% block canonical %}{{ request.url }}{% endblock %}">

<!-- Open Graph -->
<meta property="og:type" content="{% block og_type %}website{% endblock %}">
<meta property="og:title" content="{% block og_title %}{% block title %}ERP PIM{% endblock %}{% endblock %}">
<meta property="og:description" content="{% block og_description %}{% endblock %}">
<meta property="og:image" content="{% block og_image %}{% endblock %}">
<meta property="og:url" content="{{ request.url }}">

<!-- Twitter Card -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{% block tw_title %}{% endblock %}">
```

Each product template overrides `meta_description`, `canonical`, `og_type=product`, `og_image`.

### 3. Semantic HTML Rules

| Element | Usage | Requirement |
|---------|-------|-------------|
| `<html lang="en">` | Root | Required in `base.html` |
| `<main>` | Content area | Wrap `{% block content %}` in `<main>` |
| `<nav aria-label="Sidebar">` | Sidebar nav | Required aria-label |
| `<nav aria-label="Top navigation">` | Navbar | Required aria-label |
| `<nav aria-label="Breadcrumb">` | Breadcrumb | On all content pages |
| `<h1>` | Page title | One per page (product name on detail) |
| `<h2>` | Section titles | Attribute groups, variant section |
| `<article>` | Product card | In list views |
| `<figure>` + `<figcaption>` | Product images | Required for image blocks |
| `<dl><dt><dd>` | Key-value specs | Product info panel, attribute values |
| `alt` on `<img>` | All images | Required; use `product.name + ' image'` fallback |
| `<table>` `<th scope="col/row">` | All tables | `scope` attribute required for AEO |

### 4. Machine-Readable Endpoints (in `export.py` router)

| Endpoint | Format | AEO Purpose |
|----------|--------|------------|
| `GET /sitemap.xml` | XML sitemap | AI/search crawlers discover all product URLs |
| `GET /robots.txt` | Plain text | Allow AI crawlers (`GPTBot`, `PerplexityBot`, `ClaudeBot`) |
| `GET /export/products.json` | JSON-LD array | Direct feed for AI indexing tools |
| `GET /export/products.csv` | CSV | IMS integration + spreadsheet AI tools |

`robots.txt` content:
```
User-agent: *
Allow: /products
Allow: /export/products.json
Disallow: /users
Disallow: /login

User-agent: GPTBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: ClaudeBot
Allow: /
```

### 5. Content Quality Rules (enforced in forms + validation)

- `product.name` — required, 3–128 chars, descriptive (not just a code)
- `product.short_description` — recommended, shown in list cards and og:description
- `product.description` — full description, minimum 50 chars recommended for active products
- `product.seo_title` — if blank, auto-generate from `{name} | ERP PIM`
- `product.seo_description` — if blank, truncate `short_description` to 160 chars
- `product.seo_keywords` — comma-separated, auto-suggest from tags + category + brand
- Image `alt_text` — required on primary image before product can be set to `active`
- All attribute values shown on detail page as `<dl>` (not hidden in tabs)

### 6. Breadcrumb Navigation

Every content page must render a visible breadcrumb AND a matching JSON-LD `BreadcrumbList`:
```html
<nav aria-label="Breadcrumb" class="mb-3">
  <ol class="breadcrumb">
    <li class="breadcrumb-item"><a href="/dashboard">Home</a></li>
    <li class="breadcrumb-item"><a href="/products">Products</a></li>
    <li class="breadcrumb-item active">{{ product.name }}</li>
  </ol>
</nav>
```

### 7. Template Checklist (per-page AEO requirements)

| Template | JSON-LD | Meta desc | OG tags | H1 | Breadcrumb | Semantic tags |
|----------|---------|-----------|---------|-----|------------|---------------|
| `products/detail.html` | Product | ✅ | ✅ product | ✅ | ✅ | article, dl, figure |
| `products/list.html` | ItemList | ✅ | ✅ | ✅ | ✅ | article per row |
| `categories/list.html` | ItemList | ✅ | — | ✅ | ✅ | — |
| `brands/list.html` | ItemList | ✅ | — | ✅ | ✅ | — |
| `dashboard/index.html` | — | ✅ | — | ✅ | — | — |
| All other pages | — | ✅ | — | ✅ | ✅ | — |

---

## IMS Integration Notes

- **products.sku** is the universal join key between PIM and IMS
- **categories.name** is unique in both systems; PIM adds `parent_id` and `slug` but keeps the same `id`
- **suppliers** schema is identical; can be a shared DB or replicated via CSV export
- PIM `export.py` router exports `products` in IMS-compatible CSV format (sku, name, description, category, unit, cost_price, reorder_point)
- Future: API-level sync endpoint (`GET /api/export/ims-products`) returns JSON matching IMS import schema

---

## Feature Modules & Development Todos

### Phase 0 — Project Scaffolding
- [ ] `app/__init__.py` — empty
- [ ] `app/config.py` — Settings class, ERP_PIM_* env vars, security validation
- [ ] `app/database.py` — engine, SessionLocal, Base, WAL pragma
- [ ] `app/security.py` — hash_password, verify_password (bcrypt)
- [ ] `app/models.py` — all models (User, Category, Supplier, Brand, Product, ProductImage, AttributeGroup, ProductAttribute, AttributeOption, ProductAttributeValue, ProductVariant, VariantAttributeValue, Tag, ProductTag)
- [ ] `app/dependencies.py` — get_current_user, require_admin, csrf helpers, flash, tmpl_ctx
- [ ] `app/templates.py` — Jinja2Templates instance
- [ ] `app/bootstrap.py` — init_db(), seed_initial_data() (admin user, default category, default brand)
- [ ] `app/demo_seed.py` — demo brands, categories, suppliers, products with attributes, variants, tags
- [ ] `app/main.py` — FastAPI app, lifespan, all routers, SessionMiddleware, static mount
- [ ] `requirements.txt` — mirror IMS + add python-multipart (already included), pillow (optional image resize)
- [ ] `Dockerfile` — mirror IMS, ERP_PIM_* env vars
- [ ] `docker-compose.yml` — web service, volume for DB + uploads
- [ ] `.env.example` — all ERP_PIM_* vars with placeholder values
- [ ] `alembic.ini` + `alembic/` — migration setup

### Phase 1 — Auth & Base Templates
- [ ] `app/routers/auth.py` — GET /login, POST /login, POST /logout (identical to IMS)
- [ ] `app/templates/base.html` — navbar (Products, Categories, Brands, Attributes, Tags, Suppliers, Users), flash messages, CSRF injection
- [ ] `app/templates/partials/pagination.html`
- [ ] `app/templates/auth/login.html`
- [ ] `app/static/styles.css` — extend IMS styles

### Phase 2 — Users & Dashboard
- [ ] `app/routers/users.py` — CRUD (admin only), same as IMS
- [ ] `app/routers/dashboard.py` — stats: total products, active/draft/archived counts, brands, categories, top tags
- [ ] `app/templates/users/list.html`, `form.html`
- [ ] `app/templates/dashboard/index.html` — stat cards + recent products

### Phase 3 — Categories, Brands, Suppliers
- [ ] `app/routers/categories.py` — CRUD + tree structure (parent_id), slug auto-generation
- [ ] `app/routers/brands.py` — CRUD + logo upload
- [ ] `app/routers/suppliers.py` — CRUD (IMS-compatible schema)
- [ ] Templates: `categories/list.html`, `categories/form.html`, `brands/list.html`, `brands/form.html`, `suppliers/list.html`, `suppliers/form.html`

### Phase 4 — Products Core
- [ ] `app/services.py` — ProductService: create, update, search (full-text on sku/name/barcode), paginate, status change, archive, get_with_relations
- [ ] `app/routers/products.py` — list (filter by category/brand/status/tag, search, paginate), detail, new, create, edit, update, archive, export
- [ ] `app/templates/products/list.html` — table with filters, status badge, thumbnail
- [ ] `app/templates/products/detail.html` — all fields, attributes section, variants section, images carousel, tags
- [ ] `app/templates/products/form.html` — full create/edit form with dynamic attribute fields

### Phase 5 — Attributes System
- [ ] `app/routers/attributes.py` — AttributeGroup CRUD, ProductAttribute CRUD, AttributeOption CRUD (inline)
- [ ] `app/services.py` — AttributeService: get_attributes_for_category, render_attribute_form_fields
- [ ] `app/templates/attributes/list.html` — grouped list, type badges
- [ ] `app/templates/attributes/form.html` — attribute form with dynamic options editor
- [ ] `app/templates/partials/attribute_editor.html` — reusable partial for product form

### Phase 6 — Product Variants
- [ ] `app/routers/variants.py` — CRUD per product, matrix generation helper
- [ ] `app/services.py` — VariantService: generate_variants_from_options, bulk_create, sku_suggestion
- [ ] `app/templates/variants/list.html` — per-product variant table
- [ ] `app/templates/variants/form.html` — variant form with attribute option selectors

### Phase 7 — Images
- [ ] `app/routers/images.py` — POST /products/{id}/images (multipart upload), DELETE, PATCH (reorder, set primary)
- [ ] File storage under `ERP_PIM_UPLOAD_DIR`, filename sanitization, size validation
- [ ] `app/templates/partials/image_upload.html` — drag-reorder image grid
- [ ] Serve `/uploads/` as StaticFiles mount

### Phase 8 — Tags
- [ ] `app/routers/tags.py` — Tag CRUD, product association (add/remove tag)
- [ ] `app/templates/tags/list.html`, tag cloud view
- [ ] Tag autocomplete partial for product form

### Phase 9 — Export & IMS Integration
- [ ] `app/routers/export.py` — GET /export/products.csv (IMS-compatible fields), GET /export/products.json
- [ ] Export filters: status=active only, category filter, brand filter
- [ ] `scripts/export_to_ims.py` — CLI script to dump PIM products CSV in IMS import format

### Phase 10 — Scripts & Tests
- [ ] `scripts/check_sensitive_data.py` — mirror IMS, scan for hardcoded secrets
- [ ] `scripts/seed_demo_data.py` — standalone demo seed script
- [ ] `scripts/screenshot.py` — headless browser screenshots for docs
- [ ] `tests/conftest.py` — test DB setup (in-memory SQLite), TestClient, auth helpers
- [ ] `tests/test_app.py` — smoke tests (login, dashboard, product list, product create)
- [ ] `tests/test_products.py` — product CRUD, search, filter, status transitions
- [ ] `tests/test_attributes.py` — attribute/option CRUD, value assignment
- [ ] `tests/test_variants.py` — variant generation, SKU uniqueness

### Phase 11 — Docs
- [ ] `README.md` — architecture, features, specs (English, generated separately)
- [ ] `docs/screenshots/` — captured from screenshot.py
- [ ] `docs/ims-integration.md` — how to sync PIM → IMS

---

## Notes

- env var prefix `ERP_PIM_*` avoids collision with IMS `ERP_IMS_*`
- Docker container name: `erp-pim-web`, port `8001` (IMS uses `8000`)
- `uploads/` folder gitignored; Docker volume `erp_pim_uploads` for persistence
- All monetary fields use `Numeric(12,2)` (same as IMS)
- Alembic migrations live in `alembic/` folder; initial migration generated from models
- Pre-commit hooks: trailing-whitespace, end-of-file-fixer, check-yaml, check-added-large-files
