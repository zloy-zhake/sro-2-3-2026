"""Подсчёт баллов за ответы на вопросы задания.

Логика вынесена из Streamlit-интерфейса, чтобы её можно было проверить
обычными юнит-тестами без запуска приложения.
"""

from decimal import ROUND_HALF_UP, Decimal

# Шкала, в которую пересчитывается сумма: вес СРО в итоговой оценке.
GRADE_SCALE = 26
# Пересчитанный балл показывается с точностью до десятых.
_TENTHS = Decimal("0.1")


def accepted_total(scores: list[tuple[bool, int]]) -> int:
    """Суммирует баллы только принятых ответов.

    Непринятый ответ не даёт баллов, даже если в поле стоит число: по
    умолчанию поле заполнено максимумом уровня, и без галочки этот максимум
    не должен попадать в сумму.

    Args:
        scores: Пары «принят ли ответ, выставленный балл» по вопросам.

    Returns:
        Сумма баллов принятых ответов.
    """
    return sum(points for accepted, points in scores if accepted)


def scale_points(points: int, maximum: int, scale: int = GRADE_SCALE) -> Decimal:
    """Пересчитывает баллы в шкалу ``scale`` с округлением до десятых.

    Используем ``Decimal`` и ``ROUND_HALF_UP``: встроенный ``round`` округляет
    к чётному и спотыкается о двоичное представление (``round(0.25, 1)`` даёт
    ``0.2``), а преподаватель ждёт школьного округления.

    Args:
        points: Набранные баллы.
        maximum: Максимум баллов за задание.
        scale: Максимум целевой шкалы.

    Returns:
        Баллы в целевой шкале, например ``Decimal("14.6")``.

    Raises:
        ValueError: Если максимум не положителен — делить не на что.
    """
    if maximum <= 0:
        raise ValueError(f"максимум баллов должен быть положительным, а не {maximum}")
    exact = Decimal(points) * Decimal(scale) / Decimal(maximum)
    return exact.quantize(exp=_TENTHS, rounding=ROUND_HALF_UP)
