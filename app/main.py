from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.bootstrap import init_db, seed_initial_data
from app.config import get_settings
from app.database import SessionLocal
from app.routers import attributes, auth, brands, categories, channels, dashboard, export, images, products, suppliers, tags, users, variants


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        seed_initial_data(db)
    finally:
        db.close()
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    same_site="lax",
    https_only=settings.session_https_only,
)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(products.router)
app.include_router(attributes.router)
app.include_router(variants.router)
app.include_router(tags.router)
app.include_router(images.router)
app.include_router(channels.router)
app.include_router(categories.router)
app.include_router(brands.router)
app.include_router(suppliers.router)
app.include_router(users.router)
app.include_router(export.router)
