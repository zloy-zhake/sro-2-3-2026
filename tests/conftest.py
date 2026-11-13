"""Общие фикстуры тестов."""

from typing import Any

import pytest

from exam_tickets.models import (
    LEVEL_HEADINGS,
    LEVEL_LETTERS,
    LEVEL_ORDER,
    LEVEL_POINTS,
    Lang,
)


@pytest.fixture
def chapter_data() -> dict[str, Any]:
    """Возвращает корректные «сырые» данные файла главы (docker, ru, глава 3).

    Тесты портят по одному полю и проверяют, что валидация это ловит.

    Returns:
        Словарь, пригодный для ``ChapterFile.model_validate``.
    """
    levels: dict[str, Any] = {}
    for key in LEVEL_ORDER:
        levels[key.value] = {
            "heading": LEVEL_HEADINGS[Lang.RU][key],
            "points": LEVEL_POINTS[key],
            "instructions": "Инструкция.\n",
            "questions": [
                {"id": f"D03-{LEVEL_LETTERS[key]}-01", "text": "Вопрос?\n"},
            ],
        }
    return {
        "subject": "docker",
        "language": "ru",
        "file_chapter": 3,
        "chapters": [3],
        "chapter_titles": ["Building your own Docker images"],
        "levels": levels,
    }
