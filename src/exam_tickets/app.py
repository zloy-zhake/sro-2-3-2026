"""Streamlit-интерфейс генератора билетов (требования §5).

Ключ каждого виджета и есть ключ его состояния в ``st.session_state`` — второй
копии значения нет, поэтому смена подписей при смене языка интерфейса не
сбрасывает выбор. В ключи виджетов пишут только колбэки: запись после
отрисовки виджета в том же прогоне запрещена Streamlit.
"""

import html
import logging
import random
from importlib.resources import files
from importlib.resources.abc import Traversable

import streamlit as st

from exam_tickets.dataset import Dataset
from exam_tickets.exceptions import DataError
from exam_tickets.i18n import t
from exam_tickets.models import Lang, Stage
from exam_tickets.render import format_chapter_ref, render_text
from exam_tickets.tickets import (
    PoolItem,
    Ticket,
    build_pool,
    empty_levels,
    generate_ticket,
)

logger = logging.getLogger(name=__name__)

# Корень данных вынесен в константу, чтобы тесты могли подменить его каталогом.
DATA_ROOT: Traversable = files("exam_tickets").joinpath("data")

_STAGES: tuple[Stage, ...] = (Stage.SRO2, Stage.SRO3)
# Казахский идёт первым: он язык интерфейса по умолчанию.
_UI_LANGUAGES: tuple[Lang, ...] = (Lang.KK, Lang.RU)
_DEFAULT_UI_LANG: Lang = Lang.KK


@st.cache_resource
def load_dataset() -> Dataset:
    """Загружает данные один раз на процесс (требования §6.2).

    Стартовое сообщение пишется здесь, а не в ``streamlit_app.py``: тот файл
    выполняется на каждый rerun, а эта функция — один раз на процесс.

    Returns:
        Проверенный набор данных.

    Raises:
        DataError: Если данные не загрузились или не прошли валидацию.
    """
    dataset = Dataset.load(root=DATA_ROOT)
    logger.info(
        "Приложение запущено",
        extra={"subjects": len(dataset.registry.subjects)},
    )
    return dataset


def _ui_lang() -> Lang:
    """Возвращает язык интерфейса, безопасный до инициализации состояния."""
    return Lang(st.session_state.get("ui_lang", _DEFAULT_UI_LANG))


def _resync_stage_widget() -> None:
    """Заставляет фронтенд заново показать выбранный этап после смены подписей.

    При смене языка интерфейса меняются подписи радио, и фронтенд рисует его с
    дефолтом (пустой выбор), хотя на сервере этап сохранён. Присвоение того же
    значения в колбэке заставляет Streamlit отправить фронтенду явное
    ``set_value``. Значение не меняется, ``on_change`` не вызывается.
    """
    st.session_state["stage"] = st.session_state["stage"]


def _apply_qlang(value: Lang | None) -> None:
    """Применяет язык вопросов: сбрасывает билет и ведёт за ним язык интерфейса.

    Программная запись в ``qlang`` не вызывает ``on_change`` виджета, поэтому
    и колбэк предмета, и колбэк языка вопросов проходят через эту функцию.

    Args:
        value: Новый язык вопросов или ``None``.
    """
    st.session_state["qlang"] = value
    st.session_state["ticket"] = None
    if value is not None and not st.session_state["ui_lang_manual"]:
        st.session_state["ui_lang"] = value
        _resync_stage_widget()


def _on_subject() -> None:
    """Смена предмета: язык вопросов — первый из языков предмета (§5.1)."""
    slug = st.session_state["subject"]
    if slug is None:
        _apply_qlang(None)
        return
    subject = load_dataset().registry.get(slug=slug)
    _apply_qlang(subject.languages[0])


def _on_qlang() -> None:
    """Смена языка вопросов."""
    _apply_qlang(st.session_state["qlang"])


def _on_stage() -> None:
    """Смена этапа скрывает билет и сбрасывает историю без повторов."""
    st.session_state["ticket"] = None


def _on_ui_lang() -> None:
    """Ручной выбор языка интерфейса: больше не следуем за языком вопросов."""
    st.session_state["ui_lang_manual"] = True
    _resync_stage_widget()


def _on_generate() -> None:
    """Формирует билет прямо в колбэке кнопки.

    Тогда подпись кнопки на следующем прогоне уже соответствует новому состоянию
    (``generate_again`` после первого билета).
    """
    state = st.session_state
    if state["subject"] is None or state["qlang"] is None or state["stage"] is None:
        return
    pool = build_pool(
        dataset=load_dataset(),
        subject=state["subject"],
        language=state["qlang"],
        stage=state["stage"],
    )
    if empty_levels(pool=pool):
        return
    state["ticket"] = generate_ticket(
        pool=pool, previous=state["ticket"], rng=state["rng"]
    )


def _init_state() -> None:
    """Задаёт начальные значения до отрисовки виджетов.

    ``index`` виджетам не передаётся: иначе Streamlit предупредит о двух
    источниках значения.
    """
    defaults: dict[str, object] = {
        "subject": None,
        "qlang": None,
        "stage": None,
        "ui_lang": _DEFAULT_UI_LANG,
        "ui_lang_manual": False,
        "ticket": None,
        # Не криптография, поэтому обычный Random.
        "rng": random.Random(),  # noqa: S311
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _render_form(dataset: Dataset) -> None:
    """Рисует форму выбора над билетом (§5.1).

    Все четыре виджета рисуются на каждом прогоне: Streamlit удаляет ключи
    виджетов, которые в прогоне не отрисованы.

    Args:
        dataset: Загруженные данные.
    """
    lang = _ui_lang()
    registry = dataset.registry
    labels = {s.slug: s.label for s in registry.subjects}

    left, right = st.columns(2)
    with left:
        st.selectbox(
            t("subject", lang),
            options=[s.slug for s in registry.subjects],
            format_func=lambda slug: labels[slug],
            placeholder=t("subject_placeholder", lang),
            key="subject",
            on_change=_on_subject,
        )
    slug = st.session_state["subject"]
    languages = registry.get(slug=slug).languages if slug is not None else []
    with right:
        st.selectbox(
            t("question_language", lang),
            options=languages,
            format_func=lambda value: t(f"lang_{value.value}", lang),
            key="qlang",
            disabled=len(languages) <= 1,
            on_change=_on_qlang,
        )
    st.radio(
        t("stage", lang),
        options=list(_STAGES),
        format_func=lambda stage: t(f"stage_{stage.value}", lang),
        index=None,
        horizontal=True,
        key="stage",
        on_change=_on_stage,
    )
    st.radio(
        t("ui_language", lang),
        options=list(_UI_LANGUAGES),
        format_func=lambda value: t(f"lang_{value.value}", lang),
        horizontal=True,
        key="ui_lang",
        on_change=_on_ui_lang,
    )


def _render_button(dataset: Dataset) -> None:
    """Рисует кнопку и сообщение о пустых уровнях (§5.3, §5.6).

    Args:
        dataset: Загруженные данные.
    """
    state = st.session_state
    lang = _ui_lang()
    ready = (
        state["subject"] is not None
        and state["qlang"] is not None
        and state["stage"] is not None
    )
    missing = []
    if ready:
        pool = build_pool(
            dataset=dataset,
            subject=state["subject"],
            language=state["qlang"],
            stage=state["stage"],
        )
        missing = empty_levels(pool=pool)
    label_key = "generate_first" if state["ticket"] is None else "generate_again"
    st.button(
        t(label_key, lang),
        key="generate",
        disabled=not ready or bool(missing),
        on_click=_on_generate,
    )
    if missing:
        names = ", ".join(t(f"level_{level.value}", lang) for level in missing)
        st.warning(t("empty_level", lang, levels=names))
    elif not ready:
        st.caption(t("hint_select", lang))


def _render_item(item: PoolItem) -> None:
    """Рисует один вопрос билета (§5.4).

    Заголовок, инструкция и главы берутся из файла именно этого вопроса, а
    всё, что пришло из данных, экранируется и выводится без Markdown.

    Args:
        item: Вопрос билета.
    """
    level = item.chapter.levels[item.level]
    chapter_ref = format_chapter_ref(item.chapter, item.chapter.language)
    reference = f"{item.question.id} · {chapter_ref}"
    st.html(
        f'<div style="font-weight:700;font-size:1.15rem;margin-top:0.6rem;">'
        f"{html.escape(level.heading)}</div>"
        '<div style="opacity:0.7;margin:0.2rem 0 0.5rem 0;">'
        f"{html.escape(reference)}</div>"
    )
    st.html(render_text(level.instructions))
    st.html('<div style="height:0.5rem;"></div>')
    st.html(render_text(item.question.text))


def _render_ticket(ticket: Ticket) -> None:
    """Рисует билет: три вопроса сверху вниз.

    Args:
        ticket: Текущий билет.
    """
    for position, item in enumerate(ticket.items):
        if position:
            st.divider()
        _render_item(item)


def main() -> None:
    """Точка входа приложения, вызывается из ``streamlit_app.py``."""
    st.set_page_config(page_title=t("page_title", _ui_lang()), layout="centered")
    try:
        dataset = load_dataset()
    except DataError:
        logger.exception("Данные вопросов не загружены")
        st.error(t("data_error", _ui_lang()))
        st.stop()
    except Exception:
        # Граница критичного пути: пользователь не должен видеть трассировку.
        logger.critical("Непредвиденная ошибка при загрузке данных", exc_info=True)
        st.error(t("data_error", _ui_lang()))
        st.stop()
    _init_state()
    st.title(t("title", _ui_lang()))
    _render_form(dataset)
    _render_button(dataset)
    ticket = st.session_state["ticket"]
    if ticket is not None:
        st.divider()
        _render_ticket(ticket)
