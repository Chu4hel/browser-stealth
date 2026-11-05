# Issue 01: Устранение кросс-атрибутных несоответствий ОС, WebGL рендерера и шрифтов в синтезаторе отпечатков

## Описание
В модуле генерации цифровых отпечатков (`fingerprint/synthesizer.py` и `fingerprint/procedural.py`) параметры WebGL, видеокарты, операционной системы и шрифтов могут генерироваться независимо друг от друга. В результате возможны комбинации, физически невозможные на реальных устройствах.

## Уязвимость для антифрод-систем (CreepJS, Pixelscan, Cloudflare, DataDome)
1. **Несовместимость ОС и графического API WebGL:**
   - Если в профиле сгенерирован `User-Agent` для **macOS** (`MacIntel`), но WebGL рендерер возвращает строку вида `ANGLE (NVIDIA GeForce RTX 3080 Direct3D11 vs_5_0 ps_5_0)` или `ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11...)`. На macOS физически не существует Direct3D/DirectX (используется Apple Metal или OpenGL/Vulkan ANGLE).
   - Аналогично для **Linux**, где не может быть рендерера с суффиксом `Direct3D11`.
2. **Несоответствие списка шрифтов операционной системе:**
   - Измерение ширины рендеринга текста через скрытые элементы Canvas / DOM определяет системные шрифты Windows (`Calibri`, `Segoe UI`, `Consolas`) в профиле, декларирующем себя как Linux или macOS.
3. **Рассинхронизация Client Hints:**
   - Заголовки `Sec-CH-UA-Platform-Version`, `architecture` и `bitness` должны строго коррелировать с версией Chromium и ОС (например, Windows 10/11 мапится в `platformVersion: "10.0.0"` или `"15.0.0"`, а архитектура x86 на Apple M1/M2/M3 должна быть `arm`).

## Требуемые изменения
1. **Категоризация пулов GPU по платформам:**
   - Для `macOS`: ограничить список доступных рендереров семейством Apple Silicon (`Apple M1`, `Apple M2`, `Apple M3`), AMD Radeon Pro и Metal ANGLE.
   - Для `Windows`: допустимы NVIDIA, AMD Radeon, Intel UHD/Iris Xe с Direct3D11 / Direct3D12 ANGLE.
   - Для `Linux`: рендереры с Mesa, OpenGL и Vulkan ANGLE.
2. **Строгая валидация при синтезе профиля:**
   - В `FingerprintProfile` и `ProceduralSynthesizer` внедрить валидатор консистентности: принудительно согласовывать ОС, видеокарту, шрифты и Client Hints.
3. **Тестирование:**
   - Добавить модульные тесты проверки отсутствия несовместимых связок (например, тест, гарантирующий, что для macOS никогда не выбирается Direct3D).
