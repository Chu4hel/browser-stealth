"""Генерация человекоподобных опечаток и ошибок раскладки клавиатуры."""

from __future__ import annotations

import random
from typing import NamedTuple

__all__ = ["KeyboardTypoGenerator", "TypoAction"]

_QWERTY_NEIGHBORS = {
    "q": "wa",
    "w": "qase",
    "e": "wsdr",
    "r": "edft",
    "t": "rfgy",
    "y": "tghu",
    "u": "yhji",
    "i": "ujko",
    "o": "iklp",
    "p": "ol",
    "a": "qwsz",
    "s": "wedcxz",
    "d": "erfvcxs",
    "f": "rtgbvcd",
    "g": "tyhnbvf",
    "h": "yujmnbg",
    "j": "uikmnh",
    "k": "ijlm",
    "l": "okp",
    "z": "asx",
    "x": "zsdc",
    "c": "xdfv",
    "v": "cfgb",
    "b": "vghn",
    "n": "bhjm",
    "m": "njk",
}
"""Карта соседних клавиш для QWERTY-раскладки, используемая для имитации опечаток."""

_JCUKEN_NEIGHBORS = {
    "й": "ёцфы",
    "ц": "йуфыв",
    "у": "цывка",
    "к": "увапе",
    "е": "капрн",
    "н": "епрог",
    "г": "нролш",
    "ш": "голдщ",
    "щ": "шлджз",
    "з": "щджэх",
    "х": "зжэъ",
    "ъ": "хэ",
    "ф": "йцыя",
    "ы": "фйцувяч",
    "в": "ыцукачс",
    "а": "вукепсм",
    "п": "акенрми",
    "р": "пенгоит",
    "о": "рнгшлоть",
    "л": "огшщдьб",
    "д": "лщзжбю",
    "ж": "дэзхю",
    "э": "жхъ",
    "я": "фыч",
    "ч": "яывс",
    "с": "чвам",
    "м": "сапи",
    "и": "мпрт",
    "т": "ироь",
    "ь": "толб",
    "б": "ьлдю",
    "ю": "бдж",
    "ё": "й",
}
"""Карта соседних клавиш для ЙЦУКЕН-раскладки, используемая для имитации опечаток."""

_RU_TO_EN_LAYOUT = {
    "й": "q",
    "ц": "w",
    "у": "e",
    "к": "r",
    "е": "t",
    "н": "y",
    "г": "u",
    "ш": "i",
    "щ": "o",
    "з": "p",
    "х": "[",
    "ъ": "]",
    "ф": "a",
    "ы": "s",
    "в": "d",
    "а": "f",
    "п": "g",
    "р": "h",
    "о": "j",
    "л": "k",
    "д": "l",
    "ж": ";",
    "э": "'",
    "я": "z",
    "ч": "x",
    "с": "c",
    "м": "v",
    "и": "b",
    "т": "n",
    "ь": "m",
    "б": ",",
    "ю": ".",
    "ё": "`",
}
"""Карта трансляции физических клавиш русской раскладки (ЙЦУКЕН) в английскую (QWERTY)."""

_EN_TO_RU_LAYOUT = {v: k for k, v in _RU_TO_EN_LAYOUT.items()}
"""Карта трансляции физических клавиш английской раскладки (QWERTY) в русскую (ЙЦУКЕН)."""


class TypoAction(NamedTuple):
    """Представляет действие ввода символа или нажатия клавиши при имитации печати."""

    action: str  # 'type', 'backspace' или 'key'
    char: (
        str  # символ для ввода (или имя клавиши: 'ArrowLeft', 'End', 'ArrowRight' для action='key')
    )


class KeyboardTypoGenerator:
    """Генератор последовательностей ввода символов с реалистичными опечатками."""

    def __init__(
        self,
        layout_error_rate: float = 0.0,
        delayed_fix_rate: float = 0.0,
    ) -> None:
        """Инициализирует генератор опечаток.

        Args:
            layout_error_rate: Вероятность ошибки переключения раскладки в начале ввода (0.0 - 1.0).
            delayed_fix_rate: Вероятность отложенного исправления опечатки навигацией стрелками (0.0 - 1.0).
        """
        self.layout_error_rate = layout_error_rate
        self.delayed_fix_rate = delayed_fix_rate

    def generate_sequence(
        self,
        text: str,
        error_rate: float = 0.05,
        layout_error_rate: float | None = None,
        delayed_fix_rate: float | None = None,
    ) -> list[TypoAction]:
        """Генерирует последовательность нажатий клавиш для ввода текста.

        Включает случайные опечатки, их обнаружение и исправление через Backspace.
        При ненулевой layout_error_rate в самом начале ввода может произойти реалистичная
        ошибка раскладки (например, ввод нескольких символов латиницей вместо кириллицы
        с последующим полным стиранием и повторным вводом на правильном языке).
        При ненулевой delayed_fix_rate моделируется более сложная опечатка: пользователь
        допускает ошибку, по инерции допечатывает несколько символов/слов, а затем возвращается
        клавишами стрелок назад (ArrowLeft), исправляет опечатку и прыгает в конец строки (End).

        Args:
            text: Исходный текст.
            error_rate: Вероятность совершения ошибки на каждом символе.
            layout_error_rate: Вероятность ошибки раскладки в начале ввода. Если None,
                используется значение из конструктора (по умолчанию 0.0).
            delayed_fix_rate: Вероятность отложенного исправления опечатки. Если None,
                используется значение из конструктора (по умолчанию 0.0).

        Returns:
            Список действий TypoAction, имитирующий последовательный ввод текста человеком.
        """
        sequence: list[TypoAction] = []
        if not text:
            return sequence

        eff_layout_rate = self.layout_error_rate if layout_error_rate is None else layout_error_rate

        # Ошибка раскладки возможна СТРОГО в начале ввода
        if eff_layout_rate > 0.0 and random.random() < eff_layout_rate:
            first_char = text[0].lower()
            layout_map: dict[str, str] | None = None
            if first_char in _RU_TO_EN_LAYOUT:
                layout_map = _RU_TO_EN_LAYOUT
            elif first_char in _EN_TO_RU_LAYOUT:
                layout_map = _EN_TO_RU_LAYOUT

            if layout_map is not None:
                # Ошибочно вводим от 1 до 3 символов
                max_err = min(random.randint(1, 3), len(text))
                err_chars: list[str] = []
                for c in text[:max_err]:
                    lowered_c = c.lower()
                    if lowered_c in layout_map:
                        mapped = layout_map[lowered_c]
                        err_chars.append(mapped.upper() if c.isupper() else mapped)
                    else:
                        break

                if err_chars:
                    # Печатаем символы в неверной раскладке
                    for wrong_c in err_chars:
                        sequence.append(TypoAction("type", wrong_c))
                    # Замечаем ошибку и стираем неверно введенные символы
                    for _ in err_chars:
                        sequence.append(TypoAction("backspace", ""))

        n = len(text)
        eff_delayed_rate = self.delayed_fix_rate if delayed_fix_rate is None else delayed_fix_rate

        # Планируем отложенное исправление опечатки, если текст достаточно длинный
        delayed_fix_pos: int | None = None
        delayed_drift_len: int = 0
        delayed_is_double: bool = False

        if eff_delayed_rate > 0.0 and n >= 15 and random.random() < eff_delayed_rate:
            search_candidates = []
            for idx in range(2, max(3, n - 8)):
                ch = text[idx].lower()
                if ch in _QWERTY_NEIGHBORS or ch in _JCUKEN_NEIGHBORS:
                    search_candidates.append(idx)
            if search_candidates:
                cand_pos = random.choice(search_candidates)
                remaining = n - cand_pos - 1
                max_drift = min(14, remaining)
                min_drift = min(4, max_drift)
                if max_drift >= min_drift > 0:
                    delayed_fix_pos = cand_pos
                    delayed_drift_len = random.randint(min_drift, max_drift)
                    if (
                        random.random() < 0.25
                        and delayed_drift_len >= 3
                        and cand_pos + 1 + delayed_drift_len < n
                        and (
                            text[cand_pos + 1].lower() in _QWERTY_NEIGHBORS
                            or text[cand_pos + 1].lower() in _JCUKEN_NEIGHBORS
                        )
                    ):
                        delayed_is_double = True

        i = 0
        while i < n:
            # Специфическое отложенное исправление опечатки навигацией стрелками
            if delayed_fix_pos is not None and i == delayed_fix_pos:
                if delayed_is_double:
                    # Транспозиция двух соседних букв
                    sequence.append(TypoAction("type", text[i + 1]))
                    sequence.append(TypoAction("type", text[i]))
                    drift_text = text[i + 2 : i + 2 + delayed_drift_len]
                    for d_char in drift_text:
                        sequence.append(TypoAction("type", d_char))
                    # Навигация стрелками влево к месту ошибки
                    for _ in range(len(drift_text)):
                        sequence.append(TypoAction("key", "ArrowLeft"))
                    # Исправление: удаление двух неверных символов
                    sequence.append(TypoAction("backspace", ""))
                    sequence.append(TypoAction("backspace", ""))
                    sequence.append(TypoAction("type", text[i]))
                    sequence.append(TypoAction("type", text[i + 1]))
                    # Возврат каретки в конец напечатанного текста
                    if random.random() < 0.75:
                        sequence.append(TypoAction("key", "End"))
                    else:
                        for _ in range(len(drift_text)):
                            sequence.append(TypoAction("key", "ArrowRight"))
                    i += 2 + len(drift_text)
                else:
                    # Одиночная опечатка в символе
                    char = text[i]
                    lowered = char.lower()
                    neighbors = _QWERTY_NEIGHBORS.get(lowered) or _JCUKEN_NEIGHBORS.get(lowered)
                    wrong_char = random.choice(neighbors) if neighbors else char
                    if char.isupper():
                        wrong_char = wrong_char.upper()

                    sequence.append(TypoAction("type", wrong_char))
                    drift_text = text[i + 1 : i + 1 + delayed_drift_len]
                    for d_char in drift_text:
                        sequence.append(TypoAction("type", d_char))
                    # Навигация стрелками влево
                    for _ in range(len(drift_text)):
                        sequence.append(TypoAction("key", "ArrowLeft"))
                    # Исправление опечатки
                    sequence.append(TypoAction("backspace", ""))
                    sequence.append(TypoAction("type", char))
                    # Возврат в конец
                    if random.random() < 0.75:
                        sequence.append(TypoAction("key", "End"))
                    else:
                        for _ in range(len(drift_text)):
                            sequence.append(TypoAction("key", "ArrowRight"))
                    i += 1 + len(drift_text)

                delayed_fix_pos = None
                continue

            char = text[i]

            lowered = char.lower()
            neighbors = _QWERTY_NEIGHBORS.get(lowered) or _JCUKEN_NEIGHBORS.get(lowered)

            # Решаем, делать ли обычную мгновенную опечатку
            if error_rate > 0.0 and random.random() < error_rate and neighbors is not None:
                # Берем случайного соседа
                wrong_char = random.choice(neighbors)
                # Сохраняем регистр
                if char.isupper():
                    wrong_char = wrong_char.upper()

                # Печатаем неверный символ
                sequence.append(TypoAction("type", wrong_char))

                # Иногда пользователь печатает еще один символ перед тем, как заметит ошибку
                notice_immediately = random.choice([True, False])
                if not notice_immediately and i + 1 < n:
                    next_char = text[i + 1]
                    sequence.append(TypoAction("type", next_char))

                    # Заметили ошибку, стираем оба символа
                    sequence.append(TypoAction("backspace", ""))
                    sequence.append(TypoAction("backspace", ""))
                    # Повторяем ввод текущего символа и переходим к следующему
                    sequence.append(TypoAction("type", char))
                    sequence.append(TypoAction("type", next_char))
                    i += 2
                else:
                    # Заметили сразу, стираем и пишем правильно
                    sequence.append(TypoAction("backspace", ""))
                    sequence.append(TypoAction("type", char))
                    i += 1
            else:
                sequence.append(TypoAction("type", char))
                i += 1

        return sequence
