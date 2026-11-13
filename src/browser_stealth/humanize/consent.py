"""Автоматическое обнаружение и принятие диалогов согласия (Google Consent / GDPR)."""

from typing import Any

from browser_stealth.logging import get_logger as setup_logger

from .actions import (
    async_human_sleep,
    human_sleep,
)

logger = setup_logger(__name__)

FIND_CONSENT_BTN_JS = """(() => {
    const selectors = [
        '#L2AG9b',
        'button[id*="L2AG9b"]',
        'form[action*="consent"] button',
        'form[action*="consent"] input[type="submit"]',
        'button[aria-label*="Accept all"]',
        'button[aria-label*="Принять все"]',
        'button[aria-label*="Alle akzeptieren"]'
    ];
    for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el && (el.offsetParent !== null || (el.getClientRects && el.getClientRects().length > 0))) {
            const rect = el.getBoundingClientRect();
            return { found: true, x: rect.left + rect.width * 0.5, y: rect.top + rect.height * 0.5 };
        }
    }
    const buttons = Array.from(document.querySelectorAll('button, input[type="submit"], a[role="button"]'));
    const acceptPhrases = [
        'accept all', 'принять все', 'i agree', 'согласен', 'согласиться',
        'alle akzeptieren', 'tout accepter', 'aceptar todo', 'accetta tutto'
    ];
    for (const btn of buttons) {
        const text = (btn.innerText || btn.value || btn.getAttribute('aria-label') || '').trim().toLowerCase();
        if (acceptPhrases.some(phrase => text === phrase || text.includes(phrase))) {
            const rect = btn.getBoundingClientRect();
            return { found: true, x: rect.left + rect.width * 0.5, y: rect.top + rect.height * 0.5 };
        }
    }
    return { found: false };
})()"""


CONSENT_CLICK_JS = """(() => {
    const selectors = [
        '#L2AG9b',
        'button[id*="L2AG9b"]',
        'form[action*="consent"] button',
        'form[action*="consent"] input[type="submit"]',
        'button[aria-label*="Accept all"]',
        'button[aria-label*="Принять все"]',
        'button[aria-label*="Alle akzeptieren"]'
    ];
    for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el && (el.offsetParent !== null || (el.getClientRects && el.getClientRects().length > 0))) {
            el.click();
            return true;
        }
    }
    const buttons = Array.from(document.querySelectorAll('button, input[type="submit"], a[role="button"]'));
    const acceptPhrases = [
        'accept all', 'принять все', 'i agree', 'согласен', 'согласиться',
        'alle akzeptieren', 'tout accepter', 'aceptar todo', 'accetta tutto'
    ];
    for (const btn of buttons) {
        const text = (btn.innerText || btn.value || btn.getAttribute('aria-label') || '').trim().toLowerCase();
        if (acceptPhrases.some(phrase => text === phrase || text.includes(phrase))) {
            btn.click();
            return true;
        }
    }
    return false;
})()"""


async def _handle_consent_dialog(browser_or_tab: Any) -> bool:
    """Обнаруживает и автоматически принимает модальные окна согласия (Google Consent).

    Приоритетно использует наведение курсора и физический клик мышью по координатам.

    Args:
        browser_or_tab: Объект страницы Playwright Page или вкладки nodriver Tab.

    Returns:
        True, если окно согласия было обнаружено и кнопка нажата, иначе False.
    """
    if not hasattr(browser_or_tab, "evaluate") or not callable(browser_or_tab.evaluate):
        return False

    try:
        from .actions import async_click

        info = await browser_or_tab.evaluate(FIND_CONSENT_BTN_JS)
        if isinstance(info, dict) and info.get("found"):
            x = int(info.get("x", 0))
            y = int(info.get("y", 0))
            await async_click(browser_or_tab, x=x, y=y)
            logger.info("Обнаружено и принято окно согласия (Consent) через нативный CDP клик.")
            await async_human_sleep(1.5, 3.0)
            return True

        clicked = await browser_or_tab.evaluate(CONSENT_CLICK_JS)
        if isinstance(clicked, bool) and clicked:
            logger.info("Обнаружено и автоматически принято окно согласия (Consent).")
            await async_human_sleep(1.5, 3.0)
            return True
    except Exception as ex:
        logger.debug("Не удалось обработать диалог согласия: %s", ex)
    return False


def _handle_consent_dialog_sync(driver: Any) -> bool:
    """Синхронно обнаруживает и автоматически принимает модальные окна согласия (Google Consent).

    Приоритетно использует наведение курсора и физический клик мышью по координатам.

    Args:
        driver: Экземпляр Selenium WebDriver.

    Returns:
        True, если окно согласия было обнаружено и кнопка нажата, иначе False.
    """
    if not hasattr(driver, "execute_script") or not callable(driver.execute_script):
        return False

    try:
        from .actions import click

        info = driver.execute_script(f"return {FIND_CONSENT_BTN_JS};")
        if isinstance(info, dict) and info.get("found"):
            x = int(info.get("x", 0))
            y = int(info.get("y", 0))
            click(driver, x=x, y=y)
            logger.info("Обнаружено и принято окно согласия (Consent) через нативный клик.")
            human_sleep(1.5, 3.0)
            return True

        clicked = driver.execute_script(f"return {CONSENT_CLICK_JS};")
        if isinstance(clicked, bool) and clicked:
            logger.info("Обнаружено и автоматически принято окно согласия (Consent).")
            human_sleep(1.5, 3.0)
            return True
    except Exception as ex:
        logger.debug("Не удалось обработать диалог согласия в Selenium: %s", ex)
    return False


__all__ = [
    "CONSENT_CLICK_JS",
    "FIND_CONSENT_BTN_JS",
    "_handle_consent_dialog",
    "_handle_consent_dialog_sync",
]
