"""
Спросить DeepSeek Agent о проблеме с виртуальными инструментами GitHub Copilot
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.agents.unified_agent_interface import (
    get_agent_interface,
    AgentRequest,
    AgentType,
)
from loguru import logger


async def ask_deepseek_about_virtual_tools():
    """Спросить DeepSeek о решении проблемы с virtual tools"""
    
    interface = get_agent_interface()
    
    prompt = """
# ПРОБЛЕМА С GITHUB COPILOT VIRTUAL TOOLS

## Контекст
GitHub Copilot Chat имеет настройку "Virtual Tools Threshold":
- **Цель**: Группировать похожие инструменты вместе когда их слишком много
- **Порог по умолчанию**: 128 tools
- **Текущая ситуация**: Активировано 133 tools (превышение на 5)
- **Проблема**: "You may experience degraded tool calling once the threshold is hit"

## Описание Virtual Tools
Virtual tools группируют похожие наборы инструментов и активируют их по требованию (on-demand).
Некоторые группы инструментов оптимистично пре-активируются.

## Настройка
```
github.copilot.chat.virtualTools.threshold: 128 (default)
```
Можно установить в 0 для отключения virtual tools.

## Наша ситуация
У нас активировано 133 tools из-за:
1. **MCP Server tools** (~40-50 tools):
   - mcp_bybit-strateg_* (DeepSeek integration)
   - mcp_copilot_conta_* (Container management)
   - pgsql_* (PostgreSQL tools)
   
2. **Standard Copilot tools** (~80 tools):
   - Файловые операции
   - Terminal команды
   - Git operations
   - Python environment
   - Testing tools
   - etc.

## ВОПРОСЫ К DEEPSEEK

### 1. Стратегия решения
Какой подход лучше для превышения порога на 5 tools (133 vs 128)?

**Вариант A**: Увеличить threshold до 150
- Pros: Все tools активны, без группировки
- Cons: Возможна деградация при large context

**Вариант B**: Отключить virtual tools (threshold=0)
- Pros: Нет группировки, все tools всегда доступны
- Cons: Может быть проблема с performance при 133 tools

**Вариант C**: Деактивировать 5+ редко используемых MCP tools
- Pros: Остаёмся в пределах 128
- Cons: Теряем функциональность

**Вариант D**: Оставить как есть (133 active, threshold 128)
- Pros: Все tools доступны
- Cons: Virtual tools будут группировать, возможна деградация

### 2. Архитектурные вопросы
- Как virtual tools влияют на latency tool calling?
- Группируются ли MCP tools автоматически по префиксу (mcp_bybit-strateg_*)?
- Есть ли способ пре-активировать критические tool groups?

### 3. Best Practices
- Какой threshold рекомендуется для проектов с MCP servers?
- Стоит ли разделять tools на несколько MCP servers для снижения count?
- Влияет ли virtual tools на качество ответов AI (degraded reasoning)?

### 4. Performance Impact
- При каком количестве tools virtual grouping становится критичным?
- Есть ли разница между 133 vs 128 tools (5 tools overhead)?
- Можно ли измерить degradation (latency, success rate)?

## ЗАПРОС
Дай детальный анализ:
1. Рекомендуемую стратегию (A/B/C/D или другую)
2. Обоснование с точки зрения performance и usability
3. Пошаговый план реализации выбранной стратегии
4. Возможные риски и как их минимизировать

Отвечай на русском языке с техническими деталями и примерами.
"""

    request = AgentRequest(
        agent_type=AgentType.DEEPSEEK,
        task_type="technical_consultation",
        prompt=prompt,
        context={
            "project": "bybit_strategy_tester_v2",
            "current_tools_count": 133,
            "threshold": 128,
            "mcp_servers": ["bybit-strateg", "copilot-container", "pgsql"],
            "issue": "virtual_tools_threshold_exceeded"
        }
    )
    
    logger.info("📨 Отправка запроса в DeepSeek Agent...")
    logger.info(f"📝 Длина prompt: {len(prompt)} символов")
    
    response = await interface.send_request(request)
    
    if response.success:
        logger.success(f"✅ DeepSeek ответил за {response.latency_ms:.0f}ms")
        logger.info(f"📊 Channel: {response.channel}, API key: #{response.api_key_index}")
        logger.info("="*80)
        logger.info("📄 ОТВЕТ DEEPSEEK:")
        logger.info("="*80)
        print(response.content)
        logger.info("="*80)
        
        # Save to file
        output_file = Path(__file__).parent / "DEEPSEEK_VIRTUAL_TOOLS_SOLUTION.md"
        output_file.write_text(response.content, encoding="utf-8")
        logger.success(f"💾 Ответ сохранён в: {output_file}")
        
        return True
    else:
        logger.error(f"❌ DeepSeek не смог ответить: {response.error}")
        return False


if __name__ == "__main__":
    logger.info("🚀 Запуск консультации с DeepSeek Agent...")
    logger.info("❓ Вопрос: Как обойти ограничение Virtual Tools Threshold (133 vs 128)?")
    logger.info("")
    
    result = asyncio.run(ask_deepseek_about_virtual_tools())
    
    if result:
        logger.success("✅ Консультация завершена успешно!")
    else:
        logger.error("❌ Не удалось получить ответ от DeepSeek")
        sys.exit(1)
