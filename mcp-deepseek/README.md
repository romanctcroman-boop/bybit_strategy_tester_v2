# MCP DeepSeek (Node.js) для Cursor IDE

MCP-сервер для вызова DeepSeek API из Cursor IDE.

## Установка

```bash
cd mcp-deepseek
npm install
```

## API-ключ

Ключ **не должен** храниться в коде или в репозитории.

1. Скопируйте `.env.example` в `.env`:
   ```bash
   cp .env.example .env
   ```
2. В `.env` укажите ваш ключ:
   ```
   DEEPSEEK_API_KEY=sk-ваш_ключ
   ```

Либо задайте переменную окружения `DEEPSEEK_API_KEY` в настройках MCP в Cursor (Settings → MCP → deepseek-node → env).

## Подключение в Cursor

В `.cursor/mcp.json` уже добавлен сервер `deepseek-node`. Путь к скрипту задаётся относительно корня проекта.

**Если в Cursor у deepseek-node показывается "Error - Show Output":**

1. Выполните в папке проекта: `cd mcp-deepseek && npm install`.
2. Задайте `DEEPSEEK_API_KEY` в настройках MCP для deepseek-node (Cursor → Settings → Tools & MCP → deepseek-node → env) или создайте `mcp-deepseek/.env` из `.env.example`.
3. В `.cursor/mcp.json` для deepseek-node используется `cmd /c cd /d D:\...\mcp-deepseek && node server.js` — путь должен совпадать с вашим путём к проекту; при другом расположении проекта замените путь в `args`.
4. Перезапустите Cursor или отключите и снова включите сервер deepseek-node.

## Инструменты

- **deepseek_chat** — чат с DeepSeek (модели `deepseek-chat` или `deepseek-coder`).
- **deepseek_code_completion** — завершение кода через DeepSeek Coder.

## Запуск вручную (проверка)

```bash
cd mcp-deepseek
npm install
# задайте DEEPSEEK_API_KEY в .env или в окружении
node server.js
```

Сервер общается через stdio; в Cursor его запускает IDE.
