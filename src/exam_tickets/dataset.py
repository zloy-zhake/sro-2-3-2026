"""Загрузка данных вопросов из корня данных (пакетного или временного)."""

import logging
from importlib.resources.abc import Traversable

import yaml
from pydantic import ValidationError

from exam_tickets.exceptions import DataError
from exam_tickets.models import SubjectRegistry

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
