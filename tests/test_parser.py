"""Тесты парсера исходных файлов: корректный разбор и «битые» случаи."""

from pathlib import Path

import pytest

from exam_tickets.convert import (
    SourceFile,
    discover_sources,
    parse_chapter_text,
    parse_source,
)
from exam_tickets.exceptions import ConversionError
from exam_tickets.models import (
    LEVEL_HEADINGS,
    ChapterFile,
    Lang,
    LevelKey,
    Subject,
    SubjectRegistry,
)
from tests.builders import DASH, EQ, build_source

DOCKER = Subject(
    slug="docker",
    folder="Docker",
    label="Docker",
    id_prefix="D",
    languages=[Lang.RU, Lang.KK],
)
FILE = "Docker/ch3_questions_ru.txt"


def parse(text: str, language: Lang = Lang.RU, chapter: int = 3) -> ChapterFile:
    """Разбирает текст как файл Docker ch3 (ru)."""
    return parse_chapter_text(
        text.encode(encoding="utf-8"),
        file=FILE,
        subject=DOCKER,
        language=language,
        file_chapter=chapter,
    )


def fails(text: str, *, line: int | None, match: str) -> None:
    """Проверяет, что разбор падает с нужной строкой и причиной."""
    with pytest.raises(ConversionError, match=match) as info:
        parse(text)
    assert info.value.line == line


def test_valid_file_is_parsed() -> None:
    chapter = parse(build_source())
    assert chapter.chapters == [3]
    assert chapter.chapter_titles == ["Название главы"]
    assert [q.id for q in chapter.levels[LevelKey.COGNITIVE].questions] == [
        "D03-К-01",
        "D03-К-02",
    ]


def test_text_keeps_inner_indent_and_has_single_trailing_newline() -> None:
    question = parse(build_source()).levels[LevelKey.FUNCTIONAL].questions[0]
    assert question.text == "Вопрос Ф1.\n  с отступом\n"


def test_trailing_blank_lines_of_last_question_are_trimmed() -> None:
    chapter = parse(build_source() + "\n\n\n")
    assert chapter.levels[LevelKey.SYSTEMIC].questions[-1].text.endswith("отступом\n")


def test_book_is_content_of_last_parentheses() -> None:
    # «(с оговоркой)» в названии курса не должно путаться с книгой.
    assert parse(build_source()).chapters == [3]


def test_fences_are_removed_from_questions() -> None:
    text = build_source().replace(
        "Вопрос К1.", "Вопрос К1.\n```yaml\nservices:\n  a: 1\n```"
    )
    question = parse(text).levels[LevelKey.COGNITIVE].questions[0]
    assert question.text == "Вопрос К1.\nservices:\n  a: 1\n  с отступом\n"


def test_chapters_range_is_parsed() -> None:
    text = build_source(chapter=2).replace(
        "глава 2 «Название главы»", "главы 1–2 «Один», «Два»"
    )
    chapter = parse(text, chapter=2)
    assert chapter.chapters == [1, 2]
    assert chapter.chapter_titles == ["Один", "Два"]


def test_kazakh_chapter_forms_are_parsed() -> None:
    text = build_source()
    for ru, kk in zip(
        LEVEL_HEADINGS[Lang.RU].values(), LEVEL_HEADINGS[Lang.KK].values(), strict=True
    ):
        text = text.replace(ru, kk)
    text = text.replace("глава 3", "3-тарау")
    assert parse(text, language=Lang.KK).chapters == [3]


def test_bom_is_rejected() -> None:
    with pytest.raises(ConversionError, match="BOM"):
        parse_chapter_text(
            b"\xef\xbb\xbf" + build_source().encode(),
            file=FILE,
            subject=DOCKER,
            language=Lang.RU,
            file_chapter=3,
        )


def test_carriage_return_is_rejected_with_line() -> None:
    fails(
        build_source().replace("служебная строка 3", "служебная\rстрока"),
        line=3,
        match="CR",
    )


def test_tab_is_rejected_with_line() -> None:
    fails(
        build_source().replace("Вопрос К1.", "Вопрос\tК1."), line=13, match="табуляция"
    )


def test_trailing_space_is_rejected_with_line() -> None:
    fails(
        build_source().replace("Вопрос К1.", "Вопрос К1. "),
        line=13,
        match="пробелы в конце",
    )


def test_invalid_utf8_is_rejected() -> None:
    with pytest.raises(ConversionError, match="UTF-8"):
        parse_chapter_text(
            b"\xff\xfe\n", file=FILE, subject=DOCKER, language=Lang.RU, file_chapter=3
        )


def test_header_with_wrong_format_is_rejected() -> None:
    fails(build_source().replace("устный экзамен", "экзамен"), line=2, match="строка 2")


def test_chapter_form_of_other_language_is_rejected() -> None:
    fails(build_source().replace("глава 3", "3-тарау"), line=2, match="форма глав")


def test_header_chapter_differs_from_file_name() -> None:
    fails(build_source().replace("глава 3", "глава 4"), line=2, match="не равна номеру")


def test_titles_must_be_guillemet_list() -> None:
    fails(
        build_source().replace("«Название главы»", "«A» и «B»"),
        line=2,
        match="названия глав",
    )


def test_line_four_must_be_blank() -> None:
    fails(
        build_source().replace(
            "служебная строка 3\n\n", "служебная строка 3\nлишнее\n"
        ),
        line=4,
        match="строка 4",
    )


def test_text_between_header_and_first_level_is_rejected() -> None:
    fails(
        build_source().replace(f"\n\n{EQ}", f"\n\nлишнее\n{EQ}", 1),
        line=5,
        match="ожидался заголовок",
    )


def test_unknown_level_heading_is_rejected() -> None:
    with pytest.raises(ConversionError, match="неизвестный заголовок") as info:
        parse(build_source().replace("СИСТЕМНЫЙ УРОВЕНЬ", "ДРУГОЙ УРОВЕНЬ"))
    assert info.value.line is not None


def test_duplicate_level_is_rejected() -> None:
    text = build_source(letters="КФС").replace(
        "ФУНКЦИОНАЛЬНЫЙ УРОВЕНЬ (32 балла)", "КОГНИТИВНЫЙ УРОВЕНЬ (24 балла)"
    )
    with pytest.raises(ConversionError, match="повторно"):
        parse(text)


def test_wrong_id_prefix_is_rejected_with_line() -> None:
    with pytest.raises(ConversionError, match="не соответствует шаблону") as info:
        parse(build_source().replace("D03-К-01", "X03-К-01"))
    assert info.value.line == 11


def test_id_chapter_must_equal_file_chapter() -> None:
    with pytest.raises(ConversionError, match="не соответствует шаблону"):
        parse(build_source().replace("D03-Ф-02", "D04-Ф-02"))


def test_id_level_letter_must_match_level() -> None:
    with pytest.raises(ConversionError, match="не соответствует шаблону"):
        parse(build_source().replace("D03-С-01", "D03-К-01"))


def test_latin_level_letter_in_id_is_rejected() -> None:
    with pytest.raises(ConversionError, match="не соответствует шаблону"):
        parse(build_source().replace("D03-К-01", "D03-K-01"))


def test_stray_question_rule_in_text_is_rejected() -> None:
    with pytest.raises(ConversionError, match="одиночный разделитель"):
        parse(build_source().replace("Вопрос К1.", f"Вопрос К1.\n{DASH}\nхвост"))


def test_stray_level_rule_in_text_is_rejected() -> None:
    with pytest.raises(ConversionError, match="одиночный разделитель"):
        parse(build_source().replace("Вопрос К1.", f"Вопрос К1.\n{EQ}"))


def test_shorter_dash_lines_are_ordinary_text() -> None:
    text = build_source().replace("Вопрос К1.", "Вопрос К1.\n|---|---|\n" + "-" * 69)
    assert "|---|---|" in parse(text).levels[LevelKey.COGNITIVE].questions[0].text


def test_unclosed_fence_is_rejected() -> None:
    with pytest.raises(ConversionError, match="незакрытая ограда"):
        parse(build_source().replace("Вопрос К1.", "Вопрос К1.\n```yaml\nкод"))


def test_fence_in_instructions_is_rejected() -> None:
    with pytest.raises(ConversionError, match="инструкции"):
        parse(build_source().replace("Инструкция К.", "Инструкция К.\n```"))


def test_empty_question_text_is_rejected_with_line() -> None:
    text = build_source().replace("Вопрос К1.\n  с отступом\n", "")
    with pytest.raises(ConversionError, match="текст вопроса") as info:
        parse(text)
    assert info.value.line == 11


def test_level_without_questions_is_rejected() -> None:
    lines = build_source(questions_per_level=0)
    with pytest.raises(ConversionError, match="хотя бы один вопрос"):
        parse(lines)


def test_too_short_file_is_rejected() -> None:
    fails("a\nb\n", line=None, match="слишком короткий")


# --- поиск файлов ---------------------------------------------------------


def make_questions(root: Path, folder: str, names: list[str]) -> None:
    """Создаёт в ``root/folder`` пустые файлы с указанными именами."""
    directory = root / folder
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        (directory / name).write_text(encoding="utf-8", data="x")


def registry() -> SubjectRegistry:
    """Реестр из Docker (ru+kk) и Java (kk)."""
    java = Subject(
        slug="java", folder="Java", label="Java", id_prefix="J", languages=[Lang.KK]
    )
    return SubjectRegistry(subjects=[DOCKER, java])


def test_discovery_resolves_languages_and_ignores_keys(tmp_path: Path) -> None:
    make_questions(
        tmp_path,
        "Docker",
        [
            "ch2_questions_ru.txt",
            "ch2_questions_kz.txt",
            "ch10_questions_ru(d).txt",
            "ch2_question_keys_ru.txt",
            "exam_prompts_docker.md",
        ],
    )
    make_questions(tmp_path, "Java", ["ch1_questions.txt"])
    found = [
        (s.subject.slug, s.language, s.file_chapter)
        for s in discover_sources(tmp_path, registry())
    ]
    assert found == [
        ("docker", Lang.KK, 2),
        ("docker", Lang.RU, 2),
        ("docker", Lang.RU, 10),
        ("java", Lang.KK, 1),
    ]


def test_discovery_rejects_suffix_for_single_language_subject(tmp_path: Path) -> None:
    make_questions(tmp_path, "Docker", ["ch2_questions_ru.txt"])
    make_questions(tmp_path, "Java", ["ch1_questions_kz.txt"])
    with pytest.raises(ConversionError, match="суффикс языка недопустим"):
        discover_sources(tmp_path, registry())


def test_discovery_requires_suffix_for_multi_language_subject(tmp_path: Path) -> None:
    make_questions(tmp_path, "Docker", ["ch2_questions.txt"])
    make_questions(tmp_path, "Java", ["ch1_questions.txt"])
    with pytest.raises(ConversionError, match="нужен суффикс"):
        discover_sources(tmp_path, registry())


def test_discovery_rejects_bad_file_name(tmp_path: Path) -> None:
    make_questions(tmp_path, "Docker", ["chapter2_questions_ru.txt"])
    make_questions(tmp_path, "Java", ["ch1_questions.txt"])
    with pytest.raises(ConversionError, match="не соответствует шаблону"):
        discover_sources(tmp_path, registry())


def test_discovery_rejects_missing_folder(tmp_path: Path) -> None:
    with pytest.raises(ConversionError, match="нет папки"):
        discover_sources(tmp_path, registry())


def test_discovery_rejects_folder_without_files(tmp_path: Path) -> None:
    make_questions(tmp_path, "Docker", ["ch2_question_keys_ru.txt"])
    make_questions(tmp_path, "Java", ["ch1_questions.txt"])
    with pytest.raises(ConversionError, match="нет файлов вопросов"):
        discover_sources(tmp_path, registry())


def test_discovery_rejects_duplicate_chapter(tmp_path: Path) -> None:
    make_questions(
        tmp_path, "Docker", ["ch2_questions_ru.txt", "ch2_questions_ru(d).txt"]
    )
    make_questions(tmp_path, "Java", ["ch1_questions.txt"])
    with pytest.raises(ConversionError, match="дубликат"):
        discover_sources(tmp_path, registry())


def test_parse_source_reads_file(tmp_path: Path) -> None:
    path = tmp_path / "ch3_questions_ru.txt"
    path.write_text(encoding="utf-8", data=build_source())
    chapter = parse_source(
        SourceFile(path=path, subject=DOCKER, language=Lang.RU, file_chapter=3)
    )
    assert chapter.subject == "docker"


def test_parse_source_wraps_read_error(tmp_path: Path) -> None:
    missing = SourceFile(
        path=tmp_path / "nope.txt", subject=DOCKER, language=Lang.RU, file_chapter=3
    )
    with pytest.raises(ConversionError, match="не удалось прочитать"):
        parse_source(missing)
