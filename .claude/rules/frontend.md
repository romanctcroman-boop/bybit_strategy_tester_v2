---
paths:
  - "frontend/**/*.js"
  - "frontend/**/*.html"
  - "frontend/**/*.css"
---

# Frontend Rules

## Ключевые правила
- **Нет build-шага** — чистые ES modules, без npm/webpack. Тестирование = перезагрузка браузера
- **Нет `var`** — только `const`/`let`
- **Нет sync XHR** — только `fetch()` + async/await
- Комиссия в UI — в **процентах** (0.07%), в backend — в **десятичных** (0.0007). Конвертация при отправке

## Ловушки direction
- CSS-класс `.direction-mismatch` = красный пунктирный провод (stroke: #ef4444)
- Провода нужно перерисовывать при изменении параметров блока
- Поле `warnings[]` из ответа бэктеста = показывать как notification

## Strategy Builder (strategy_builder.js — 13378 строк)
- `symbolSync` создаётся ДО `initDunnahBasePanel()` (иначе null)
- Drag/Marquee/Drop координаты делятся на `zoom` (логическое пространство)
- ID блоков: `block_${Date.now()}_${random}` (с суффиксом для уникальности)
- `pushUndo()` откладывается до первого реального движения мыши (>3px)

## Координаты канваса
```js
// Правильно — логические координаты
const logicalX = (clientX - canvasRect.left) / zoom;
// Неправильно — экранные без учёта zoom
const screenX = clientX - canvasRect.left;
```

## Тесты
```bash
# Запуск frontend тестов
npx jest frontend/js/
```
