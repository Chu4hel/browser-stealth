"""Модуль выравнивания географических параметров, часовых поясов и локалей прокси."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from browser_stealth.antidetect.config import AntidetectConfig
    from browser_stealth.proxy.models import ProxyConfig

COUNTRY_GEO_MAP: dict[str, dict[str, Any]] = {
    "US": {"timezone": "America/New_York", "locale": "en-US", "languages": ["en-US", "en"]},
    "GB": {"timezone": "Europe/London", "locale": "en-GB", "languages": ["en-GB", "en"]},
    "DE": {"timezone": "Europe/Berlin", "locale": "de-DE", "languages": ["de-DE", "de", "en"]},
    "FR": {"timezone": "Europe/Paris", "locale": "fr-FR", "languages": ["fr-FR", "fr", "en"]},
    "NL": {"timezone": "Europe/Amsterdam", "locale": "nl-NL", "languages": ["nl-NL", "nl", "en"]},
    "RU": {"timezone": "Europe/Moscow", "locale": "ru-RU", "languages": ["ru-RU", "ru", "en"]},
    "JP": {"timezone": "Asia/Tokyo", "locale": "ja-JP", "languages": ["ja-JP", "ja", "en"]},
    "CN": {"timezone": "Asia/Shanghai", "locale": "zh-CN", "languages": ["zh-CN", "zh", "en"]},
    "SG": {"timezone": "Asia/Singapore", "locale": "en-SG", "languages": ["en-SG", "en"]},
    "CA": {"timezone": "America/Toronto", "locale": "en-CA", "languages": ["en-CA", "en"]},
    "AU": {"timezone": "Australia/Sydney", "locale": "en-AU", "languages": ["en-AU", "en"]},
    "UA": {"timezone": "Europe/Kyiv", "locale": "uk-UA", "languages": ["uk-UA", "uk", "en"]},
    "PL": {"timezone": "Europe/Warsaw", "locale": "pl-PL", "languages": ["pl-PL", "pl", "en"]},
    "TR": {"timezone": "Europe/Istanbul", "locale": "tr-TR", "languages": ["tr-TR", "tr", "en"]},
    "BR": {"timezone": "America/Sao_Paulo", "locale": "pt-BR", "languages": ["pt-BR", "pt", "en"]},
    "IN": {"timezone": "Asia/Kolkata", "locale": "en-IN", "languages": ["en-IN", "en"]},
    "ES": {"timezone": "Europe/Madrid", "locale": "es-ES", "languages": ["es-ES", "es", "en"]},
    "IT": {"timezone": "Europe/Rome", "locale": "it-IT", "languages": ["it-IT", "it", "en"]},
    "CH": {"timezone": "Europe/Zurich", "locale": "de-CH", "languages": ["de-CH", "de", "en"]},
    "SE": {"timezone": "Europe/Stockholm", "locale": "sv-SE", "languages": ["sv-SE", "sv", "en"]},
}
"""Справочник сопоставления ISO-кодов стран с IANA-часовыми поясами и локалями."""


def infer_proxy_geo(proxy: ProxyConfig) -> dict[str, str]:
    """Определяет страну, часовой пояс и локаль прокси-сервера.

    Args:
        proxy: Экземпляр ProxyConfig.

    Returns:
        Словарь с ключами 'country', 'timezone', 'locale'.
    """
    country = (
        proxy.country or proxy.metadata.get("country") or proxy.metadata.get("country_code") or "US"
    ).upper()

    geo_data = COUNTRY_GEO_MAP.get(country, COUNTRY_GEO_MAP["US"])

    timezone = (
        proxy.timezone
        or proxy.metadata.get("timezone")
        or proxy.metadata.get("time_zone")
        or geo_data["timezone"]
    )

    locale = proxy.locale or proxy.metadata.get("locale") or geo_data["locale"]

    return {
        "country": country,
        "timezone": timezone,
        "locale": locale,
    }


def align_proxy_with_antidetect(
    proxy: ProxyConfig,
    config: AntidetectConfig,
) -> AntidetectConfig:
    """Выравнивает параметры часового пояса и локали AntidetectConfig в соответствии с прокси.

    Args:
        proxy: Конфигурация используемого прокси.
        config: Целевая конфигурация антидетекта.

    Returns:
        Сконфигурированный экземпляр AntidetectConfig с непротиворечивыми таймзоной и локалью.
    """
    geo = infer_proxy_geo(proxy)

    # Устанавливаем таймзону прокси, если в конфигурации она не была задана явно
    if not config.timezone:
        config.timezone = geo["timezone"]

    # Синхронизируем локаль, если она оставалась дефолтной или не была изменена пользователем
    if config.locale == "en-US" and geo["locale"] != "en-US":
        config.locale = geo["locale"]

    return config
