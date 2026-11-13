"""Точка входа Streamlit: настройка логирования и запуск приложения.

Файл выполняется на каждый rerun, поэтому здесь только лёгкая инициализация.
"""

import logging

from exam_tickets.app import main

# basicConfig не перезаписывает уже настроенное логирование (Streamlit мог его
# настроить), поэтому повторные вызовы на rerun безвредны.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

main()
