"""Тесты исключений приложения."""

from exam_tickets.exceptions import AppError, ConversionError, DataError


def test_conversion_error_message_contains_file_line_and_reason() -> None:
    error = ConversionError(file="a.txt", line=7, reason="плохая строка")
    assert str(error) == "a.txt:7: плохая строка"


def test_conversion_error_without_line_omits_line_number() -> None:
    error = ConversionError(file="a.txt", line=None, reason="BOM")
    assert str(error) == "a.txt: BOM"


def test_domain_errors_share_app_error_base() -> None:
    assert issubclass(DataError, AppError)
    assert issubclass(ConversionError, AppError)
