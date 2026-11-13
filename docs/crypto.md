# Портативное шифрование (crypto)

Модуль `browser_stealth.crypto` шифрует небольшие строки (секреты профиля,
cookies, JSON-настройки) детерминированным ключом, выведенным из seed. Формат
совместим между машинами: достаточно одного и того же seed, без хранения ключа.

```python
from browser_stealth import decrypt_portable, encrypt_portable

token = encrypt_portable('{"cookies": []}', seed="profile-a")
data = decrypt_portable(token, seed="profile-a")
```

## Установка

Шифрование использует `cryptography` из extra `crypto`:

```bash
uv add "browser-stealth[crypto]"
```

Без установленного пакета функции поднимают `OptionalDependencyError`.

## API

| Функция | Описание |
|---|---|
| `encrypt_portable(data, seed)` | Шифрует строку и возвращает URL-safe Base64-токен |
| `decrypt_portable(encrypted_data, seed, raise_on_error=False)` | Расшифровывает токен; при ошибке возвращает `None` или поднимает исключение |

```python
plain = decrypt_portable(token, seed="profile-a", raise_on_error=True)
```

## Ограничения

Ключ выводится из seed через SHA-256, поэтому:

- одинаковый seed всегда даёт одинаковый ключ — это удобно для переноса
  профилей, но означает, что **seed является секретом**;
- токены не детерминированы: Fernet добавляет случайный IV и временную метку,
  поэтому один и тот же открытый текст даёт разные токены;
- для ключей, которые нельзя восстановить из seed, используйте
  `chutils.SecretManager` вместо этого модуля.
