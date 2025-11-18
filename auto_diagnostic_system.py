"""
🔍 Automatic Self-Diagnostic System
Автоматическая система само-диагностики для MCP Reliability System

Функции:
1. Запуск MCP server с проверкой
2. Загрузка и проверка всех API ключей (8 DeepSeek + 4 Perplexity)
3. Проверка связи с каждым агентом через каждый ключ
4. Непрерывная работа в фоне
5. Критический анализ через оба агента
"""

import asyncio
import httpx
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any


class AutoDiagnosticSystem:
    """Система автоматической само-диагностики"""
    
    def __init__(self):
        self.mcp_url = "http://localhost:3000"
        self.deepseek_url = "https://api.deepseek.com/v1/chat/completions"
        self.perplexity_url = "https://api.perplexity.ai/chat/completions"
        
        # API ключи (загружаются из шифрования)
        self.api_keys = {
            "deepseek": [],
            "perplexity": []
        }
        
        # Статистика диагностики
        self.stats = {
            "mcp_checks": 0,
            "mcp_success": 0,
            "deepseek_keys_tested": 0,
            "deepseek_keys_working": 0,
            "perplexity_keys_tested": 0,
            "perplexity_keys_working": 0,
            "last_full_diagnostic": None,
            "continuous_monitoring_active": False
        }
        
        # Результаты проверки каждого ключа
        self.key_health = {
            "deepseek": {},  # key_index -> {"working": bool, "last_check": timestamp}
            "perplexity": {}
        }
    
    def load_api_keys_from_config(self):
        """Загрузка API ключей из конфигурации"""
        print("📦 Загрузка API ключей из конфигурации...")
        
        try:
            # Импортируем функцию загрузки ключей
            import sys
            backend_path = Path("backend/core")
            if str(backend_path) not in sys.path:
                sys.path.insert(0, str(backend_path))
            
            from config import get_api_keys
            
            keys = get_api_keys()
            
            self.api_keys["deepseek"] = keys.get("deepseek", [])
            self.api_keys["perplexity"] = keys.get("perplexity", [])
            
            print(f"✅ Загружено DeepSeek ключей: {len(self.api_keys['deepseek'])}")
            print(f"✅ Загружено Perplexity ключей: {len(self.api_keys['perplexity'])}")
            
        except Exception as e:
            print(f"⚠️ Ошибка загрузки ключей из config.py: {e}")
            print("   Пытаемся загрузить из .env файла...")
            
            # Fallback: загрузка из .env
            try:
                from dotenv import load_dotenv
                import os
                
                load_dotenv()
                
                # DeepSeek keys (8 шт)
                for i in range(1, 9):
                    key = os.getenv(f"DEEPSEEK_API_KEY_{i}")
                    if key:
                        self.api_keys["deepseek"].append(key)
                
                # Perplexity keys (4 шт)
                for i in range(1, 5):
                    key = os.getenv(f"PERPLEXITY_API_KEY_{i}")
                    if key:
                        self.api_keys["perplexity"].append(key)
                
                print(f"✅ Загружено из .env - DeepSeek: {len(self.api_keys['deepseek'])}, Perplexity: {len(self.api_keys['perplexity'])}")
            
            except Exception as env_error:
                print(f"❌ Не удалось загрузить ключи: {env_error}")
    
    async def check_mcp_server(self) -> bool:
        """Проверка работоспособности MCP server"""
        self.stats["mcp_checks"] += 1
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.mcp_url}/health")
                
                if response.status_code == 200:
                    self.stats["mcp_success"] += 1
                    return True
        except Exception as e:
            print(f"⚠️ MCP server недоступен: {e}")
        
        return False
    
    async def test_deepseek_key(self, api_key: str, key_index: int) -> bool:
        """Тест одного DeepSeek API ключа"""
        self.stats["deepseek_keys_tested"] += 1
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.deepseek_url,
                    json={
                        "model": "deepseek-chat",
                        "messages": [{"role": "user", "content": "Test: 2+2=?"}],
                        "max_tokens": 50
                    },
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    self.stats["deepseek_keys_working"] += 1
                    self.key_health["deepseek"][key_index] = {
                        "working": True,
                        "last_check": time.time(),
                        "status": "✅ OK"
                    }
                    return True
                else:
                    self.key_health["deepseek"][key_index] = {
                        "working": False,
                        "last_check": time.time(),
                        "status": f"❌ HTTP {response.status_code}"
                    }
        
        except Exception as e:
            self.key_health["deepseek"][key_index] = {
                "working": False,
                "last_check": time.time(),
                "status": f"❌ {type(e).__name__}"
            }
        
        return False
    
    async def test_perplexity_key(self, api_key: str, key_index: int) -> bool:
        """Тест одного Perplexity API ключа"""
        self.stats["perplexity_keys_tested"] += 1
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.perplexity_url,
                    json={
                        "model": "sonar",
                        "messages": [{"role": "user", "content": "Test: 2+2=?"}],
                        "max_tokens": 50
                    },
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    self.stats["perplexity_keys_working"] += 1
                    self.key_health["perplexity"][key_index] = {
                        "working": True,
                        "last_check": time.time(),
                        "status": "✅ OK"
                    }
                    return True
                else:
                    self.key_health["perplexity"][key_index] = {
                        "working": False,
                        "last_check": time.time(),
                        "status": f"❌ HTTP {response.status_code}"
                    }
        
        except Exception as e:
            self.key_health["perplexity"][key_index] = {
                "working": False,
                "last_check": time.time(),
                "status": f"❌ {type(e).__name__}"
            }
        
        return False
    
    async def run_full_diagnostic(self) -> Dict[str, Any]:
        """Полная диагностика всех компонентов"""
        print("\n" + "=" * 80)
        print("🔍 ЗАПУСК ПОЛНОЙ ДИАГНОСТИКИ СИСТЕМЫ")
        print("=" * 80)
        
        start_time = time.time()
        
        # 1. Проверка MCP Server
        print("\n📦 [1/3] Проверка MCP Server...")
        mcp_ok = await self.check_mcp_server()
        
        if mcp_ok:
            print("   ✅ MCP Server работает")
        else:
            print("   ⚠️ MCP Server недоступен (будет использован Direct API)")
        
        # 2. Проверка всех DeepSeek ключей (8 шт)
        print(f"\n📦 [2/3] Проверка DeepSeek ключей ({len(self.api_keys['deepseek'])} шт)...")
        
        deepseek_tasks = [
            self.test_deepseek_key(key, idx)
            for idx, key in enumerate(self.api_keys["deepseek"])
        ]
        
        deepseek_results = await asyncio.gather(*deepseek_tasks)
        
        for idx, result in enumerate(deepseek_results):
            status = self.key_health["deepseek"][idx]["status"]
            print(f"   DeepSeek Key #{idx + 1}: {status}")
        
        # 3. Проверка всех Perplexity ключей (4 шт)
        print(f"\n📦 [3/3] Проверка Perplexity ключей ({len(self.api_keys['perplexity'])} шт)...")
        
        perplexity_tasks = [
            self.test_perplexity_key(key, idx)
            for idx, key in enumerate(self.api_keys["perplexity"])
        ]
        
        perplexity_results = await asyncio.gather(*perplexity_tasks)
        
        for idx, result in enumerate(perplexity_results):
            status = self.key_health["perplexity"][idx]["status"]
            print(f"   Perplexity Key #{idx + 1}: {status}")
        
        # Итоговая статистика
        elapsed = time.time() - start_time
        self.stats["last_full_diagnostic"] = datetime.now()
        
        print("\n" + "=" * 80)
        print("📊 РЕЗУЛЬТАТЫ ДИАГНОСТИКИ")
        print("=" * 80)
        print(f"   MCP Server: {'✅ Работает' if mcp_ok else '⚠️ Недоступен'}")
        print(f"   DeepSeek ключей работает: {sum(deepseek_results)}/{len(deepseek_results)}")
        print(f"   Perplexity ключей работает: {sum(perplexity_results)}/{len(perplexity_results)}")
        print(f"   Время выполнения: {elapsed:.2f}s")
        print("=" * 80)
        
        return {
            "success": True,
            "mcp_available": mcp_ok,
            "deepseek_working": sum(deepseek_results),
            "deepseek_total": len(deepseek_results),
            "perplexity_working": sum(perplexity_results),
            "perplexity_total": len(perplexity_results),
            "elapsed_time": elapsed
        }
    
    async def request_agent_analysis(self) -> Dict[str, Any]:
        """
        🔥 КРИТИЧНАЯ ФУНКЦИЯ: Запрос дополнительной аналитики от обоих агентов
        
        Оба агента (DeepSeek и Perplexity) анализируют результаты диагностики
        и дают рекомендации по улучшению системы
        """
        print("\n" + "=" * 80)
        print("🧠 ЗАПРОС ДОПОЛНИТЕЛЬНОЙ АНАЛИТИКИ ОТ АГЕНТОВ")
        print("=" * 80)
        
        # Подготовка контекста для агентов
        diagnostic_context = {
            "mcp_status": "available" if self.stats["mcp_success"] > 0 else "unavailable",
            "deepseek_keys_working": self.stats["deepseek_keys_working"],
            "deepseek_keys_total": len(self.api_keys["deepseek"]),
            "perplexity_keys_working": self.stats["perplexity_keys_working"],
            "perplexity_keys_total": len(self.api_keys["perplexity"]),
            "key_health_details": self.key_health
        }
        
        analysis_prompt = f"""
# КРИТИЧЕСКАЯ ЗАДАЧА: Анализ результатов диагностики MCP Reliability System

## Текущее состояние системы

**MCP Server:** {diagnostic_context['mcp_status']}
**DeepSeek Keys:** {diagnostic_context['deepseek_keys_working']}/{diagnostic_context['deepseek_keys_total']} работают
**Perplexity Keys:** {diagnostic_context['perplexity_keys_working']}/{diagnostic_context['perplexity_keys_total']} работают

## Детали проверки ключей

{json.dumps(diagnostic_context['key_health_details'], indent=2)}

## Твоя задача

Проанализируй результаты диагностики и дай рекомендации:

1. **Оценка надёжности:** Насколько система готова к production использованию?
2. **Критические проблемы:** Какие ключи не работают и почему?
3. **Рекомендации:** Что нужно исправить СРОЧНО?
4. **Мониторинг:** Какие метрики отслеживать для предотвращения сбоев?
5. **Автоматизация:** Как улучшить автоматическую диагностику?

Будь конкретным и actionable. Это критически важно для production deployment.
"""
        
        # Запрос к DeepSeek Agent (используем первый рабочий ключ)
        deepseek_analysis = None
        for idx, key in enumerate(self.api_keys["deepseek"]):
            if self.key_health["deepseek"].get(idx, {}).get("working", False):
                print(f"\n🤖 Запрос аналитики от DeepSeek Agent (ключ #{idx + 1})...")
                
                try:
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        response = await client.post(
                            self.deepseek_url,
                            json={
                                "model": "deepseek-chat",
                                "messages": [{"role": "user", "content": analysis_prompt}],
                                "max_tokens": 3000,
                                "temperature": 0.7
                            },
                            headers={
                                "Authorization": f"Bearer {key}",
                                "Content-Type": "application/json"
                            }
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            deepseek_analysis = data["choices"][0]["message"]["content"]
                            print(f"✅ DeepSeek Agent ответил ({len(deepseek_analysis)} символов)")
                            break
                
                except Exception as e:
                    print(f"❌ DeepSeek Agent #{idx + 1} error: {e}")
        
        # Запрос к Perplexity Agent (используем первый рабочий ключ)
        perplexity_analysis = None
        for idx, key in enumerate(self.api_keys["perplexity"]):
            if self.key_health["perplexity"].get(idx, {}).get("working", False):
                print(f"\n🤖 Запрос аналитики от Perplexity Agent (ключ #{idx + 1})...")
                
                try:
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        response = await client.post(
                            self.perplexity_url,
                            json={
                                "model": "sonar",
                                "messages": [{"role": "user", "content": analysis_prompt}],
                                "max_tokens": 2000
                            },
                            headers={
                                "Authorization": f"Bearer {key}",
                                "Content-Type": "application/json"
                            }
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            perplexity_analysis = data["choices"][0]["message"]["content"]
                            print(f"✅ Perplexity Agent ответил ({len(perplexity_analysis)} символов)")
                            break
                
                except Exception as e:
                    print(f"❌ Perplexity Agent #{idx + 1} error: {e}")
        
        # Сохранение результатов
        results = {
            "timestamp": datetime.now().isoformat(),
            "diagnostic_context": {
                **diagnostic_context,
                "key_health_details": {
                    service: {
                        str(k): {
                            **v,
                            "last_check": datetime.fromtimestamp(v["last_check"]).isoformat() if "last_check" in v else None
                        }
                        for k, v in keys.items()
                    }
                    for service, keys in self.key_health.items()
                }
            },
            "deepseek_analysis": deepseek_analysis,
            "perplexity_analysis": perplexity_analysis
        }
        
        # Сохраняем в файл
        output_file = f"ai_audit_results/diagnostic_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        Path("ai_audit_results").mkdir(exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Результаты сохранены: {output_file}")
        
        # Вывод аналитики
        if deepseek_analysis:
            print("\n" + "=" * 80)
            print("🤖 DEEPSEEK AGENT ANALYSIS")
            print("=" * 80)
            print(deepseek_analysis)
        
        if perplexity_analysis:
            print("\n" + "=" * 80)
            print("🤖 PERPLEXITY AGENT ANALYSIS")
            print("=" * 80)
            print(perplexity_analysis)
        
        return results
    
    async def continuous_monitoring(self, interval: int = 300):
        """
        Непрерывный мониторинг в фоне (каждые 5 минут по умолчанию)
        
        Args:
            interval: Интервал проверки в секундах (default: 300 = 5 минут)
        """
        print("\n" + "=" * 80)
        print(f"🔄 ЗАПУСК НЕПРЕРЫВНОГО МОНИТОРИНГА (каждые {interval}s)")
        print("=" * 80)
        
        self.stats["continuous_monitoring_active"] = True
        
        cycle = 0
        
        while self.stats["continuous_monitoring_active"]:
            cycle += 1
            
            print(f"\n⏰ Цикл мониторинга #{cycle} ({datetime.now().strftime('%H:%M:%S')})")
            
            # Быстрая проверка MCP
            mcp_ok = await self.check_mcp_server()
            print(f"   MCP Server: {'✅' if mcp_ok else '⚠️'}")
            
            # Быстрая проверка по одному ключу каждого агента
            deepseek_ok = False
            if self.api_keys["deepseek"]:
                deepseek_ok = await self.test_deepseek_key(
                    self.api_keys["deepseek"][0], 0
                )
            
            perplexity_ok = False
            if self.api_keys["perplexity"]:
                perplexity_ok = await self.test_perplexity_key(
                    self.api_keys["perplexity"][0], 0
                )
            
            print(f"   DeepSeek: {'✅' if deepseek_ok else '⚠️'}")
            print(f"   Perplexity: {'✅' if perplexity_ok else '⚠️'}")
            
            # Каждые 10 циклов - полная диагностика
            if cycle % 10 == 0:
                print("\n🔍 Запуск полной диагностики (каждые 10 циклов)...")
                await self.run_full_diagnostic()
            
            # Ждём следующего цикла
            await asyncio.sleep(interval)
    
    def stop_monitoring(self):
        """Остановка непрерывного мониторинга"""
        self.stats["continuous_monitoring_active"] = False
        print("\n⏹️ Непрерывный мониторинг остановлен")


async def main():
    """Главная функция запуска диагностики"""
    
    print("=" * 80)
    print("🔍 AUTOMATIC SELF-DIAGNOSTIC SYSTEM")
    print("=" * 80)
    print()
    
    # Инициализация системы
    diagnostic = AutoDiagnosticSystem()
    
    # Загрузка API ключей
    diagnostic.load_api_keys_from_config()
    
    # Проверка наличия ключей
    total_keys = len(diagnostic.api_keys["deepseek"]) + len(diagnostic.api_keys["perplexity"])
    
    if total_keys == 0:
        print("\n❌ ОШИБКА: API ключи не найдены!")
        print("   Проверьте backend/core/config.py")
        return
    
    print(f"\n✅ Всего API ключей: {total_keys}")
    print(f"   - DeepSeek: {len(diagnostic.api_keys['deepseek'])}")
    print(f"   - Perplexity: {len(diagnostic.api_keys['perplexity'])}")
    
    # Выполнение полной диагностики
    diagnostic_result = await diagnostic.run_full_diagnostic()
    
    # 🔥 КРИТИЧНО: Запрос аналитики от агентов
    if diagnostic_result["success"]:
        print("\n🔥 КРИТИЧНАЯ ЗАДАЧА: Запрос аналитики от AI агентов...")
        agent_analysis = await diagnostic.request_agent_analysis()
    
    # Опционально: Непрерывный мониторинг
    print("\n" + "=" * 80)
    print("❓ Запустить непрерывный мониторинг в фоне?")
    print("=" * 80)
    print("   [y] Да - запустить непрерывный мониторинг (Ctrl+C для остановки)")
    print("   [n] Нет - завершить диагностику")
    print()
    
    # Для автоматического режима - запускаем мониторинг
    # В интерактивном режиме можно спросить пользователя
    
    # Автоматический запуск мониторинга (закомментируйте, если нужен интерактивный режим)
    print("🔄 Автоматический запуск непрерывного мониторинга...")
    
    try:
        await diagnostic.continuous_monitoring(interval=300)  # 5 минут
    except KeyboardInterrupt:
        print("\n\n⏹️ Мониторинг остановлен пользователем")
        diagnostic.stop_monitoring()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️ Программа остановлена пользователем")
