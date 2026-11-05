# Issue 02: Углубленная изоляция дочерних контекстов (Iframe Cross-realm inspection и Web Workers)

## Описание
В антидетект-скриптах (`antidetect/scripts.py`) подмена свойств `navigator`, `WebGL`, `Canvas` и `Permissions` выполняется в основном контексте окна (`window`). Однако продвинутые бот-детекторы (CreepJS, DataDome, Cloudflare Turnstile) используют скрытые изолированные контексты (Cross-realm inspection).

## Уязвимость для антифрод-систем
1. **Скрытые динамические Iframes:**
   - Скрипт защиты создает iframe в памяти без атрибута `src` (`about:blank` или `srcdoc`):
     ```javascript
     const iframe = document.createElement('iframe');
     iframe.style.display = 'none';
     document.documentElement.appendChild(iframe);
     const cleanNavigator = iframe.contentWindow.navigator;
     const isBot = cleanNavigator.webdriver; // Вернет true, если не защищен contentWindow!
     ```
   - Если маскировка не перехватывает доступ к `contentWindow` и `contentDocument` через геттеры `HTMLIFrameElement.prototype`, чистый контекст фрейма раскрывает реальные нативные свойства Chromium.
2. **Изолированные Web Workers и ServiceWorkers:**
   - Внутри фоновых воркеров (`new Worker(...)`, `SharedWorker`) нет объекта `window`, но доступен `WorkerGlobalScope` с собственным объектом `navigator`.
   - Воркер имеет доступ к `OffscreenCanvas`, `hardwareConcurrency`, `userAgent` и производит замер производительности. Если стелс-инъекция не распространяется на фабрику создания `Worker`, воркер выдает реальное железо и незамаскированный User-Agent.

## Требуемые изменения
1. **Каскадный перехват геттеров Iframe:**
   - Перехватить `HTMLIFrameElement.prototype.contentWindow` и `HTMLIFrameElement.prototype.contentDocument` через `Proxy` / `Object.defineProperty`, чтобы при любом обращении к новому фрейму применялись правила маскировки.
   - Перехватить `HTMLIFrameElement.prototype.srcdoc` и динамические методы вставки (`appendChild`, `insertBefore`).
2. **Перехват конструктора `Worker`:**
   - Обернуть глобальный конструктор `window.Worker` так, чтобы передаваемый рабочий скрипт оборачивался предварительной инъекцией стелс-прослойки в `WorkerGlobalScope` (подмена `navigator.hardwareConcurrency`, `navigator.userAgent`, маскировка `OffscreenCanvas`).
3. **Тестирование:**
   - Написать тесты с созданием динамических iframes и проверкой того, что `iframe.contentWindow.navigator.webdriver === false` или `undefined`.
