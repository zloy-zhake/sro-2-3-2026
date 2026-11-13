"""Тесты рендера: экранирование, определение таблиц, ссылки на главы."""

from pathlib import Path
from typing import Any

import pytest

from exam_tickets.models import ChapterFile, Lang
from exam_tickets.render import (
    format_chapter_ref,
    is_table_line,
    render_text,
    table_mask,
)

REAL_QUESTIONS = Path(__file__).resolve().parent.parent / "questions"

DOCKER_PS = [
    "CONTAINER ID   IMAGE        COMMAND              STATUS         PORTS",
    'b7e20c41d9aa   kz/site:v1   "httpd-foreground"   Up 5 seconds   0.0.0.0:8181',
]


# --- таблицы: контрольные примеры из §5.4 -----------------------------------


def test_pipe_table_row_is_table_line() -> None:
    assert is_table_line("| 1 | int x = 2; |       |")


def test_pipe_separator_row_is_table_line() -> None:
    assert is_table_line("|---|---|---|")


def test_fsharp_pipeline_with_indent_is_not_table() -> None:
    assert not is_table_line("    |> List.map (fun x -> x * 2)")


def test_fsharp_unindented_pipe_operator_is_not_table() -> None:
    assert not is_table_line("|> printfn")


def test_array_end_marker_is_not_table() -> None:
    assert not is_table_line("|];;")


def test_prose_with_hanging_indent_is_not_table() -> None:
    assert not is_table_line("    продолжение строки с висячим отступом и словами")


def test_long_docker_compose_command_is_not_table() -> None:
    assert not is_table_line(
        "docker compose -f docker-compose.yml -f override.yml up -d"
    )


def test_spaces_inside_quotes_are_not_column_gaps() -> None:
    assert not is_table_line('let s = "  data  " + "  more  "')


def test_docker_ps_block_is_table() -> None:
    assert table_mask(DOCKER_PS) == [True, True]


def test_single_aligned_line_is_not_table() -> None:
    assert table_mask(DOCKER_PS[:1]) == [False]


def test_aligned_block_followed_by_prose() -> None:
    lines = [*DOCKER_PS, "Обычная строка текста."]
    assert table_mask(lines) == [True, True, False]


def test_pipe_row_is_table_even_alone() -> None:
    assert table_mask(["| a | b |"]) == [True]


def test_java_comments_aligned_code_not_table() -> None:
    lines = ["int a = 1;      // первый", "int bb = 22;     // второй"]
    assert table_mask(lines) == [False, False]


# --- HTML ---------------------------------------------------------------


def test_html_special_characters_are_escaped() -> None:
    html = render_text("$x = <tag> & `code` # не заголовок\n")
    assert "&lt;tag&gt;" in html
    assert "&amp;" in html
    assert "<tag>" not in html
    assert "$x" in html
    assert "`code`" in html


def test_script_text_cannot_inject_markup() -> None:
    assert "<script>" not in render_text('<script>alert("x")</script>')


def test_indent_is_preserved_and_hanging() -> None:
    html = render_text("    отступ")
    assert "padding-left:4ch;text-indent:-4ch;" in html
    assert "    отступ" in html


def test_blank_line_is_kept() -> None:
    assert "<div>&nbsp;</div>" in render_text("a\n\nb\n")


def test_consecutive_table_lines_share_one_block() -> None:
    html = render_text("текст\n| a | b |\n| c | d |\nещё\n")
    assert html.count('class="tbl"') == 1
    assert "| a | b |\n| c | d |" in html


def test_tables_do_not_wrap_but_text_does() -> None:
    html = render_text("| a | b |\nпроза")
    assert "white-space:pre;overflow-x:auto;" in html
    assert "white-space:pre-wrap;overflow-wrap:anywhere;" in html


def test_html_does_not_use_streamlit_css_variables() -> None:
    assert "--" not in render_text("текст")


# --- ссылки на главы ------------------------------------------------------


def chapter(data: dict[str, Any], **changes: Any) -> ChapterFile:
    """Файл главы из фикстуры с изменёнными полями."""
    return ChapterFile.model_validate({**data, **changes})


def test_ref_ru_single(chapter_data: dict[str, Any]) -> None:
    chapter_data["chapter_titles"] = ["Building images"]
    ref = format_chapter_ref(chapter(chapter_data), Lang.RU)
    assert ref == "Глава 3 «Building images»"


def test_ref_ru_range(chapter_data: dict[str, Any]) -> None:
    c = chapter(
        chapter_data, file_chapter=2, chapters=[1, 2], chapter_titles=["A", "B"]
    )
    assert format_chapter_ref(c, Lang.RU) == "Главы 1–2 «A», «B»"


def test_ref_kk_single(chapter_data: dict[str, Any]) -> None:
    c = chapter(chapter_data, chapter_titles=["Images"])
    assert format_chapter_ref(c, Lang.KK) == "3-тарау «Images»"


def test_ref_kk_range(chapter_data: dict[str, Any]) -> None:
    c = chapter(
        chapter_data, file_chapter=2, chapters=[1, 2], chapter_titles=["A", "B"]
    )
    assert format_chapter_ref(c, Lang.KK) == "1–2-тараулар «A», «B»"


# --- реальные данные ------------------------------------------------------


@pytest.mark.skipif(not REAL_QUESTIONS.is_dir(), reason="нет каталога questions/")
def test_real_fsharp_quoted_spaces_do_not_trigger_tables() -> None:
    path = REAL_QUESTIONS / "F#" / "ch11_questions.txt"
    lines = path.read_text(encoding="utf-8").split("\n")
    flagged = [
        line for line, flag in zip(lines, table_mask(lines), strict=True) if flag
    ]
    assert not [line for line in flagged if '"  data  "' in line]
