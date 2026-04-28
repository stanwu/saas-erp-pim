"""Take screenshots of key ERP PIM pages for README documentation."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bootstrap import init_db, seed_initial_data
from app.database import SessionLocal
from app.demo_seed import DEMO_SKUS, seed_demo_data

try:
    from playwright.async_api import async_playwright
except ModuleNotFoundError as exc:  # pragma: no cover - local tooling script
    raise SystemExit(
        "playwright is not installed in .venv. Run `.venv/bin/pip install playwright` first."
    ) from exc


BASE = os.environ.get("ERP_PIM_SCREENSHOT_BASE", "http://127.0.0.1:8001")
OUT = ROOT / "docs" / "screenshots"
CHROME_EXECUTABLE = os.environ.get(
    "ERP_PIM_CHROME_PATH",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)
LOGIN_USERNAME = os.environ.get("ERP_PIM_SCREENSHOT_USERNAME", "admin")
LOGIN_PASSWORD = os.environ.get("ERP_PIM_SCREENSHOT_PASSWORD", "admin@12345")


class CaptureError(RuntimeError):
    """Raised when browser automation cannot continue safely."""


def _seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        seed_initial_data(db)
        seed_demo_data(db, cleanup_legacy=True)
    finally:
        db.close()


async def find_form_for_selector(page, selector: str):
    return page.locator("form", has=page.locator(selector)).first


async def submit_form(form):
    submit = form.locator('button[type="submit"], input[type="submit"]').first
    await submit.click()


async def ensure_logged_in(page, context: str) -> None:
    await page.wait_for_load_state("domcontentloaded")
    current_url = page.url
    if "/login" in current_url:
        raise CaptureError(f"{context}: redirected to login at {current_url}")


async def login(page) -> None:
    await page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    await page.wait_for_selector('[name="csrf_token"]', timeout=5000, state="attached")
    form = await find_form_for_selector(page, '[name="username"]')
    await page.fill('[name="username"]', LOGIN_USERNAME)
    await page.fill('[name="password"]', LOGIN_PASSWORD)
    await submit_form(form)
    await page.wait_for_load_state("domcontentloaded")
    if page.url.rstrip("/") != BASE.rstrip("/"):
        raise CaptureError(f"login failed; current_url={page.url}")


async def screenshot(page, name: str, url: str, label: str, require_auth: bool = True) -> None:
    await page.goto(f"{BASE}{url}", wait_until="domcontentloaded")
    if require_auth:
        await ensure_logged_in(page, f"while capturing {label}")
    await page.wait_for_timeout(800)
    await page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
    print(f"✓ {label}")


async def screenshot_product_detail(page) -> None:
    await page.goto(f"{BASE}/products?q=PIM-DEMO", wait_until="domcontentloaded")
    await ensure_logged_in(page, "while opening products list for detail capture")
    detail_link = page.locator('table tbody tr:first-child td:first-child a').first
    href = await detail_link.get_attribute("href")
    if not href:
        raise CaptureError("product detail link not found")
    await screenshot(page, "04b_product_detail", href, "商品詳情")


async def screenshot_first_channel_connect(page) -> None:
    await page.goto(f"{BASE}/channels", wait_until="domcontentloaded")
    await ensure_logged_in(page, "while opening channels list")
    connect_link = page.locator('a[href*="/connect"]').first
    href = await connect_link.get_attribute("href")
    if not href:
        raise CaptureError("channel connect link not found")
    await screenshot(page, "08_channel_connect", href, "Channel 連線設定")


async def screenshot_first_images_page(page) -> None:
    await page.goto(f"{BASE}/products?q=PIM-DEMO", wait_until="domcontentloaded")
    await ensure_logged_in(page, "while opening products list for images capture")
    detail_link = page.locator('table tbody tr:first-child td:first-child a').first
    href = await detail_link.get_attribute("href")
    if not href:
        raise CaptureError("product detail link not found for images capture")
    product_id = href.rstrip("/").split("/")[-1]
    await screenshot(page, "09_images_manage", f"/images/products/{product_id}", "商品圖片管理")


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _seed()
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path=CHROME_EXECUTABLE,
        )
        context = await browser.new_context(viewport={"width": 1440, "height": 980})
        page = await context.new_page()

        await screenshot(page, "01_login", "/login", "登入頁面", require_auth=False)
        await login(page)

        pages = [
            ("02_dashboard", "/?demo=1", "儀表板"),
            ("03_products_list", "/products?q=PIM-DEMO", "商品列表"),
            ("04_product_new", "/products/new", "新增商品"),
            ("05_attributes_list", "/attributes", "屬性管理"),
            ("06_variants_list", "/variants", "變體列表"),
            ("07_channels_list", "/channels", "Channels 列表"),
            ("10_suppliers_list", "/suppliers", "供應商列表"),
            ("11_users_list", "/users", "使用者管理"),
        ]
        for name, url, label in pages:
            await screenshot(page, name, url, label)
        await screenshot_product_detail(page)
        await screenshot_first_channel_connect(page)
        await screenshot_first_images_page(page)

        await browser.close()
        print(f"\nAll screenshots saved to {OUT}/")


if __name__ == "__main__":
    asyncio.run(main())
