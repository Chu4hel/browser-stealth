# Управление прокси (proxy)

Модуль `browser_stealth.proxy` предоставляет надежные средства для парсинга, валидации, кэширования и ротации прокси-серверов.

---

## 1. Парсинг строковых форматов (`parse_proxy`)

Поддерживает все распространенные форматы записи:
* URL: `http://user:pass@1.2.3.4:8080`, `socks5://1.2.3.4:1080`
* Колоночные: `1.2.3.4:8080:user:pass`, `user:pass:1.2.3.4:8080`
* Специфичные: `user:pass@1.2.3.4:8080`, `1.2.3.4:8080@user:pass`
* Простой host:port: `1.2.3.4:8080`

```python
from browser_stealth import parse_proxy

config = parse_proxy("1.2.3.4:8080:myuser:mypass")
print(config.protocol)  # "http"
print(config.host)  # "1.2.3.4"
print(config.port)  # 8080
print(config.url)  # "http://myuser:mypass@1.2.3.4:8080"
```

---

## 2. Умный резолвер и зондирование (`SmartProxyResolver`)

Если прокси передан без явного указания протокола (например, `1.2.3.4:8080`), `SmartProxyResolver` выполняет быстрое активное TCP/HTTP зондирование (CONNECT / SOCKS5 handshake) и кэширует успешный протокол на диск:

```python
from browser_stealth.proxy.resolver import SmartProxyResolver

resolver = SmartProxyResolver()

# Автоматическое определение работающего протокола (HTTP vs SOCKS5)
working_url = await resolver.resolve("1.2.3.4:8080:user:pass")
print(working_url)  # "socks5://user:pass@1.2.3.4:8080"

# Проверка работоспособности и задержки (Health Check)
health = await resolver.check_health("http://1.2.3.4:8080")
if health.is_alive:
    print(f"Пинг: {health.latency_ms} мс")
```

---

## 3. Пул прокси с ротацией (`ProxyPool`)

Управление списком прокси с автоматической ротацией (Round-Robin, Random) и отслеживанием сбойных узлов:

```python
from browser_stealth import ProxyPool

pool = ProxyPool(
    proxies=[
        "http://proxy1.com:8080",
        "http://proxy2.com:8080",
    ],
    strategy="round_robin",
)

proxy = pool.get_next_proxy()
```
