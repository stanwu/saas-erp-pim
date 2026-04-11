from functools import lru_cache
from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parent.parent
INSECURE_SECRET_KEYS = {
    "dev-secret-key",
    "dev-secret-key-change-in-prod",
    "change-me-in-production",
}
INSECURE_CSRF_SECRETS = {
    "csrf-secret-change-in-prod",
    "change-me-in-production",
}


class Settings:
    def __init__(self) -> None:
        self.app_name = "Stanis PIM"
        self.secret_key = os.getenv("ERP_PIM_SECRET_KEY", "dev-secret-key-change-in-prod")
        self.csrf_secret = os.getenv("ERP_PIM_CSRF_SECRET", "csrf-secret-change-in-prod")
        self.environment = os.getenv("ERP_PIM_ENV", "development").strip().lower()
        self.database_url = os.getenv(
            "ERP_PIM_DATABASE_URL",
            f"sqlite:///{BASE_DIR / 'erp_pim.db'}",
        )
        self.admin_username = os.getenv("ERP_PIM_ADMIN_USERNAME", "admin")
        self.admin_password = os.getenv("ERP_PIM_ADMIN_PASSWORD", "admin@12345")
        self.seed_demo_data = os.getenv("ERP_PIM_SEED_DEMO_DATA", "true").strip().lower() == "true"
        self.upload_dir = os.getenv("ERP_PIM_UPLOAD_DIR", "app/static/uploads")
        self.max_upload_mb = int(os.getenv("ERP_PIM_MAX_UPLOAD_MB", "5"))
        self.page_size = 20
        self.validate_security()

    @property
    def is_production_like(self) -> bool:
        return self.environment in {"production", "staging"}

    @property
    def session_https_only(self) -> bool:
        return self.is_production_like

    def validate_security(self) -> None:
        if not self.is_production_like:
            return

        if self.secret_key in INSECURE_SECRET_KEYS:
            raise ValueError("ERP_PIM_SECRET_KEY must be set to a strong unique value in production.")
        if self.csrf_secret in INSECURE_CSRF_SECRETS:
            raise ValueError("ERP_PIM_CSRF_SECRET must be set to a strong unique value in production.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
