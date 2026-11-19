"""Строки интерфейса на русском и казахском (требования §5.5).

Все тексты интерфейса лежат здесь, в одном словаре ``{ключ: {язык: текст}}``.
Содержимое задания (вопросы, инструкции, заголовки уровней) сюда не входит —
оно всегда на языке вопросов и берётся из данных.
"""

from exam_tickets.models import Lang

STRINGS: dict[str, dict[Lang, str]] = {
    "page_title": {
        Lang.RU: "Генератор заданий СРО-2 / СРО-3",
        Lang.KK: "СӨЖ-2 / СӨЖ-3 тапсырма генераторы",
    },
    "title": {
        Lang.RU: "Генератор заданий",
        Lang.KK: "Тапсырма генераторы",
    },
    "subject": {Lang.RU: "Предмет", Lang.KK: "Пән"},
    "subject_placeholder": {Lang.RU: "Выберите предмет", Lang.KK: "Пәнді таңдаңыз"},
    "question_language": {Lang.RU: "Язык вопросов", Lang.KK: "Сұрақтар тілі"},
    "stage": {Lang.RU: "Этап", Lang.KK: "Кезең"},
    "stage_sro2": {Lang.RU: "СРО-2", Lang.KK: "СӨЖ-2"},
    "stage_sro3": {Lang.RU: "СРО-3", Lang.KK: "СӨЖ-3"},
    "ui_language": {Lang.RU: "Язык интерфейса", Lang.KK: "Интерфейс тілі"},
    # Названия языков — на самом языке (эндонимы): они одинаковы в обоих интерфейсах.
    "lang_ru": {Lang.RU: "Русский", Lang.KK: "Русский"},
    "lang_kk": {Lang.RU: "Қазақша", Lang.KK: "Қазақша"},
    "generate_first": {Lang.RU: "Сформировать задание", Lang.KK: "Тапсырма құрастыру"},
    "generate_again": {
        Lang.RU: "Сгенерировать другое задание",
        Lang.KK: "Басқа тапсырма жасау",
    },
    "hint_select": {
        Lang.RU: "Выберите предмет и этап, затем сформируйте задание.",
        Lang.KK: "Пәнді және кезеңді таңдап, тапсырманы құрастырыңыз.",
    },
    "level_cognitive": {Lang.RU: "когнитивный", Lang.KK: "когнитивтік"},
    "level_functional": {Lang.RU: "функциональный", Lang.KK: "функционалдық"},
    "level_systemic": {Lang.RU: "системный", Lang.KK: "жүйелік"},
    "empty_level": {
        Lang.RU: "Для выбранной комбинации нет вопросов уровней: {levels}.",
        Lang.KK: "Таңдалған үйлесімде мына деңгейлерде сұрақ жоқ: {levels}.",
    },
    "accepted": {Lang.RU: "Принято", Lang.KK: "Қабылданды"},
    "score": {Lang.RU: "Балл", Lang.KK: "Ұпай"},
    "subitem": {
        Lang.RU: "{name} — макс. {points}",
        Lang.KK: "{name} — ең көбі {points}",
    },
    "defense": {Lang.RU: "Защита", Lang.KK: "Қорғау"},
    "score_total": {
        Lang.RU: "Баллы: {total} / {maximum} ({scaled} / {scale})",
        Lang.KK: "Ұпай: {total} / {maximum} ({scaled} / {scale})",
    },
    "data_error": {
        Lang.RU: "Не удалось загрузить вопросы. Подробности записаны в журнал.",
        Lang.KK: "Сұрақтарды жүктеу мүмкін болмады. Толық ақпарат журналға жазылды.",
    },
}


def t(key: str, lang: Lang, **values: str) -> str:
    """Возвращает строку интерфейса на языке ``lang``.

    Args:
        key: Ключ строки из ``STRINGS``.
        lang: Язык интерфейса.
        **values: Значения для подстановки в ``{плейсхолдеры}``.

    Returns:
        Готовая строка.

    Raises:
        KeyError: Если ключа нет — опечатка должна падать громко, а не
            показывать пользователю пустую подпись.
    """
    text = STRINGS[key][lang]
    return text.format(**values) if values else text
