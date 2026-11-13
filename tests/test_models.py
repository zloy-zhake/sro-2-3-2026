"""Тесты моделей и правил валидации §3.5, не требующих реестра."""

from typing import Any

import pytest
from pydantic import ValidationError

from exam_tickets.exceptions import DataError
from exam_tickets.models import ChapterFile, Lang, Stage, SubjectRegistry


def test_valid_chapter_file_loads(chapter_data: dict[str, Any]) -> None:
    chapter = ChapterFile.model_validate(chapter_data)
    assert chapter.stage is Stage.SRO2


def test_chapter_six_belongs_to_sro3(chapter_data: dict[str, Any]) -> None:
    chapter_data.update(file_chapter=6, chapters=[6])
    assert ChapterFile.model_validate(chapter_data).stage is Stage.SRO3


def test_unknown_key_is_rejected(chapter_data: dict[str, Any]) -> None:
    chapter_data["tittle"] = "опечатка"
    with pytest.raises(ValidationError):
        ChapterFile.model_validate(chapter_data)


def test_levels_in_wrong_order_are_rejected(chapter_data: dict[str, Any]) -> None:
    levels = chapter_data["levels"]
    chapter_data["levels"] = {
        "functional": levels["functional"],
        "cognitive": levels["cognitive"],
        "systemic": levels["systemic"],
    }
    with pytest.raises(ValidationError, match="порядке"):
        ChapterFile.model_validate(chapter_data)


def test_missing_level_is_rejected(chapter_data: dict[str, Any]) -> None:
    del chapter_data["levels"]["systemic"]
    with pytest.raises(ValidationError, match="порядке"):
        ChapterFile.model_validate(chapter_data)


def test_level_without_questions_is_rejected(chapter_data: dict[str, Any]) -> None:
    chapter_data["levels"]["cognitive"]["questions"] = []
    with pytest.raises(ValidationError, match="хотя бы один вопрос"):
        ChapterFile.model_validate(chapter_data)


def test_wrong_points_are_rejected(chapter_data: dict[str, Any]) -> None:
    chapter_data["levels"]["cognitive"]["points"] = 25
    with pytest.raises(ValidationError, match="баллы"):
        ChapterFile.model_validate(chapter_data)


def test_heading_of_other_language_is_rejected(chapter_data: dict[str, Any]) -> None:
    chapter_data["language"] = "kk"
    with pytest.raises(ValidationError, match="заголовок"):
        ChapterFile.model_validate(chapter_data)


def test_blank_question_text_is_rejected(chapter_data: dict[str, Any]) -> None:
    chapter_data["levels"]["functional"]["questions"][0]["text"] = "  \n"
    with pytest.raises(ValidationError, match="текст вопроса"):
        ChapterFile.model_validate(chapter_data)


def test_blank_instructions_are_rejected(chapter_data: dict[str, Any]) -> None:
    chapter_data["levels"]["systemic"]["instructions"] = ""
    with pytest.raises(ValidationError, match="инструкция"):
        ChapterFile.model_validate(chapter_data)


def test_empty_chapters_are_rejected(chapter_data: dict[str, Any]) -> None:
    chapter_data.update(chapters=[], chapter_titles=[])
    with pytest.raises(ValidationError):
        ChapterFile.model_validate(chapter_data)


@pytest.mark.parametrize("number", [0, 12])
def test_chapter_out_of_range_is_rejected(
    chapter_data: dict[str, Any], number: int
) -> None:
    chapter_data.update(file_chapter=number, chapters=[number])
    with pytest.raises(ValidationError, match="диапазоне"):
        ChapterFile.model_validate(chapter_data)


def test_file_chapter_must_be_last_of_range(chapter_data: dict[str, Any]) -> None:
    chapter_data.update(file_chapter=1, chapters=[1, 2], chapter_titles=["Один", "Два"])
    with pytest.raises(ValidationError, match="file_chapter"):
        ChapterFile.model_validate(chapter_data)


def test_titles_count_must_match_chapters(chapter_data: dict[str, Any]) -> None:
    chapter_data.update(file_chapter=2, chapters=[1, 2])
    with pytest.raises(ValidationError, match="chapter_titles"):
        ChapterFile.model_validate(chapter_data)


def test_range_across_stages_is_rejected(chapter_data: dict[str, Any]) -> None:
    chapter_data.update(
        file_chapter=6, chapters=[5, 6], chapter_titles=["Пять", "Шесть"]
    )
    with pytest.raises(ValidationError, match="разных этапах"):
        ChapterFile.model_validate(chapter_data)


def test_chapter_file_is_frozen(chapter_data: dict[str, Any]) -> None:
    chapter = ChapterFile.model_validate(chapter_data)
    with pytest.raises(ValidationError):
        chapter.subject = "java"  # type: ignore[misc] # frozen-модель: проверяем запрет записи


def test_registry_rejects_duplicate_prefix() -> None:
    subject = {
        "slug": "a",
        "folder": "A",
        "label": "A",
        "id_prefix": "X",
        "languages": ["ru"],
    }
    other = {**subject, "slug": "b", "folder": "B"}
    with pytest.raises(ValidationError, match="id_prefix"):
        SubjectRegistry.model_validate({"subjects": [subject, other]})


def test_subject_without_languages_is_rejected() -> None:
    subject = {
        "slug": "a",
        "folder": "A",
        "label": "A",
        "id_prefix": "X",
        "languages": [],
    }
    with pytest.raises(ValidationError, match="хотя бы один язык"):
        SubjectRegistry.model_validate({"subjects": [subject]})


def test_registry_get_unknown_slug_raises_data_error() -> None:
    registry = SubjectRegistry(subjects=[])
    with pytest.raises(DataError):
        registry.get(slug="nope")


def test_lang_values_are_iso_codes() -> None:
    assert [lang.value for lang in Lang] == ["ru", "kk"]
