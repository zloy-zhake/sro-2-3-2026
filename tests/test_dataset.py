"""Тесты загрузки реестра предметов."""

from importlib.resources import files
from pathlib import Path

import pytest

from exam_tickets.dataset import load_registry
from exam_tickets.exceptions import DataError


def test_packaged_registry_has_three_subjects() -> None:
    registry = load_registry(root=files("exam_tickets").joinpath("data"))
    assert [s.slug for s in registry.subjects] == ["java", "fsharp", "docker"]


def test_docker_default_language_is_first_in_registry() -> None:
    registry = load_registry(root=files("exam_tickets").joinpath("data"))
    assert [lang.value for lang in registry.get(slug="docker").languages] == [
        "ru",
        "kk",
    ]


def test_missing_registry_raises_data_error(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="не удалось прочитать"):
        load_registry(root=tmp_path)


def test_broken_yaml_raises_data_error(tmp_path: Path) -> None:
    (tmp_path / "subjects.yaml").write_text(encoding="utf-8", data="subjects: [\n")
    with pytest.raises(DataError, match="не удалось прочитать"):
        load_registry(root=tmp_path)


def test_invalid_registry_raises_data_error(tmp_path: Path) -> None:
    (tmp_path / "subjects.yaml").write_text(encoding="utf-8", data="subjects: 5\n")
    with pytest.raises(DataError, match="валидац"):
        load_registry(root=tmp_path)
