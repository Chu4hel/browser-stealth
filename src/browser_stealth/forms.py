"""Извлечение и стелс-заполнение внешних веб-форм.

Модуль работает с Google Forms, Яндекс.Формами, Typeform, Tally и обычными
HTML-формами. Вопросы извлекаются одним JavaScript-вызовом, а ответы
подставляются через нативные setter'ы и события ``input``/``change``. Это
позволяет React/Vue/Angular controlled inputs увидеть изменение, не выполняя
посимвольный ввод и не зависая на каскадных селекторах.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel

from browser_stealth.logging import get_logger

logger = get_logger(__name__)

FormQuestionType = Literal["text", "textarea", "choice", "number", "select"]


class FormQuestion(BaseModel):
    """Структура вопроса внешней формы.

    Attributes:
        id: Уникальный идентификатор вопроса в пределах формы.
        question_text: Видимый текст вопроса.
        question_type: Тип поля: ``text``, ``textarea``, ``choice``, ``number``
            или ``select``.
        is_required: Обязателен ли вопрос.
        suggested_answer: Ответ, подготовленный агентом.
        user_answer: Итоговый ответ пользователя; имеет приоритет при заполнении.
        selector: Необязательный CSS-селектор контейнера вопроса.
    """

    id: str = ""
    question_text: str
    question_type: FormQuestionType = "text"
    is_required: bool = True
    suggested_answer: str = ""
    user_answer: str | None = None
    selector: str = ""

    @property
    def answer(self) -> str:
        """Возвращает итоговый ответ пользователя или ответ агента."""
        return (self.user_answer or self.suggested_answer or "").strip()


_JS_EXTRACT_FORM = r"""
(() => {
  const IGNORED = new Set([
    "отправить", "очистить форму", "далее", "назад", "яндекс формы",
    "яндекс.формы", "обязательное поле", "войти", "подтвердить",
    "submit", "next", "back", "clear form", "required"
  ]);

  function clean(raw) {
    let text = String(raw == null ? "" : raw).replace(/\s+/g, " ").trim();
    text = text.replace(/\s*Обязательное поле\s*$/i, "").trim();
    text = text.replace(/\s*\*\s*$/, "").trim();
    return text;
  }

  function visible(el) {
    if (!el) return false;
    const style = window.getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") {
      return false;
    }
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function detectType(container) {
    if (!container) return "text";
    if (container.querySelector("select")) return "select";
    if (container.querySelector("textarea")) return "textarea";
    if (container.querySelector(
      'input[type="radio"], input[type="checkbox"], [role="radiogroup"], [role="radio"], [role="checkbox"]'
    )) return "choice";
    if (container.querySelector('input[type="number"]')) return "number";
    return "text";
  }

  function required(container, raw) {
    if (/\*\s*$/.test(String(raw || "").trim())) return true;
    return Boolean(container && container.querySelector(
      '[required], [aria-required="true"], [class*="Required"], [class*="required"]'
    ));
  }

  function cssPath(el) {
    if (!el || !el.tagName) return "";
    if (el.id) return "#" + String(el.id).replace(/([^\w-])/g, "\\$1");
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && node.tagName.toLowerCase() !== "body") {
      const tag = node.tagName.toLowerCase();
      const parent = node.parentElement;
      if (!parent) break;
      const index = Array.prototype.indexOf.call(parent.children, node) + 1;
      parts.unshift(tag + ":nth-child(" + index + ")");
      if (parts.length >= 4) break;
      node = parent;
    }
    return parts.join(" > ");
  }

  const results = [];
  const seen = new Set();

  function add(rawText, container) {
    const text = clean(rawText);
    if (!text || text.length < 3) return;
    const key = text.toLowerCase();
    if (IGNORED.has(key) || seen.has(key)) return;
    seen.add(key);
    results.push({
      question_text: text,
      question_type: detectType(container),
      is_required: required(container, rawText),
      selector: cssPath(container)
    });
  }

  const blocks = [
    '[class*="SurveyPage-Question"]',
    '[class*="SurveyQuestion"]',
    '[class*="Question_"]',
    '.g-form-field',
    '[data-testid*="question"]',
    '[data-qa="question"]',
    '[role="listitem"]',
    'fieldset'
  ];

  for (const selector of blocks) {
    const found = document.querySelectorAll(selector);
    if (!found || !found.length) continue;
    for (const block of found) {
      if (!visible(block)) continue;
      const hasInput = block.querySelector(
        'input:not([type="hidden"]), textarea, select, [role="radiogroup"], [role="radio"], [role="checkbox"]'
      );
      if (!hasInput) continue;
      const label = block.querySelector(
        'legend, [role="heading"], h2, h3, label, [class*="QuestionLabel"], [class*="question-label"], [class*="Label"], .g-form-field__label'
      );
      if (label && label.innerText) add(label.innerText, block);
    }
    if (results.length) break;
  }

  if (!results.length) {
    const inputs = document.querySelectorAll(
      'textarea, select, [role="radiogroup"], input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"])'
    );
    for (const input of inputs) {
      if (!visible(input)) continue;
      let text = "";
      let container = input.closest('fieldset, [role="group"], [role="listitem"], form > div, section, div');
      if (input.id) {
        try {
          const label = document.querySelector('label[for="' + String(input.id).replace(/"/g, '\\"') + '"]');
          if (label && label.innerText) text = label.innerText;
        } catch (e) {}
      }
      if (!text) {
        const label = input.closest("label");
        if (label && label.innerText) text = label.innerText;
      }
      if (!text && input.getAttribute("aria-labelledby")) {
        text = String(input.getAttribute("aria-labelledby")).split(/\s+/).map((id) => {
          const el = document.getElementById(id);
          return el ? el.innerText : "";
        }).join(" ");
      }
      if (!text && input.getAttribute("aria-label")) text = input.getAttribute("aria-label");
      if (!text && container) {
        const heading = container.querySelector('legend, [role="heading"], label, h2, h3, h4, p');
        if (heading && heading.innerText) text = heading.innerText;
      }
      if (!text && input.placeholder) text = input.placeholder;
      if (text) add(text, container || input.parentElement);
    }
  }

  return JSON.stringify(results);
})()
"""

_JS_FILL_FORM = r"""
((items) => {
  const IGNORED = new Set([
    "отправить", "очистить форму", "далее", "назад", "яндекс формы",
    "яндекс.формы", "обязательное поле", "войти", "подтвердить",
    "submit", "next", "back", "clear form", "required"
  ]);

  function clean(raw) {
    return String(raw == null ? "" : raw).replace(/\s+/g, " ").trim().toLowerCase();
  }

  function visible(el) {
    if (!el) return false;
    const style = window.getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") {
      return false;
    }
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function setNativeValue(el, value) {
    const tag = String(el.tagName || "").toUpperCase();
    const proto = tag === "TEXTAREA" ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
    const descriptor = Object.getOwnPropertyDescriptor(proto, "value");
    try {
      el.dispatchEvent(new InputEvent("beforeinput", {
        bubbles: true, cancelable: true, inputType: "insertFromPaste", data: value
      }));
    } catch (e) {}
    if (descriptor && descriptor.set) descriptor.set.call(el, value);
    else if ("value" in el) el.value = value;
    else el.textContent = value;
    try {
      el.dispatchEvent(new InputEvent("input", {
        bubbles: true, inputType: "insertFromPaste", data: value
      }));
    } catch (e) {
      el.dispatchEvent(new Event("input", { bubbles: true }));
    }
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function affirmative(text) {
    return /^(да|да,|да\.|согласен|согласна|даю согласие|подтверждаю|yes|agree|ok|ок)/i.test(text);
  }

  function fillContainer(container, answer) {
    if (!container || !answer) return false;

    const textEl = container.querySelector(
      'textarea, input[type="text"], input[type="number"], input[type="email"], input[type="tel"], input[type="url"], input:not([type])'
    );
    if (textEl && visible(textEl)) {
      textEl.focus();
      setNativeValue(textEl, answer);
      return true;
    }

    const selectEl = container.querySelector("select");
    if (selectEl && visible(selectEl)) {
      const target = clean(answer);
      for (const option of selectEl.options) {
        const optionText = clean(option.textContent || option.value);
        if (optionText && (optionText === target || target.includes(optionText) || optionText.includes(target))) {
          selectEl.value = option.value;
          selectEl.dispatchEvent(new Event("change", { bubbles: true }));
          return true;
        }
      }
    }

    const radios = Array.from(container.querySelectorAll('[role="radio"], input[type="radio"]'));
    if (radios.length) {
      const target = clean(answer);
      let best = null;
      for (const radio of radios) {
        const label = clean(
          radio.getAttribute("aria-label") ||
          radio.getAttribute("data-value") ||
          (radio.closest("label") ? radio.closest("label").innerText : "") ||
          (radio.parentElement ? radio.parentElement.innerText : "")
        );
        if (label && label === target) { best = radio; break; }
      }
      if (!best) {
        for (const radio of radios) {
          const label = clean(
            radio.getAttribute("aria-label") ||
            radio.getAttribute("data-value") ||
            (radio.closest("label") ? radio.closest("label").innerText : "") ||
            (radio.parentElement ? radio.parentElement.innerText : "")
          );
          if (label && (target.includes(label) || label.includes(target))) { best = radio; break; }
        }
      }
      if (!best && radios.length === 1 && affirmative(target)) best = radios[0];
      if (best) {
        if (best.getAttribute("aria-checked") !== "true" && best.checked !== true) best.click();
        return true;
      }
    }

    const checkboxes = Array.from(container.querySelectorAll('[role="checkbox"], input[type="checkbox"]'));
    if (checkboxes.length) {
      const target = clean(answer);
      let clicked = false;
      for (const checkbox of checkboxes) {
        const label = clean(
          checkbox.getAttribute("aria-label") ||
          checkbox.getAttribute("data-answer-value") ||
          (checkbox.closest("label") ? checkbox.closest("label").innerText : "") ||
          (checkbox.parentElement ? checkbox.parentElement.innerText : "")
        );
        if (label && (target.includes(label) || label.includes(target))) {
          if (checkbox.getAttribute("aria-checked") !== "true" && checkbox.checked !== true) checkbox.click();
          clicked = true;
        }
      }
      if (!clicked && checkboxes.length === 1 && affirmative(target)) {
        const checkbox = checkboxes[0];
        if (checkbox.getAttribute("aria-checked") !== "true" && checkbox.checked !== true) checkbox.click();
        clicked = true;
      }
      if (clicked) return true;
    }

    return false;
  }

  const blocks = [];
  const selectors = [
    '[class*="SurveyPage-Question"]',
    '[class*="SurveyQuestion"]',
    '[class*="Question_"]',
    '.g-form-field',
    '[data-testid*="question"]',
    '[data-qa="question"]',
    '[role="listitem"]',
    'fieldset'
  ];
  for (const selector of selectors) {
    const found = document.querySelectorAll(selector);
    if (!found || !found.length) continue;
    for (const block of found) {
      if (!visible(block)) continue;
      const hasInput = block.querySelector(
        'input:not([type="hidden"]), textarea, select, [role="radiogroup"], [role="radio"], [role="checkbox"]'
      );
      if (!hasInput) continue;
      const label = block.querySelector(
        'legend, [role="heading"], h2, h3, label, [class*="QuestionLabel"], [class*="question-label"], [class*="Label"], .g-form-field__label'
      );
      const text = label && label.innerText ? clean(label.innerText) : "";
      if (text && !IGNORED.has(text)) blocks.push({ el: block, text: text });
    }
    if (blocks.length) break;
  }

  const used = new Set();
  const unmatched = [];
  let filled = 0;
  for (let index = 0; index < items.length; index++) {
    const item = items[index];
    const answer = String(item.suggested_answer || "").trim();
    if (!answer) continue;
    const target = clean(item.question_text || "");
    let block = null;
    if (item.selector) {
      try {
        const selected = document.querySelector(item.selector);
        if (selected) block = { el: selected, text: target };
      } catch (e) {}
    }
    if (!block && target && !/^вопрос\s+\d+$/i.test(target)) {
      block = blocks.find((candidate) => !used.has(candidate) && candidate.text === target) || null;
      if (!block && target.length >= 4) {
        block = blocks.find((candidate) => !used.has(candidate) &&
          (candidate.text.includes(target) || target.includes(candidate.text))) || null;
      }
    }
    if (!block && index < blocks.length && !used.has(blocks[index])) block = blocks[index];
    if (block && fillContainer(block.el, answer)) {
      used.add(block);
      filled += 1;
    } else {
      unmatched.push(item.question_text || item.id || String(index + 1));
    }
  }

  return JSON.stringify({
    filled: filled,
    total: items.filter((item) => String(item.suggested_answer || "").trim()).length,
    blocks_found: blocks.length,
    unmatched: unmatched
  });
})
"""


def _parse_payload(raw: Any) -> Any:
    """Разбирает JSON-строку, dict или список из ``evaluate``."""
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return None
    return raw


def _normalize_type(raw: Any) -> FormQuestionType:
    """Приводит тип поля из JavaScript к публичному литералу."""
    value = str(raw or "text").strip().lower()
    if value in {"textarea", "text"}:
        return "textarea" if value == "textarea" else "text"
    if value in {"number"}:
        return "number"
    if value in {"select", "dropdown"}:
        return "select"
    if value in {"choice", "single_choice", "multi_choice", "radio", "checkbox"}:
        return "choice"
    return "text"


def parse_form_questions(raw: Any) -> list[FormQuestion]:
    """Преобразует результат JavaScript-экстрактора в список вопросов.

    Args:
        raw: JSON-строка, список словарей или словарь с ключом ``questions``.

    Returns:
        Список :class:`FormQuestion` с устойчивыми идентификаторами.
    """
    parsed = _parse_payload(raw)
    if isinstance(parsed, Mapping):
        parsed = parsed.get("questions")
    if not isinstance(parsed, Sequence) or isinstance(parsed, (str, bytes)):
        return []

    questions: list[FormQuestion] = []
    for index, entry in enumerate(parsed, start=1):
        if not isinstance(entry, Mapping):
            continue
        text = str(entry.get("question_text") or "").strip()
        if not text:
            continue
        questions.append(
            FormQuestion(
                id=str(entry.get("id") or f"q_{index}"),
                question_text=text,
                question_type=_normalize_type(entry.get("question_type")),
                is_required=bool(entry.get("is_required", True)),
                selector=str(entry.get("selector") or ""),
            )
        )
    return questions


async def extract_form_questions(tab: Any, *, timeout: float = 10.0) -> list[FormQuestion]:
    """Извлекает вопросы открытой внешней формы одним вызовом JavaScript.

    Args:
        tab: Вкладка nodriver или совместимый объект с ``evaluate``.
        timeout: Таймаут чтения DOM в секундах.

    Returns:
        Список вопросов; пустой список, если форма не распознана или вкладка
        недоступна.

    Example:
        >>> from browser_stealth.forms import extract_form_questions
        >>> questions = await extract_form_questions(tab)
    """
    evaluate = getattr(tab, "evaluate", None)
    if not callable(evaluate):
        return []
    try:
        raw = await asyncio.wait_for(evaluate(_JS_EXTRACT_FORM), timeout=timeout)
    except TimeoutError:
        logger.debug("Таймаут извлечения вопросов формы")
        return []
    except Exception as exc:
        logger.debug("Не удалось извлечь вопросы формы: %s", exc)
        return []
    return parse_form_questions(raw)


def _question_payload(
    questions: Sequence[FormQuestion | Mapping[str, Any]],
) -> list[dict[str, str]]:
    """Оставляет только вопросы с непустым итоговым ответом."""
    payload: list[dict[str, str]] = []
    for question in questions:
        if isinstance(question, FormQuestion):
            item = question
        else:
            item = FormQuestion.model_validate(question)
        answer = item.answer
        if answer:
            payload.append(
                {
                    "id": item.id,
                    "question_text": item.question_text,
                    "suggested_answer": answer,
                    "selector": item.selector,
                }
            )
    return payload


def build_fill_form_js(questions: Sequence[FormQuestion | Mapping[str, Any]]) -> str:
    """Формирует JavaScript для заполнения формы подготовленными ответами.

    Args:
        questions: Вопросы с заполненными ``suggested_answer`` или ``user_answer``.

    Returns:
        Самовызывающееся JavaScript-выражение для передачи в ``tab.evaluate``.
    """
    payload = _question_payload(questions)
    return f"({_JS_FILL_FORM})({json.dumps(payload, ensure_ascii=False)})"


async def fill_form(
    tab: Any,
    questions: Sequence[FormQuestion | Mapping[str, Any]],
    *,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Заполняет открытую форму ответами с поддержкой React/Vue controlled inputs.

    Args:
        tab: Вкладка nodriver или совместимый объект с ``evaluate``.
        questions: Вопросы с заполненными ``suggested_answer`` или ``user_answer``.
        timeout: Таймаут выполнения JavaScript в секундах.

    Returns:
        Отчёт ``filled``, ``total``, ``blocks_found``, ``unmatched`` и
        ``error`` (при сбое).
    """
    payload = _question_payload(questions)
    base: dict[str, Any] = {
        "filled": 0,
        "total": len(payload),
        "blocks_found": 0,
        "unmatched": [],
    }
    evaluate = getattr(tab, "evaluate", None)
    if not callable(evaluate):
        return {**base, "error": "Вкладка не поддерживает evaluate"}
    if not payload:
        return {**base, "error": "Нет заполненных ответов"}

    try:
        raw = await asyncio.wait_for(evaluate(build_fill_form_js(questions)), timeout=timeout)
    except TimeoutError:
        return {**base, "error": f"Таймаут заполнения формы за {timeout} с"}
    except Exception as exc:
        logger.debug("Не удалось заполнить форму: %s", exc)
        return {**base, "error": str(exc)}

    parsed = _parse_payload(raw)
    if not isinstance(parsed, Mapping):
        return {**base, "error": "Браузер вернул некорректный отчёт"}
    report = dict(base)
    for key in ("filled", "total", "blocks_found"):
        value = parsed.get(key)
        if isinstance(value, (int, float)):
            report[key] = int(value)
    unmatched = parsed.get("unmatched")
    if isinstance(unmatched, Sequence) and not isinstance(unmatched, (str, bytes)):
        report["unmatched"] = [str(item) for item in unmatched]
    return report


__all__ = [
    "FormQuestion",
    "FormQuestionType",
    "build_fill_form_js",
    "extract_form_questions",
    "fill_form",
    "parse_form_questions",
]
