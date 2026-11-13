FROM python:3.14.2-slim AS base

# Poetry ставится в образ, а зависимости — в venv внутри проекта: после
# USER appuser глобальный venv Poetry был бы недоступен.
ENV POETRY_VIRTUALENVS_IN_PROJECT=true \
    PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir poetry==2.5.1

# Зависимости — отдельным слоем: он кэшируется, пока не меняются pyproject и lock
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-interaction --no-ansi --no-root --only=main

# Исходники — после зависимостей, чтобы правки кода не сбрасывали кэш
COPY src/ ./src/
COPY streamlit_app.py ./
COPY .streamlit/ ./.streamlit/
RUN poetry install --no-interaction --no-ansi --only-root

# Приложение работает не от root
RUN useradd --create-home appuser && chown --recursive appuser /app
USER appuser

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py", "--server.address=0.0.0.0", "--server.headless=true"]
