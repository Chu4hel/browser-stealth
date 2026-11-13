"""Тесты автоопределения гео-данных прокси и синхронизации с AntidetectConfig (Issue #04)."""

from __future__ import annotations

from browser_stealth.antidetect.config import AntidetectConfig
from browser_stealth.proxy.geo import align_proxy_with_antidetect, infer_proxy_geo
from browser_stealth.proxy.models import ProxyConfig


def test_infer_proxy_geo_by_country_field() -> None:
    """Проверяет определение таймзоны и локали по явному полю country."""
    proxy = ProxyConfig(
        host="1.2.3.4",
        port=8080,
        country="DE",
    )
    geo = infer_proxy_geo(proxy)
    assert geo["country"] == "DE"
    assert geo["timezone"] == "Europe/Berlin"
    assert geo["locale"] == "de-DE"


def test_infer_proxy_geo_by_metadata() -> None:
    """Проверяет извлечение метаданных о геопозиции из словаря metadata."""
    proxy = ProxyConfig(
        host="5.6.7.8",
        port=1080,
        metadata={"country": "JP"},
    )
    geo = infer_proxy_geo(proxy)
    assert geo["country"] == "JP"
    assert geo["timezone"] == "Asia/Tokyo"
    assert geo["locale"] == "ja-JP"


def test_infer_proxy_geo_explicit_overrides() -> None:
    """Проверяет приоритет явных параметров таймзоны и локали над справочником страны."""
    proxy = ProxyConfig(
        host="9.10.11.12",
        port=3128,
        country="US",
        timezone="America/Los_Angeles",
        locale="en-CA",
    )
    geo = infer_proxy_geo(proxy)
    assert geo["timezone"] == "America/Los_Angeles"
    assert geo["locale"] == "en-CA"


def test_align_proxy_with_antidetect_updates_timezone_and_locale() -> None:
    """Проверяет выравнивание таймзоны и локали в AntidetectConfig."""
    proxy = ProxyConfig(
        host="45.145.57.203",
        port=11847,
        country="NL",
    )
    config = AntidetectConfig()
    assert config.timezone is None
    assert config.locale == "en-US"

    aligned = align_proxy_with_antidetect(proxy, config)
    assert aligned.timezone == "Europe/Amsterdam"
    assert aligned.locale == "nl-NL"


def test_proxy_to_antidetect_config_helper() -> None:
    """Проверяет вызов вспомогательного метода ProxyConfig.to_antidetect_config()."""
    proxy = ProxyConfig(
        host="185.190.140.1",
        port=8000,
        country="FR",
    )
    cfg = proxy.to_antidetect_config()
    assert cfg.timezone == "Europe/Paris"
    assert cfg.locale == "fr-FR"


def test_align_proxy_preserves_user_explicit_timezone() -> None:
    """Проверяет, что явно заданная пользователем таймзона в конфиге не перезаписывается."""
    proxy = ProxyConfig(host="1.1.1.1", port=80, country="RU")
    custom_cfg = AntidetectConfig(timezone="Asia/Vladivostok", locale="ru-RU")

    aligned = align_proxy_with_antidetect(proxy, custom_cfg)
    assert aligned.timezone == "Asia/Vladivostok"
    assert aligned.locale == "ru-RU"
