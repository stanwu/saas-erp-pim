"""Build a release zip with seeded demo data for first-run evaluation."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"


def _copy_tree(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".DS_Store"))


def _write_release_files(bundle_dir: Path) -> None:
    run_script = """#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001
"""
    env_example = """ERP_PIM_SECRET_KEY=change-me-in-production
ERP_PIM_CSRF_SECRET=change-me-in-production
ERP_PIM_DATABASE_URL=sqlite:///./erp_pim.db
ERP_PIM_ADMIN_USERNAME=admin
ERP_PIM_ADMIN_PASSWORD=admin@12345
ERP_PIM_SEED_DEMO_DATA=true
ERP_PIM_ENV=development
ERP_PIM_UPLOAD_DIR=app/static/uploads
ERP_PIM_MAX_UPLOAD_MB=5
"""
    quick_start = """# ERP PIM Release Bundle

This package includes a seeded `erp_pim.db` so the first run already contains demo products,
attributes, variants, images, and channel setup examples.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Open `http://127.0.0.1:8001/login`

Default account:

- Username: `admin`
- Password: `admin@12345`

If you need to regenerate the sample database, delete `erp_pim.db` and start the app again,
or run the source-repo seed script before building a new bundle.
"""
    (bundle_dir / "run.sh").write_text(run_script, encoding="utf-8")
    (bundle_dir / "run.sh").chmod(0o755)
    (bundle_dir / ".env.example").write_text(env_example, encoding="utf-8")
    (bundle_dir / "QUICKSTART.md").write_text(quick_start, encoding="utf-8")


def _seed_release_database(bundle_dir: Path) -> None:
    db_path = bundle_dir / "erp_pim.db"
    upload_dir = bundle_dir / "app" / "static" / "uploads"
    if upload_dir.exists():
        shutil.rmtree(upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(ROOT),
            "ERP_PIM_DATABASE_URL": f"sqlite:///{db_path}",
            "ERP_PIM_UPLOAD_DIR": str(upload_dir),
            "ERP_PIM_SECRET_KEY": "dev-secret-key-change-in-prod",
            "ERP_PIM_CSRF_SECRET": "csrf-secret-change-in-prod",
            "ERP_PIM_ENV": "development",
            "ERP_PIM_SEED_DEMO_DATA": "true",
            "ERP_PIM_ADMIN_USERNAME": "admin",
            "ERP_PIM_ADMIN_PASSWORD": "admin@12345",
        }
    )
    subprocess.run([sys.executable, str(ROOT / "scripts" / "seed_demo_data.py")], check=True, cwd=ROOT, env=env)
    for suffix in ("-wal", "-shm"):
        sidecar = db_path.with_name(db_path.name + suffix)
        if sidecar.exists():
            sidecar.unlink()


def build() -> Path:
    version = os.environ.get("GITHUB_REF_NAME") or os.environ.get("RELEASE_VERSION") or "dev"
    bundle_name = f"erp-pim-{version}"
    bundle_dir = BUILD_DIR / bundle_name

    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    DIST_DIR.mkdir(exist_ok=True)
    BUILD_DIR.mkdir(exist_ok=True)

    _copy_tree(ROOT / "app", bundle_dir / "app")
    shutil.copy2(ROOT / "requirements.txt", bundle_dir / "requirements.txt")
    shutil.copy2(ROOT / "README.md", bundle_dir / "README.md")
    shutil.copy2(ROOT / "LICENSE", bundle_dir / "LICENSE")
    _write_release_files(bundle_dir)
    _seed_release_database(bundle_dir)

    archive = shutil.make_archive(str(DIST_DIR / bundle_name), "zip", BUILD_DIR, bundle_name)
    print(f"Release bundle created: {archive}")
    return Path(archive)


if __name__ == "__main__":
    build()
