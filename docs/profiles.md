# Менеджер профилей браузеров (profiles)

Модуль `browser_stealth.profiles` предоставляет средства для управления постоянными профилями браузеров (user data dir), их изоляцией, шифрованием и автоматическим восстановлением после аварийных завершений.

---

## 1. Менеджер профилей (`ProfileManager`)

Позволяет создавать, загружать и удалять постоянные профили пользователей:

```python
from browser_stealth import ProfileManager

manager = ProfileManager(storage_dir="~/.local/share/browser_profiles")

# Создание нового профиля с привязкой прокси и фингерпринта
profile = manager.create_profile(
    name="account_01",
    proxy="http://user:pass@1.2.3.4:8080",
    tags=["finance", "google"],
)

# Получение пути к user-data-dir
user_data_path = profile.path
```

---

## 2. Гигиена профилей и защита от блокировок (`hygiene`)

При неожиданном завершении процесса браузера (SIGKILL, падение системы) в каталоге профиля остаются lock-файлы (`SingletonLock`, `lockfile`) и маркеры аварийного завершения (`exit_type: "Crashed"`). 

При следующем запуске Chrome покажет диалоговое окно «Восстановить вкладки?», что ломает автоматизацию.

Функции гигиены устраняют эту проблему автоматически:

```python
from browser_stealth.profiles.hygiene import (
    is_profile_locked,
    sanitize_profile,
    sanitize_profile_crash_state,
)

profile_path = "/path/to/profile"

# 1. Проверка, не заблокирован ли профиль другим активным процессом
if is_profile_locked(profile_path):
    print("Профиль сейчас занят другим процессом!")

# 2. Очистка crash-состояний в Preferences и Local State
sanitize_profile_crash_state(profile_path)

# 3. Полный санитайзинг (удаление singleton locks, кэша GPU, shader cache)
sanitize_profile(profile_path)
```

Фабрика `launch_nodriver` автоматически выполняет санитайзинг перед запуском, если передан параметр `sanitize_profile_dir=True`.

---

## 3. Прогрев профиля (`ProfileWarmer`)

Имитация естественной истории посещений и куки для свежесозданного профиля:

```python
from browser_stealth.humanize.warmer import ProfileWarmer

warmer = ProfileWarmer(
    target_domains=["google.com", "wikipedia.org", "github.com"],
    min_page_sleep=3.0,
    max_page_sleep=8.0,
)

# Прогрев сессии
await warmer.warm_playwright(page)
```
