---
applyTo: "**"
name: "ArchitectureSerial"
description: "Руководство по написанию архитектурного сериала"
---

# 📺 Architecture Serial

**Цель:** Документирование архитектурных решений в формате сериала  
**Триггер:** Пользователь явно просит написать серию + код работает

---

## Workflow (10 шагов)

1. **Читай** `docs/architecture/STYLE_GUIDE.md` целиком
2. **Определи номер** — проверь все `season-X/README.md`, возьми следующий
3. **Коммиты** — `git log --oneline -n 10`, выбери связанные (1-5)
4. **Тема** — одна логическая концепция = одна серия
5. **Напиши** — следуй STYLE_GUIDE (Synopsis → Problem → Solution → Details)
6. **Диаграммы** — минимум 2 Mermaid (architecture + sequence)
7. **Проверь** — checklist ниже
8. **Сохрани** — `season-X-name/XX_title.md`
9. **Обнови каталоги** — Season README + центральный README
10. **Сообщи** пользователю (файл, сезон, коммиты, длина)

---

## Выбор сезона

| Season         | Тема                                       |
| -------------- | ------------------------------------------ |
| 1 Foundation   | Clean Architecture, базовая инфраструктура |
| 2 UI Evolution | Интерфейс, виджеты, конфигурация           |
| 3 Intelligence | LLM, поиск, SQLite, clipboard              |
| 4 Performance  | Оптимизация, потоки, кроссплатформенность  |
| 5 Production   | Логирование, packaging, MCP, полировка     |

---

## Checklist

- [ ] Synopsis понятен без чтения всей серии?
- [ ] Минимум 2 Mermaid диаграммы?
- [ ] НЕТ code blocks (кроме mermaid)?
- [ ] 300-500 строк?
- [ ] Commits указаны (7 символов)?
- [ ] Файлы/классы/модули упомянуты?
- [ ] Focus on WHY, not WHAT?

---

## НЕ пиши серию если

- Всего 1 мелкий commit (typo, formatting)
- Код не работает / не подтверждён
- Нет логической связи между коммитами
- Просто bug fix без архитектурных изменений

---

**Конец Architecture Serial Instructions**
