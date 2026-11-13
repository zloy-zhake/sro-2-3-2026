"""Тесты Dataset.load, пулов по этапам и генерации билетов."""

import random
import shutil
from importlib.resources import files
from pathlib import Path

import pytest

from exam_tickets.dataset import Dataset
from exam_tickets.exceptions import DataError
from exam_tickets.models import LEVEL_ORDER, Lang, Stage
from exam_tickets.tickets import (
    Pool,
    build_pool,
    empty_levels,
    generate_ticket,
)

PACKAGED = files("exam_tickets").joinpath("data")

# Требования §5.2: диапазон глав каждого пула.
EXPECTED_CHAPTERS = {
    ("java", Lang.KK, Stage.SRO2): set(range(1, 6)),
    ("java", Lang.KK, Stage.SRO3): set(range(6, 12)),
    ("fsharp", Lang.RU, Stage.SRO2): set(range(2, 6)),
    ("fsharp", Lang.RU, Stage.SRO3): set(range(6, 12)),
    ("docker", Lang.RU, Stage.SRO2): set(range(1, 6)),
    ("docker", Lang.RU, Stage.SRO3): set(range(6, 11)),
    ("docker", Lang.KK, Stage.SRO2): set(range(1, 6)),
    ("docker", Lang.KK, Stage.SRO3): set(range(6, 11)),
}


@pytest.fixture(scope="module")
def dataset() -> Dataset:
    """Пакетные данные, загруженные один раз на модуль."""
    return Dataset.load(root=PACKAGED)


def test_dataset_loads_all_39_files(dataset: Dataset) -> None:
    assert sum(len(v) for v in dataset.chapters.values()) == 39


def test_dataset_files_are_sorted_by_chapter(dataset: Dataset) -> None:
    numbers = [c.file_chapter for c in dataset.files(subject="java", language=Lang.KK)]
    assert numbers == sorted(numbers)


def test_dataset_files_of_unknown_combination_are_empty(dataset: Dataset) -> None:
    assert dataset.files(subject="java", language=Lang.RU) == []


def test_dataset_load_fails_on_missing_subject_folder(tmp_path: Path) -> None:
    shutil.copy(Path(str(PACKAGED)) / "subjects.yaml", tmp_path / "subjects.yaml")
    with pytest.raises(DataError, match="нет каталога"):
        Dataset.load(root=tmp_path)


def test_dataset_load_fails_on_renamed_file(tmp_path: Path) -> None:
    shutil.copytree(Path(str(PACKAGED)), tmp_path / "data")
    root = tmp_path / "data"
    (root / "docker" / "ch03.ru.yaml").rename(root / "docker" / "ch03.kk.yaml.bak")
    (root / "docker" / "ch04.ru.yaml").rename(root / "docker" / "ch99.ru.yaml")
    with pytest.raises(DataError, match="не соответствует имени"):
        Dataset.load(root=root)


def test_dataset_load_fails_on_broken_yaml(tmp_path: Path) -> None:
    shutil.copytree(Path(str(PACKAGED)), tmp_path / "data")
    root = tmp_path / "data"
    (root / "java" / "ch01.kk.yaml").write_text("levels: [\n", encoding="utf-8")
    with pytest.raises(DataError, match=r"ch01\.kk\.yaml"):
        Dataset.load(root=root)


def test_dataset_load_fails_on_invalid_chapter(tmp_path: Path) -> None:
    shutil.copytree(Path(str(PACKAGED)), tmp_path / "data")
    root = tmp_path / "data"
    path = root / "java" / "ch01.kk.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace("points: 24", "points: 25"),
        encoding="utf-8",
    )
    with pytest.raises(DataError, match="баллы"):
        Dataset.load(root=root)


@pytest.mark.parametrize(("subject", "language", "stage"), list(EXPECTED_CHAPTERS))
def test_pool_covers_exact_chapter_range(
    dataset: Dataset, subject: str, language: Lang, stage: Stage
) -> None:
    pool = build_pool(dataset=dataset, subject=subject, language=language, stage=stage)
    covered = {
        c for items in pool.values() for item in items for c in item.chapter.chapters
    }
    assert covered == EXPECTED_CHAPTERS[(subject, language, stage)]
    assert empty_levels(pool=pool) == []


@pytest.mark.parametrize(("subject", "language", "stage"), list(EXPECTED_CHAPTERS))
def test_ticket_has_three_questions_of_different_levels_from_stage(
    dataset: Dataset, subject: str, language: Lang, stage: Stage
) -> None:
    pool = build_pool(dataset=dataset, subject=subject, language=language, stage=stage)
    ticket = generate_ticket(pool=pool, previous=None, rng=random.Random(1))
    assert [item.level for item in ticket.items] == list(LEVEL_ORDER)
    assert all(item.chapter.stage is stage for item in ticket.items)
    assert all(
        item.question in item.chapter.levels[item.level].questions
        for item in ticket.items
    )


def test_pool_is_sorted_by_chapter_and_id(dataset: Dataset) -> None:
    pool = build_pool(
        dataset=dataset, subject="docker", language=Lang.RU, stage=Stage.SRO2
    )
    for items in pool.values():
        keys = [(i.chapter.file_chapter, i.question.id) for i in items]
        assert keys == sorted(keys)


def test_no_adjacent_repeats_in_1000_generations(dataset: Dataset) -> None:
    pool = build_pool(
        dataset=dataset, subject="java", language=Lang.KK, stage=Stage.SRO3
    )
    rng = random.Random(2026)
    previous = None
    for _ in range(1000):
        ticket = generate_ticket(pool=pool, previous=previous, rng=rng)
        if previous is not None:
            for old, new in zip(previous.items, ticket.items, strict=True):
                assert old.question.id != new.question.id
        previous = ticket


def test_every_question_of_a_level_is_reachable(dataset: Dataset) -> None:
    pool = build_pool(
        dataset=dataset, subject="fsharp", language=Lang.RU, stage=Stage.SRO2
    )
    rng = random.Random(7)
    seen: set[str] = set()
    previous = None
    for _ in range(2000):
        previous = generate_ticket(pool=pool, previous=previous, rng=rng)
        seen.update(item.question.id for item in previous.items)
    expected = {item.question.id for items in pool.values() for item in items}
    assert seen == expected


def test_same_seed_gives_same_sequence(dataset: Dataset) -> None:
    pool = build_pool(
        dataset=dataset, subject="docker", language=Lang.KK, stage=Stage.SRO3
    )

    def run() -> list[list[str]]:
        rng, previous, out = random.Random(5), None, []
        for _ in range(20):
            previous = generate_ticket(pool=pool, previous=previous, rng=rng)
            out.append([i.question.id for i in previous.items])
        return out

    assert run() == run()


def test_single_question_level_allows_repeat(dataset: Dataset) -> None:
    full = build_pool(
        dataset=dataset, subject="java", language=Lang.KK, stage=Stage.SRO2
    )
    pool: Pool = {level: items[:1] for level, items in full.items()}
    first = generate_ticket(pool=pool, previous=None, rng=random.Random(1))
    second = generate_ticket(pool=pool, previous=first, rng=random.Random(2))
    assert [i.question.id for i in first.items] == [i.question.id for i in second.items]


def test_empty_level_blocks_generation(dataset: Dataset) -> None:
    full = build_pool(
        dataset=dataset, subject="java", language=Lang.KK, stage=Stage.SRO2
    )
    pool: Pool = {**full, LEVEL_ORDER[1]: []}
    assert empty_levels(pool=pool) == [LEVEL_ORDER[1]]
    with pytest.raises(DataError, match="нет вопросов"):
        generate_ticket(pool=pool, previous=None, rng=random.Random(1))


def test_pool_of_unknown_combination_is_empty(dataset: Dataset) -> None:
    pool = build_pool(
        dataset=dataset, subject="java", language=Lang.RU, stage=Stage.SRO2
    )
    assert empty_levels(pool=pool) == list(LEVEL_ORDER)
