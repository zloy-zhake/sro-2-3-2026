"""Тесты записи YAML, атомарной замены, --check и CLI конвертера."""

import logging
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from exam_tickets.convert import (
    chapter_relative_path,
    check,
    compare_trees,
    convert,
    dump_chapter,
    generate_tree,
    main,
)
from exam_tickets.exceptions import ConversionError, DataError
from exam_tickets.models import ChapterFile
from tests.builders import build_source

ROOT = Path(__file__).resolve().parent.parent
REAL_QUESTIONS = ROOT / "questions"
REAL_DATA = ROOT / "src" / "exam_tickets" / "data"

REGISTRY = """\
subjects:
  - slug: docker
    folder: Docker
    label: Docker
    id_prefix: D
    languages: [ru]
"""


@pytest.fixture
def project(tmp_path: Path) -> tuple[Path, Path]:
    """Мини-проект: ``questions/Docker/ch3_questions.txt`` и ``data/subjects.yaml``."""
    questions = tmp_path / "questions"
    (questions / "Docker").mkdir(parents=True)
    (questions / "Docker" / "ch3_questions.txt").write_text(
        build_source(), encoding="utf-8"
    )
    data = tmp_path / "data"
    data.mkdir()
    (data / "subjects.yaml").write_text(REGISTRY, encoding="utf-8")
    return questions, data


def literal_violations(text: str) -> list[str]:
    """Возвращает многострочные скаляры YAML, записанные не блоком ``|``."""
    bad: list[str] = []

    def walk(node: yaml.Node) -> None:
        if isinstance(node, yaml.ScalarNode):
            if "\n" in node.value and node.style != "|":
                bad.append(node.value[:40])
        elif isinstance(node, yaml.SequenceNode):
            for item in node.value:
                walk(item)
        elif isinstance(node, yaml.MappingNode):
            for key, value in node.value:
                walk(key)
                walk(value)

    root = yaml.compose(text)
    assert root is not None
    walk(root)
    return bad


def test_dump_uses_literal_blocks_for_multiline_texts(
    chapter_data: dict[str, Any],
) -> None:
    text = dump_chapter(ChapterFile.model_validate(chapter_data))
    assert literal_violations(text) == []
    assert "text: |\n" in text


def test_dump_round_trips_awkward_texts(chapter_data: dict[str, Any]) -> None:
    awkward = "$ docker ps\n  # комментарий\n<tag> `x`\n|---|---|\n"
    chapter_data["levels"]["cognitive"]["questions"][0]["text"] = awkward
    chapter = ChapterFile.model_validate(chapter_data)
    assert ChapterFile.model_validate(yaml.safe_load(dump_chapter(chapter))) == chapter


def test_dump_keeps_cyrillic_unescaped(chapter_data: dict[str, Any]) -> None:
    assert "КОГНИТИВНЫЙ" in dump_chapter(ChapterFile.model_validate(chapter_data))


def test_relative_path_uses_padded_chapter_and_language(
    chapter_data: dict[str, Any],
) -> None:
    chapter = ChapterFile.model_validate(chapter_data)
    assert chapter_relative_path(chapter) == Path("docker/ch03.ru.yaml")


def test_convert_writes_tree_and_keeps_registry(project: tuple[Path, Path]) -> None:
    questions, data = project
    assert convert(questions_dir=questions, data_dir=data) == 1
    assert (data / "docker" / "ch03.ru.yaml").is_file()
    assert (data / "subjects.yaml").read_text(encoding="utf-8") == REGISTRY


def test_convert_is_idempotent(project: tuple[Path, Path]) -> None:
    questions, data = project
    convert(questions_dir=questions, data_dir=data)
    first = (data / "docker" / "ch03.ru.yaml").read_bytes()
    convert(questions_dir=questions, data_dir=data)
    assert (data / "docker" / "ch03.ru.yaml").read_bytes() == first


def test_convert_removes_files_of_vanished_chapters(project: tuple[Path, Path]) -> None:
    questions, data = project
    (data / "docker").mkdir()
    (data / "docker" / "ch99.ru.yaml").write_text("stale", encoding="utf-8")
    convert(questions_dir=questions, data_dir=data)
    assert not (data / "docker" / "ch99.ru.yaml").exists()


def test_convert_leaves_no_temp_dirs(project: tuple[Path, Path]) -> None:
    questions, data = project
    convert(questions_dir=questions, data_dir=data)
    assert not data.with_name("data.new").exists()
    assert not data.with_name("data.old").exists()


def test_failed_conversion_keeps_data_untouched(project: tuple[Path, Path]) -> None:
    questions, data = project
    convert(questions_dir=questions, data_dir=data)
    before = (data / "docker" / "ch03.ru.yaml").read_bytes()
    (questions / "Docker" / "ch3_questions.txt").write_text("битый\n", encoding="utf-8")
    with pytest.raises(ConversionError):
        convert(questions_dir=questions, data_dir=data)
    assert (data / "docker" / "ch03.ru.yaml").read_bytes() == before
    assert not data.with_name("data.new").exists()


def test_recovery_restores_data_after_interrupted_swap(
    project: tuple[Path, Path],
) -> None:
    questions, data = project
    convert(questions_dir=questions, data_dir=data)
    data.rename(data.with_name("data.old"))  # имитация падения между двумя replace
    data.with_name("data.new").mkdir()
    convert(questions_dir=questions, data_dir=data)
    assert (data / "docker" / "ch03.ru.yaml").is_file()
    assert not data.with_name("data.old").exists()
    assert not data.with_name("data.new").exists()


def test_check_passes_after_convert(project: tuple[Path, Path]) -> None:
    questions, data = project
    convert(questions_dir=questions, data_dir=data)
    assert check(questions_dir=questions, data_dir=data) == []


def test_check_reports_changed_extra_and_missing_files(
    project: tuple[Path, Path],
) -> None:
    questions, data = project
    convert(questions_dir=questions, data_dir=data)
    target = data / "docker" / "ch03.ru.yaml"
    target.write_text(target.read_text(encoding="utf-8") + "# x\n", encoding="utf-8")
    (data / "docker" / "extra.yaml").write_text("x", encoding="utf-8")
    problems = check(questions_dir=questions, data_dir=data)
    assert "отличается: docker/ch03.ru.yaml" in problems
    assert "лишний файл: docker/extra.yaml" in problems
    target.unlink()
    assert "отсутствует: docker/ch03.ru.yaml" in check(
        questions_dir=questions, data_dir=data
    )


def test_compare_trees_identical(tmp_path: Path) -> None:
    for name in ("a", "b"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "f.yaml").write_text("x", encoding="utf-8")
    assert compare_trees(expected=tmp_path / "a", actual=tmp_path / "b") == []


def test_main_convert_and_check_return_codes(
    project: tuple[Path, Path], caplog: pytest.LogCaptureFixture
) -> None:
    questions, data = project
    args = ["--questions-dir", str(questions), "--data-dir", str(data)]
    assert main(args) == 0
    assert main(["--check", *args]) == 0
    (data / "docker" / "ch03.ru.yaml").write_text("x", encoding="utf-8")
    with caplog.at_level(logging.ERROR):
        assert main(["--check", *args]) == 1
    assert "Расхождение" in caplog.text


def test_main_returns_one_on_conversion_error(project: tuple[Path, Path]) -> None:
    questions, data = project
    (questions / "Docker" / "ch3_questions.txt").write_text("битый\n", encoding="utf-8")
    code = main(["--questions-dir", str(questions), "--data-dir", str(data)])
    assert code == 1


def test_main_returns_two_on_unexpected_error(
    project: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    questions, data = project

    def boom(*, questions_dir: Path, data_dir: Path) -> int:
        raise RuntimeError("неожиданно")

    monkeypatch.setattr("exam_tickets.convert.convert", boom)
    code = main(["--questions-dir", str(questions), "--data-dir", str(data)])
    assert code == 2


def test_generate_tree_requires_registry(tmp_path: Path) -> None:
    with pytest.raises(DataError):
        generate_tree(
            questions_dir=tmp_path, data_dir=tmp_path / "none", target=tmp_path
        )


# --- интеграция на реальных данных (критерии приёмки §8 пп. 1–2) ----------


@pytest.mark.skipif(not REAL_QUESTIONS.is_dir(), reason="нет каталога questions/")
def test_real_questions_match_committed_data() -> None:
    assert check(questions_dir=REAL_QUESTIONS, data_dir=REAL_DATA) == []


@pytest.mark.skipif(not REAL_QUESTIONS.is_dir(), reason="нет каталога questions/")
def test_real_conversion_is_idempotent(tmp_path: Path) -> None:
    data = tmp_path / "data"
    shutil.copytree(REAL_DATA, data)
    convert(questions_dir=REAL_QUESTIONS, data_dir=data)
    assert compare_trees(expected=REAL_DATA, actual=data) == []


def test_committed_data_has_39_chapter_files() -> None:
    assert len(list(REAL_DATA.glob("*/*.yaml"))) == 39


def test_committed_data_has_no_fence_lines() -> None:
    for path in REAL_DATA.glob("*/*.yaml"):
        for line in path.read_text(encoding="utf-8").splitlines():
            assert not line.strip().startswith("```"), f"{path.name}: {line}"


def test_committed_data_uses_literal_blocks_everywhere() -> None:
    for path in REAL_DATA.glob("*/*.yaml"):
        assert literal_violations(path.read_text(encoding="utf-8")) == [], path.name
