"""Безопасный вывод текстов вопросов (требования §5.4).

Тексты не интерпретируются как Markdown/HTML: в них есть ``$``, ``#``,
``<тег>``, обратные кавычки и pipe-таблицы, которые иначе исказятся. Поэтому
каждая строка экранируется и выводится через ``st.html`` моноширинным шрифтом.
"""

import html
import re

from exam_tickets.models import ChapterFile, Lang

# Минимум колонок в выровненном выводе команд (docker ps, docker images).
MIN_ALIGNED_COLUMNS = 3
# Одна строка с колонками может быть прозой с отступами; таблица — от двух подряд.
MIN_ALIGNED_BLOCK = 2

_QUOTED = re.compile(r'"[^"]*"')
_COLUMN_GAP = re.compile(r"\s{2,}")

# Стили инлайновые: опираться на внутренние CSS-переменные Streamlit нельзя
# (это не публичный API), а ``color: inherit`` сам работает в тёмной теме.
_BOX_STYLE = (
    "font-family:monospace;color:inherit;background:rgba(128,128,128,0.12);"
    "padding:0.6rem 0.8rem;border-radius:0.4rem;"
)
_TABLE_STYLE = "white-space:pre;overflow-x:auto;"
_LINE_STYLE = "white-space:pre-wrap;overflow-wrap:anywhere;"


def _is_pipe_table_line(line: str) -> bool:
    """Проверяет строку pipe-таблицы: ``|`` в первой колонке и ещё хотя бы один.

    Строки F#-кода с отступом, начинающиеся с ``|`` или ``|>``, сюда не
    попадают — у них есть ведущие пробелы. Строка ``|];;`` отсекается
    требованием второго ``|``.

    Args:
        line: Строка текста.

    Returns:
        ``True`` для строки pipe-таблицы.
    """
    return line.startswith("|") and "|" in line[1:]


def _is_aligned_candidate(line: str) -> bool:
    """Проверяет, похожа ли строка на строку выровненного вывода команды.

    Колонки разделены группами из 2+ пробелов; пробелы внутри ``"…"`` не
    считаются разделителями (иначе проза со строкой ``"  data  "`` даёт
    ложное срабатывание).

    Args:
        line: Строка текста.

    Returns:
        ``True``, если в строке не меньше трёх колонок.
    """
    masked = _QUOTED.sub(lambda m: m.group(0).replace(" ", "\x00"), line.strip())
    columns = [part for part in _COLUMN_GAP.split(masked) if part]
    return len(columns) >= MIN_ALIGNED_COLUMNS


def is_table_line(line: str) -> bool:
    """Проверяет, может ли строка быть частью таблицы (до учёта соседей).

    Выровненный вывод становится таблицей только в блоке из двух и более
    строк — это решает ``table_mask``. Код по этому признаку не определяется:
    на реальных данных он не отличим от прозы.

    Args:
        line: Строка текста.

    Returns:
        ``True`` для pipe-таблицы или кандидата в выровненный вывод.
    """
    return _is_pipe_table_line(line) or _is_aligned_candidate(line)


def table_mask(lines: list[str]) -> list[bool]:
    """Определяет, какие строки текста выводятся как таблицы (без переноса).

    Pipe-таблицы помечаются построчно; выровненный вывод — только если рядом
    есть ещё хотя бы одна такая же строка.

    Args:
        lines: Строки текста.

    Returns:
        Для каждой строки — ``True``, если она табличная.
    """
    pipe = [_is_pipe_table_line(line) for line in lines]
    aligned = [
        not is_pipe and _is_aligned_candidate(line)
        for line, is_pipe in zip(lines, pipe, strict=True)
    ]
    mask = list(pipe)
    start = 0
    while start < len(lines):
        if not aligned[start]:
            start += 1
            continue
        end = start
        while end < len(lines) and aligned[end]:
            end += 1
        if end - start >= MIN_ALIGNED_BLOCK:
            mask[start:end] = [True] * (end - start)
        start = end
    return mask


def _render_wrapped_line(line: str) -> str:
    """Рисует обычную строку: перенос по ширине, продолжение под отступ.

    Ведущие пробелы остаются в тексте (``pre-wrap``), а ``padding-left`` и
    отрицательный ``text-indent`` равной величины сдвигают продолжение строки
    под первый непробельный символ.

    Args:
        line: Строка текста.

    Returns:
        HTML-фрагмент.
    """
    if not line.strip():
        return "<div>&nbsp;</div>"
    indent = len(line) - len(line.lstrip(" "))
    style = f"{_LINE_STYLE}padding-left:{indent}ch;text-indent:-{indent}ch;"
    return f'<div style="{style}">{html.escape(line)}</div>'


def render_text(text: str) -> str:
    """Превращает текст вопроса или инструкции в безопасный HTML.

    Идущие подряд табличные строки объединяются в один блок, чтобы колонки
    прокручивались вместе. Всё экранируется ``html.escape``.

    Args:
        text: Текст дословно из данных.

    Returns:
        HTML-фрагмент для ``st.html``.
    """
    lines = text.rstrip("\n").split("\n")
    mask = table_mask(lines)
    parts: list[str] = []
    index = 0
    while index < len(lines):
        if not mask[index]:
            parts.append(_render_wrapped_line(lines[index]))
            index += 1
            continue
        end = index
        while end < len(lines) and mask[end]:
            end += 1
        rows = "\n".join(html.escape(row) for row in lines[index:end])
        parts.append(f'<div class="tbl" style="{_TABLE_STYLE}">{rows}</div>')
        index = end
    return f'<div style="{_BOX_STYLE}">{"".join(parts)}</div>'


def format_chapter_ref(chapter: ChapterFile, language: Lang) -> str:
    """Формирует ссылку на главу(ы) на языке вопросов.

    Формы: ``Глава 3 «…»``, ``Главы 1–2 «…», «…»``, ``3-тарау «…»``,
    ``1–2-тараулар «…», «…»``.

    Args:
        chapter: Файл главы вопроса.
        language: Язык вопросов.

    Returns:
        Строка без HTML (экранируется при выводе).
    """
    titles = ", ".join(f"«{title}»" for title in chapter.chapter_titles)
    first, last = chapter.chapters[0], chapter.chapters[-1]
    is_range = first != last
    number = f"{first}–{last}" if is_range else str(first)
    # ``==``, а не ``is``: язык может прийти из главы в кэше со старым классом Lang.
    if language == Lang.RU:
        word = "Главы" if is_range else "Глава"
        return f"{word} {number} {titles}"
    word = "тараулар" if is_range else "тарау"
    return f"{number}-{word} {titles}"
