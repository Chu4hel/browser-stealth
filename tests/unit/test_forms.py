"""Тесты извлечения и заполнения внешних форм."""

from __future__ import annotations

import json
from typing import Any

import pytest

from browser_stealth.forms import (
    FormQuestion,
    build_fill_form_js,
    extract_form_questions,
    fill_form,
    parse_form_questions,
)


class FakeFormTab:
    """Вкладка, возвращающая заранее заданный ответ evaluate."""

    def __init__(self, result: Any) -> None:
        self.result = result
        self.scripts: list[str] = []

    async def evaluate(self, script: str) -> Any:
        self.scripts.append(script)
        return self.result


def test_parse_form_questions_normalizes_types_and_ids() -> None:
    """Парсер поддерживает типы, обязательность и устойчивые id."""
    questions = parse_form_questions(
        [
            {
                "question_text": "  Ваше имя  ",
                "question_type": "text",
                "is_required": True,
            },
            {
                "question_text": "Опыт",
                "question_type": "choice",
                "is_required": False,
            },
            {
                "question_text": "Сопроводительное письмо",
                "question_type": "textarea",
            },
        ]
    )

    assert [item.id for item in questions] == ["q_1", "q_2", "q_3"]
    assert [item.question_type for item in questions] == ["text", "choice", "textarea"]
    assert questions[1].is_required is False


def test_form_question_prefers_user_answer() -> None:
    """Итоговый ответ пользователя имеет приоритет над ответом агента."""
    question = FormQuestion(
        question_text="Город",
        suggested_answer="Москва",
        user_answer="Санкт-Петербург",
    )

    assert question.answer == "Санкт-Петербург"


@pytest.mark.asyncio
async def test_extract_form_questions_uses_single_evaluate() -> None:
    """Извлечение выполняется одним JavaScript-вызовом."""
    raw = json.dumps(
        [
            {
                "question_text": "Город",
                "question_type": "text",
                "is_required": True,
            }
        ],
        ensure_ascii=False,
    )
    tab = FakeFormTab(raw)

    questions = await extract_form_questions(tab)

    assert len(questions) == 1
    assert questions[0].question_text == "Город"
    assert len(tab.scripts) == 1
    assert "SurveyQuestion" in tab.scripts[0]


@pytest.mark.asyncio
async def test_fill_form_returns_report_and_uses_native_setter() -> None:
    """Заполнение использует beforeinput/input/change и возвращает отчёт."""
    tab = FakeFormTab(
        json.dumps(
            {
                "filled": 1,
                "total": 1,
                "blocks_found": 2,
                "unmatched": [],
            }
        )
    )
    questions = [
        FormQuestion(
            question_text="Город",
            suggested_answer="Москва",
            selector="#city",
        )
    ]

    report = await fill_form(tab, questions)

    assert report == {
        "filled": 1,
        "total": 1,
        "blocks_found": 2,
        "unmatched": [],
    }
    script = tab.scripts[0]
    assert "insertFromPaste" in script
    assert "beforeinput" in script
    assert "desc.set.call" not in script  # используется descriptor.set
    assert "getOwnPropertyDescriptor" in script
    assert 'role=\\"radio\\"' in script or 'role="radio"' in script


def test_build_fill_form_js_skips_empty_answers() -> None:
    """В JS попадают только вопросы с непустым ответом."""
    script = build_fill_form_js(
        [
            FormQuestion(question_text="Имя", suggested_answer="Анна"),
            FormQuestion(question_text="Комментарий"),
        ]
    )

    assert "Имя" in script
    assert "Анна" in script
    assert "Комментарий" not in script


@pytest.mark.asyncio
async def test_fill_form_rejects_unusable_tab_and_empty_answers() -> None:
    """Без evaluate или без ответов возвращается понятная ошибка."""
    assert (await fill_form(object(), []))["error"]
    assert (await fill_form(FakeFormTab({}), []))["error"]
