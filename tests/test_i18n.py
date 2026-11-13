"""Тесты полноты и корректности переводов интерфейса."""

import string

import pytest

from exam_tickets.i18n import STRINGS, t
from exam_tickets.models import Lang


def test_every_key_has_both_translations() -> None:
    for key, translations in STRINGS.items():
        assert set(translations) == set(Lang), key


def test_no_translation_is_blank() -> None:
    for key, translations in STRINGS.items():
        for lang, text in translations.items():
            assert text.strip(), f"{key}/{lang}"


def test_placeholders_match_between_languages() -> None:
    def fields(text: str) -> set[str]:
        return {name for _, name, _, _ in string.Formatter().parse(text) if name}

    for key, translations in STRINGS.items():
        assert fields(translations[Lang.RU]) == fields(translations[Lang.KK]), key


def test_t_formats_placeholders() -> None:
    assert "системный" in t("empty_level", Lang.RU, levels="системный")


def test_t_unknown_key_raises() -> None:
    with pytest.raises(KeyError):
        t("нет_такого", Lang.RU)
