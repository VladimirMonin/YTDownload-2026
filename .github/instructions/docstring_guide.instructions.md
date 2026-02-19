---
applyTo: "**/*.py"
name: "DocstringGuideInstructions"
description: "Руководство по написанию docstring"
---

# Документирование кода (на русском языке)

## Модули (файлы .py)

Первая строка — краткое описание. Далее — публичный API модуля:

```python
"""Утилиты для работы с изображениями.

Функции:
    get_file_mime_type(file_path: str) -> str | None
        Определяет MIME-тип файла.
    read_file_as_bytes(file_path: str) -> bytes
        Читает файл как байты.
    is_image_valid(file_path: str) -> bool
        Проверяет, поддерживается ли формат изображения.
"""
```

Для модулей с классами:

```python
"""Клиент для работы с Gemini API.

Классы:
    GeminiClient
        Клиент для отправки запросов к Gemini API.

        Методы:
            generate_content(prompt: str, image: bytes) -> dict
                Генерирует контент на основе промпта и изображения.
            analyze_video(video_path: str, mode: str) -> VideoAnalysis
                Анализирует видео с извлечением кадров.
"""
```

## Функции и методы

Google-style docstring:

```python
def analyze_image(image_path: str, model: str = "default") -> dict:
    """Анализирует изображение через Gemini API.

    Args:
        image_path: Путь к файлу изображения.
        model: Модель для анализа (по умолчанию "default").

    Returns:
        Словарь с результатами анализа.

    Raises:
        ValueError: Если формат изображения не поддерживается.
        FileNotFoundError: Если файл не найден.
    """
```

**Правила:**

- Args, Returns, Raises — только при наличии
- Типы в сигнатуре, НЕ дублировать в docstring
- Краткое описание — глагол: "Анализирует", "Получает", "Создаёт"

## Классы

```python
class ImageProcessor:
    """Процессор для обработки изображений.

    Attributes:
        client: Клиент для API запросов.
        config: Конфигурация процессора.
    """
```

## Что НЕ документировать

- Приватные методы (`_parse_response`)
- Простые getter/setter
- `__init__` с простым присваиванием
- Однострочные lambda
