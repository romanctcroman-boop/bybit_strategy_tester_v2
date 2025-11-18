"""
Полный аудит проекта Bybit Strategy Tester v2 через DeepSeek и Perplexity AI
Проверка соответствия 4 техническим заданиям:
1. Техническое задание MCP-оркестратора_1.md
2. Техническое задание MCP-оркестратора_2.md  
3. Техническое задание_3-1.md
4. Расширенное техническое задание_3-2.md
"""

import asyncio
import httpx
import json
from datetime import datetime
from pathlib import Path
import time

# API Configuration
DEEPSEEK_API_KEY = "sk-1630fbba63c64f88952c16ad33337242"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

PERPLEXITY_API_KEY = "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"
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"

# Project paths
PROJECT_ROOT = Path(r"D:\bybit_strategy_tester_v2")
TZ_DIR = Path(r"D:\PERP\Demo")

# Output
RESULTS_FILE = PROJECT_ROOT / "FULL_TZ_AUDIT_RESULTS.json"
REPORT_FILE = PROJECT_ROOT / "FULL_TZ_AUDIT_REPORT.md"


class ProjectAnalyzer:
    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "tz_documents": [],
            "deepseek_analysis": {},
            "perplexity_analysis": {},
            "compliance_matrix": {},
            "critical_gaps": [],
            "recommendations": [],
            "total_tokens": 0
        }
    
    async def load_tz_documents(self):
        """Загрузка всех 4 ТЗ документов"""
        tz_files = [
            "Техническое задание MCP-оркестратора_1.md",
            "Техническое задание MCP-оркестратора_2.md",
            "Расширенное техническое задание_3-1.md",
            "Расширенное техническое задание_3-2.md"
        ]
        
        tz_content = {}
        for filename in tz_files:
            filepath = TZ_DIR / filename
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    tz_content[filename] = content
                    self.results["tz_documents"].append({
                        "name": filename,
                        "size": len(content),
                        "loaded": True
                    })
                    print(f"✅ Загружен: {filename} ({len(content)} символов)")
            else:
                print(f"❌ Не найден: {filename}")
                self.results["tz_documents"].append({
                    "name": filename,
                    "loaded": False,
                    "error": "File not found"
                })
        
        return tz_content
    
    async def scan_project_structure(self):
        """Сканирование структуры проекта"""
        structure = {
            "backend": [],
            "frontend": [],
            "mcp_server": [],
            "scripts": [],
            "tests": [],
            "docs": []
        }
        
        # Backend
        backend_dir = PROJECT_ROOT / "backend"
        if backend_dir.exists():
            structure["backend"] = [f.name for f in backend_dir.rglob("*.py")][:50]
        
        # Frontend
        frontend_dir = PROJECT_ROOT / "frontend"
        if frontend_dir.exists():
            structure["frontend"] = [f.name for f in frontend_dir.rglob("*.tsx")][:30]
        
        # MCP Server
        mcp_dir = PROJECT_ROOT / "mcp-server"
        if mcp_dir.exists():
            structure["mcp_server"] = [f.name for f in mcp_dir.rglob("*.py")][:20]
        
        # Scripts
        scripts_dir = PROJECT_ROOT / "scripts"
        if scripts_dir.exists():
            structure["scripts"] = [f.name for f in scripts_dir.glob("*.py")][:20]
        
        return structure
    
    async def deepseek_api_call(self, prompt: str, context: str = "") -> dict:
        """Реальный вызов DeepSeek API"""
        full_prompt = f"{context}\n\n{prompt}" if context else prompt
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "system",
                    "content": "Ты эксперт по анализу архитектуры и соответствия технических заданий. Проводи глубокий технический анализ."
                },
                {
                    "role": "user",
                    "content": full_prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 4000
        }
        
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(DEEPSEEK_API_URL, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            
            self.results["total_tokens"] += result.get("usage", {}).get("total_tokens", 0)
            return result
    
    async def perplexity_api_call(self, query: str, context: str = "") -> dict:
        """Реальный вызов Perplexity AI Sonar Pro"""
        full_query = f"{context}\n\n{query}" if context else query
        
        payload = {
            "model": "sonar-pro",
            "messages": [
                {
                    "role": "system",
                    "content": "Ты эксперт по современным архитектурам MCP-оркестраторов, мультиагентным системам и торговым стратегиям."
                },
                {
                    "role": "user",
                    "content": full_query
                }
            ],
            "temperature": 0.3,
            "max_tokens": 4000
        }
        
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(PERPLEXITY_API_URL, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            
            self.results["total_tokens"] += result.get("usage", {}).get("total_tokens", 0)
            return result
    
    async def analyze_tz1_compliance(self, tz_content: str, project_structure: dict):
        """Анализ соответствия ТЗ-1: Архитектура, Протоколы, Очереди, Воркеры"""
        print("\n" + "="*80)
        print("📋 АНАЛИЗ ТЗ-1: MCP Protocol, Redis Streams, Воркеры")
        print("="*80)
        
        # DeepSeek: Архитектурный анализ
        deepseek_prompt = f"""
Проанализируй проект Bybit Strategy Tester v2 на соответствие ТЗ-1.

ТЕХНИЧЕСКОЕ ЗАДАНИЕ (ТЗ-1):
{tz_content[:8000]}

СТРУКТУРА ПРОЕКТА:
{json.dumps(project_structure, indent=2)}

КРИТЕРИИ ПРОВЕРКИ:
1. JSON-RPC 2.0 протокол (FastAPI)
2. Redis Streams для очередей (mcp_tasks)
3. Consumer Groups для масштабирования
4. Celery/ARQ для CPU/ML задач
5. Async worker pool
6. SLA-driven autoscaling
7. Signal Routing Layer
8. Saga Pattern с компенсациями
9. Checkpoint Recovery

ВЫПОЛНИ:
1. Проверь наличие каждого компонента
2. Оцени реализацию (0-10)
3. Укажи критические пробелы
4. Дай конкретные рекомендации с примерами кода

Формат ответа:
- Компонент: [название]
- Статус: [IMPLEMENTED/PARTIAL/NOT_IMPLEMENTED]
- Оценка: [0-10]
- Проблемы: [список]
- Код для исправления: [если нужно]
"""
        
        try:
            print("🤖 DeepSeek анализирует ТЗ-1...")
            deepseek_result = await self.deepseek_api_call(deepseek_prompt)
            deepseek_analysis = deepseek_result["choices"][0]["message"]["content"]
            
            self.results["deepseek_analysis"]["tz1"] = {
                "prompt_tokens": deepseek_result["usage"]["prompt_tokens"],
                "completion_tokens": deepseek_result["usage"]["completion_tokens"],
                "analysis": deepseek_analysis
            }
            
            print(f"✅ DeepSeek завершил анализ ТЗ-1")
            print(f"   Токенов: {deepseek_result['usage']['total_tokens']}")
            
        except Exception as e:
            print(f"❌ Ошибка DeepSeek: {e}")
            self.results["deepseek_analysis"]["tz1"] = {"error": str(e)}
        
        await asyncio.sleep(2)
        
        # Perplexity: Сравнение с индустриальными стандартами
        perplexity_query = f"""
Проверь соответствие проекта Bybit Strategy Tester v2 современным стандартам MCP-оркестраторов 2025 года.

ТРЕБОВАНИЯ ТЗ-1:
- JSON-RPC 2.0 протокол
- Redis Streams с Consumer Groups
- Saga Pattern для long-running workflows
- SLA-driven autoscaling
- Checkpoint Recovery

СТРУКТУРА ПРОЕКТА:
Backend: {len(project_structure['backend'])} файлов
MCP Server: {len(project_structure['mcp_server'])} файлов

ЗАДАЧА:
1. Сравни с best practices индустрии
2. Оцени архитектурную зрелость (1-10)
3. Укажи критические недостатки
4. Предложи современные альтернативы и улучшения

Используй актуальные данные о MCP Protocol, Redis Streams patterns, Saga orchestration.
"""
        
        try:
            print("🔍 Perplexity AI проверяет индустриальные стандарты...")
            perplexity_result = await self.perplexity_api_call(perplexity_query)
            perplexity_analysis = perplexity_result["choices"][0]["message"]["content"]
            
            self.results["perplexity_analysis"]["tz1"] = {
                "prompt_tokens": perplexity_result["usage"]["prompt_tokens"],
                "completion_tokens": perplexity_result["usage"]["completion_tokens"],
                "analysis": perplexity_analysis
            }
            
            print(f"✅ Perplexity завершил анализ ТЗ-1")
            print(f"   Токенов: {perplexity_result['usage']['total_tokens']}")
            
        except Exception as e:
            print(f"❌ Ошибка Perplexity: {e}")
            self.results["perplexity_analysis"]["tz1"] = {"error": str(e)}
    
    async def analyze_tz2_compliance(self, tz_content: str, project_structure: dict):
        """Анализ соответствия ТЗ-2: Sandbox, Security, SLA/Мониторинг"""
        print("\n" + "="*80)
        print("🔒 АНАЛИЗ ТЗ-2: Sandbox Security, SLA, Мониторинг")
        print("="*80)
        
        # DeepSeek: Security audit
        deepseek_prompt = f"""
Проведи security audit проекта Bybit Strategy Tester v2 по ТЗ-2.

ТЕХНИЧЕСКОЕ ЗАДАНИЕ (ТЗ-2):
{tz_content[:8000]}

СТРУКТУРА ПРОЕКТА:
{json.dumps(project_structure, indent=2)}

КРИТЕРИИ ПРОВЕРКИ:
1. Docker/gVisor sandbox для AI-кода
2. Сетевая изоляция, read-only FS
3. Syscall auditing
4. Prometheus + Grafana мониторинг
5. OpenTelemetry distributed tracing
6. Автоматическое восстановление (Saga compensation)
7. SIEM интеграция
8. Multi-tenancy isolation
9. Threat modeling

ВЫПОЛНИ:
1. Оцени уровень безопасности (0-10)
2. Найди критические уязвимости
3. Проверь SLA monitoring
4. Дай код для исправления проблем

Формат: компонент → статус → оценка → проблемы → код
"""
        
        try:
            print("🤖 DeepSeek проводит security audit...")
            deepseek_result = await self.deepseek_api_call(deepseek_prompt)
            deepseek_analysis = deepseek_result["choices"][0]["message"]["content"]
            
            self.results["deepseek_analysis"]["tz2"] = {
                "prompt_tokens": deepseek_result["usage"]["prompt_tokens"],
                "completion_tokens": deepseek_result["usage"]["completion_tokens"],
                "analysis": deepseek_analysis
            }
            
            print(f"✅ DeepSeek завершил security audit")
            print(f"   Токенов: {deepseek_result['usage']['total_tokens']}")
            
        except Exception as e:
            print(f"❌ Ошибка DeepSeek: {e}")
            self.results["deepseek_analysis"]["tz2"] = {"error": str(e)}
        
        await asyncio.sleep(2)
        
        # Perplexity: Best practices 2025
        perplexity_query = f"""
Оцени безопасность и мониторинг Bybit Strategy Tester v2 по стандартам 2025 года.

ТРЕБОВАНИЯ ТЗ-2:
- Sandbox execution (Docker-in-Docker, gVisor, Firecracker)
- Prometheus/Grafana/OpenTelemetry
- Автоматическое восстановление
- Multi-tenancy
- Threat modeling

ПРОВЕРЬ:
1. Соответствие OWASP Top 10 для AI систем
2. Zero Trust Architecture принципы
3. Observability best practices (OpenTelemetry, Grafana)
4. Incident response automation

Дай практические рекомендации с примерами кода и конфигураций.
"""
        
        try:
            print("🔍 Perplexity AI проверяет security стандарты...")
            perplexity_result = await self.perplexity_api_call(perplexity_query)
            perplexity_analysis = perplexity_result["choices"][0]["message"]["content"]
            
            self.results["perplexity_analysis"]["tz2"] = {
                "prompt_tokens": perplexity_result["usage"]["prompt_tokens"],
                "completion_tokens": perplexity_result["usage"]["completion_tokens"],
                "analysis": perplexity_analysis
            }
            
            print(f"✅ Perplexity завершил security анализ")
            print(f"   Токенов: {perplexity_result['usage']['total_tokens']}")
            
        except Exception as e:
            print(f"❌ Ошибка Perplexity: {e}")
            self.results["perplexity_analysis"]["tz2"] = {"error": str(e)}
    
    async def analyze_tz3_compliance(self, tz_content_3_1: str, tz_content_3_2: str, project_structure: dict):
        """Анализ соответствия ТЗ-3: Мультиагентная лаборатория"""
        print("\n" + "="*80)
        print("🤖 АНАЛИЗ ТЗ-3: Мультиагентная лаборатория стратегий")
        print("="*80)
        
        # DeepSeek: Архитектура мультиагентной системы
        deepseek_prompt = f"""
Проанализируй мультиагентную архитектуру Bybit Strategy Tester v2 по ТЗ-3.

ТЕХНИЧЕСКОЕ ЗАДАНИЕ (ТЗ-3.1):
{tz_content_3_1[:6000]}

ТЕХНИЧЕСКОЕ ЗАДАНИЕ (ТЗ-3.2):
{tz_content_3_2[:6000]}

СТРУКТУРА ПРОЕКТА:
{json.dumps(project_structure, indent=2)}

ТРЕБУЕМЫЕ АГЕНТЫ:
1. MCP Server (центральный оркестратор)
2. Reasoning-агенты (Perplexity AI)
3. Code generation (DeepSeek)
4. ML-агенты/AutoML
5. User Behavior/Trader Psychology Agent
6. Sandbox execution
7. User-control interface

КРИТЕРИИ:
1. Наличие всех 7 агентов
2. Pipeline: идея → reasoning → codegen → ML → backtest → review
3. Chain-of-thought logging
4. Интерактивность (user feedback)
5. Автоматическая коррекция кода
6. Behavioral simulation (профили трейдеров)
7. Knowledge base для reasoning

ВЫПОЛНИ:
1. Проверь реализацию каждого агента
2. Оцени полноту pipeline (0-10)
3. Найди отсутствующие компоненты
4. Дай код для создания недостающих агентов

Формат: агент → статус → оценка → пробелы → код
"""
        
        try:
            print("🤖 DeepSeek анализирует мультиагентную систему...")
            deepseek_result = await self.deepseek_api_call(deepseek_prompt)
            deepseek_analysis = deepseek_result["choices"][0]["message"]["content"]
            
            self.results["deepseek_analysis"]["tz3"] = {
                "prompt_tokens": deepseek_result["usage"]["prompt_tokens"],
                "completion_tokens": deepseek_result["usage"]["completion_tokens"],
                "analysis": deepseek_analysis
            }
            
            print(f"✅ DeepSeek завершил анализ мультиагентной системы")
            print(f"   Токенов: {deepseek_result['usage']['total_tokens']}")
            
        except Exception as e:
            print(f"❌ Ошибка DeepSeek: {e}")
            self.results["deepseek_analysis"]["tz3"] = {"error": str(e)}
        
        await asyncio.sleep(2)
        
        # Perplexity: Индустриальные паттерны мультиагентных систем
        perplexity_query = f"""
Оцени мультиагентную архитектуру Bybit Strategy Tester v2 по современным стандартам.

ТРЕБОВАНИЯ ТЗ-3:
- Reasoning агенты (chain-of-thought, explainable AI)
- Code generation с автокоррекцией
- AutoML для оптимизации параметров
- Trader Psychology Agent (профили: rabbit, wolf, speculator)
- User feedback loops и интерактивность
- Knowledge base для accumulation опыта

СТРУКТУРА:
Backend: {len(project_structure['backend'])} файлов
MCP Server: {len(project_structure['mcp_server'])} файлов
Frontend: {len(project_structure['frontend'])} файлов

ЗАДАЧА:
1. Сравни с современными multi-agent frameworks (LangChain, AutoGen, CrewAI)
2. Оцени архитектурную зрелость (1-10)
3. Проверь explainability и user control
4. Предложи улучшения с примерами кода

Используй актуальные данные о multi-agent systems, reasoning chains, behavioral simulation.
"""
        
        try:
            print("🔍 Perplexity AI проверяет мультиагентные паттерны...")
            perplexity_result = await self.perplexity_api_call(perplexity_query)
            perplexity_analysis = perplexity_result["choices"][0]["message"]["content"]
            
            self.results["perplexity_analysis"]["tz3"] = {
                "prompt_tokens": perplexity_result["usage"]["prompt_tokens"],
                "completion_tokens": perplexity_result["usage"]["completion_tokens"],
                "analysis": perplexity_analysis
            }
            
            print(f"✅ Perplexity завершил анализ мультиагентных систем")
            print(f"   Токенов: {perplexity_result['usage']['total_tokens']}")
            
        except Exception as e:
            print(f"❌ Ошибка Perplexity: {e}")
            self.results["perplexity_analysis"]["tz3"] = {"error": str(e)}
    
    async def generate_compliance_matrix(self):
        """Генерация матрицы соответствия"""
        print("\n" + "="*80)
        print("📊 ГЕНЕРАЦИЯ МАТРИЦЫ СООТВЕТСТВИЯ")
        print("="*80)
        
        # DeepSeek: Итоговая оценка
        summary_prompt = f"""
На основе всех проведённых анализов создай compliance matrix проекта.

АНАЛИЗЫ:
ТЗ-1 (DeepSeek): {str(self.results['deepseek_analysis'].get('tz1', {}))[:2000]}
ТЗ-2 (DeepSeek): {str(self.results['deepseek_analysis'].get('tz2', {}))[:2000]}
ТЗ-3 (DeepSeek): {str(self.results['deepseek_analysis'].get('tz3', {}))[:2000]}

СОЗДАЙ ТАБЛИЦУ:
| Компонент | ТЗ-1 | ТЗ-2 | ТЗ-3 | Статус | Оценка | Приоритет |
|-----------|------|------|------|--------|--------|-----------|
| JSON-RPC  | Req  | -    | Req  | ?      | ?/10   | ?         |
| ...

КРИТИЧЕСКИЕ ПРОБЕЛЫ (TOP-5):
1. Компонент X - отсутствует полностью
2. ...

РЕКОМЕНДАЦИИ (TOP-10 с кодом):
1. Реализовать Redis Streams
```python
[код]
```
2. ...

ИТОГОВАЯ ОЦЕНКА: X/10
ВРЕМЯ ДО PRODUCTION: Y недель
"""
        
        try:
            print("🤖 DeepSeek генерирует итоговую матрицу...")
            deepseek_result = await self.deepseek_api_call(summary_prompt)
            compliance_matrix = deepseek_result["choices"][0]["message"]["content"]
            
            self.results["compliance_matrix"] = {
                "prompt_tokens": deepseek_result["usage"]["prompt_tokens"],
                "completion_tokens": deepseek_result["usage"]["completion_tokens"],
                "matrix": compliance_matrix
            }
            
            print(f"✅ Матрица соответствия готова")
            print(f"   Токенов: {deepseek_result['usage']['total_tokens']}")
            
        except Exception as e:
            print(f"❌ Ошибка DeepSeek: {e}")
            self.results["compliance_matrix"] = {"error": str(e)}
    
    async def save_results(self):
        """Сохранение результатов"""
        print("\n" + "="*80)
        print("💾 СОХРАНЕНИЕ РЕЗУЛЬТАТОВ")
        print("="*80)
        
        # JSON results
        with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        print(f"✅ JSON: {RESULTS_FILE}")
        
        # Markdown report
        report = self.generate_markdown_report()
        with open(REPORT_FILE, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"✅ Markdown: {REPORT_FILE}")
        
        print(f"\n📊 Всего использовано токенов: {self.results['total_tokens']}")
    
    def generate_markdown_report(self) -> str:
        """Генерация Markdown отчёта"""
        report = f"""# 🎯 ПОЛНЫЙ АУДИТ ПРОЕКТА BYBIT STRATEGY TESTER V2

**Дата**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Всего токенов**: {self.results['total_tokens']}

---

## 📚 ТЕХНИЧЕСКИЕ ЗАДАНИЯ

"""
        for tz in self.results["tz_documents"]:
            status = "✅" if tz.get("loaded") else "❌"
            report += f"- {status} **{tz['name']}**"
            if tz.get("loaded"):
                report += f" ({tz['size']} символов)\n"
            else:
                report += f" - {tz.get('error', 'Unknown error')}\n"
        
        report += "\n---\n\n## 🤖 АНАЛИЗ DEEPSEEK\n\n"
        
        for tz_key in ["tz1", "tz2", "tz3"]:
            if tz_key in self.results["deepseek_analysis"]:
                analysis = self.results["deepseek_analysis"][tz_key]
                report += f"### {tz_key.upper()}\n\n"
                if "error" in analysis:
                    report += f"❌ **Ошибка**: {analysis['error']}\n\n"
                else:
                    report += f"**Токены**: {analysis.get('prompt_tokens', 0)} → {analysis.get('completion_tokens', 0)}\n\n"
                    report += f"```\n{analysis.get('analysis', 'N/A')[:2000]}\n```\n\n"
        
        report += "\n---\n\n## 🔍 АНАЛИЗ PERPLEXITY AI\n\n"
        
        for tz_key in ["tz1", "tz2", "tz3"]:
            if tz_key in self.results["perplexity_analysis"]:
                analysis = self.results["perplexity_analysis"][tz_key]
                report += f"### {tz_key.upper()}\n\n"
                if "error" in analysis:
                    report += f"❌ **Ошибка**: {analysis['error']}\n\n"
                else:
                    report += f"**Токены**: {analysis.get('prompt_tokens', 0)} → {analysis.get('completion_tokens', 0)}\n\n"
                    report += f"```\n{analysis.get('analysis', 'N/A')[:2000]}\n```\n\n"
        
        report += "\n---\n\n## 📊 МАТРИЦА СООТВЕТСТВИЯ\n\n"
        
        if "matrix" in self.results["compliance_matrix"]:
            report += f"{self.results['compliance_matrix']['matrix']}\n\n"
        else:
            report += "❌ Матрица не сгенерирована\n\n"
        
        report += "\n---\n\n## 🎉 ИТОГО\n\n"
        report += f"- **Документов проанализировано**: {len([t for t in self.results['tz_documents'] if t.get('loaded')])}/4\n"
        report += f"- **DeepSeek анализов**: {len(self.results['deepseek_analysis'])}\n"
        report += f"- **Perplexity анализов**: {len(self.results['perplexity_analysis'])}\n"
        report += f"- **Всего токенов**: {self.results['total_tokens']}\n"
        
        return report
    
    async def run(self):
        """Главный pipeline"""
        print("\n" + "="*80)
        print("🚀 ЗАПУСК ПОЛНОГО АУДИТА ПРОЕКТА")
        print("="*80)
        print(f"Проект: {PROJECT_ROOT}")
        print(f"ТЗ документы: {TZ_DIR}")
        print()
        
        start_time = time.time()
        
        # 1. Загрузка ТЗ
        tz_content = await self.load_tz_documents()
        
        # 2. Сканирование проекта
        print("\n📂 Сканирование структуры проекта...")
        project_structure = await self.scan_project_structure()
        print(f"✅ Backend: {len(project_structure['backend'])} файлов")
        print(f"✅ Frontend: {len(project_structure['frontend'])} файлов")
        print(f"✅ MCP Server: {len(project_structure['mcp_server'])} файлов")
        
        # 3. Анализ ТЗ-1
        if "Техническое задание MCP-оркестратора_1.md" in tz_content:
            await self.analyze_tz1_compliance(
                tz_content["Техническое задание MCP-оркестратора_1.md"],
                project_structure
            )
        
        # 4. Анализ ТЗ-2
        if "Техническое задание MCP-оркестратора_2.md" in tz_content:
            await self.analyze_tz2_compliance(
                tz_content["Техническое задание MCP-оркестратора_2.md"],
                project_structure
            )
        
        # 5. Анализ ТЗ-3
        if ("Расширенное техническое задание_3-1.md" in tz_content and 
            "Расширенное техническое задание_3-2.md" in tz_content):
            await self.analyze_tz3_compliance(
                tz_content["Расширенное техническое задание_3-1.md"],
                tz_content["Расширенное техническое задание_3-2.md"],
                project_structure
            )
        
        # 6. Генерация матрицы соответствия
        await self.generate_compliance_matrix()
        
        # 7. Сохранение результатов
        await self.save_results()
        
        elapsed = time.time() - start_time
        
        print("\n" + "="*80)
        print("🎉 АУДИТ ЗАВЕРШЁН!")
        print("="*80)
        print(f"⏱️  Время выполнения: {elapsed:.1f} секунд")
        print(f"📊 Всего токенов: {self.results['total_tokens']}")
        print(f"📄 Результаты: {RESULTS_FILE}")
        print(f"📄 Отчёт: {REPORT_FILE}")
        print("="*80)


async def main():
    analyzer = ProjectAnalyzer()
    await analyzer.run()


if __name__ == "__main__":
    asyncio.run(main())
