"""Песочница и изолированный виртуальный буфер обмена для браузерных сессий."""

from __future__ import annotations

import inspect
import logging
from typing import Any

logger = logging.getLogger("browser_stealth.antidetect.clipboard")

INSTALL_CLIPBOARD_HOOK_JS = """
(() => {
    if (typeof window.__lastCopiedText === 'undefined') {
        window.__lastCopiedText = null;
    }
    if (!window.__clipboardHookInstalled) {
        window.__clipboardHookInstalled = true;

        function saveIsolatedText(text) {
            if (typeof text === 'string' && text.length > 0) {
                window.__lastCopiedText = text.trim();
                try {
                    if (window.top && window.top !== window) {
                        window.top.__lastCopiedText = window.__lastCopiedText;
                    }
                } catch (e) {}
                try {
                    if (window.parent && window.parent !== window) {
                        window.parent.__lastCopiedText = window.__lastCopiedText;
                    }
                } catch (e) {}
            }
            return window.__lastCopiedText;
        }

        function extractAndSaveCopiedText(e) {
            let text = '';
            try {
                const el = document.activeElement;
                if (el && (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT')) {
                    const start = el.selectionStart;
                    const end = el.selectionEnd;
                    if (typeof start === 'number' && typeof end === 'number' && end > start) {
                        text = el.value.substring(start, end);
                    } else if (el.value) {
                        text = el.value;
                    }
                }
            } catch (err) {}

            if (!text) {
                try {
                    if (window.getSelection) {
                        const sel = window.getSelection();
                        if (sel) text = sel.toString();
                    }
                } catch (err) {}
            }

            if (!text && e && e.clipboardData) {
                try {
                    text = e.clipboardData.getData('text/plain') || e.clipboardData.getData('text') || '';
                } catch (err) {}
            }

            return saveIsolatedText(text);
        }

        const virtualClipboard = {
            writeText: async (text) => {
                saveIsolatedText(String(text || ''));
                return Promise.resolve();
            },
            readText: async () => {
                return Promise.resolve(window.__lastCopiedText || '');
            },
            write: async (items) => {
                if (items && Array.isArray(items)) {
                    for (const item of items) {
                        if (item && item.types) {
                            for (const type of item.types) {
                                if (type === 'text/plain' || type === 'text') {
                                    try {
                                        const blob = await item.getType(type);
                                        const txt = await blob.text();
                                        saveIsolatedText(txt);
                                    } catch (e) {}
                                }
                            }
                        }
                    }
                }
                return Promise.resolve();
            },
            read: async () => {
                return Promise.resolve([]);
            }
        };

        try {
            if (typeof DataTransfer !== 'undefined' && DataTransfer.prototype) {
                const origSetData = DataTransfer.prototype.setData;
                DataTransfer.prototype.setData = function(format, data) {
                    const fmt = String(format).toLowerCase();
                    if (fmt === 'text/plain' || fmt === 'text') {
                        saveIsolatedText(String(data));
                        return;
                    }
                    return origSetData ? origSetData.call(this, format, data) : undefined;
                };
            }
        } catch (err) {}

        try {
            if (typeof Clipboard !== 'undefined' && Clipboard.prototype) {
                try {
                    Clipboard.prototype.writeText = virtualClipboard.writeText;
                    Clipboard.prototype.readText = virtualClipboard.readText;
                    Clipboard.prototype.write = virtualClipboard.write;
                    Clipboard.prototype.read = virtualClipboard.read;
                } catch (e) {}
            }
        } catch (err) {}

        try {
            if (navigator.clipboard) {
                try {
                    navigator.clipboard.writeText = virtualClipboard.writeText;
                    navigator.clipboard.readText = virtualClipboard.readText;
                    navigator.clipboard.write = virtualClipboard.write;
                    navigator.clipboard.read = virtualClipboard.read;
                } catch (e) {}
            }
            try {
                Object.defineProperty(navigator, 'clipboard', {
                    value: virtualClipboard,
                    configurable: true,
                    writable: true
                });
            } catch (e) {}
            try {
                if (typeof Navigator !== 'undefined' && Navigator.prototype) {
                    Object.defineProperty(Navigator.prototype, 'clipboard', {
                        get: () => virtualClipboard,
                        configurable: true,
                        enumerable: true
                    });
                }
            } catch (e) {}
        } catch (err) {}

        try {
            const patchExecCommand = (target) => {
                if (target && target.execCommand) {
                    const origExec = target.execCommand;
                    target.execCommand = function(cmd, ...args) {
                        if (String(cmd).toLowerCase() === 'copy') {
                            extractAndSaveCopiedText();
                            return true;
                        }
                        return origExec ? origExec.apply(this, [cmd, ...args]) : false;
                    };
                }
            };
            if (typeof Document !== 'undefined' && Document.prototype) {
                patchExecCommand(Document.prototype);
            }
            if (typeof document !== 'undefined') {
                patchExecCommand(document);
            }
        } catch (err) {}

        const copyHandler = (e) => {
            try {
                extractAndSaveCopiedText(e);
                if (e.preventDefault) {
                    e.preventDefault();
                }
                if (e.clipboardData && e.clipboardData.clearData) {
                    try {
                        e.clipboardData.clearData();
                    } catch (err) {}
                }
                if (e.stopImmediatePropagation) {
                    e.stopImmediatePropagation();
                }
            } catch (err) {}
        };

        if (typeof document !== 'undefined' && document.addEventListener) {
            document.addEventListener('copy', copyHandler, true);
        }
        if (typeof window !== 'undefined' && window.addEventListener) {
            window.addEventListener('copy', copyHandler, true);
        }
    }
    return true;
})();
"""

GET_COPIED_CLIPBOARD_JS = """
(() => {
    try {
        if (window.__lastCopiedText) return window.__lastCopiedText;
        if (window.top && window.top.__lastCopiedText) return window.top.__lastCopiedText;
    } catch (e) {}
    return null;
})()
"""


async def apply_clipboard_isolation(page_or_tab: Any) -> bool:
    """Применяет изолированный буфер обмена к странице/вкладке (Playwright, nodriver, Selenium).

    Предотвращает запись в системный буфер ОС и считывание системного буфера веб-страницами.

    Args:
        page_or_tab: Объект страницы Playwright (Page), вкладки nodriver (Tab) или Selenium WebDriver.

    Returns:
        True, если изоляция успешно установлена, иначе False.
    """
    if page_or_tab is None:
        return False

    success = False

    # 1. nodriver (CDP tab with send)
    if hasattr(page_or_tab, "send") and callable(page_or_tab.send):
        try:
            from nodriver.cdp import page as cdp_page

            res_send = page_or_tab.send(
                cdp_page.add_script_to_evaluate_on_new_document(source=INSTALL_CLIPBOARD_HOOK_JS)
            )
            if inspect.isawaitable(res_send):
                await res_send
            if hasattr(page_or_tab, "evaluate") and callable(page_or_tab.evaluate):
                res_eval = page_or_tab.evaluate(INSTALL_CLIPBOARD_HOOK_JS)
                if inspect.isawaitable(res_eval):
                    await res_eval
            return True
        except Exception as exc:
            logger.debug("Сбой установки изоляции буфера обмена в nodriver: %s", exc)

    # 2. Playwright (Page / BrowserContext)
    if hasattr(page_or_tab, "add_init_script") and callable(page_or_tab.add_init_script):
        try:
            res_init = page_or_tab.add_init_script(INSTALL_CLIPBOARD_HOOK_JS)
            if inspect.isawaitable(res_init):
                await res_init
            if hasattr(page_or_tab, "evaluate") and callable(page_or_tab.evaluate):
                res_eval = page_or_tab.evaluate(INSTALL_CLIPBOARD_HOOK_JS)
                if inspect.isawaitable(res_eval):
                    await res_eval
            return True
        except Exception as exc:
            logger.debug("Сбой установки изоляции буфера обмена в Playwright: %s", exc)

    # 3. Selenium
    if hasattr(page_or_tab, "execute_cdp_cmd") and callable(page_or_tab.execute_cdp_cmd):
        try:
            page_or_tab.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": INSTALL_CLIPBOARD_HOOK_JS},
            )
            if hasattr(page_or_tab, "execute_script") and callable(page_or_tab.execute_script):
                page_or_tab.execute_script(INSTALL_CLIPBOARD_HOOK_JS)
            return True
        except Exception as exc:
            logger.debug("Сбой установки изоляции буфера обмена в Selenium CDP: %s", exc)

    # Fallback evaluate/execute_script
    if hasattr(page_or_tab, "evaluate") and callable(page_or_tab.evaluate):
        try:
            res_eval = page_or_tab.evaluate(INSTALL_CLIPBOARD_HOOK_JS)
            if inspect.isawaitable(res_eval):
                await res_eval
            success = True
        except Exception as exc:
            logger.debug("Сбой установки изоляции буфера обмена через evaluate: %s", exc)

    return success


async def get_isolated_clipboard_text(page_or_tab: Any) -> str | None:
    """Извлекает скопированный в песочнице текст без обращения к системному буферу ОС.

    Args:
        page_or_tab: Объект страницы или вкладки.

    Returns:
        Текст последнего скопированного фрагмента или None.
    """
    if page_or_tab is None:
        return None

    try:
        if hasattr(page_or_tab, "evaluate") and callable(page_or_tab.evaluate):
            res = page_or_tab.evaluate(GET_COPIED_CLIPBOARD_JS)
            if inspect.isawaitable(res):
                res = await res
            return str(res) if res is not None else None
        if hasattr(page_or_tab, "execute_script") and callable(page_or_tab.execute_script):
            res = page_or_tab.execute_script(GET_COPIED_CLIPBOARD_JS)
            return str(res) if res is not None else None
    except Exception as exc:
        logger.debug("Не удалось получить текст из изолированного буфера: %s", exc)

    return None


__all__ = [
    "GET_COPIED_CLIPBOARD_JS",
    "INSTALL_CLIPBOARD_HOOK_JS",
    "apply_clipboard_isolation",
    "get_isolated_clipboard_text",
]
