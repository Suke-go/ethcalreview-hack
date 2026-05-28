from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from pydantic_settings import BaseSettings


class LaboratorySettings(BaseModel):
    name: str = "善甫研究室"
    building: str = "総合研究棟B"
    room: str = "3M211"


class InvestigatorSettings(BaseModel):
    name: str = "善甫 啓一"
    affiliation: str = "筑波大学 システム情報系"
    position: str = "准教授"
    email: str = "zempo@iit.tsukuba.ac.jp"
    phone: str = "029-853-5338"


class ExperimentConductorSettings(BaseModel):
    phone: str = "029-853-6185"


class EthicsCommitteeSettings(BaseModel):
    name: str = "筑波大学 システム情報系 研究倫理委員会"
    office: str = "システム情報エリア支援室"
    phone: str = "029-853-4989"


class BudgetSettings(BaseModel):
    source: str = "運営費交付金"
    project_name: str = ""
    reward_per_person: int = 800
    reward_type: str = "Amazonギフトカード（Eメールタイプ）"
    hourly_rate: int = 1000


class InsuranceSettings(BaseModel):
    type: str = "傷害保険"
    coverage: str = "実験参加者全員"


class UserSettings(BaseModel):
    laboratory: LaboratorySettings = LaboratorySettings()
    submission_destination: str = "システム情報系長　殿"
    principal_investigator: InvestigatorSettings = InvestigatorSettings()
    experiment_conductor: ExperimentConductorSettings = ExperimentConductorSettings()
    ethics_committee: EthicsCommitteeSettings = EthicsCommitteeSettings()
    budget: BudgetSettings = BudgetSettings()
    insurance: InsuranceSettings = InsuranceSettings()


def _get_bundle_root() -> Path:
    """同梱データ (templates, schemas, presets) のルートを返す。

    - PyInstaller bundle 内 (frozen): sys._MEIPASS / 同梱データはここに展開される
    - 通常の Python 実行: backend/ ディレクトリ
    """
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).parent.parent  # = backend/


def _get_data_dir() -> Path:
    """ユーザー固有データ (settings.json, sessions, output, lab_defaults.json) の保存先。

    - ETHICS_DATA_DIR 環境変数で明示できる (Tauri / Docker で外部ボリュームに向ける)
    - 未設定時:
        * frozen (PyInstaller 単体実行): 実行ファイルの隣 (ポータブル動作)
        * 通常実行: backend/ ディレクトリ
          (既存リポジトリで sessions / output / settings.json が backend/ 直下に置かれている前提)
    """
    if data_dir := os.environ.get("ETHICS_DATA_DIR"):
        return Path(data_dir)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent  # = backend/


_BUNDLE_ROOT = _get_bundle_root()


class AppConfig(BaseSettings):
    project_root: Path = Path(__file__).parent.parent.parent
    bundle_root: Path = _BUNDLE_ROOT
    data_dir: Path = _get_data_dir()

    settings_file: Path = data_dir / "settings.json"
    lab_defaults_file: Path = data_dir / "lab_defaults.json"

    templates_dir: Path = _BUNDLE_ROOT / "templates"
    presets_dir: Path = _BUNDLE_ROOT / "presets"
    schemas_dir: Path = _BUNDLE_ROOT / "schemas"
    user_presets_dir: Path = data_dir / "presets"
    output_dir: Path = data_dir / "output"
    sessions_dir: Path = data_dir / "sessions"

    model_config = ConfigDict(env_prefix="ERH_")

    def ensure_dirs(self) -> None:
        for dir_path in [self.output_dir, self.sessions_dir, self.user_presets_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)


def load_user_settings(config: AppConfig) -> UserSettings:
    if config.settings_file.exists():
        with open(config.settings_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return UserSettings(**data)
    return UserSettings()


def save_user_settings(settings: UserSettings, config: AppConfig) -> None:
    with open(config.settings_file, "w", encoding="utf-8") as f:
        json.dump(settings.model_dump(), f, ensure_ascii=False, indent=2)


def load_lab_defaults(config: AppConfig) -> dict:
    if config.lab_defaults_file.exists():
        with open(config.lab_defaults_file, "r", encoding="utf-8") as f:
            return json.load(f)

    fallback = config.project_root / "backend" / "lab_defaults.json"
    if fallback.exists():
        with open(fallback, "r", encoding="utf-8") as f:
            return json.load(f)

    return {}


app_config = AppConfig()
app_config.ensure_dirs()
