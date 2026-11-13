"""Тесты реестра предметов и межфайловых правил §3.5."""

import copy
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest

from exam_tickets.dataset import check_chapters, find_id_mismatches, load_registry
from exam_tickets.exceptions import DataError
from exam_tickets.models import LEVEL_HEADINGS, ChapterFile, Lang, SubjectRegistry


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


# --- межфайловые правила §3.5 пп. 2, 3, 4, 7 -------------------------------

REGISTRY = SubjectRegistry.model_validate(
    {
        "subjects": [
            {
                "slug": "docker",
                "folder": "Docker",
                "label": "Docker",
                "id_prefix": "D",
                "languages": ["ru", "kk"],
            }
        ]
    }
)


def kazakh(data: dict[str, Any]) -> dict[str, Any]:
    """Превращает «сырые» данные русской главы в казахскую версию."""
    result = copy.deepcopy(data)
    result["language"] = "kk"
    for key, level in result["levels"].items():
        level["heading"] = LEVEL_HEADINGS[Lang.KK][
            next(k for k in LEVEL_HEADINGS[Lang.RU] if k.value == key)
        ]
    return result


def test_valid_chapters_pass(chapter_data: dict[str, Any]) -> None:
    check_chapters(
        chapters=[ChapterFile.model_validate(chapter_data)], registry=REGISTRY
    )


def test_unknown_subject_is_rejected(chapter_data: dict[str, Any]) -> None:
    chapter_data["subject"] = "ghost"
    with pytest.raises(DataError, match="не найден"):
        check_chapters(
            chapters=[ChapterFile.model_validate(chapter_data)], registry=REGISTRY
        )


def test_language_outside_subject_languages_is_rejected(
    chapter_data: dict[str, Any],
) -> None:
    registry = SubjectRegistry.model_validate(
        {
            "subjects": [
                {
                    "slug": "docker",
                    "folder": "D",
                    "label": "D",
                    "id_prefix": "D",
                    "languages": ["kk"],
                }
            ]
        }
    )
    with pytest.raises(DataError, match="не входит в языки"):
        check_chapters(
            chapters=[ChapterFile.model_validate(chapter_data)], registry=registry
        )


def test_duplicate_file_is_rejected(chapter_data: dict[str, Any]) -> None:
    chapter = ChapterFile.model_validate(chapter_data)
    with pytest.raises(DataError, match="дубликат"):
        check_chapters(chapters=[chapter, chapter], registry=REGISTRY)


def test_duplicate_id_is_rejected(chapter_data: dict[str, Any]) -> None:
    questions = chapter_data["levels"]["cognitive"]["questions"]
    questions.append(dict(questions[0]))
    with pytest.raises(DataError, match="повторно"):
        check_chapters(
            chapters=[ChapterFile.model_validate(chapter_data)], registry=REGISTRY
        )


@pytest.mark.parametrize("bad_id", ["X03-К-01", "D04-К-01", "D03-Ф-01", "D03-K-01"])
def test_id_not_matching_subject_chapter_or_level_is_rejected(
    chapter_data: dict[str, Any], bad_id: str
) -> None:
    chapter_data["levels"]["cognitive"]["questions"][0]["id"] = bad_id
    with pytest.raises(DataError, match="не соответствует"):
        check_chapters(
            chapters=[ChapterFile.model_validate(chapter_data)], registry=REGISTRY
        )


def test_same_ids_in_both_languages_are_not_a_mismatch(
    chapter_data: dict[str, Any],
) -> None:
    chapters = [
        ChapterFile.model_validate(d) for d in (chapter_data, kazakh(chapter_data))
    ]
    assert find_id_mismatches(chapters=chapters) == []


def test_different_ids_in_languages_are_a_mismatch(
    chapter_data: dict[str, Any],
) -> None:
    other = kazakh(chapter_data)
    other["levels"]["cognitive"]["questions"][0]["id"] = "D03-К-02"
    chapters = [ChapterFile.model_validate(d) for d in (chapter_data, other)]
    assert find_id_mismatches(chapters=chapters) == [("docker", 3)]


def test_missing_language_version_is_a_mismatch(chapter_data: dict[str, Any]) -> None:
    other = kazakh(chapter_data)
    other.update(file_chapter=4, chapters=[4])
    for level in other["levels"].values():
        for question in level["questions"]:
            question["id"] = question["id"].replace("03", "04")
    chapters = [ChapterFile.model_validate(d) for d in (chapter_data, other)]
    assert find_id_mismatches(chapters=chapters) == [("docker", 3), ("docker", 4)]
