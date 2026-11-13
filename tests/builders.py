"""Сборщики тестовых данных."""

EQ = "=" * 70
DASH = "-" * 70
RU_HEADINGS = [
    "КОГНИТИВНЫЙ УРОВЕНЬ (24 балла)",
    "ФУНКЦИОНАЛЬНЫЙ УРОВЕНЬ (32 балла)",
    "СИСТЕМНЫЙ УРОВЕНЬ (44 балла)",
]


def build_source(
    letters: str = "КФС", chapter: int = 3, questions_per_level: int = 2
) -> str:
    """Собирает корректный исходный файл Docker (ru) для тестов парсера.

    Тесты делают из него «битые» варианты точечной заменой строк, поэтому
    все строки файла уникальны и легко находятся.

    Args:
        letters: Буквы уровней в порядке следования.
        chapter: Номер главы.
        questions_per_level: Сколько вопросов на каждом уровне.

    Returns:
        Текст файла с завершающим переводом строки.
    """
    lines = [
        "служебная строка 1",
        "Курс (с оговоркой) — устный экзамен, "
        f"глава {chapter} «Название главы» (Автор, Книга)",
        "служебная строка 3",
        "",
    ]
    for heading, letter in zip(RU_HEADINGS, letters, strict=True):
        lines += [EQ, heading, EQ, f"Инструкция {letter}.", ""]
        for number in range(1, questions_per_level + 1):
            lines += [
                DASH,
                f"D{chapter:02d}-{letter}-{number:02d}",
                DASH,
                f"Вопрос {letter}{number}.",
                "  с отступом",
                "",
            ]
    return "\n".join(lines).rstrip("\n") + "\n"
