---
applyTo: "**"
name: "MyPy Error Analysis Guide"
description: "Как анализировать и исправлять ошибки MyPy в проекте."
---

# 🔍 MyPy - Краткий гайд по отлову багов

## Что такое MyPy?
MyPy — статический анализатор типов для Python. Находит ошибки ДО запуска кода.

## Базовое использование

```bash
# Проверить один файл
mypy app.py

# Проверить весь проект
mypy src/

# Проверить с игнорированием отсутствующих импортов
mypy --ignore-missing-imports src/
```

## Конфигурация (mypy.ini или pyproject.toml)

```ini
[mypy]
python_version = 3.12
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True
ignore_missing_imports = True
```

## Типичные ошибки и как их чинить

### 1. "Argument has incompatible type"
**Проблема:** Передаёшь неправильный тип
```python
def process(value: int) -> str:
    return str(value)

process("test")  # ❌ Error: str вместо int
```
**Решение:** Проверь типы аргументов, используй правильный тип или Union.

### 2. "Function is missing a return statement"
**Проблема:** Функция не возвращает значение во всех ветках
```python
def get_name(user_id: int) -> str:
    if user_id > 0:
        return "User"
    # ❌ Если user_id <= 0, ничего не возвращается
```
**Решение:** Добавь return во все ветки или используй Optional.

### 3. "Item has no attribute"
**Проблема:** Обращаешься к несуществующему атрибуту
```python
value: int = 42
value.split()  # ❌ int не имеет метода split()
```
**Решение:** Проверь тип переменной, добавь type guard.

### 4. "Incompatible return value type"
**Проблема:** Возвращаешь не тот тип, что указан в сигнатуре
```python
def get_count() -> int:
    return "zero"  # ❌ Возвращаем str вместо int
```
**Решение:** Измени возвращаемое значение или аннотацию.

## Workflow

1. **Добавляй типы постепенно** — начни с публичных API
2. **Запускай mypy регулярно** — интегрируй в CI/CD
3. **Используй `reveal_type()`** — для отладки выведенных типов

---

**Главное:** MyPy помогает найти баги ДО запуска. Используй его как защитную сетку!
