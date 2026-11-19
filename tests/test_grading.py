"""Тесты подсчёта баллов: сумма принятых ответов и пересчёт в шкалу СРО."""

from decimal import Decimal

import pytest

from exam_tickets.grading import (
    GRADE_SCALE,
    SUBITEM_POINTS,
    checked_total,
    scale_points,
)
from exam_tickets.models import LEVEL_ORDER, LEVEL_POINTS, LevelKey


def test_checked_total_ignores_unchecked_subitems() -> None:
    assert checked_total(scores=[(True, 24), (False, 32), (True, 30)]) == 54


def test_checked_total_is_zero_when_nothing_checked() -> None:
    assert checked_total(scores=[(False, 24), (False, 32), (False, 44)]) == 0


def test_scale_points_rounds_to_tenths() -> None:
    assert scale_points(points=56, maximum=100) == Decimal("14.6")


def test_scale_points_rounds_half_up() -> None:
    # 25 × 26 / 100 = 6.5 → до десятых без изменений; 1 × 26 / 40 = 0.65 → 0.7.
    assert scale_points(points=1, maximum=40) == Decimal("0.7")


def test_scale_points_full_score_gives_full_scale() -> None:
    assert scale_points(points=100, maximum=100) == Decimal(GRADE_SCALE)


def test_scale_points_rejects_non_positive_maximum() -> None:
    with pytest.raises(ValueError, match="положительным"):
        scale_points(points=0, maximum=0)


@pytest.mark.parametrize("level", LEVEL_ORDER)
def test_subitem_points_sum_to_level_points(level: LevelKey) -> None:
    assert sum(SUBITEM_POINTS[level]) == LEVEL_POINTS[level]
