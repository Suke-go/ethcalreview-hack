from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.config import AppConfig, app_config


class SubmissionPreset(BaseModel):
    id: str
    label: str
    recipient: str = ""
    committee_name: str = ""
    office_name: str = ""
    office_tel: str = ""
    default_affiliation_label: str = ""
    domain_head_candidates: list[dict[str, str]] = Field(default_factory=list)
    enabled: bool = True
    version: int = 1
    updated_at: str = ""


class InvestigatorPreset(BaseModel):
    id: str
    label: str
    name: str = ""
    affiliation: str = ""
    position: str = ""
    email: str = ""
    tel: str = ""
    default_rooms: list[str] = Field(default_factory=list)
    default_budget_ids: list[str] = Field(default_factory=list)
    default_submission_preset_id: str = ""
    enabled: bool = True
    version: int = 1
    updated_at: str = ""


class BudgetPreset(BaseModel):
    id: str
    label: str
    source: str = ""
    project_name: str = ""
    reward_per_person: int | None = None
    reward_type: str = ""
    hourly_rate: int | None = None
    enabled: bool = True
    version: int = 1
    updated_at: str = ""


class RoomPreset(BaseModel):
    id: str
    label: str
    rooms: list[str] = Field(default_factory=list)
    enabled: bool = True
    version: int = 1
    updated_at: str = ""


class PresetBundle(BaseModel):
    submission_presets: list[SubmissionPreset] = Field(default_factory=list)
    investigator_presets: list[InvestigatorPreset] = Field(default_factory=list)
    budget_presets: list[BudgetPreset] = Field(default_factory=list)
    room_presets: list[RoomPreset] = Field(default_factory=list)


PRESET_FILES = {
    "submission_presets": "submission_presets.json",
    "investigator_presets": "investigator_presets.json",
    "budget_presets": "budget_presets.json",
    "room_presets": "room_presets.json",
}


PRESET_MODEL_MAP = {
    "submission_presets": SubmissionPreset,
    "investigator_presets": InvestigatorPreset,
    "budget_presets": BudgetPreset,
    "room_presets": RoomPreset,
}


def _load_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Preset file must contain a list: {path}")
    return data


def _merge_by_id(default_items: list[dict[str, Any]], user_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = {item["id"]: deepcopy(item) for item in default_items if isinstance(item, dict) and item.get("id")}
    for item in user_items:
        item_id = item.get("id") if isinstance(item, dict) else None
        if not item_id:
            continue
        merged[item_id] = deepcopy(item)
    return list(merged.values())


def _validate_collection(kind: str, items: list[dict[str, Any]]) -> list[BaseModel]:
    model = PRESET_MODEL_MAP[kind]
    return [model.model_validate(item) for item in items]


def load_preset_bundle(config: AppConfig = app_config) -> PresetBundle:
    data: dict[str, Any] = {}
    for kind, filename in PRESET_FILES.items():
        default_path = config.presets_dir / filename
        user_path = config.user_presets_dir / filename
        default_items = _load_json(default_path)
        user_items = _load_json(user_path)
        merged_items = _merge_by_id(default_items, user_items)
        data[kind] = _validate_collection(kind, merged_items)
    return PresetBundle(**data)


def save_preset_collection(kind: str, items: list[dict[str, Any]], config: AppConfig = app_config) -> list[BaseModel]:
    if kind not in PRESET_FILES:
        raise ValueError(f"Unknown preset kind: {kind}")
    validated = _validate_collection(kind, items)
    output_path = config.user_presets_dir / PRESET_FILES[kind]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump([item.model_dump() for item in validated], f, ensure_ascii=False, indent=2)
    return validated


def get_enabled_presets(bundle: PresetBundle, kind: str) -> list[BaseModel]:
    items = getattr(bundle, kind)
    return [item for item in items if getattr(item, "enabled", True)]


def get_preset_by_id(bundle: PresetBundle, kind: str, preset_id: str) -> BaseModel | None:
    for item in getattr(bundle, kind):
        if item.id == preset_id and getattr(item, "enabled", True):
            return item
    return None

