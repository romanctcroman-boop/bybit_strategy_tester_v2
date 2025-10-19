# Alembic Migrations

Запускайте миграции командой:

```powershell
(.venv) PS D:\bybit_strategy_tester_v2> alembic revision --autogenerate -m "create tables"
(.venv) PS D:\bybit_strategy_tester_v2> alembic upgrade head
```

Переменная окружения `ALEMBIC_DATABASE_URL` (или `DATABASE_URL`) переопределяет URL подключения.
