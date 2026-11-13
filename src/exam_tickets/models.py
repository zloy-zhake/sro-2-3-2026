"""Pydantic-модели данных: реестр предметов и файл главы.

Модели — единый контракт для конвертера, приложения и тестов (требования §3.1).
Здесь только проверки, которым не нужен реестр предметов (§3.5 пп. 1, 5, 6, 8
и проверка заголовка из п. 9); остальное проверяет ``Dataset``.
"""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from exam_tickets.exceptions import DataError


class Lang(StrEnum):
    """Язык вопросов или интерфейса (ISO 639-1)."""

    RU = "ru"
    KK = "kk"


class LevelKey(StrEnum):
    """Уровень вопроса; значения — ключи в YAML."""

    COGNITIVE = "cognitive"
    FUNCTIONAL = "functional"
    SYSTEMIC = "systemic"


class Stage(StrEnum):
    """Этап: СРО-2 (главы 1–5) или СРО-3 (главы 6–11)."""

    SRO2 = "sro2"
    SRO3 = "sro3"


# Порядок уровней фиксирован: К → Ф → С (требования §2.2).
LEVEL_ORDER: tuple[LevelKey, ...] = (
    LevelKey.COGNITIVE,
    LevelKey.FUNCTIONAL,
    LevelKey.SYSTEMIC,
)

LEVEL_POINTS: dict[LevelKey, int] = {
    LevelKey.COGNITIVE: 24,
    LevelKey.FUNCTIONAL: 32,
    LevelKey.SYSTEMIC: 44,
}

# Буква уровня в ID вопроса — именно кириллица, а не латинские K/C.
LEVEL_LETTERS: dict[LevelKey, str] = {
    LevelKey.COGNITIVE: "К",
    LevelKey.FUNCTIONAL: "Ф",
    LevelKey.SYSTEMIC: "С",
}

# Точные заголовки уровней по языкам; сверяются дословно (§3.5 п. 9),
# чтобы файл с неверно приписанным языком не прошёл незамеченным.
LEVEL_HEADINGS: dict[Lang, dict[LevelKey, str]] = {
    Lang.RU: {
        LevelKey.COGNITIVE: "КОГНИТИВНЫЙ УРОВЕНЬ (24 балла)",
        LevelKey.FUNCTIONAL: "ФУНКЦИОНАЛЬНЫЙ УРОВЕНЬ (32 балла)",
        LevelKey.SYSTEMIC: "СИСТЕМНЫЙ УРОВЕНЬ (44 балла)",
    },
    Lang.KK: {
        LevelKey.COGNITIVE: "КОГНИТИВТІК ДЕҢГЕЙ (24 ұпай)",
        LevelKey.FUNCTIONAL: "ФУНКЦИОНАЛДЫҚ ДЕҢГЕЙ (32 ұпай)",
        LevelKey.SYSTEMIC: "ЖҮЙЕЛІК ДЕҢГЕЙ (44 ұпай)",
    },
}

MIN_CHAPTER = 1
MAX_CHAPTER = 11
# Граница этапов: главы 1–5 → СРО-2, 6–11 → СРО-3 (требования §5.2).
SRO2_LAST_CHAPTER = 5


def _require_non_blank(value: str, what: str) -> str:
    """Проверяет, что строка не пуста и не состоит из одних пробелов.

    Args:
        value: Проверяемая строка.
        what: Название поля для сообщения об ошибке.

    Returns:
        Исходная строка без изменений: тексты хранятся дословно.

    Raises:
        ValueError: Если строка пуста (§3.5 п. 8).
    """
    if not value.strip():
        raise ValueError(f"{what} не должен быть пустым")
    return value


class Subject(BaseModel):
    """Предмет из реестра ``subjects.yaml`` (требования §3.3)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    slug: str
    folder: str
    label: str
    id_prefix: str
    languages: list[Lang]

    @field_validator("languages")
    @classmethod
    def _languages_not_empty_unique(cls, value: list[Lang]) -> list[Lang]:
        """Требует хотя бы один язык и отсутствие повторов.

        Первый язык — язык по умолчанию в интерфейсе (план §1.6), поэтому
        порядок значим, а дубль бессмыслен.

        Args:
            value: Языки предмета.

        Returns:
            Те же языки.

        Raises:
            ValueError: Если список пуст или содержит повторы.
        """
        if not value:
            raise ValueError("у предмета должен быть хотя бы один язык")
        if len(set(value)) != len(value):
            raise ValueError("языки предмета не должны повторяться")
        return value


class SubjectRegistry(BaseModel):
    """Реестр предметов: единственное место, куда добавляют новый предмет."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    subjects: list[Subject]

    @model_validator(mode="after")
    def _unique_keys(self) -> Self:
        """Следит, чтобы slug, папка и префикс ID не повторялись.

        Повтор префикса сделал бы ID неоднозначными между предметами, а
        повтор папки — прочитал бы одни и те же файлы дважды.

        Returns:
            Сам реестр.

        Raises:
            ValueError: Если какое-либо из полей повторяется.
        """
        for field in ("slug", "folder", "id_prefix"):
            values = [getattr(subject, field) for subject in self.subjects]
            if len(set(values)) != len(values):
                raise ValueError(f"в реестре повторяется {field}")
        return self

    def get(self, slug: str) -> Subject:
        """Возвращает предмет по slug.

        Args:
            slug: Идентификатор предмета.

        Returns:
            Найденный предмет.

        Raises:
            DataError: Если предмета нет в реестре.
        """
        for subject in self.subjects:
            if subject.slug == slug:
                return subject
        raise DataError(f"предмет не найден в реестре: {slug}")


class Question(BaseModel):
    """Вопрос уровня."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    text: str

    @field_validator("text")
    @classmethod
    def _text_not_blank(cls, value: str) -> str:
        """Запрещает пустой текст вопроса (§3.5 п. 8).

        Args:
            value: Текст вопроса.

        Returns:
            Тот же текст.
        """
        return _require_non_blank(value=value, what="текст вопроса")


class Level(BaseModel):
    """Уровень в файле главы: заголовок, инструкция и вопросы."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    heading: str
    points: int
    instructions: str
    questions: list[Question]

    @field_validator("instructions")
    @classmethod
    def _instructions_not_blank(cls, value: str) -> str:
        """Запрещает пустую инструкцию уровня (§3.5 п. 8).

        Args:
            value: Текст инструкции.

        Returns:
            Тот же текст.
        """
        return _require_non_blank(value=value, what="инструкция")

    @field_validator("questions")
    @classmethod
    def _at_least_one_question(cls, value: list[Question]) -> list[Question]:
        """Требует хотя бы один вопрос на уровне (§3.5 п. 1).

        Args:
            value: Вопросы уровня.

        Returns:
            Те же вопросы.

        Raises:
            ValueError: Если вопросов нет.
        """
        if not value:
            raise ValueError("на уровне должен быть хотя бы один вопрос")
        return value


class ChapterFile(BaseModel):
    """Файл главы (или двух глав) на одном языке (требования §3.4)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    subject: str
    language: Lang
    file_chapter: int
    chapters: list[int]
    chapter_titles: list[str]
    levels: dict[LevelKey, Level]

    @model_validator(mode="after")
    def _validate_levels(self) -> Self:
        """Проверяет набор, порядок, баллы и заголовки уровней.

        Порядок словаря важен: YAML отдаёт его при загрузке, а UI опирается
        на К → Ф → С. Заголовок сверяется с языком файла дословно (§3.5 п. 9).

        Returns:
            Сам файл главы.

        Raises:
            ValueError: При любом нарушении §3.5 п. 1 или п. 9.
        """
        if tuple(self.levels) != LEVEL_ORDER:
            raise ValueError(
                "уровни должны идти в порядке cognitive, functional, systemic"
            )
        for key, level in self.levels.items():
            if level.points != LEVEL_POINTS[key]:
                raise ValueError(
                    f"уровень {key}: баллы {level.points}, "
                    f"ожидалось {LEVEL_POINTS[key]}"
                )
            expected = LEVEL_HEADINGS[self.language][key]
            if level.heading != expected:
                raise ValueError(
                    f"уровень {key}: заголовок {level.heading!r} не соответствует "
                    f"языку {self.language}, ожидалось {expected!r}"
                )
        return self

    @model_validator(mode="after")
    def _validate_chapters(self) -> Self:
        """Проверяет главы, их названия и принадлежность одному этапу.

        Вычисляет этап при создании модели, чтобы файл, лежащий на границе
        СРО-2/СРО-3, падал уже в конвертере, а не молча выпадал из обоих
        пулов в ``build_pool`` (§3.5 п. 6).

        Returns:
            Сам файл главы.

        Raises:
            ValueError: При любом нарушении §3.5 п. 5 или п. 6.
        """
        if not self.chapters:
            raise ValueError("список chapters не должен быть пустым")
        if any(not MIN_CHAPTER <= number <= MAX_CHAPTER for number in self.chapters):
            raise ValueError(
                f"номера глав должны лежать в диапазоне {MIN_CHAPTER}–{MAX_CHAPTER}"
            )
        if self.file_chapter != self.chapters[-1]:
            raise ValueError("file_chapter должен равняться последней главе диапазона")
        if len(self.chapter_titles) != len(self.chapters):
            raise ValueError("число chapter_titles должно равняться числу chapters")
        _ = self.stage  # обращение запускает проверку принадлежности одному этапу
        return self

    @property
    def stage(self) -> Stage:
        """Этап, к которому относится файл.

        Returns:
            ``SRO2``, если все главы в 1–5; ``SRO3``, если все в 6–11.

        Raises:
            ValueError: Если главы файла лежат в разных этапах.
        """
        in_sro2 = [number <= SRO2_LAST_CHAPTER for number in self.chapters]
        if all(in_sro2):
            return Stage.SRO2
        if not any(in_sro2):
            return Stage.SRO3
        raise ValueError(
            f"главы {self.chapters} лежат в разных этапах — "
            "файл выпал бы из обоих пулов"
        )
