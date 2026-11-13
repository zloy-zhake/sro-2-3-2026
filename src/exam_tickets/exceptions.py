"""Исключения приложения.

Собственные классы нужны, чтобы вызывающий код ловил именно ошибки
предметной области, а не случайные ``ValueError`` из чужих библиотек.
"""


class AppError(Exception):
    """Базовый класс для всех исключений приложения."""


class DataError(AppError):
    """Ошибка загрузки или валидации данных вопросов."""


class ConversionError(AppError):
    """Ошибка конвертации исходного ``.txt`` в YAML.

    Сообщение всегда содержит файл, номер строки и причину (требования §4):
    автору вопросов нужно сразу видеть, где именно сломан файл.

    Attributes:
        file: Путь к исходному файлу.
        line: Номер строки (с 1) или ``None``, если ошибка относится ко всему файлу.
        reason: Описание причины.
    """

    def __init__(self, file: str, line: int | None, reason: str) -> None:
        """Формирует сообщение вида ``файл:строка: причина``.

        Args:
            file: Путь к исходному файлу.
            line: Номер строки или ``None``.
            reason: Описание причины.
        """
        self.file = file
        self.line = line
        self.reason = reason
        location = file if line is None else f"{file}:{line}"
        super().__init__(f"{location}: {reason}")
