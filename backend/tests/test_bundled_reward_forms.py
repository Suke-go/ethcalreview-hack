from __future__ import annotations

import filecmp
from pathlib import Path
from shutil import rmtree

import pytest

from app.config import app_config
from app.services.official_document_service import (
    OFFICIAL_OUTPUTS,
    default_official_document_types,
    render_official_document,
)
from app.services.official_template_registry import get_official_templates_dir


@pytest.fixture
def output_dir() -> Path:
    path = Path(".pytest_tmp") / "bundled_reward_forms"
    if path.exists():
        rmtree(path)
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        if path.exists():
            rmtree(path)


def test_reward_documents_are_gated_by_reward_enabled() -> None:
    with_reward = default_official_document_types({"reward": {"enabled": True}})
    assert "honorarium_request" in with_reward
    assert "honorarium_payment_request" in with_reward
    assert "honorarium_rationale" in with_reward

    without_reward = default_official_document_types({"reward": {"enabled": False}})
    assert "honorarium_request" not in without_reward
    assert "honorarium_payment_request" not in without_reward


@pytest.mark.parametrize("document_type", ["honorarium_request", "honorarium_payment_request"])
def test_copy_kind_forms_are_bundled_byte_identical(document_type: str, output_dir: Path) -> None:
    """マクロ付き様式などはそのまま同梱する（バイナリ完全一致＝マクロ/数式/書式が保持される）。"""
    kind, source_name, output_name = OFFICIAL_OUTPUTS[document_type]
    assert kind == "copy"

    source = get_official_templates_dir() / source_name
    assert source.exists(), f"bundled source missing: {source}"

    out = render_official_document(document_type, {}, output_dir)
    assert out.exists()
    assert out.name == output_name
    # コピー方式は一切書き換えないのでバイト完全一致でなければならない
    assert filecmp.cmp(source, out, shallow=False)
