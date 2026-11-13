"""Проверка белого списка ``.gitignore`` для каталога вопросов (требования §6.4)."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GIT = shutil.which("git")

pytestmark = pytest.mark.skipif(
    GIT is None or not (ROOT / ".git").exists(), reason="нужен git-репозиторий"
)


def is_ignored(path: str) -> bool:
    """Спрашивает у git, игнорируется ли путь (код 0 — игнорируется)."""
    assert GIT is not None
    result = subprocess.run(  # noqa: S603 — фиксированная команда, путь из тестов
        [GIT, "check-ignore", "--quiet", path], cwd=ROOT, check=False
    )
    return result.returncode == 0


@pytest.mark.parametrize(
    "path",
    [
        "questions/Docker/ch2_question_keys_ru.txt",
        "questions/Java/ch1_question_keys.txt",
        "questions/Docker/exam_prompts_docker.md",
        "questions/Docker/любой_новый_файл.pdf",
    ],
)
def test_keys_prompts_and_unknown_files_are_ignored(path: str) -> None:
    assert is_ignored(path)


@pytest.mark.parametrize(
    "path",
    [
        "questions/Docker/ch2_questions_ru.txt",
        "questions/Docker/ch10_questions_kz(d).txt",
        "questions/F#/ch4_questions.txt",
        "questions/Java/ch1_questions.txt",
    ],
)
def test_question_files_are_not_ignored(path: str) -> None:
    assert not is_ignored(path)
