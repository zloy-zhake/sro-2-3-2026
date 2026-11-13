"""Конвертер исходных ``.txt`` в ``ChapterFile`` (требования §2, §4).

Парсер — построчный конечный автомат. Он помнит номер строки начала каждого
блока, поэтому любая ошибка, включая ошибки Pydantic, сообщает «файл, строка,
причина».
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from exam_tickets.exceptions import ConversionError
from exam_tickets.models import (
    LEVEL_HEADINGS,
    LEVEL_LETTERS,
    ChapterFile,
    Lang,
    LevelKey,
    Subject,
    SubjectRegistry,
)

logger = logging.getLogger(name=__name__)

LEVEL_RULE = "=" * 70
QUESTION_RULE = "-" * 70

# Первая строка таблицы с содержимым начинается с 5-й строки файла (индекс 4).
FIRST_LEVEL_INDEX = 4
MIN_LINES = 5
# loc ошибки Pydantic: levels / <уровень> / questions / <индекс> / поле.
QUESTION_LOC_DEPTH = 4
HEADER_LINE_INDEX = 1
BLANK_LINE_INDEX = 3

# Имя файла вопросов; ``(d)`` — исторический суффикс, при конвертации отбрасывается.
_FILE_NAME = re.compile(
    r"^ch(?P<number>\d+)_questions(?:_(?P<suffix>ru|kz))?(?:\(d\))?\.txt$"
)
_SUFFIX_LANG: dict[str, Lang] = {"ru": Lang.RU, "kz": Lang.KK}

# Книга — содержимое ПОСЛЕДНИХ скобок: в названии курса тоже бывают скобки.
_BOOK_TAIL = re.compile(r"^(?P<head>.*\S)\s+\([^()]*\)$")
_HEAD = re.compile(
    r"^.+ — (?:устный экзамен|ауызша емтихан), "
    r"(?P<chapters>.+?) (?P<titles>«.*»)$"
)
_CHAPTERS = re.compile(
    r"^(?:(?P<ru>глава|главы) (?P<a>\d+)(?:–(?P<b>\d+))?"
    r"|(?P<c>\d+)(?:–(?P<d>\d+))?-(?P<kk>тараулар|тарау))$"
)
_TITLE = re.compile(r"«([^»]*)»")
_POINTS = re.compile(r"\((\d+) ")
# Ограда markdown: только ``` и необязательное имя языка.
_FENCE = re.compile(r"^```[A-Za-z0-9_+#.-]*$")


@dataclass(frozen=True)
class SourceFile:
    """Найденный исходный файл вопросов с вычисленными метаданными.

    Attributes:
        path: Путь к ``.txt``.
        subject: Предмет из реестра.
        language: Язык вопросов файла.
        file_chapter: Номер главы из имени файла.
    """

    path: Path
    subject: Subject
    language: Lang
    file_chapter: int


@dataclass
class _ParseContext:
    """Состояние разбора одного файла, общее для всех его уровней.

    Attributes:
        file: Путь к файлу для сообщений.
        language: Язык файла (выбирает таблицу заголовков).
        subject: Предмет (префикс ID).
        file_chapter: Номер главы из имени файла.
        positions: Строки блоков (с 1) для привязки ошибок модели к строкам.
        seen: Уже разобранные уровни — для поиска дублей.
    """

    file: str
    language: Lang
    subject: Subject
    file_chapter: int
    positions: dict[tuple[Any, ...], int] = field(default_factory=dict)
    seen: set[LevelKey] = field(default_factory=set)


def _fail(file: str, line_index: int | None, reason: str) -> ConversionError:
    """Создаёт ошибку конвертации по индексу строки (с 0).

    Args:
        file: Путь к файлу для сообщения.
        line_index: Индекс строки с 0 или ``None``.
        reason: Причина.

    Returns:
        Исключение с номером строки с 1.
    """
    line = None if line_index is None else line_index + 1
    return ConversionError(file=file, line=line, reason=reason)


def _decode(raw: bytes, file: str) -> str:
    """Проверяет байты (BOM, CR, табуляции, UTF-8) и декодирует текст.

    Args:
        raw: Содержимое файла.
        file: Путь к файлу для сообщений.

    Returns:
        Декодированный текст.

    Raises:
        ConversionError: Если файл нарушает §2.2.
    """
    if raw.startswith(b"\xef\xbb\xbf"):
        raise _fail(file, 0, "файл начинается с BOM")
    for needle, name in ((b"\r", "символ CR (ожидается LF)"), (b"\t", "табуляция")):
        position = raw.find(needle)
        if position != -1:
            raise _fail(file, raw.count(b"\n", 0, position), name)
    try:
        return raw.decode(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise _fail(file, raw.count(b"\n", 0, e.start), "файл не в UTF-8") from e


def _parse_header(
    line: str, file: str, language: Lang, file_chapter: int
) -> tuple[list[int], list[str]]:
    """Разбирает строку 2: главы и их названия.

    Args:
        line: Вторая строка файла.
        file: Путь к файлу для сообщений.
        language: Язык, приписанный файлу; форма глав обязана ему соответствовать.
        file_chapter: Номер главы из имени файла.

    Returns:
        Кортеж ``(номера глав, названия глав)``.

    Raises:
        ConversionError: Если строка не соответствует формату §2.2.
    """
    index = HEADER_LINE_INDEX
    book = _BOOK_TAIL.match(line)
    head = _HEAD.match(book.group("head") if book else "")
    if head is None:
        raise _fail(file, index, "строка 2 не соответствует формату §2.2")
    chapters_match = _CHAPTERS.match(head.group("chapters"))
    if chapters_match is None:
        raise _fail(file, index, f"неизвестный формат глав: {head.group('chapters')!r}")
    groups = chapters_match.groupdict()
    word = groups["ru"] or groups["kk"]
    first = int(groups["a"] or groups["c"])
    last_raw = groups["b"] or groups["d"]
    last = int(last_raw) if last_raw else first
    if last < first:
        raise _fail(file, index, f"диапазон глав убывает: {first}–{last}")
    is_range = last_raw is not None
    expected_word = {
        (Lang.RU, False): "глава",
        (Lang.RU, True): "главы",
        (Lang.KK, False): "тарау",
        (Lang.KK, True): "тараулар",
    }[(language, is_range)]
    if word != expected_word:
        raise _fail(
            file,
            index,
            f"форма глав {word!r} не соответствует языку {language} "
            f"(ожидалось {expected_word!r})",
        )
    titles_text = head.group("titles")
    titles = _TITLE.findall(titles_text)
    if ", ".join(f"«{title}»" for title in titles) != titles_text:
        raise _fail(file, index, "названия глав должны быть вида «A», «B»")
    if last != file_chapter:
        raise _fail(
            file,
            index,
            f"последняя глава строки 2 ({last}) не равна номеру из имени файла "
            f"({file_chapter})",
        )
    return list(range(first, last + 1)), titles


def _is_level_start(lines: list[str], index: int) -> bool:
    """Проверяет тройку «=×70 / заголовок / =×70» с позиции ``index``."""
    return (
        lines[index] == LEVEL_RULE
        and index + 2 < len(lines)
        and lines[index + 2] == LEVEL_RULE
    )


def _is_question_start(lines: list[str], index: int) -> bool:
    """Проверяет тройку «-×70 / ID / -×70» с позиции ``index``."""
    return (
        lines[index] == QUESTION_RULE
        and index + 2 < len(lines)
        and lines[index + 2] == QUESTION_RULE
    )


def _check_not_stray_rule(lines: list[str], index: int, file: str) -> None:
    """Запрещает одиночный разделитель внутри текста.

    Тихий разрыв на строке из 70 дефисов в середине вопроса исказил бы данные,
    поэтому такая строка — ошибка с номером, а не граница блока.

    Args:
        lines: Строки файла.
        index: Индекс проверяемой строки.
        file: Путь к файлу для сообщений.

    Raises:
        ConversionError: Если строка — разделитель вне полной тройки.
    """
    if lines[index] in (LEVEL_RULE, QUESTION_RULE):
        raise _fail(
            file,
            index,
            "одиночный разделитель из 70 символов вне структуры "
            "«разделитель / заголовок / разделитель»",
        )


def _trim_blank(block: list[str]) -> list[str]:
    """Обрезает ведущие и замыкающие пустые строки, внутренние не трогает."""
    start, end = 0, len(block)
    while start < end and block[start] == "":
        start += 1
    while end > start and block[end - 1] == "":
        end -= 1
    return block[start:end]


def _join(block: list[str]) -> str:
    """Склеивает строки в текст с одним завершающим переводом строки."""
    return "\n".join(block) + "\n" if block else ""


def _strip_fences(block: list[str], first_index: int, file: str) -> list[str]:
    """Удаляет строки-ограды markdown из текста вопроса.

    Args:
        block: Строки текста вопроса.
        first_index: Индекс первой строки блока в файле (для сообщений).
        file: Путь к файлу для сообщений.

    Returns:
        Строки без оград.

    Raises:
        ConversionError: При незакрытой или вложенной ограде.
    """
    result: list[str] = []
    opened_at: int | None = None
    for offset, line in enumerate(block):
        if _FENCE.match(line) is None:
            result.append(line)
            continue
        index = first_index + offset
        if opened_at is None:
            opened_at = index
        elif line == "```":
            opened_at = None
        else:
            raise _fail(file, index, "ограда с именем языка внутри открытой ограды")
    if opened_at is not None:
        raise _fail(file, opened_at, "незакрытая ограда ```")
    return result


def _check_no_fences(block: list[str], first_index: int, file: str) -> None:
    """Запрещает ограды в инструкции уровня (§4)."""
    for offset, line in enumerate(block):
        if _FENCE.match(line) is not None:
            raise _fail(file, first_index + offset, "ограда ``` в инструкции уровня")


def _error_line(
    error: ValidationError, positions: dict[tuple[Any, ...], int]
) -> int | None:
    """Находит строку файла для первой ошибки Pydantic по её пути ``loc``.

    Args:
        error: Ошибка валидации модели.
        positions: Строки блоков (с 1), собранные парсером.

    Returns:
        Номер строки или ``None``, если ошибка относится ко всему файлу.
    """
    loc = tuple(error.errors()[0]["loc"])
    if not loc:
        return None
    if loc[0] != "levels":
        return positions.get(("header",))
    if len(loc) >= QUESTION_LOC_DEPTH and loc[2] == "questions":
        return positions.get(("question", loc[1], loc[3]))
    return positions.get(("level", loc[1]))


def _format_validation_error(error: ValidationError) -> str:
    """Собирает читаемую причину из ошибок Pydantic."""
    parts = []
    for item in error.errors():
        where = ".".join(str(part) for part in item["loc"])
        message = str(item["msg"]).removeprefix("Value error, ")
        parts.append(f"{where}: {message}" if where else message)
    return "; ".join(parts)


def _scan_block(lines: list[str], start: int, file: str) -> int:
    """Находит конец блока текста: до следующего вопроса, уровня или конца файла.

    Args:
        lines: Строки файла.
        start: Индекс первой строки блока.
        file: Путь к файлу для сообщений.

    Returns:
        Индекс первой строки, не входящей в блок.

    Raises:
        ConversionError: Если внутри блока одиночный разделитель.
    """
    end = start
    while (
        end < len(lines)
        and not _is_question_start(lines, end)
        and not _is_level_start(lines, end)
    ):
        _check_not_stray_rule(lines, end, file)
        end += 1
    return end


def _parse_level(
    lines: list[str], start: int, ctx: _ParseContext
) -> tuple[LevelKey, dict[str, Any], int]:
    """Разбирает один уровень: заголовок, инструкцию и вопросы.

    Args:
        lines: Строки файла.
        start: Индекс первого ``=``×70 заголовка уровня.
        ctx: Контекст разбора файла.

    Returns:
        Кортеж ``(ключ уровня, данные уровня, индекс строки после уровня)``.

    Raises:
        ConversionError: При нарушении структуры уровня.
    """
    file, subject, file_chapter = ctx.file, ctx.subject, ctx.file_chapter
    language, positions, seen = ctx.language, ctx.positions, ctx.seen
    if not _is_level_start(lines, start):
        raise _fail(file, start, "ожидался заголовок уровня (=×70, заголовок, =×70)")
    heading = lines[start + 1]
    key = {h: k for k, h in LEVEL_HEADINGS[language].items()}.get(heading)
    if key is None:
        raise _fail(
            file,
            start + 1,
            f"неизвестный заголовок уровня для языка {language}: {heading!r}",
        )
    if key in seen:
        raise _fail(file, start + 1, f"уровень {key.value} встречается повторно")
    seen.add(key)
    positions[("level", key.value)] = start + 2
    points = _POINTS.search(heading)

    instructions_start = start + 3
    j = _scan_block(lines, instructions_start, file)
    instruction_block = lines[instructions_start:j]
    _check_no_fences(instruction_block, instructions_start, file)

    letter = LEVEL_LETTERS[key]
    id_pattern = re.compile(
        rf"^{re.escape(subject.id_prefix)}{file_chapter:02d}-{letter}-\d{{2}}$"
    )
    questions: list[dict[str, str]] = []
    while j < len(lines) and _is_question_start(lines, j):
        question_id = lines[j + 1]
        if id_pattern.match(question_id) is None:
            raise _fail(
                file,
                j + 1,
                f"ID {question_id!r} не соответствует шаблону "
                f"{subject.id_prefix}{file_chapter:02d}-{letter}-NN",
            )
        end = _scan_block(lines, j + 3, file)
        body = _strip_fences(lines[j + 3 : end], j + 3, file)
        positions[("question", key.value, len(questions))] = j + 2
        questions.append({"id": question_id, "text": _join(_trim_blank(body))})
        j = end
    level = {
        "heading": heading,
        # -1 заведомо не пройдёт проверку баллов в модели, если в заголовке нет числа.
        "points": int(points.group(1)) if points else -1,
        "instructions": _join(_trim_blank(instruction_block)),
        "questions": questions,
    }
    return key, level, j


def parse_chapter_text(
    raw: bytes,
    *,
    file: str,
    subject: Subject,
    language: Lang,
    file_chapter: int,
) -> ChapterFile:
    """Разбирает содержимое исходного файла в ``ChapterFile``.

    Args:
        raw: Байты файла.
        file: Путь к файлу — только для сообщений об ошибках.
        subject: Предмет файла (нужен префикс ID).
        language: Язык вопросов файла.
        file_chapter: Номер главы из имени файла.

    Returns:
        Проверенный файл главы.

    Raises:
        ConversionError: При любом нарушении структуры: файл, строка, причина.
    """
    lines = _decode(raw, file).split("\n")
    if lines[-1] == "":
        lines.pop()  # финальный перевод строки не создаёт пустой строки
    for index, line in enumerate(lines):
        if line.endswith(" "):
            raise _fail(file, index, "пробелы в конце строки")
    if len(lines) < MIN_LINES:
        raise _fail(file, None, "файл слишком короткий")

    chapters, titles = _parse_header(
        lines[HEADER_LINE_INDEX], file, language, file_chapter
    )
    if lines[BLANK_LINE_INDEX] != "":
        raise _fail(file, BLANK_LINE_INDEX, "строка 4 должна быть пустой")

    ctx = _ParseContext(
        file=file, language=language, subject=subject, file_chapter=file_chapter
    )
    ctx.positions[("header",)] = HEADER_LINE_INDEX + 1
    levels: dict[str, Any] = {}
    i = FIRST_LEVEL_INDEX
    while i < len(lines):
        key, level, i = _parse_level(lines, i, ctx)
        levels[key.value] = level

    data = {
        "subject": subject.slug,
        "language": language.value,
        "file_chapter": file_chapter,
        "chapters": chapters,
        "chapter_titles": titles,
        "levels": levels,
    }
    try:
        return ChapterFile.model_validate(data)
    except ValidationError as e:
        raise ConversionError(
            file=file,
            line=_error_line(e, ctx.positions),
            reason=_format_validation_error(e),
        ) from e


def discover_sources(
    questions_dir: Path, registry: SubjectRegistry
) -> list[SourceFile]:
    """Находит исходные файлы вопросов всех предметов реестра.

    Язык определяется по реестру и суффиксу имени, без угадывания по
    содержимому (§2.1): у предмета с одним языком суффикса быть не должно, у
    предмета с несколькими — он обязателен.

    Args:
        questions_dir: Каталог ``questions``.
        registry: Реестр предметов.

    Returns:
        Файлы, упорядоченные по предмету, главе и языку.

    Raises:
        ConversionError: Если имя файла, суффикс или набор файлов некорректны.
    """
    sources: list[SourceFile] = []
    seen: set[tuple[str, Lang, int]] = set()
    for subject in registry.subjects:
        folder = questions_dir / subject.folder
        if not folder.is_dir():
            raise ConversionError(
                file=str(folder), line=None, reason="нет папки предмета"
            )
        paths = sorted(folder.glob(pattern="*_questions*.txt"))
        if not paths:
            raise ConversionError(
                file=str(folder), line=None, reason="нет файлов вопросов"
            )
        for path in paths:
            match = _FILE_NAME.match(path.name)
            if match is None:
                raise ConversionError(
                    file=str(path),
                    line=None,
                    reason="имя не соответствует шаблону "
                    "chN_questions[_ru|_kz][(d)].txt",
                )
            suffix = match.group("suffix")
            if len(subject.languages) == 1:
                if suffix is not None:
                    raise ConversionError(
                        file=str(path),
                        line=None,
                        reason="у предмета один язык — суффикс языка недопустим",
                    )
                language = subject.languages[0]
            else:
                if suffix is None:
                    raise ConversionError(
                        file=str(path),
                        line=None,
                        reason="у предмета несколько языков — нужен суффикс "
                        "_ru или _kz",
                    )
                language = _SUFFIX_LANG[suffix]
            number = int(match.group("number"))
            key = (subject.slug, language, number)
            if key in seen:
                raise ConversionError(
                    file=str(path), line=None, reason="дубликат главы и языка"
                )
            seen.add(key)
            sources.append(SourceFile(path, subject, language, number))
    sources.sort(key=lambda s: (s.subject.slug, s.file_chapter, s.language.value))
    logger.info("Найдены исходные файлы", extra={"count": len(sources)})
    return sources


def parse_source(source: SourceFile) -> ChapterFile:
    """Читает и разбирает один исходный файл.

    Args:
        source: Файл, найденный ``discover_sources``.

    Returns:
        Проверенный файл главы.

    Raises:
        ConversionError: Если файл не читается или нарушает формат.
    """
    try:
        raw = source.path.read_bytes()
    except OSError as e:
        raise ConversionError(
            file=str(source.path), line=None, reason=f"не удалось прочитать: {e}"
        ) from e
    return parse_chapter_text(
        raw,
        file=str(source.path),
        subject=source.subject,
        language=source.language,
        file_chapter=source.file_chapter,
    )
