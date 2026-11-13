"""Тесты интерфейса через ``streamlit.testing.v1.AppTest`` (план §1.7)."""

import shutil
from collections.abc import Iterator
from importlib.resources import files
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import exam_tickets.app as app_module
from exam_tickets.convert import convert
from exam_tickets.dataset import Dataset
from exam_tickets.models import Lang
from tests.builders import build_source

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = str(ROOT / "streamlit_app.py")
PACKAGED = Path(str(files("exam_tickets").joinpath("data")))


@pytest.fixture(autouse=True)
def _fresh_cache() -> Iterator[None]:
    """Очищает кэш данных до и после теста: он живёт на уровне процесса."""
    st.cache_resource.clear()
    yield
    st.cache_resource.clear()


def new_app() -> AppTest:
    """Запускает приложение и возвращает первый прогон."""
    return AppTest.from_file(SCRIPT, default_timeout=10).run()


def pick(at: AppTest, subject: str = "docker", stage: str = "СРО-2") -> AppTest:
    """Выбирает предмет и этап."""
    at.selectbox(key="subject").select(subject).run()
    return at.radio(key="stage").set_value(stage).run()


def generate(at: AppTest) -> AppTest:
    """Нажимает кнопку формирования билета."""
    return at.button(key="generate").click().run()


def bodies(at: AppTest) -> list[str]:
    """HTML-тела всех ``st.html`` на странице."""
    return [element.proto.body for element in at.get("html")]


# --- форма ----------------------------------------------------------------


def test_app_starts_without_exceptions() -> None:
    assert not new_app().exception


def test_form_is_on_screen_with_all_four_widgets() -> None:
    at = new_app()
    assert len(at.selectbox) == 2
    assert len(at.radio) == 2


def test_nothing_is_selected_on_open() -> None:
    at = new_app()
    assert at.selectbox(key="subject").value is None
    assert at.radio(key="stage").value is None
    assert at.radio(key="ui_lang").value == Lang.RU


def test_question_language_is_disabled_and_empty_before_subject() -> None:
    at = new_app()
    assert at.selectbox(key="qlang").disabled
    assert at.selectbox(key="qlang").value is None


def test_button_is_disabled_until_subject_and_stage_chosen() -> None:
    at = new_app()
    assert at.button(key="generate").disabled
    at.selectbox(key="subject").select("docker").run()
    assert at.button(key="generate").disabled
    at.radio(key="stage").set_value("СРО-2").run()
    assert not at.button(key="generate").disabled


def test_single_language_subject_is_fixed_and_disabled() -> None:
    at = new_app()
    at.selectbox(key="subject").select("java").run()
    assert at.session_state["qlang"] == Lang.KK
    assert at.selectbox(key="qlang").disabled


def test_docker_defaults_to_russian_and_is_not_disabled() -> None:
    at = new_app()
    at.selectbox(key="subject").select("docker").run()
    assert at.session_state["qlang"] == Lang.RU
    assert not at.selectbox(key="qlang").disabled


# --- билет ------------------------------------------------------------------


def test_button_label_changes_after_first_ticket() -> None:
    at = pick(new_app())
    assert at.button(key="generate").label == "Сформировать задание"
    at = generate(at)
    assert at.button(key="generate").label == "Сгенерировать другое задание"


def test_ticket_shows_three_questions_in_level_order() -> None:
    at = generate(pick(new_app()))
    headings = [b for b in bodies(at) if "УРОВЕНЬ" in b]
    assert [h.split("УРОВЕНЬ")[0].split(">")[-1].strip() for h in headings] == [
        "КОГНИТИВНЫЙ",
        "ФУНКЦИОНАЛЬНЫЙ",
        "СИСТЕМНЫЙ",
    ]


def test_ticket_shows_id_and_chapter_in_question_language() -> None:
    at = generate(pick(new_app(), subject="java", stage="СӨЖ-2"))
    references = [b for b in bodies(at) if " · " in b and "тарау" in b]
    assert len(references) == 3


def test_next_ticket_has_no_repeats_of_same_level() -> None:
    at = generate(pick(new_app()))
    first = [i.question.id for i in at.session_state["ticket"].items]
    for _ in range(5):
        at = generate(at)
        second = [i.question.id for i in at.session_state["ticket"].items]
        assert all(a != b for a, b in zip(first, second, strict=True))
        first = second


@pytest.mark.parametrize("change", ["subject", "qlang", "stage"])
def test_ticket_is_hidden_when_selection_changes(change: str) -> None:
    at = generate(pick(new_app()))
    assert at.session_state["ticket"] is not None
    if change == "subject":
        at.selectbox(key="subject").select("fsharp").run()
    elif change == "qlang":
        at.selectbox(key="qlang").select(Lang.KK).run()
    else:
        at.radio(key="stage").set_value("СРО-3").run()
    assert at.session_state["ticket"] is None
    # При смене языка вопросов интерфейс следует за ним, поэтому подпись казахская.
    expected = "Тапсырма құрастыру" if change == "qlang" else "Сформировать задание"
    assert at.button(key="generate").label == expected


# --- язык интерфейса --------------------------------------------------------


def test_ui_language_change_keeps_ticket_and_form() -> None:
    at = generate(pick(new_app()))
    ticket = at.session_state["ticket"]
    at.radio(key="ui_lang").set_value("Қазақша").run()
    assert at.session_state["ticket"] is ticket
    assert at.session_state["subject"] == "docker"
    assert at.session_state["qlang"] == Lang.RU
    assert at.session_state["stage"] == "sro2"
    assert at.selectbox(key="subject").label == "Пән"
    assert at.button(key="generate").label == "Басқа тапсырма жасау"


def test_ui_language_follows_question_language_until_manual_choice() -> None:
    at = new_app()
    at.selectbox(key="subject").select("java").run()
    assert at.session_state["ui_lang"] == Lang.KK
    at.selectbox(key="subject").select("fsharp").run()
    assert at.session_state["ui_lang"] == Lang.RU


def test_ui_language_follows_qlang_change() -> None:
    at = new_app()
    at.selectbox(key="subject").select("docker").run()
    at.selectbox(key="qlang").select(Lang.KK).run()
    assert at.session_state["ui_lang"] == Lang.KK


def test_manual_ui_language_choice_is_sticky() -> None:
    at = new_app()
    at.selectbox(key="subject").select("docker").run()
    at.radio(key="ui_lang").set_value("Қазақша").run()
    at.selectbox(key="subject").select("fsharp").run()
    assert at.session_state["ui_lang"] == Lang.KK
    at.selectbox(key="subject").select("docker").run()
    at.selectbox(key="qlang").select(Lang.RU).run()
    assert at.session_state["ui_lang"] == Lang.KK


def test_ticket_content_stays_in_question_language_when_ui_changes() -> None:
    at = generate(pick(new_app(), subject="java", stage="СӨЖ-2"))
    at.radio(key="ui_lang").set_value("Русский").run()
    assert any("ДЕҢГЕЙ" in b for b in bodies(at))


# --- ошибки данных ----------------------------------------------------------


def test_data_error_shows_message_instead_of_traceback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(app_module, "DATA_ROOT", tmp_path)
    at = new_app()
    assert not at.exception
    assert [e.value for e in at.error] == [
        "Не удалось загрузить вопросы. Подробности записаны в журнал."
    ]


def test_unexpected_loader_error_shows_message_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(**_: object) -> None:
        raise RuntimeError("неожиданно")

    monkeypatch.setattr(Dataset, "load", boom)
    at = new_app()
    assert not at.exception
    assert len(at.error) == 1


def test_empty_level_shows_warning_and_disables_button(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "data"
    shutil.copytree(PACKAGED, root)
    for number in range(6, 12):
        (root / "java" / f"ch{number:02d}.kk.yaml").unlink()
    monkeypatch.setattr(app_module, "DATA_ROOT", root)
    at = pick(new_app(), subject="java", stage="СӨЖ-3")
    assert at.button(key="generate").disabled
    assert len(at.warning) == 1
    assert "когнитивтік" in at.warning[0].value


# --- экранирование (§8 п. 5) ---------------------------------------------


def test_special_characters_are_escaped_end_to_end(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    questions = tmp_path / "questions"
    (questions / "Docker").mkdir(parents=True)
    source = build_source().replace("Вопрос", "$x <tag> # Вопрос")
    (questions / "Docker" / "ch3_questions.txt").write_text(source, encoding="utf-8")
    data = tmp_path / "data"
    data.mkdir()
    (data / "subjects.yaml").write_text(
        "subjects:\n  - slug: docker\n    folder: Docker\n    label: Docker\n"
        "    id_prefix: D\n    languages: [ru]\n",
        encoding="utf-8",
    )
    convert(questions_dir=questions, data_dir=data)
    monkeypatch.setattr(app_module, "DATA_ROOT", data)
    at = generate(pick(new_app()))
    page = "\n".join(bodies(at))
    assert "$x &lt;tag&gt; # Вопрос" in page
    assert "<tag>" not in page
