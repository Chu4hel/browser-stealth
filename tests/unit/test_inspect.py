"""Тесты read-only инспекции страницы (browser_stealth.inspect)."""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess

import pytest

from browser_stealth.exceptions import InspectionError
from browser_stealth.inspect import find, frames, screenshot, snapshot
from browser_stealth.inspect._collect import _JS_COLLECT, coerce_payload
from browser_stealth.inspect._nodes import normalize_attrs, normalize_box, normalize_node

RAW_PAYLOAD = {
    "url": "https://example.com/login",
    "title": "Вход",
    "viewport": {"width": 1280, "height": 720, "scrollX": 0, "scrollY": 15},
    "total": 3,
    "truncated": False,
    "nodes": [
        {
            "tag": "BUTTON",
            "role": "button",
            "name": "Войти",
            "text": "Войти",
            "selector": "#login",
            "attrs": {"id": "login", "type": "submit", "data-track": "1"},
            "box": [10, 20, 100, 30],
            "visible": True,
            "enabled": True,
        },
        {
            "tag": "input",
            "role": "textbox",
            "name": "Почта",
            "text": "",
            "selector": "form > input:nth-child(2)",
            "attrs": {"placeholder": "Почта", "name": "email"},
            "box": None,
            "visible": True,
            "enabled": True,
        },
        {
            "tag": "a",
            "role": "link",
            "name": "Забыли пароль?",
            "text": "Забыли пароль?",
            "selector": "a:nth-child(3)",
            "attrs": {"href": "/reset"},
            "box": [10, 60, 120, 20],
            "visible": True,
            "enabled": False,
        },
    ],
}


class FakeTab:
    """Вкладка, возвращающая заранее заданный ответ и запоминающая скрипты."""

    def __init__(self, result: object) -> None:
        self.result = result
        self.scripts: list[str] = []
        self.kwargs: list[dict[str, object]] = []

    async def evaluate(self, script: str, **kwargs: object) -> object:
        """Запоминает и возвращает подготовленный результат."""
        self.scripts.append(script)
        self.kwargs.append(kwargs)
        return self.result


def test_coerce_payload_accepts_dict_json_and_pairs() -> None:
    """Проверяет приведение разных форматов ответа evaluate к словарю."""
    assert coerce_payload({"nodes": []}) == {"nodes": []}
    assert coerce_payload(json.dumps({"nodes": []})) == {"nodes": []}
    assert coerce_payload([["url", "https://example.com"], ["total", 1]]) == {
        "url": "https://example.com",
        "total": 1,
    }
    assert coerce_payload(None) is None
    assert coerce_payload("не json") is None
    assert coerce_payload(42) is None


def test_coerce_payload_unwraps_nested_cdp_remote_objects() -> None:
    """Проверяет разворачивание вложенных CDP-обёрток в ответе evaluate."""
    wrapped = {
        "type": "object",
        "value": [
            ["url", {"type": "string", "value": "https://example.com"}],
            [
                "nodes",
                {
                    "type": "array",
                    "value": [
                        {
                            "type": "object",
                            "value": [
                                ["tag", {"type": "string", "value": "button"}],
                                [
                                    "box",
                                    {
                                        "type": "array",
                                        "value": [
                                            {"type": "number", "value": 1},
                                            {"type": "number", "value": 2},
                                        ],
                                    },
                                ],
                            ],
                        }
                    ],
                },
            ],
        ],
    }

    payload = coerce_payload(wrapped)

    assert payload is not None
    assert payload["url"] == "https://example.com"
    assert payload["nodes"][0]["tag"] == "button"
    assert payload["nodes"][0]["box"] == [1, 2]
    assert coerce_payload({"type": "string", "value": "просто строка"}) is None


def test_normalize_node_filters_attributes_and_skips_empty() -> None:
    """Проверяет отбрасывание неизвестных атрибутов и пустых полей."""
    node = normalize_node(
        {
            "tag": "A",
            "role": "LINK",
            "name": "  Каталог ",
            "text": "",
            "selector": "a",
            "attrs": {"href": "/catalog", "onclick": "steal()", "title": " "},
            "box": [0, 0, 10, 10],
            "visible": True,
            "enabled": True,
        }
    )

    assert node is not None
    assert node["tag"] == "a"
    assert node["role"] == "link"
    assert node["name"] == "Каталог"
    assert "text" not in node
    assert node["attrs"] == {"href": "/catalog"}
    assert node["box"] == [0, 0, 10, 10]


def test_normalize_helpers_reject_bad_values() -> None:
    """Проверяет устойчивость нормализаторов к мусорным значениям."""
    assert normalize_attrs("нет") == {}
    assert normalize_attrs({"id": None, "href": " "}) == {}
    assert normalize_box("1,2,3,4") is None
    assert normalize_box([1, 2, 3]) is None
    assert normalize_box(["1.4", 2, "3", 4.6]) == [1, 2, 3, 5]
    assert normalize_node({"tag": ""}) is None
    assert normalize_node("button") is None


@pytest.mark.asyncio
async def test_snapshot_returns_normalized_page() -> None:
    """Проверяет публичный формат снимка и фильтрацию узлов."""
    tab = FakeTab(json.dumps(RAW_PAYLOAD))

    page = await snapshot(tab, max_nodes=10)

    assert page["url"] == "https://example.com/login"
    assert page["title"] == "Вход"
    assert page["viewport"] == {"width": 1280, "height": 720, "scrollX": 0, "scrollY": 15}
    assert page["total"] == 3
    assert page["truncated"] is False
    assert [node["role"] for node in page["nodes"]] == ["button", "textbox", "link"]
    assert page["nodes"][0]["attrs"] == {"id": "login", "type": "submit"}
    assert "box" not in page["nodes"][1]  # некорректная рамка отбрасывается
    assert page["nodes"][1]["attrs"] == {"placeholder": "Почта", "name": "email"}


@pytest.mark.asyncio
async def test_snapshot_passes_options_to_javascript() -> None:
    """Проверяет, что параметры снимка попадают в вызов evaluate."""
    tab = FakeTab(RAW_PAYLOAD)

    await snapshot(tab, max_nodes=7, include_hidden=True, text_limit=40)

    script = tab.scripts[0]
    assert '"maxNodes": 7' in script
    assert '"includeHidden": true' in script
    assert '"textLimit": 40' in script


@pytest.mark.asyncio
async def test_snapshot_rejects_unusable_tab_and_bad_payload() -> None:
    """Проверяет исключения при отсутствии evaluate и некорректном ответе."""
    with pytest.raises(InspectionError):
        await snapshot(object())

    with pytest.raises(InspectionError):
        await snapshot(FakeTab(None))

    with pytest.raises(InspectionError):
        await snapshot(FakeTab("не json"))


@pytest.mark.asyncio
async def test_snapshot_wraps_evaluate_failure_and_timeout() -> None:
    """Проверяет превращение ошибок браузера в InspectionError."""

    class BrokenTab:
        async def evaluate(self, script: str) -> object:
            raise RuntimeError("CDP отвалился")

    with pytest.raises(InspectionError, match="CDP отвалился"):
        await snapshot(BrokenTab())

    class SlowTab:
        async def evaluate(self, script: str) -> object:
            await asyncio.sleep(1)
            return {}

    with pytest.raises(InspectionError, match="Таймаут"):
        await snapshot(SlowTab(), timeout=0.01)


@pytest.mark.asyncio
async def test_find_filters_by_text_role_and_limit() -> None:
    """Проверяет текстовый и ролевой фильтры, регистр и лимит."""
    tab = FakeTab(RAW_PAYLOAD)

    by_text = await find(tab, text="ВОЙТИ")
    assert [node["name"] for node in by_text] == ["Войти"]
    assert {node["role"] for node in by_text} == {"button"}

    by_role = await find(tab, role="LINK")
    assert [node["name"] for node in by_role] == ["Забыли пароль?"]

    exact = await find(tab, text="Войти", exact=True)
    assert len(exact) == 1

    limited = await find(tab, text="а", limit=1)
    assert len(limited) == 1


@pytest.mark.asyncio
async def test_find_uses_custom_selector_and_validates_args() -> None:
    """Проверяет передачу селектора и ошибки на пустой запрос."""
    tab = FakeTab(RAW_PAYLOAD)

    await find(tab, selector="#login-form", text="Войти")
    assert "#login-form" in tab.scripts[0]

    with pytest.raises(ValueError):
        await find(tab)

    with pytest.raises(ValueError):
        await find(tab, text="x", limit=-1)

    assert await find(tab, text="x", limit=0) == []


@pytest.mark.asyncio
async def test_find_returns_empty_list_without_matches() -> None:
    """Проверяет отсутствие совпадений без исключения."""
    tab = FakeTab(RAW_PAYLOAD)

    assert await find(tab, text="Купить") == []


class FakeScreenshotTab:
    """Вкладка с запоминанием аргументов save_screenshot."""

    def __init__(self, result: object = "auto") -> None:
        self.result = result
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    async def save_screenshot(self, *args: object, **kwargs: object) -> object:
        """Запоминает параметры снимка."""
        self.calls.append((args, kwargs))
        return self.result


@pytest.mark.asyncio
async def test_screenshot_delegates_options(tmp_path) -> None:
    """Проверяет параметры сохранения и создание директории."""
    tab = FakeScreenshotTab("/tmp/page.png")
    target = tmp_path / "shots" / "page.png"

    saved = await screenshot(tab, target, full_page=True, image_format="jpeg")

    assert saved == "/tmp/page.png"
    args, kwargs = tab.calls[0]
    assert args[0] == str(target)
    assert kwargs == {"format": "jpeg", "full_page": True, "as_base64": False}
    assert target.parent.is_dir()


@pytest.mark.asyncio
async def test_screenshot_defaults_and_errors() -> None:
    """Проверяет путь auto и исключения для неподдерживаемой вкладки."""
    tab = FakeScreenshotTab("/tmp/auto.png")
    await screenshot(tab)
    assert tab.calls[0][0][0] == "auto"

    with pytest.raises(InspectionError):
        await screenshot(object())

    with pytest.raises(InspectionError):
        await screenshot(FakeScreenshotTab(None))


@pytest.mark.asyncio
async def test_screenshot_timeout_is_wrapped() -> None:
    """Проверяет таймаут асинхронного снимка."""

    class SlowTab:
        async def save_screenshot(self, *args: object, **kwargs: object) -> str:
            await asyncio.sleep(1)
            return "late.png"

    with pytest.raises(InspectionError, match="Таймаут"):
        await screenshot(SlowTab(), timeout=0.01)


class FakeFrame:
    """Минимальный фрейм CDP."""

    def __init__(
        self,
        frame_id: str,
        url: str,
        *,
        name: str | None = None,
        parent_id: str | None = None,
        origin: str = "https://example.com",
    ) -> None:
        self.id_ = frame_id
        self.url = url
        self.name = name
        self.parent_id = parent_id
        self.security_origin = origin


class FakeTree:
    """Узел дерева фреймов CDP."""

    def __init__(self, frame: FakeFrame, children: list[FakeTree] | None = None) -> None:
        self.frame = frame
        self.child_frames = children


@pytest.mark.asyncio
async def test_frames_flattens_frame_tree() -> None:
    """Проверяет порядок, глубину и поля дерева фреймов."""
    tree = FakeTree(
        FakeFrame("main", "https://example.com"),
        [
            FakeTree(
                FakeFrame("pay", "https://pay.example.com", parent_id="main"),
                [FakeTree(FakeFrame("pay-inner", "https://pay.example.com/3ds", parent_id="pay"))],
            ),
            FakeTree(FakeFrame("help", "about:blank", name="helper", parent_id="main")),
        ],
    )

    class TreeTab:
        async def get_frame_tree(self) -> FakeTree:
            return tree

    result = await frames(TreeTab())

    assert [f["id"] for f in result] == ["main", "pay", "pay-inner", "help"]
    assert [f["depth"] for f in result] == [0, 1, 2, 1]
    assert "parent_id" not in result[0]
    assert result[1]["security_origin"] == "https://example.com"
    assert result[3]["name"] == "helper"


@pytest.mark.asyncio
async def test_frames_supports_dict_payload_and_errors() -> None:
    """Проверяет словарный формат CDP и обёртку ошибок."""

    class DictTab:
        async def get_frame_tree(self) -> dict[str, object]:
            return {
                "frame": {"id_": "root", "url": "https://example.com"},
                "childFrames": [{"frame": {"id_": "child", "url": "about:blank"}}],
            }

    result = await frames(DictTab())
    assert [f["id"] for f in result] == ["root", "child"]

    with pytest.raises(InspectionError):
        await frames(object())


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js не установлен")
def test_collect_js_returns_semantic_snapshot() -> None:
    """Проверяет сборщик в runtime: роли, имена, видимость и отсутствие обхода iframe."""
    script = f"""
    const assert = require('assert');
    const collect = {_JS_COLLECT};

    function makeEl(tag, props) {{
      const attrs = props.attrs || {{}};
      return {{
        nodeType: 1,
        tagName: tag.toUpperCase(),
        id: attrs.id || '',
        textContent: props.text || '',
        value: props.value || '',
        disabled: !!props.disabled,
        offsetParent: props.hidden ? null : {{}},
        parentElement: null,
        children: [],
        getAttribute: (name) => (name in attrs ? attrs[name] : null),
        hasAttribute: (name) => name in attrs,
        getBoundingClientRect: () =>
          props.hidden
            ? {{ left: 0, top: 0, width: 0, height: 0 }}
            : {{ left: 10, top: 20, width: 100, height: 30 }}
      }};
    }}

    const nodes = [
      makeEl('button', {{ text: 'Войти', attrs: {{ id: 'login', type: 'submit' }} }}),
      makeEl('a', {{ text: 'Каталог', attrs: {{ href: '/catalog' }} }}),
      makeEl('input', {{ attrs: {{ placeholder: 'Почта', type: 'email' }} }}),
      makeEl('input', {{ attrs: {{ type: 'hidden', name: 'csrf' }} }}),
      makeEl('button', {{ text: 'Скрытая', hidden: true }}),
      makeEl('iframe', {{ attrs: {{ src: 'https://widget.example.com', title: 'Виджет' }} }})
    ];

    global.window = {{
      innerWidth: 1280,
      innerHeight: 720,
      scrollX: 0,
      scrollY: 5,
      getComputedStyle: () => ({{ visibility: 'visible', display: 'block', opacity: '1', position: 'static' }})
    }};
    global.document = {{
      title: 'Страница',
      body: {{ querySelectorAll: () => nodes }}
    }};
    global.location = {{ href: 'https://example.com/' }};

    const page = collect({{ maxNodes: 10, textLimit: 50 }});
    assert.strictEqual(page.url, 'https://example.com/');
    assert.strictEqual(page.title, 'Страница');
    assert.deepStrictEqual(page.viewport, {{ width: 1280, height: 720, scrollX: 0, scrollY: 5 }});
    assert.deepStrictEqual(
      page.nodes.map((n) => n.role),
      ['button', 'link', 'textbox', 'iframe']
    );
    assert.strictEqual(page.nodes[0].name, 'Войти');
    assert.strictEqual(page.nodes[0].selector, '#login');
    assert.deepStrictEqual(page.nodes[0].box, [10, 20, 100, 30]);
    assert.strictEqual(page.nodes[2].name, 'Почта');
    assert.strictEqual(page.nodes[3].name, 'Виджет');
    assert.strictEqual(page.truncated, false);
    assert.strictEqual(page.total, 4);

    const limited = collect({{ maxNodes: 2 }});
    assert.strictEqual(limited.nodes.length, 2);
    assert.strictEqual(limited.total, 4);
    assert.strictEqual(limited.truncated, true);
    console.log('INSPECT_JS_PASSED');
    """

    result = subprocess.run(
        ["node", "-e", script],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "INSPECT_JS_PASSED" in result.stdout


def test_collect_js_does_not_traverse_frames() -> None:
    """Проверяет, что сборщик не обращается к содержимому iframe."""
    assert "contentWindow" not in _JS_COLLECT
    assert "contentDocument" not in _JS_COLLECT
    assert "iframe[src]" in _JS_COLLECT
