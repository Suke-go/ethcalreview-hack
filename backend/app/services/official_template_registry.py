from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import app_config


def get_official_templates_dir() -> Path:
    return app_config.templates_dir / "official"


def get_manifest_path() -> Path:
    return get_official_templates_dir() / "manifest.json"


def load_template_manifest() -> dict[str, Any]:
    manifest_path = get_manifest_path()
    if not manifest_path.exists():
        return {"version": "", "templates": {}}
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)

