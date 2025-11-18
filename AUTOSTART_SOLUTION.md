# ⚡ РЕШЕНИЕ АВТОЗАПУСКА - AUTOMATION SYSTEM

## 📌 ОТВЕТ НА ГЛАВНЫЙ ВОПРОС

> **"Когда перезапустится IDE, все процессы запустятся автоматически?"**

###  **НЕТ**, сейчас автозапуск **НЕ НАСТРОЕН**. 

Компоненты запускаются только вручную.

---

## ✅ РЕШЕНИЕ: 3 СПОСОБА НАСТРОЙКИ АВТОЗАПУСКА

### 🎯 СПОСОБ 1: VS CODE TASKS (РЕКОМЕНДУЕТСЯ)

**Преимущества:**
- ✅ Автозапуск при открытии папки в VS Code
- ✅ Интеграция с IDE
- ✅ Простая настройка
- ✅ Логи в Output панели

**Создай файл `.vscode/tasks.json`:**

```json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Test Watcher - Autostart",
            "type": "shell",
            "command": "${workspaceFolder}/.venv/Scripts/python.exe",
            "args": [
                "${workspaceFolder}/automation/task1_test_watcher/test_watcher.py"
            ],
            "isBackground": true,
            "problemMatcher": [],
            "runOptions": {
                "runOn": "folderOpen"
            },
            "presentation": {
                "reveal": "silent",
                "panel": "dedicated"
            }
        },
        {
            "label": "Audit Agent - Autostart",
            "type": "shell",
            "command": "${workspaceFolder}/.venv/Scripts/python.exe",
            "args": [
                "${workspaceFolder}/automation/task3_audit_agent/audit_agent.py"
            ],
            "isBackground": true,
            "problemMatcher": [],
            "runOptions": {
                "runOn": "folderOpen"
            },
            "presentation": {
                "reveal": "silent",
                "panel": "dedicated"
            }
        }
    ]
}
```

**Как это работает:**
1. При открытии папки в VS Code
2. Tasks автоматически запускаются (`runOn: "folderOpen"`)
3. Компоненты работают в фоне (`isBackground: true`)
4. Логи доступны в Output панели

**Установка:**
```powershell
# 1. Создай директорию (если нет):
New-Item -ItemType Directory -Path .vscode -Force

# 2. Скопируй tasks.json в .vscode/tasks.json

# 3. Перезапусти VS Code

# 4. Компоненты запустятся автоматически!
```

---

### 🎯 СПОСОБ 2: WINDOWS TASK SCHEDULER (ДЛЯ АВТОЗАПУСКА ПРИ ЗАГРУЗКЕ WINDOWS)

**Преимущества:**
- ✅ Запуск при загрузке Windows (даже без VS Code)
- ✅ Автоматический restart при сбое
- ✅ Работает 24/7
- ❌ Сложнее настроить

**Создай PowerShell скрипт `automation_service.ps1`:**

```powershell
# automation_service.ps1
# Запуск всех компонентов автоматизации

$ProjectRoot = "D:\bybit_strategy_tester_v2"
$PythonExe = "$ProjectRoot\.venv\Scripts\python.exe"

# Функция для запуска компонента
function Start-Component {
    param (
        [string]$Name,
        [string]$ScriptPath
    )
    
    Write-Host "Starting $Name..." -ForegroundColor Green
    
    Start-Process -FilePath $PythonExe `
                  -ArgumentList $ScriptPath `
                  -WorkingDirectory $ProjectRoot `
                  -WindowStyle Hidden `
                  -PassThru
}

# Запуск Test Watcher
$tw = Start-Component -Name "Test Watcher" `
                     -ScriptPath "$ProjectRoot\automation\task1_test_watcher\test_watcher.py"

# Задержка между запусками
Start-Sleep -Seconds 2

# Запуск Audit Agent
$aa = Start-Component -Name "Audit Agent" `
                     -ScriptPath "$ProjectRoot\automation\task3_audit_agent\audit_agent.py"

Write-Host "`n✅ All components started!" -ForegroundColor Green
Write-Host "   Test Watcher PID: $($tw.Id)" -ForegroundColor White
Write-Host "   Audit Agent PID: $($aa.Id)" -ForegroundColor White

# Мониторинг процессов (бесконечный цикл)
while ($true) {
    Start-Sleep -Seconds 60
    
    # Проверка Test Watcher
    if (-not (Get-Process -Id $tw.Id -ErrorAction SilentlyContinue)) {
        Write-Host "⚠️  Test Watcher crashed! Restarting..." -ForegroundColor Yellow
        $tw = Start-Component -Name "Test Watcher" `
                             -ScriptPath "$ProjectRoot\automation\task1_test_watcher\test_watcher.py"
    }
    
    # Проверка Audit Agent
    if (-not (Get-Process -Id $aa.Id -ErrorAction SilentlyContinue)) {
        Write-Host "⚠️  Audit Agent crashed! Restarting..." -ForegroundColor Yellow
        $aa = Start-Component -Name "Audit Agent" `
                             -ScriptPath "$ProjectRoot\automation\task3_audit_agent\audit_agent.py"
    }
}
```

**Создание задачи в Task Scheduler:**

```powershell
# create_scheduled_task.ps1
# Создание задачи для автозапуска

$TaskName = "Bybit Automation System"
$ScriptPath = "D:\bybit_strategy_tester_v2\automation_service.ps1"

# Создание действия
$Action = New-ScheduledTaskAction -Execute "PowerShell.exe" `
                                   -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ScriptPath`""

# Триггер - запуск при загрузке
$Trigger = New-ScheduledTaskTrigger -AtStartup

# Настройки
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
                                          -DontStopIfGoingOnBatteries `
                                          -StartWhenAvailable `
                                          -RestartCount 3 `
                                          -RestartInterval (New-TimeSpan -Minutes 1)

# Создание задачи
Register-ScheduledTask -TaskName $TaskName `
                       -Action $Action `
                       -Trigger $Trigger `
                       -Settings $Settings `
                       -User $env:USERNAME `
                       -RunLevel Highest `
                       -Force

Write-Host "✅ Task '$TaskName' created successfully!" -ForegroundColor Green
Write-Host "   Will start at Windows boot" -ForegroundColor White
Write-Host "   Auto-restart on failure (3 attempts)" -ForegroundColor White
```

**Установка:**
```powershell
# 1. Создай automation_service.ps1 в корне проекта
# 2. Запусти create_scheduled_task.ps1 с правами администратора:
.\create_scheduled_task.ps1

# 3. Проверь Task Scheduler:
taskschd.msc

# 4. Найди "Bybit Automation System"
# 5. Готово! Система запустится при следующей загрузке Windows
```

---

### 🎯 СПОСОБ 3: PM2 (CROSS-PLATFORM)

**Преимущества:**
- ✅ Работает на Windows/Linux/Mac
- ✅ Автоматический restart
- ✅ Логи и мониторинг
- ✅ Простое управление

**Установка PM2:**
```powershell
# 1. Установи Node.js (если нет)
# Скачай: https://nodejs.org/

# 2. Установи PM2:
npm install -g pm2

# 3. Установи pm2-windows-startup (только Windows):
npm install -g pm2-windows-startup

# 4. Настрой автозапуск:
pm2-startup install
```

**Создай `ecosystem.config.js`:**

```javascript
// ecosystem.config.js
module.exports = {
  apps: [
    {
      name: "test-watcher",
      script: "D:\\bybit_strategy_tester_v2\\.venv\\Scripts\\python.exe",
      args: "D:\\bybit_strategy_tester_v2\\automation\\task1_test_watcher\\test_watcher.py",
      cwd: "D:\\bybit_strategy_tester_v2",
      autorestart: true,
      max_restarts: 10,
      min_uptime: "10s",
      restart_delay: 5000,
      error_file: "./logs/test_watcher_error.log",
      out_file: "./logs/test_watcher_out.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss"
    },
    {
      name: "audit-agent",
      script: "D:\\bybit_strategy_tester_v2\\.venv\\Scripts\\python.exe",
      args: "D:\\bybit_strategy_tester_v2\\automation\\task3_audit_agent\\audit_agent.py",
      cwd: "D:\\bybit_strategy_tester_v2",
      autorestart: true,
      max_restarts: 10,
      min_uptime: "10s",
      restart_delay: 5000,
      error_file: "./logs/audit_agent_error.log",
      out_file: "./logs/audit_agent_out.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss"
    }
  ]
};
```

**Запуск через PM2:**
```powershell
# 1. Запусти все компоненты:
pm2 start ecosystem.config.js

# 2. Сохрани конфигурацию для автозапуска:
pm2 save

# 3. Проверь статус:
pm2 status

# 4. Просмотр логов:
pm2 logs

# 5. Restart:
pm2 restart all

# 6. Stop:
pm2 stop all

# 7. Удаление:
pm2 delete all
```

---

## 📊 СРАВНЕНИЕ СПОСОБОВ

| Характеристика | VS Code Tasks | Task Scheduler | PM2 |
|---------------|---------------|----------------|-----|
| Простота настройки | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Автозапуск при загрузке Windows | ❌ | ✅ | ✅ |
| Автозапуск при открытии VS Code | ✅ | ❌ | ❌ |
| Auto-restart при сбое | ❌ | ✅ | ✅ |
| Логи и мониторинг | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| Cross-platform | ✅ | ❌ (Windows only) | ✅ |
| Управление процессами | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## 🎯 РЕКОМЕНДАЦИЯ

### Для разработки: **VS Code Tasks**
- Быстро настроить
- Запуск при открытии проекта
- Удобно для тестирования

### Для production: **PM2**
- Надёжный restart
- Отличный мониторинг
- Cross-platform

### Для Windows 24/7: **Task Scheduler**
- Запуск при загрузке системы
- Не требует дополнительного ПО
- Работает даже без VS Code

---

## ⚡ БЫСТРЫЙ СТАРТ

**Хочешь запустить СЕЙЧАС?**

```powershell
# 1. Создай tasks.json (см. выше)

# 2. Перезапусти VS Code

# 3. Всё! Компоненты запустятся автоматически
```

**Или:**

```powershell
# 1. Установи PM2:
npm install -g pm2

# 2. Создай ecosystem.config.js (см. выше)

# 3. Запусти:
pm2 start ecosystem.config.js
pm2 save

# 4. Готово! PM2 управляет процессами
```

---

## ✅ ЧЕКЛИСТ АВТОЗАПУСКА

- [ ] Выбрал способ автозапуска
- [ ] Создал конфигурационные файлы
- [ ] Протестировал запуск
- [ ] Проверил логи
- [ ] Настроил мониторинг
- [ ] Проверил auto-restart
- [ ] Документировал настройку

---

## 🎊 ИТОГ

**После настройки автозапуска:**
- ✅ Компоненты запускаются автоматически
- ✅ Auto-restart при сбое (если PM2/Task Scheduler)
- ✅ Логи ведутся автоматически
- ✅ Система работает 24/7
- ✅ Не нужно запускать вручную

**Система готова к autonomous operation!** 🚀
