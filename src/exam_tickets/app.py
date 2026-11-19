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
from exam_tickets.grading import (
    DEFENSE_LEVEL,
    GRADE_SCALE,
    SUBITEM_POINTS,
    checked_total,
    scale_points,
)
from exam_tickets.i18n import t
from exam_tickets.models import Lang, LevelKey, Stage
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
# Ширина поля балла подпункта в пикселях — под трёхзначное число. На такой
# ширине Streamlit сам прячет кнопки −/+, остаётся только ввод.
_SUBITEM_INPUT_WIDTH = 80


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
    # Оценки прошлого задания к новым вопросам не относятся: удаляем ключи,
    # и _init_grading заново выставит значения по умолчанию.
    for position, item in enumerate(state["ticket"].items):
        state.pop(_accepted_key(position), None)
        state.pop(_score_key(position), None)
        for index in range(len(SUBITEM_POINTS[item.level])):
            state.pop(_sub_checked_key(position, index), None)
            state.pop(_sub_points_key(position, index), None)


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


def _accepted_key(position: int) -> str:
    """Ключ галочки «принято» для вопроса задания.

    Args:
        position: Номер вопроса в задании, с нуля.

    Returns:
        Ключ виджета в ``st.session_state``.
    """
    return f"accepted_{position}"


def _score_key(position: int) -> str:
    """Ключ поля балла для вопроса задания.

    Args:
        position: Номер вопроса в задании, с нуля.

    Returns:
        Ключ виджета в ``st.session_state``.
    """
    return f"score_{position}"


def _sub_checked_key(position: int, index: int) -> str:
    """Ключ галочки подпункта вопроса.

    Args:
        position: Номер вопроса в задании, с нуля.
        index: Номер подпункта внутри вопроса, с нуля.

    Returns:
        Ключ виджета в ``st.session_state``.
    """
    return f"sub_{position}_{index}_checked"


def _sub_points_key(position: int, index: int) -> str:
    """Ключ поля балла подпункта вопроса.

    Args:
        position: Номер вопроса в задании, с нуля.
        index: Номер подпункта внутри вопроса, с нуля.

    Returns:
        Ключ виджета в ``st.session_state``.
    """
    return f"sub_{position}_{index}_points"


def _on_subitem(position: int, count: int) -> None:
    """Пересчитывает балл вопроса как сумму отмеченных подпунктов.

    Пишем в поле вопроса только при изменении подпункта: ручная правка поля
    вопроса сохраняется, пока преподаватель снова не тронет подпункты.
    Запись идёт в колбэке — после отрисовки виджета в прогоне это запрещено.

    Args:
        position: Номер вопроса в задании, с нуля.
        count: Число подпунктов у вопроса.
    """
    state = st.session_state
    scores = [
        (
            bool(state[_sub_checked_key(position, index)]),
            int(state[_sub_points_key(position, index)]),
        )
        for index in range(count)
    ]
    state[_score_key(position)] = checked_total(scores=scores)


def _on_accepted(position: int, level: LevelKey) -> None:
    """Синхронизирует подпункты с галочкой «принято».

    Принятие — частый случай «ответ полностью верный», поэтому оно отмечает
    все подпункты с максимальными баллами. Снятие лишь снимает галочки
    подпунктов: введённые частичные баллы остаются, чтобы не вводить их
    заново при повторном выборе. Балл вопроса пересчитывается как обычно.

    Args:
        position: Номер вопроса в задании, с нуля.
        level: Уровень вопроса — по нему берётся схема подпунктов.
    """
    state = st.session_state
    accepted = bool(state[_accepted_key(position)])
    points = SUBITEM_POINTS[level]
    for index, maximum in enumerate(points):
        state[_sub_checked_key(position, index)] = accepted
        if accepted:
            state[_sub_points_key(position, index)] = maximum
    _on_subitem(position=position, count=len(points))


def _init_grading(ticket: Ticket) -> None:
    """Задаёт значения оценки по умолчанию.

    Вопрос не принят, подпункты не отмечены (их поля — максимум подпункта),
    поэтому балл вопроса — 0, то есть сумма отмеченных подпунктов.

    Значения пишутся в состояние до отрисовки виджетов, а не через ``value=``:
    иначе Streamlit предупредит о двух источниках значения (как и в
    ``_init_state``).

    Args:
        ticket: Текущее задание.
    """
    state = st.session_state
    for position, item in enumerate(ticket.items):
        state.setdefault(_accepted_key(position), False)
        state.setdefault(_score_key(position), 0)
        for index, points in enumerate(SUBITEM_POINTS[item.level]):
            state.setdefault(_sub_checked_key(position, index), False)
            state.setdefault(_sub_points_key(position, index), points)


def _render_total(ticket: Ticket) -> None:
    """Рисует сумму баллов всех вопросов и её пересчёт в шкалу СРО.

    Галочка «принято» в сумме не участвует: она лишь быстро заполняет или
    снимает подпункты, а балл вопроса уже отражает их состояние. Иначе
    отмеченные подпункты непринятого вопроса не меняли бы сумму.

    Args:
        ticket: Текущее задание.
    """
    state = st.session_state
    total = sum(
        int(state[_score_key(position)]) for position in range(len(ticket.items))
    )
    maximum = sum(item.chapter.levels[item.level].points for item in ticket.items)
    scaled = scale_points(points=total, maximum=maximum)
    st.markdown(
        "**"
        + t(
            "score_total",
            _ui_lang(),
            total=str(total),
            maximum=str(maximum),
            scaled=str(scaled),
            scale=str(GRADE_SCALE),
        )
        + "**"
    )


def _render_subitems(item: PoolItem, position: int) -> None:
    """Рисует подпункты вопроса: галочку и поле балла у каждого.

    Поле подпункта нужно для частичного балла (например, «верно» без полного
    обоснования); оно ограничено 0…максимумом подпункта.

    Args:
        item: Вопрос задания.
        position: Номер вопроса в задании, с нуля.
    """
    lang = _ui_lang()
    points = SUBITEM_POINTS[item.level]
    args = (position, len(points))
    for index, maximum in enumerate(points):
        # ``==``, а не ``is``: задание в состоянии сессии может хранить уровень
        # старого класса LevelKey после горячей перезагрузки модулей.
        is_defense = item.level == DEFENSE_LEVEL and index == len(points) - 1
        name = t("defense", lang) if is_defense else str(index + 1)
        label = t("subitem", lang, name=name, points=str(maximum))
        # Горизонтальный контейнер, а не st.columns: колонки делят ширину
        # поровну и оставляют пустоту между галочкой и полем.
        with st.container(horizontal=True, vertical_alignment="center"):
            st.checkbox(
                label,
                key=_sub_checked_key(position, index),
                on_change=_on_subitem,
                args=args,
            )
            st.number_input(
                label,
                min_value=0,
                max_value=maximum,
                step=1,
                key=_sub_points_key(position, index),
                on_change=_on_subitem,
                args=args,
                label_visibility="collapsed",
                width=_SUBITEM_INPUT_WIDTH,
            )


def _render_grading(item: PoolItem, position: int) -> None:
    """Рисует под вопросом галочку «принято» и поле балла.

    Поле ограничено диапазоном 0…максимум уровня, чтобы опечатка вроде 240
    вместо 24 не исказила сумму.

    Args:
        item: Вопрос задания.
        position: Номер вопроса в задании, с нуля.
    """
    _render_subitems(item=item, position=position)
    lang = _ui_lang()
    maximum = item.chapter.levels[item.level].points
    left, right = st.columns(2, vertical_alignment="bottom")
    with left:
        st.checkbox(
            t("accepted", lang),
            key=_accepted_key(position),
            on_change=_on_accepted,
            args=(position, item.level),
        )
    with right:
        st.number_input(
            f"{t('score', lang)} (0–{maximum})",
            min_value=0,
            max_value=maximum,
            step=1,
            key=_score_key(position),
        )


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

    Общая сумма выводится сверху и после формы оценивания каждого вопроса,
    чтобы итог был виден, где бы преподаватель ни ставил баллы. Сумма после
    последней формы служит и нижней суммой задания.

    Args:
        ticket: Текущий билет.
    """
    _init_grading(ticket=ticket)
    _render_total(ticket=ticket)
    for position, item in enumerate(ticket.items):
        if position:
            st.divider()
        _render_item(item)
        _render_grading(item=item, position=position)
        _render_total(ticket=ticket)


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
