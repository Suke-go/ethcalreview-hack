"""
研究室デフォルト設定管理

lab_defaults.jsonの読み込み・保存機能を提供
"""

from pathlib import Path
import json
from typing import Dict, Any
from pydantic import BaseModel
from datetime import datetime
from app.logger import get_logger

logger = get_logger(__name__)


class DomainHead(BaseModel):
    """域長情報"""
    title: str
    name: str
    updated_at: str
    editable: bool = True


class LabDefaults(BaseModel):
    """研究室デフォルト設定"""
    lab_info: Dict[str, Any]
    application_defaults: Dict[str, Any]
    domain_head: DomainHead
    data_management_defaults: Dict[str, Any]


def get_lab_defaults_path() -> Path:
    """lab_defaults.jsonのパスを取得"""
    return Path(__file__).parent.parent.parent / "lab_defaults.json"


def load_lab_defaults() -> LabDefaults:
    """
    lab_defaults.jsonを読み込み
    
    Returns:
        LabDefaults
    """
    defaults_path = get_lab_defaults_path()
    
    if not defaults_path.exists():
        logger.warning(f"lab_defaults.json が見つかりません: {defaults_path}")
        # デフォルト値を返す
        return _get_empty_defaults()
    
    try:
        with open(defaults_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return LabDefaults(**data)
    
    except Exception as e:
        logger.error(f"lab_defaults.json 読み込みエラー: {e}")
        # エラー時もデフォルト値を返す（例外を上げない）
        return _get_empty_defaults()


def _get_empty_defaults() -> LabDefaults:
    """空のデフォルト値を生成"""
    return LabDefaults(
        lab_info={
            "name": "",
            "pi_name": "",
            "pi_affiliation": "",
            "pi_position": "",
            "pi_email": "",
            "pi_phone": "",
            "lab_room": "",
            "experimental_rooms": []
        },
        application_defaults={},
        domain_head=DomainHead(
            title="",
            name="",
            updated_at=datetime.now().isoformat()
        ),
        data_management_defaults={}
    )


def save_lab_defaults(defaults: LabDefaults) -> None:
    """
    lab_defaults.jsonに保存
    
    Args:
        defaults: 保存するデフォルト設定
    """
    defaults_path = get_lab_defaults_path()
    
    try:
        with open(defaults_path, "w", encoding="utf-8") as f:
            json.dump(
                defaults.model_dump(),
                f,
                ensure_ascii=False,
                indent=2
            )
        logger.info(f"lab_defaults.json を保存しました: {defaults_path}")
    
    except Exception as e:
        logger.error(f"lab_defaults.json 保存エラー: {e}")
        raise


def update_domain_head(title: str, name: str) -> DomainHead:
    """
    域長情報を更新
    
    Args:
        title: 域長の役職名
        name: 域長の氏名
    
    Returns:
        更新後のDomainHead
    """
    defaults = load_lab_defaults()
    defaults.domain_head.title = title
    defaults.domain_head.name = name
    defaults.domain_head.updated_at = datetime.now().isoformat()
    
    save_lab_defaults(defaults)
    
    logger.info(f"域長情報を更新: {title} - {name}")
    return defaults.domain_head
