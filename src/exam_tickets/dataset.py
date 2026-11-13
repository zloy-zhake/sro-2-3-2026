"""Загрузка данных вопросов из корня данных (пакетного или временного)."""

import logging
import re
from collections import defaultdict
from collections.abc import Sequence
from importlib.resources.abc import Traversable

import yaml
from pydantic import ValidationError

from exam_tickets.exceptions import DataError
from exam_tickets.models import LEVEL_LETTERS, ChapterFile, Lang, SubjectRegistry

logger = logging.getLogger(name=__name__)

REGISTRY_FILE = "subjects.yaml"


def load_registry(root: Traversable) -> SubjectRegistry:
    """Читает и валидирует реестр предметов ``subjects.yaml``.

    Корень передаётся параметром (а не берётся из пакета), чтобы один и тот же
    код читал и боевые данные, и временный каталог конвертера, и фикстуры тестов.

    Args:
        root: Корень данных, в котором лежит ``subjects.yaml``.

    Returns:
        Проверенный реестр предметов.

    Raises:
        DataError: Если файл не читается, не является YAML или не проходит валидацию.
    """
    try:
        raw = yaml.safe_load(root.joinpath(REGISTRY_FILE).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
        logger.error("Не удалось прочитать реестр предметов", extra={"error": str(e)})
        raise DataError(f"не удалось прочитать {REGISTRY_FILE}: {e}") from e
    try:
        return SubjectRegistry.model_validate(raw)
    except ValidationError as e:
        logger.error("Реестр предметов не прошёл валидацию")
        raise DataError(f"{REGISTRY_FILE} не прошёл валидацию: {e}") from e


def check_chapters(chapters: Sequence[ChapterFile], registry: SubjectRegistry) -> None:
    """Проверяет правила §3.5, требующие реестра или сравнения файлов.

    Выполняется и конвертером (по только что разобранным файлам), и при
    загрузке готового YAML: ID в YAML могли испортить вручную.

    Проверяются: язык входит в языки предмета (п. 4), нет двух файлов одной
    главы и языка, ID уникальны в пределах предмета и языка (п. 2), ID
    соответствует префиксу предмета, ``file_chapter`` и букве уровня (п. 3).

    Args:
        chapters: Все файлы глав.
        registry: Реестр предметов.

    Raises:
        DataError: При любом нарушении.
    """
    files_seen: set[tuple[str, Lang, int]] = set()
    ids_seen: set[tuple[str, Lang, str]] = set()
    for chapter in chapters:
        subject = registry.get(slug=chapter.subject)
        if chapter.language not in subject.languages:
            raise DataError(
                f"{subject.slug}: язык {chapter.language} не входит в языки предмета"
            )
        file_key = (chapter.subject, chapter.language, chapter.file_chapter)
        if file_key in files_seen:
            raise DataError(f"{file_key}: дубликат файла главы")
        files_seen.add(file_key)
        for level_key, level in chapter.levels.items():
            pattern = re.compile(
                rf"^{re.escape(subject.id_prefix)}{chapter.file_chapter:02d}"
                rf"-{LEVEL_LETTERS[level_key]}-\d{{2}}$"
            )
            for question in level.questions:
                if pattern.match(question.id) is None:
                    raise DataError(
                        f"{subject.slug}/{chapter.language}: ID {question.id!r} не "
                        f"соответствует предмету, главе {chapter.file_chapter} "
                        f"и уровню {level_key}"
                    )
                id_key = (chapter.subject, chapter.language, question.id)
                if id_key in ids_seen:
                    raise DataError(f"ID {question.id!r} встречается повторно")
                ids_seen.add(id_key)


def find_id_mismatches(chapters: Sequence[ChapterFile]) -> list[tuple[str, int]]:
    """Находит главы, у которых наборы ID языковых версий различаются (§3.5 п. 7).

    Расхождение — не ошибка, а предупреждение: языковые версии могут
    временно разойтись. Отсутствие одной из языковых версий главы у
    многоязычного предмета тоже считается расхождением.

    Args:
        chapters: Все файлы глав.

    Returns:
        Пары ``(slug предмета, номер главы)`` с расхождением, по порядку.
    """
    by_chapter: dict[tuple[str, int], dict[Lang, set[str]]] = defaultdict(dict)
    all_languages: dict[str, set[Lang]] = defaultdict(set)
    for chapter in chapters:
        ids = {q.id for level in chapter.levels.values() for q in level.questions}
        by_chapter[(chapter.subject, chapter.file_chapter)][chapter.language] = ids
        all_languages[chapter.subject].add(chapter.language)
    mismatches = []
    for (slug, number), per_language in sorted(by_chapter.items()):
        id_sets = list(per_language.values())
        incomplete = set(per_language) != all_languages[slug]
        if incomplete or any(ids != id_sets[0] for ids in id_sets):
            mismatches.append((slug, number))
    return mismatches
