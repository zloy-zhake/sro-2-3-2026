# LLM.md

> Context for AI assistants working in this codebase.

## Project

<!-- One sentence: what does this project do? -->

---

## Working with This Codebase

Before starting any non-trivial task, ask all the questions whose answers would help you complete it at the highest possible quality. If after receiving answers new questions arise, continue asking until you have everything you need. Only then begin the task.

This applies to: implementing new features, refactoring, debugging, writing tests, and any task where the requirements, context, or intent are ambiguous.

Do not make assumptions to avoid asking — a wrong assumption costs more to fix than a clarifying question.

---

## Environment & Dependencies

This project uses **Poetry** for dependency and virtual environment management.

```bash
poetry install              # install all dependencies
poetry add <pkg>            # add a runtime dependency
poetry add --group dev <pkg>  # add a dev dependency
poetry run <cmd>            # run a command inside the venv
poetry shell                # activate the venv interactively
```

**Never use `pip install` directly.** All dependencies must go through Poetry and be committed to `pyproject.toml` and `poetry.lock`.

---

## Terminal Commands

When running shell commands, always prefer long option names (starting with `--`) over short ones (starting with `-`) wherever the tool supports them. Long names are self-documenting and make commands readable without consulting the man page.

```bash
# ✅ — intent is immediately clear
pytest --verbose --exitfirst --cov=src --cov-report=term-missing
isort --check-only --diff .
ruff check --fix .
git commit --message "добавлена валидация email"
git switch --create feature/add-email-validation

# ❌ — requires mental decoding
pytest -v -x --cov=src
isort -c --diff .
git commit -m "добавлена валидация email"
git switch -c feature/add-email-validation
```

This applies to all CLI tools used in the project: `pytest`, `mypy`, `ruff`, `isort`, `git`, `poetry`, and any others. If a flag has no long form, use the short one and add a comment explaining it.

---

## Makefile

All common project operations are run via `make`. Never invoke the underlying tools (Poetry, pytest, mypy, ruff, isort) directly from the command line — use the corresponding `make` target instead.

```bash
make install       # install all dependencies (poetry install)
make test          # run the test suite
make lint          # run all linters (ruff, mypy, isort)
make format        # auto-format and sort imports
make run           # start the application
make clean         # remove build artifacts and caches
```

If a `make` target does not yet exist for a task you need, add it to the `Makefile` — don't work around it with raw commands. Keep targets short, composable, and documented with a `##` comment so `make help` stays useful:

```makefile
.PHONY: test
test:  ## Run the full test suite with coverage
	poetry run pytest --cov=src --cov-report=term-missing
```

Before running any project operation, check whether a `make` target exists for it:

```bash
make help   # list all available targets
```

---

## Docker & Docker Compose

The project can be built and run inside Docker. All Docker operations are wrapped in `make` targets — use those instead of invoking `docker` or `docker compose` directly.

```bash
make docker-build    # build the image
make docker-up       # start all services (detached)
make docker-down     # stop and remove containers
make docker-logs     # follow container logs
make docker-shell    # open a shell inside the app container
```

Add the corresponding targets to the `Makefile` if they don't exist yet:

```makefile
.PHONY: docker-build
docker-build:  ## Build the Docker image
	docker build --tag myproject:latest .

.PHONY: docker-up
docker-up:  ## Start all services in detached mode
	docker compose up --detach --build

.PHONY: docker-down
docker-down:  ## Stop and remove containers, networks, and volumes
	docker compose down --volumes --remove-orphans

.PHONY: docker-logs
docker-logs:  ## Follow logs from all running containers
	docker compose logs --follow

.PHONY: docker-shell
docker-shell:  ## Open an interactive shell inside the app container
	docker compose exec app bash
```

### Environment variables

Never bake secrets into the image. Pass them through a `.env` file that is **never committed** (add it to `.gitignore`). Docker Compose picks it up automatically:

```bash
# .env  (local only, not committed)
DATABASE_URL=postgresql://user:password@db:5432/myproject
SECRET_KEY=your-secret-key
```

Reference variables in `docker-compose.yml` via `env_file`:

```yaml
services:
  app:
    build: .
    env_file:
      - .env
    depends_on:
      - db

  db:
    image: postgres:16-alpine
    env_file:
      - .env
```

Provide a `.env.example` file with all required keys and placeholder values — this is the contract for anyone setting up the project:

```bash
# .env.example  (committed)
DATABASE_URL=postgresql://user:password@db:5432/myproject
SECRET_KEY=changeme
```

### Running tests inside Docker

To run the test suite inside the container (mirrors CI behaviour):

```bash
docker compose run --rm app poetry run pytest --cov=src --cov-report=term-missing
```

Or add a `make` target:

```makefile
.PHONY: docker-test
docker-test:  ## Run the test suite inside Docker
	docker compose run --rm app poetry run pytest --cov=src --cov-report=term-missing
```

### Dockerfile conventions

- Use a specific, pinned base image tag — never `latest`.
- Install dependencies in a separate layer before copying source code so Docker's cache is not invalidated on every code change.
- Run the application as a non-root user.

```dockerfile
FROM python:3.12-slim AS base

WORKDIR /app

# Install dependencies first — this layer is cached until pyproject.toml changes
COPY pyproject.toml poetry.lock ./
RUN pip install --no-cache-dir poetry \
    && poetry install --no-interaction --no-ansi --only=main

# Copy source after deps to maximise cache reuse
COPY src/ ./src/

# Run as non-root user
RUN useradd --create-home appuser
USER appuser

CMD ["poetry", "run", "python", "-m", "myproject"]
```

---

## Code Style & Conventions

### Type Hints

Type hints are **required everywhere** — all function arguments, return types, and class attributes must be annotated.

- Use built-in generics: `list[str]`, `dict[str, int]`, `tuple[int, ...]` — not `typing.List`, `typing.Dict` (Python 3.9+).
- Prefer `X | None` over `Optional[X]`.
- Avoid `Any`. If unavoidable, add an inline comment explaining why.

```python
# ✅
def process(items: list[str]) -> dict[str, int]: ...
def find(name: str) -> User | None: ...

# ❌
def process(items): ...
def find(name: str) -> Optional[User]: ...
```

### TYPE_CHECKING Imports

Use `TYPE_CHECKING` to avoid circular imports:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from myproject.models import ClassB
```

### Type Checking — mypy

mypy runs in strict mode:

```bash
poetry run mypy .
```

All code must pass with zero errors. Avoid `# type: ignore` — if truly necessary, add a comment explaining why.

### Import Sorting — isort

```bash
poetry run isort .
```

Import order: **standard library → third-party → local**. Always use absolute imports — relative imports are not allowed.

```python
# ✅
import os
from pathlib import Path

import httpx

from myproject.models import User

# ❌
from .models import User
```

### Named Parameters

Always use named parameters when calling functions and methods:

```python
# ✅
with open(file="file.txt", mode="r") as f: ...
result = some_func(timeout=30, retry=True)

# ❌
with open("file.txt", "r") as f: ...
result = some_func(30, True)
```

### Linting — ruff

```bash
poetry run ruff check .         # lint
poetry run ruff check . --fix   # auto-fix safe issues
```

Do not introduce code that produces ruff warnings. If a rule must be suppressed, add an inline comment with justification:

```python
result = eval(expr)  # noqa: S307 — input is validated upstream
```

---

## Documentation

- Write docstrings for **every** function, method, and class.
- **Language: Russian.**
- **Format: Google Docstring style.**
- Explain **why** the code does what it does, not just what.
- Add inline comments for anything non-obvious or unexpected.

```python
def calculate_retry_delay(attempt: int) -> float:
    """Вычисляет задержку перед повторной попыткой с экспоненциальным откатом.

    Используем экспоненциальный откат, чтобы снизить нагрузку на сервер
    при последовательных ошибках. Максимум ограничен 60 секундами,
    чтобы не блокировать очередь задач надолго.

    Args:
        attempt: Номер попытки, начиная с 1.

    Returns:
        Количество секунд ожидания перед следующей попыткой.
    """
    return min(2 ** attempt, 60)
```

---

## Testing

Tests use **pytest** with coverage tracked via `pytest-cov`.

```bash
poetry run pytest                                            # run all tests
poetry run pytest -x                                        # stop on first failure
poetry run pytest --cov=src --cov-report=term-missing       # with coverage
```

### Conventions

- Test files live in `tests/` and mirror the `src/` layout.
- Name tests `test_<what_it_does>` — be descriptive.
- One logical assertion per test where possible.
- Use `pytest.raises` for expected exceptions — never bare `try/except` in tests.
- Fixtures go in `conftest.py` at the appropriate scope level.
- All test functions must have return type `-> None`.

```python
# ✅
def test_user_creation_sets_default_role() -> None:
    user = User(name="Alice")
    assert user.role == "viewer"

# ❌
def test_user():
    ...
```

---

## Exception Handling

Exceptions must be handled in the safest, most explicit manner possible. Reliability is the priority.

### Always catch specific exceptions

In general, never catch bare `Exception` or `BaseException` — always name the specific exception type you expect. The only two legitimate uses of a bare `Exception` catch are: (a) a top-level boundary that immediately re-raises or logs with full context, and (b) a safety-net handler at the end of a critical path, which is covered in the next section.

```python
# ✅
try:
    response = client.get(url=url, timeout=5)
except httpx.TimeoutException:
    logger.warning("Request timed out", extra={"url": url})
    raise

# ❌ — swallows everything, hides bugs
try:
    response = client.get(url=url, timeout=5)
except Exception:
    pass
```

### Catch-all handler in critical paths

This is the one deliberate exception to the rule above. In code that is critical to the project's reliability — entry points, background workers, request handlers, scheduled jobs — add a bare `Exception` catch at the very end of the handler, after all specific exceptions. Its sole purpose is to ensure nothing escapes silently. It must always log the full traceback and either re-raise or perform a safe shutdown/recovery action.

```python
# ✅ — critical path with a safety net at the end
def process_payment(order_id: int) -> None:
    try:
        order = fetch_order(order_id=order_id)
        charge(order=order)
    except OrderNotFoundError:
        logger.warning("Заказ не найден", extra={"order_id": order_id})
    except PaymentGatewayError as e:
        logger.error("Ошибка платёжного шлюза", extra={"order_id": order_id})
        raise
    except Exception:
        # Непредвиденная ошибка — логируем с трейсбеком и пробрасываем дальше,
        # чтобы вышестоящий обработчик мог среагировать корректно.
        logger.critical(
            "Непредвиденная ошибка при обработке платежа",
            extra={"order_id": order_id},
            exc_info=True,
        )
        raise
```

This pattern is only appropriate at well-defined boundaries. Do not scatter bare `Exception` catches throughout business logic — that defeats the purpose. See the rule about specific exceptions above.

Every `except` block must do at least one of: log, re-raise, or return a meaningful fallback. A bare `pass` is never acceptable.

```python
# ✅ — log and re-raise
except ValueError as e:
    logger.error("Invalid input", extra={"error": str(e)})
    raise

# ✅ — explicit fallback with a comment explaining why it's safe
except KeyError:
    return default_value  # key is optional; absence is a valid state

# ❌
except ValueError:
    pass
```

### Always preserve the exception chain

Use `raise ... from` to keep the original traceback when wrapping exceptions:

```python
# ✅
try:
    data = json.loads(raw)
except json.JSONDecodeError as e:
    raise ConfigurationError("Invalid config format") from e

# ❌ — original traceback is lost
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    raise ConfigurationError("Invalid config format")
```

### Use custom exception classes

Define domain-specific exceptions rather than reusing built-ins. Place them in `exceptions.py`:

```python
class AppError(Exception):
    """Базовый класс для всех исключений приложения."""

class ConfigurationError(AppError):
    """Ошибка конфигурации приложения."""

class ExternalServiceError(AppError):
    """Ошибка при взаимодействии с внешним сервисом."""
```

### Cleanup with finally and context managers

Use `finally` or context managers (`with`) to guarantee resource cleanup — never rely on an exception being caught to release resources:

```python
# ✅ — file is always closed
with open(file="data.txt", mode="r") as f:
    process(data=f.read())

# ✅ — cleanup always runs
try:
    connection.open()
    connection.send(data=payload)
finally:
    connection.close()
```

---

## Logging

This project uses Python's **stdlib `logging`** module. All log output is human-readable plaintext, intended for development and local debugging.

### Logger instantiation

Every module gets its own logger, named after the module. Never use the root logger directly.

```python
import logging

logger = logging.getLogger(name=__name__)
```

Never call `logging.basicConfig()` inside library or module code — only at the application entry point.

### Log levels

| Level | When to use |
|---|---|
| `DEBUG` | Detailed internal state, variable values, branching decisions — only useful when actively debugging |
| `INFO` | Normal lifecycle events: startup, shutdown, successful operations, key state transitions |
| `WARNING` | Something unexpected happened but the application recovered and can continue |
| `ERROR` | An operation failed and requires attention; the application continues running |
| `CRITICAL` | The application cannot continue and is about to crash or exit |

```python
logger.debug("Вычисляем задержку повтора", extra={"attempt": attempt})
logger.info("Соединение с базой данных установлено")
logger.warning("Кеш не найден, загружаем из источника", extra={"key": cache_key})
logger.error("Не удалось отправить запрос", extra={"url": url, "status": status})
logger.critical("Конфигурационный файл не найден, завершение работы")
```

### What must always be logged

- **Errors and exceptions** — every caught exception at `ERROR` or above, with context.
- **Application startup and shutdown** — at `INFO`, including key config values (but not secrets).
- **External calls** — outgoing HTTP requests, DB queries, and their outcomes at `DEBUG` or `INFO`.
- **Security-relevant events** — authentication attempts, permission denials, at `WARNING` or above.

```python
# ✅ — exception logged with context before re-raising
except httpx.HTTPStatusError as e:
    logger.error(
        "Внешний сервис вернул ошибку",
        extra={"url": str(e.request.url), "status": e.response.status_code},
    )
    raise
```

### What must never be logged

Never log the following — even at `DEBUG`:

- **Passwords, API keys, tokens, secrets** of any kind
- **Personal data (PII):** names, emails, phone numbers, IP addresses, user IDs linked to real people
- **Full request/response bodies** unless explicitly sanitized
- **Stack traces at INFO or below** — tracebacks belong at `ERROR` or `CRITICAL`

```python
# ❌ — logs a secret
logger.debug("Подключение к сервису", extra={"api_key": settings.api_key})

# ✅ — log presence, not value
logger.debug("Подключение к сервису", extra={"api_key_set": bool(settings.api_key)})
```

If you must log an object that may contain sensitive fields, implement a `__repr__` or `safe_dict()` method that explicitly redacts them.

### Log messages style

- Write log messages in **Russian**, consistent with docstrings and comments.
- Messages should be static strings — put variable data in `extra={}`, not in the message itself.

```python
# ✅
logger.info("Задача завершена", extra={"task_id": task_id, "duration_ms": elapsed})

# ❌ — hard to filter/search in log output
logger.info(f"Задача {task_id} завершена за {elapsed}ms")
```

---

## Git

### Branching model

This project follows a lightweight Git Flow with four branch types:

| Branch | Purpose |
|---|---|
| `master` / `main` | Production-ready code only. Never commit directly. |
| `develop` | Integration branch. All completed features merge here. |
| `feature/xxx` | New functionality. Branch off `develop`, merge back into `develop`. |
| `experiment/xxx` | Exploratory or throwaway work. No merge guarantees. |

### Working in the right branch

Before starting any work, check that you are on an appropriate branch for the task. If not, warn the user and offer to switch or create one.

**When to warn:**

- You are on `master`/`main` or `develop` and are about to implement a feature or make non-trivial changes — suggest creating a `feature/xxx` branch.
- You are on a `feature/xxx` branch but the task is exploratory or throwaway — suggest switching to or creating an `experiment/xxx` branch.
- You are on a branch that does not match any of the four patterns above — warn that the branch name is non-standard and suggest renaming or switching.

**How to check the current branch:**

```bash
git branch --show-current
```

**Switching and creating branches:**

Prefer `git switch` — it is the modern replacement for `git checkout` for branch operations and is clearer in intent. `git checkout` still works but is discouraged for this purpose.

```bash
# ✅ preferred — modern syntax
git switch develop
git switch --create feature/add-email-validation
git switch --create experiment/try-new-caching-strategy

# still works, but outdated
git checkout develop
git checkout -b feature/add-email-validation
```

Always confirm with the user before switching branches or creating new ones. Never switch branches silently.

### Commit regularly

Don't let changes pile up into one large commit. Commit as you complete logical steps: implemented a function — commit, added tests — commit, fixed a bug — commit. This makes reviews easier, lets you roll back to a known-good state, and keeps the project history readable.

### Each commit must be meaningful

One commit, one logical change. Don't mix refactoring with new features, bug fixes with formatting changes, or API changes with test updates. If a commit is hard to describe in a single phrase, it should probably be split.

```bash
# ✅ — atomic, descriptive commits
git commit -m "добавлена валидация email при регистрации"
git commit -m "покрыт тестами UserService.create"
git commit -m "исправлена утечка соединений в DatabasePool"

# ❌ — vague, useless messages
git commit -m "фиксы"
git commit -m "wip"
git commit -m "изменения"
```

### Commit messages must be in Russian

Write all messages in Russian, using the **short perfective past passive participle** (краткое страдательное причастие прошедшего времени совершенного вида: «добавлено», «исправлен», «удалены» — not «добавить», «добавлять»). This form is impersonal and subjectless by nature. Start with a lowercase letter, no trailing period. Keep the subject line to **72 characters or fewer**. In special cases — a particularly complex change or one that requires context — a longer body is allowed; separate it from the subject with a blank line.

```bash
# ✅
git commit -m "добавлено кэширование результатов внешнего API"
git commit -m "удалён устаревший модуль legacy_auth"
git commit -m "переименован get_user в find_user_by_id для ясности"

# With a body — when context is needed
git commit -m "увеличен таймаут запросов к платёжному сервису

Платёжный провайдер стал отвечать медленнее под нагрузкой.
Таймаут поднят с 5 до 15 секунд на основе их SLA-документации."

# ❌ — wrong language, wrong form
git commit -m "fix bug"
git commit -m "добавить валидацию"
git commit -m "исправлять баги"
```

---

## Abstractions

### Don't abstract prematurely

If a pattern appears in the codebase only once, implement it directly. Do not introduce abstract base classes, interfaces, factories, registries, or strategy objects speculatively — they add indirection without delivering any benefit yet.

```python
# ✅ — one use case, one direct implementation
class EmailNotifier:
    def send(self, recipient: str, subject: str, body: str) -> None:
        ...

# ❌ — abstract machinery for a single concrete thing
class BaseNotifier(ABC):
    @abstractmethod
    def send(self, recipient: str, subject: str, body: str) -> None:
        ...

class NotifierFactory:
    def create(self, kind: str) -> BaseNotifier:
        ...
```

The rule of thumb: **if you can't point to two distinct call sites that would benefit from a shared abstraction, don't create one.**

### Propose abstractions when duplication appears

When you are about to add code that is structurally similar to something already in the codebase, do not simply duplicate it. Instead, stop and present the options to the user before writing any code.

For each option, describe:
- **What changes** — what gets extracted, renamed, or restructured.
- **What you gain** — less duplication, easier extension, better testability, clearer intent, etc.
- **What it costs** — added indirection, migration effort, increased surface area, etc.

**Example options to consider and explain:**

| Abstraction | When it helps |
|---|---|
| Shared base class | Two classes share state and behaviour that will evolve together |
| Protocol / interface | Two classes share a contract but have unrelated implementations |
| Helper function | Two call sites share a stateless algorithm |
| Parametrised class | One class can cover both cases with a configuration argument |
| Strategy pattern | The differing part is a behaviour that may grow into more variants |

Present the options clearly, recommend one, and explain the reasoning — then wait for confirmation before proceeding. The user decides; you advise.

---

## Common Pitfalls

**Don't use `datetime.utcnow()`** — it returns a naive datetime with no timezone info. Use `datetime.now(UTC)` instead:

```python
# ❌
from datetime import datetime
now = datetime.utcnow()

# ✅
from datetime import datetime, UTC
now = datetime.now(tz=UTC)
```

**Don't use mutable default arguments** — the default object is created once and shared across all calls:

```python
# ❌ — all callers share the same list
def append_item(item: str, result: list[str] = []) -> list[str]:
    result.append(item)
    return result

# ✅
def append_item(item: str, result: list[str] | None = None) -> list[str]:
    if result is None:
        result = []
    result.append(item)
    return result
```

**Don't catch bare `Exception` in business logic** — always catch the specific exception type you expect. The only legitimate use is a safety-net handler at the end of a critical-path boundary (entry point, worker, request handler), where it must log with `exc_info=True` and re-raise. See the Exception Handling section for both rules.

**Don't use `assert` for runtime validation** — `assert` statements are stripped when Python runs with the `-O` flag. Use explicit `if` checks with proper exceptions instead:

```python
# ❌
assert user_id > 0, "user_id must be positive"

# ✅
if user_id <= 0:
    raise ValueError(f"user_id must be positive, got {user_id}")
```

**Don't use relative imports** — always use absolute imports. See the Import Sorting section.

```python
# ❌
from .models import User

# ✅
from myproject.models import User
```

**Don't compare to `None` with `==`** — always use `is` or `is not`:

```python
# ❌
if value == None: ...

# ✅
if value is None: ...
```

**Don't silence `mypy` errors with `# type: ignore` without explanation** — if it is truly unavoidable, add a comment explaining why. See the Type Checking section.

```python
# ❌
result = legacy_func()  # type: ignore

# ✅
result = legacy_func()  # type: ignore[return-value] — legacy_func стороннее, возвращает Any
```