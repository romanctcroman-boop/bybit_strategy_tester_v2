"""
🔄 Background Diagnostic Service
Фоновый сервис автоматической диагностики

Запускается автоматически при старте IDE и работает непрерывно
"""

import asyncio
import httpx
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import os
import logging
import sys
from typing import Dict, Any

# Fix Windows encoding for emoji
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('diagnostic_service.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Загрузка .env
load_dotenv()


class BackgroundDiagnosticService:
    """Фоновый сервис непрерывной диагностики"""
    
    def __init__(self):
        self.keys = {"deepseek": [], "perplexity": []}
        self.stats = {
            "total_cycles": 0,
            "mcp_checks": 0,
            "mcp_available": 0,
            "deepseek_checks": 0,
            "deepseek_working": 0,
            "perplexity_checks": 0,
            "perplexity_working": 0,
            "last_agent_analysis": None
        }
        self.running = False
        self.cycle_interval = 60  # Проверка каждую минуту
        self.analysis_interval = 1800  # Анализ агентов каждые 30 минут
    
    async def load_api_keys(self):
        """Загрузка всех API ключей"""
        logger.info("📦 Загрузка API ключей...")
        
        # DeepSeek keys: основной + _1 до _7 (всего 8)
        base_key = os.getenv("DEEPSEEK_API_KEY")
        if base_key:
            self.keys["deepseek"].append(base_key)
        
        for i in range(1, 8):  # _1 до _7
            key = os.getenv(f"DEEPSEEK_API_KEY_{i}")
            if key:
                self.keys["deepseek"].append(key)
        
        # Perplexity keys: основной + _1 до _3 (всего 4)
        base_key = os.getenv("PERPLEXITY_API_KEY")
        if base_key:
            self.keys["perplexity"].append(base_key)
        
        for i in range(1, 4):  # _1 до _3
            key = os.getenv(f"PERPLEXITY_API_KEY_{i}")
            if key:
                self.keys["perplexity"].append(key)
        
        logger.info(f"✅ DeepSeek: {len(self.keys['deepseek'])} ключей")
        logger.info(f"✅ Perplexity: {len(self.keys['perplexity'])} ключей")
    
    async def check_mcp_server(self) -> bool:
        """Проверка MCP Server через /mcp/health (HTTP 200 ожидается)"""
        self.stats["mcp_checks"] += 1
        
        try:
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=False) as client:
                response = await client.get("http://127.0.0.1:8000/mcp/health")

                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") in ("healthy", "degraded") and data.get("tool_count", 0) >= 1:
                        self.stats["mcp_available"] += 1
                        return True
        except:
            pass
        
        return False
    
    async def quick_test_api(self, url: str, key: str, model: str, service: str) -> bool:
        """Быстрый тест API ключа"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 10
                    },
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    if service == "deepseek":
                        self.stats["deepseek_working"] += 1
                    else:
                        self.stats["perplexity_working"] += 1
                    return True
        except:
            pass
        
        return False
    
    async def diagnostic_cycle(self):
        """Один цикл диагностики (быстрая проверка)"""
        self.stats["total_cycles"] += 1
        cycle = self.stats["total_cycles"]
        
        logger.info(f"🔄 Цикл #{cycle} начат")
        
        # Проверка MCP Server
        mcp_ok = await self.check_mcp_server()
        mcp_status = "✅" if mcp_ok else "⚠️"
        
        # Быстрая проверка первого ключа каждого сервиса
        deepseek_ok = False
        if self.keys["deepseek"]:
            self.stats["deepseek_checks"] += 1
            deepseek_ok = await self.quick_test_api(
                "https://api.deepseek.com/v1/chat/completions",
                self.keys["deepseek"][0],
                "deepseek-chat",
                "deepseek"
            )
        
        perplexity_ok = False
        if self.keys["perplexity"]:
            self.stats["perplexity_checks"] += 1
            perplexity_ok = await self.quick_test_api(
                "https://api.perplexity.ai/chat/completions",
                self.keys["perplexity"][0],
                "sonar",
                "perplexity"
            )
        
        deepseek_status = "✅" if deepseek_ok else "⚠️"
        perplexity_status = "✅" if perplexity_ok else "⚠️"
        
        logger.info(f"   MCP: {mcp_status} | DeepSeek: {deepseek_status} | Perplexity: {perplexity_status}")
        
        # Сохранение статуса в файл
        self.save_status()
    
    async def request_agent_analysis(self):
        """Запрос детального анализа от агентов (раз в 10 минут)"""
        logger.info("🧠 Запрос аналитики от агентов...")
        
        analysis_prompt = f"""
# Автоматический мониторинг системы (Цикл #{self.stats['total_cycles']})

## Текущая статистика

- **Всего циклов проверки:** {self.stats['total_cycles']}
- **MCP Server:** {self.stats['mcp_available']}/{self.stats['mcp_checks']} доступен ({self.stats['mcp_available']/max(self.stats['mcp_checks'], 1)*100:.1f}%)
- **DeepSeek:** {self.stats['deepseek_working']}/{self.stats['deepseek_checks']} работают ({self.stats['deepseek_working']/max(self.stats['deepseek_checks'], 1)*100:.1f}%)
- **Perplexity:** {self.stats['perplexity_working']}/{self.stats['perplexity_checks']} работают ({self.stats['perplexity_working']/max(self.stats['perplexity_checks'], 1)*100:.1f}%)

## Задача

Проанализируй текущее состояние системы и дай:
1. Общую оценку стабильности (0-100%)
2. Критичные проблемы (если есть)
3. Рекомендации по улучшению
"""
        
        analysis = {}
        
        # DeepSeek
        if self.keys["deepseek"]:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        "https://api.deepseek.com/v1/chat/completions",
                        json={
                            "model": "deepseek-chat",
                            "messages": [{"role": "user", "content": analysis_prompt}],
                            "max_tokens": 1000
                        },
                        headers={
                            "Authorization": f"Bearer {self.keys['deepseek'][0]}",
                            "Content-Type": "application/json"
                        }
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        analysis["deepseek"] = data["choices"][0]["message"]["content"]
                        logger.info(f"✅ DeepSeek: {len(analysis['deepseek'])} символов")
            except Exception as e:
                logger.error(f"❌ DeepSeek error: {e}")
        
        # Perplexity
        if self.keys["perplexity"]:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        "https://api.perplexity.ai/chat/completions",
                        json={
                            "model": "sonar",
                            "messages": [{"role": "user", "content": analysis_prompt}],
                            "max_tokens": 800
                        },
                        headers={
                            "Authorization": f"Bearer {self.keys['perplexity'][0]}",
                            "Content-Type": "application/json"
                        }
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        analysis["perplexity"] = data["choices"][0]["message"]["content"]
                        logger.info(f"✅ Perplexity: {len(analysis['perplexity'])} символов")
            except Exception as e:
                logger.error(f"❌ Perplexity error: {e}")
        
        if analysis:
            self.stats["last_agent_analysis"] = datetime.now().isoformat()
            
            # Сохранение анализа
            analysis_file = f"ai_audit_results/background_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            Path("ai_audit_results").mkdir(exist_ok=True)
            
            with open(analysis_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "stats": self.stats.copy(),
                    "analysis": analysis
                }, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Анализ сохранён: {analysis_file}")
    
    async def wait_for_agents_idle(self) -> bool:
        """Ожидание завершения работы агентов (если они заняты)"""
        agent_lock_files = [
            Path("logs/deepseek_agent.lock"),
            Path("logs/perplexity_agent.lock")
        ]
        
        max_wait = 300  # Максимум 5 минут
        waited = 0
        
        while waited < max_wait:
            # Проверяем все lock-файлы
            all_idle = True
            busy_agents = []
            
            for lock_file in agent_lock_files:
                if lock_file.exists():
                    all_idle = False
                    busy_agents.append(lock_file.stem)
            
            if all_idle:
                return True
            
            # Агенты заняты - ждём
            logger.info(f"⏳ Агенты заняты ({', '.join(busy_agents)}), ждём...")
            await asyncio.sleep(10)  # Проверяем каждые 10 секунд
            waited += 10
        
        logger.warning("⚠️ Агенты не освободились за 5 минут, продолжаем диагностику")
        return False
    
    def save_status(self):
        """Сохранение текущего статуса"""
        status_file = "diagnostic_status.json"
        
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "stats": self.stats,
                "uptime_seconds": self.stats["total_cycles"] * self.cycle_interval
            }, f, indent=2)
    
    async def run(self):
        """Главный цикл работы сервиса"""
        logger.info("=" * 80)
        logger.info("🚀 BACKGROUND DIAGNOSTIC SERVICE STARTING")
        logger.info("=" * 80)
        
        # Загрузка ключей
        await self.load_api_keys()
        
        if not self.keys["deepseek"] and not self.keys["perplexity"]:
            logger.error("❌ Нет API ключей! Проверьте .env файл")
            return
        
        # Задержка для запуска MCP Server
        logger.info("⏳ Ожидание запуска MCP Server и других сервисов (5s)...")
        await asyncio.sleep(5)
        
        self.running = True
        logger.info(f"✅ Сервис запущен (проверка каждые {self.cycle_interval}s)")
        logger.info(f"📊 Анализ агентов каждые {self.analysis_interval // 60} минут")
        
        cycle_count = 0
        
        try:
            while self.running:
                # Диагностический цикл
                await self.diagnostic_cycle()
                
                cycle_count += 1
                
                # Запрос аналитики от агентов каждые 30 циклов (30 минут)
                if cycle_count % 30 == 0:
                    logger.info("🧠 Запрос детальной аналитики от AI агентов...")
                    await self.request_agent_analysis()
                
                # Ожидание следующего цикла
                await asyncio.sleep(self.cycle_interval)
        
        except KeyboardInterrupt:
            logger.info("\n⏹️ Остановка сервиса...")
        
        except Exception as e:
            logger.error(f"❌ Ошибка сервиса: {e}")
        
        finally:
            self.running = False
            logger.info("✅ Сервис остановлен")
    
    def stop(self):
        """Остановка сервиса"""
        self.running = False


async def main():
    service = BackgroundDiagnosticService()
    await service.run()


if __name__ == "__main__":
    asyncio.run(main())
