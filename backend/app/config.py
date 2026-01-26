"""
設定管理
"""
from pydantic_settings import BaseSettings
from pydantic import BaseModel
from pathlib import Path
import json
import os
from typing import Optional


class LaboratorySettings(BaseModel):
    name: str = "善甫研究室"
    building: str = "総合研究棟B"
    room: str = "0911"


class InvestigatorSettings(BaseModel):
    name: str = "善甫 啓一"
    affiliation: str = "筑波大学 システム情報系"
    position: str = "准教授"
    email: str = "zempo@iit.tsukuba.ac.jp"
    phone: str = "029-853-5338"


class ExperimentConductorSettings(BaseModel):
    phone: str = "029-853-6185"


class EthicsCommitteeSettings(BaseModel):
    name: str = "筑波大学 システム情報系研究倫理委員会事務局"
    office: str = "システム情報エリア支援室"
    phone: str = "029-853-4989"


class BudgetSettings(BaseModel):
    source: str = "運営費交付金"
    project_name: str = ""
    reward_per_person: int = 800
    reward_type: str = "Amazonギフトカード（Eメールタイプ）"
    hourly_rate: int = 1000  # 60分1000円基準


class InsuranceSettings(BaseModel):
    type: str = "傷害保険"
    coverage: str = "実験参加者全員"


class UserSettings(BaseModel):
    """ユーザー設定（ローカルJSONに保存）"""
    laboratory: LaboratorySettings = LaboratorySettings()
    submission_destination: str = "システム情報系"
    principal_investigator: InvestigatorSettings = InvestigatorSettings()
    experiment_conductor: ExperimentConductorSettings = ExperimentConductorSettings()
    ethics_committee: EthicsCommitteeSettings = EthicsCommitteeSettings()
    budget: BudgetSettings = BudgetSettings()
    insurance: InsuranceSettings = InsuranceSettings()


def _get_data_dir() -> Path:
    """
    データディレクトリを取得
    
    優先順位:
    1. ETHICS_DATA_DIR 環境変数（Electron設定）
    2. プロジェクトルート（開発用）
    """
    if data_dir := os.environ.get("ETHICS_DATA_DIR"):
        return Path(data_dir)
    return Path(__file__).parent.parent.parent


class AppConfig(BaseSettings):
    """アプリケーション設定"""
    # プロジェクトルート（main.pyの親の親ディレクトリ）
    project_root: Path = Path(__file__).parent.parent.parent
    
    # データディレクトリ（Electron時は別ディレクトリ）
    data_dir: Path = _get_data_dir()
    
    # 設定ファイル
    settings_file: Path = data_dir / "settings.json"
    lab_defaults_file: Path = data_dir / "lab_defaults.json"
    
    # ディレクトリ
    templates_dir: Path = project_root / "backend" / "templates"
    output_dir: Path = data_dir / "output"
    sessions_dir: Path = data_dir / "sessions"
    schemas_dir: Path = project_root / "backend" / "app" / "schemas"
    
    class Config:
        env_prefix = "ERH_"
    
    def ensure_dirs(self):
        """必要なディレクトリを作成"""
        for dir_path in [self.output_dir, self.sessions_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)


def load_user_settings(config: AppConfig) -> UserSettings:
    """ユーザー設定をJSONから読み込み"""
    if config.settings_file.exists():
        with open(config.settings_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return UserSettings(**data)
    return UserSettings()


def save_user_settings(settings: UserSettings, config: AppConfig) -> None:
    """ユーザー設定をJSONに保存"""
    with open(config.settings_file, "w", encoding="utf-8") as f:
        json.dump(settings.model_dump(), f, ensure_ascii=False, indent=2)


def load_lab_defaults(config: AppConfig) -> dict:
    """lab_defaults.jsonを読み込み（Electron用外部ファイル対応）"""
    # ユーザーデータディレクトリを優先
    if config.lab_defaults_file.exists():
        with open(config.lab_defaults_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    # フォールバック: backend/lab_defaults.json
    fallback = config.project_root / "backend" / "lab_defaults.json"
    if fallback.exists():
        with open(fallback, "r", encoding="utf-8") as f:
            return json.load(f)
    
    return {}


# グローバル設定インスタンス
app_config = AppConfig()
app_config.ensure_dirs()

