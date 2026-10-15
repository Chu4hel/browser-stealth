# Спецификация валидации экстракции данных

Спецификация описывает контракты проверки полноты и корректности данных, извлеченных браузерными сценариями.

---

## Контракты утверждений

### 1. `assert_extraction_complete`
Проверяет наличие всех обязательных ключей и их непустоту:

```python
from browser_stealth.testing.assertions import assert_extraction_complete

extracted_item = {
    "title": "Ноутбук",
    "price": 75000,
    "currency": "RUB",
}

assert_extraction_complete(
    extracted_item,
    required_fields=["title", "price", "currency"],
)
```

### 2. `assert_schema_match`
Сравнивает структуру словаря с ожидаемой Pydantic-моделью или словарем типов:

```python
from pydantic import BaseModel
from browser_stealth.testing.assertions import assert_schema_match


class ProductModel(BaseModel):
    title: str
    price: int


assert_schema_match(extracted_item, ProductModel)
```

### 3. `assert_valid_url` и `assert_valid_price`
Специализированные проверки форматов URL (схема, хост) и числовых значений цен.
