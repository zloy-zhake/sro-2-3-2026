"""Пул вопросов и генерация билета (требования §5.2, §5.3)."""

import random
from dataclasses import dataclass

from exam_tickets.dataset import Dataset
from exam_tickets.exceptions import DataError
from exam_tickets.models import (
    LEVEL_ORDER,
    ChapterFile,
    Lang,
    LevelKey,
    Question,
    Stage,
)


@dataclass(frozen=True)
class PoolItem:
    """Вопрос вместе с файлом, из которого он взят.

    Файл нужен целиком: заголовок, инструкция и главы берутся именно из него,
    потому что инструкции различаются от главы к главе (§5.4 п. 3).

    Attributes:
        level: Уровень вопроса.
        question: Сам вопрос.
        chapter: Файл главы вопроса.
    """

    level: LevelKey
    question: Question
    chapter: ChapterFile


@dataclass(frozen=True)
class Ticket:
    """Билет: ровно по одному вопросу на каждый уровень в порядке К → Ф → С.

    Attributes:
        items: Три вопроса билета.
    """

    items: tuple[PoolItem, ...]


Pool = dict[LevelKey, list[PoolItem]]


def build_pool(dataset: Dataset, subject: str, language: Lang, stage: Stage) -> Pool:
    """Собирает пул вопросов по уровням для предмета, языка и этапа.

    Пул упорядочен по ``(номер главы, ID)``: ``iterdir`` порядок не гарантирует,
    а одинаковый seed должен давать одинаковые билеты.

    Args:
        dataset: Загруженные данные.
        subject: Slug предмета.
        language: Язык вопросов.
        stage: Этап (СРО-2 или СРО-3).

    Returns:
        Для каждого уровня — список вопросов (может быть пустым).
    """
    pool: Pool = {level: [] for level in LEVEL_ORDER}
    for chapter in dataset.files(subject=subject, language=language):
        # Сравниваем значения, а не объекты: после горячей перезагрузки модулей
        # в Streamlit главы из кэша хранят экземпляр старого класса Stage, и
        # ``is`` отбросил бы их все — пул оказался бы пустым на всех уровнях.
        if chapter.stage != stage:
            continue
        for level in LEVEL_ORDER:
            pool[level] += [
                PoolItem(level=level, question=question, chapter=chapter)
                for question in chapter.levels[level].questions
            ]
    for items in pool.values():
        items.sort(key=lambda item: (item.chapter.file_chapter, item.question.id))
    return pool


def empty_levels(pool: Pool) -> list[LevelKey]:
    """Возвращает уровни, в которых нет ни одного вопроса (§5.6).

    Args:
        pool: Пул вопросов.

    Returns:
        Пустые уровни; пустой список — билет можно сформировать.
    """
    return [level for level in LEVEL_ORDER if not pool[level]]


def generate_ticket(pool: Pool, previous: Ticket | None, rng: random.Random) -> Ticket:
    """Формирует билет: независимый случайный вопрос на каждом уровне.

    Вопрос уровня отличается от вопроса того же уровня в предыдущем билете.
    Если на уровне остался единственный вопрос, повтор допускается (§5.3).

    Args:
        pool: Пул вопросов предмета, языка и этапа.
        previous: Предыдущий билет или ``None``.
        rng: Источник случайности — параметром, для детерминированных тестов.

    Returns:
        Новый билет.

    Raises:
        DataError: Если на каком-либо уровне нет вопросов.
    """
    missing = empty_levels(pool=pool)
    if missing:
        raise DataError(f"в пуле нет вопросов уровней: {', '.join(missing)}")
    previous_ids = (
        {item.level: item.question.id for item in previous.items} if previous else {}
    )
    chosen = []
    for level in LEVEL_ORDER:
        candidates = [
            item for item in pool[level] if item.question.id != previous_ids.get(level)
        ]
        # Единственный вопрос уровня: другого нет, повтор допустим.
        chosen.append(rng.choice(candidates or pool[level]))
    return Ticket(items=tuple(chosen))
