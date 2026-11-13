.DEFAULT_GOAL := help

# Пути с «F#» и «(d)» здесь не перечисляются: «#» начинает комментарий,
# скобки ломают shell — файлы ищет сам конвертер.
QUESTIONS_DIR := questions
DATA_DIR := src/exam_tickets/data

.PHONY: help
help:  ## Показать список целей
	@grep --extended-regexp '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "} {printf "  %-18s %s\n", $$1, $$2}'

.PHONY: install
install:  ## Установить все зависимости
	poetry install

.PHONY: convert
convert:  ## Сгенерировать YAML из questions/*.txt
	poetry run python -m exam_tickets.convert --questions-dir $(QUESTIONS_DIR) --data-dir $(DATA_DIR)

.PHONY: check-data
check-data:  ## Проверить, что data/ соответствует исходникам
	poetry run python -m exam_tickets.convert --check --questions-dir $(QUESTIONS_DIR) --data-dir $(DATA_DIR)

.PHONY: run
run:  ## Запустить приложение
	poetry run streamlit run streamlit_app.py

.PHONY: test
test:  ## Запустить тесты с покрытием
	poetry run pytest --cov=src --cov-report=term-missing

.PHONY: lint
lint:  ## Запустить ruff, isort, mypy
	poetry run ruff check .
	poetry run ruff format --check .
	poetry run isort --check-only --diff .
	poetry run mypy .

.PHONY: format
format:  ## Отформатировать код и отсортировать импорты
	poetry run ruff format .
	poetry run isort .

.PHONY: clean
clean:  ## Удалить кэши и артефакты сборки (data/ не трогаем)
	rm --recursive --force .pytest_cache .mypy_cache .ruff_cache .coverage dist
	find . -name __pycache__ -type d -prune -exec rm --recursive --force {} +
	rm --recursive --force $(DATA_DIR).new $(DATA_DIR).old

.PHONY: requirements
requirements:  ## Сгенерировать requirements.txt (запасной вариант деплоя)
	poetry export --without-hashes --output requirements.txt
	echo "." >> requirements.txt

.PHONY: docker-build
docker-build:  ## Собрать образ Docker
	docker build --tag exam-tickets:latest .

.PHONY: docker-up
docker-up:  ## Запустить сервисы в фоне
	docker compose up --detach --build

.PHONY: docker-down
docker-down:  ## Остановить и удалить контейнеры
	docker compose down --volumes --remove-orphans

.PHONY: docker-logs
docker-logs:  ## Следить за логами контейнеров
	docker compose logs --follow

.PHONY: docker-shell
docker-shell:  ## Открыть shell в контейнере приложения
	docker compose exec app bash
