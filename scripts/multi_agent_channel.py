#!/usr/bin/env python3
"""
Multi-Agent Communication Channel: DeepSeek ↔ Perplexity
Быстрый канал связи для совместной работы AI агентов
"""

import sys
import json
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from dotenv import load_dotenv

# Add parent directory to path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

# Load environment variables so KeyManager can read MASTER_ENCRYPTION_KEY, etc.
load_dotenv(PROJECT_ROOT / ".env")

# API Keys через безопасный KeyManager (зашифрованное хранилище)
from backend.security.key_manager import get_decrypted_key


def load_tz_context(
    directory: Path,
    keywords: Optional[List[str]] = None,
    max_files: int = 6,
    max_chars_per_file: int = 3500,
    max_total_chars: int = 15000,
) -> Tuple[str, List[Path]]:
    """Load relevant TZ documents and return aggregated context + file list."""

    if keywords is None:
        keywords = [
            "техническое",
            "задание",
            "tz",
            "spec",
            "orchestrator",
            "тз",
        ]

    if not directory.exists():
        raise FileNotFoundError(f"📁 Каталог с ТЗ не найден: {directory}")

    candidates: List[Path] = []

    for pattern in ("*.md", "*.txt"):
        for path in sorted(directory.glob(pattern)):
            lower_name = path.name.lower()
            if any(keyword in lower_name for keyword in keywords):
                candidates.append(path)

    # Fallback: возьмём первые md-файлы, если фильтр ничего не нашёл
    if not candidates:
        candidates = sorted(directory.glob("*.md"))[:max_files]

    if not candidates:
        raise ValueError("В каталоге нет Markdown файлов для анализа ТЗ")

    aggregated_parts: List[str] = []
    used_files: List[Path] = []
    total_chars = 0

    for path in candidates:
        if len(used_files) >= max_files:
            break

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="utf-8", errors="ignore")

        snippet = content.strip()
        if not snippet:
            continue

        snippet = snippet[:max_chars_per_file]
        aggregated_parts.append(f"## {path.name}\n\n{snippet}")
        used_files.append(path)
        total_chars += len(snippet)

        if total_chars >= max_total_chars:
            break

    if not aggregated_parts:
        raise ValueError("Не удалось загрузить содержимое ТЗ из каталога")

    aggregated_text = "\n\n---\n\n".join(aggregated_parts)
    if len(aggregated_text) > max_total_chars:
        aggregated_text = aggregated_text[:max_total_chars]

    return aggregated_text, used_files


def load_latest_corrected_spec(tz_corrected_dir: Path, max_chars: int = 18000) -> Tuple[Optional[str], Optional[Path]]:
    """Load the most recent corrected TZ file if available."""

    if not tz_corrected_dir.exists():
        return None, None

    candidates = sorted(tz_corrected_dir.glob("corrected_tz_*.md"))
    if not candidates:
        return None, None

    latest_path = candidates[-1]
    content = latest_path.read_text(encoding="utf-8", errors="ignore")
    return content[:max_chars], latest_path


def summarize_results(results: List[Dict], max_chars: int = 12000) -> str:
    """Create a compact summary of collaboration results for downstream prompts."""

    chunks: List[str] = []
    total = 0

    for result in results:
        if not result.get("success"):
            continue

        agent = result.get("agent", "Unknown")
        timestamp = result.get("timestamp", "")
        content = result.get("content", "")
        entry = f"[{agent} @ {timestamp}]\n{content.strip()}"
        truncated = entry[: max_chars - total]
        if not truncated:
            break
        chunks.append(truncated)
        total += len(truncated)
        if total >= max_chars:
            break

    return "\n\n".join(chunks)

PERPLEXITY_API_KEY = get_decrypted_key("PERPLEXITY_API_KEY")
DEEPSEEK_API_KEY = get_decrypted_key("DEEPSEEK_API_KEY")

class MultiAgentChannel:
    """Канал связи между DeepSeek и Perplexity"""
    
    def __init__(self):
        self.conversation_history = []
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def deepseek_call(self, prompt: str, context: Optional[str] = None) -> Dict:
        """Вызов DeepSeek с контекстом"""
        messages = [
            {
                "role": "system",
                "content": "Ты технический эксперт по архитектуре и кодогенерации. Работаешь в команде с Perplexity AI."
            }
        ]
        
        if context:
            prompt = (
                f"КОНТЕКСТ:\n{context}\n\n---\n\n"
                f"ЗАДАНИЕ:\n{prompt}"
            )
        
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 4000
        }
        
        try:
            response = requests.post(
                "https://api.deepseek.com/chat/completions",
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=60
            )
        except requests.RequestException as exc:
            return {
                "success": False,
                "error": f"DeepSeek request failed: {exc}",
                "agent": "DeepSeek"
            }
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            return {
                "success": True,
                "content": content,
                "agent": "DeepSeek",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "success": False,
                "error": f"DeepSeek error {response.status_code}: {response.text}",
                "agent": "DeepSeek"
            }
    
    def perplexity_call(self, prompt: str, context: Optional[str] = None) -> Dict:
        """Вызов Perplexity с контекстом"""
        messages = [
            {
                "role": "system",
                "content": "Ты стратегический эксперт по бизнес-анализу и приоритизации. Работаешь в команде с DeepSeek."
            }
        ]
        
        if context:
            prompt = (
                f"КОНТЕКСТ:\n{context}\n\n---\n\n"
                f"ЗАДАНИЕ:\n{prompt}"
            )
        
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        payload = {
            "model": "sonar-pro",
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 4000
        }
        
        try:
            response = requests.post(
                "https://api.perplexity.ai/chat/completions",
                headers={
                    "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=60
            )
        except requests.RequestException as exc:
            return {
                "success": False,
                "error": f"Perplexity request failed: {exc}",
                "agent": "Perplexity"
            }
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            citations = result.get('citations', [])
            return {
                "success": True,
                "content": content,
                "citations": citations,
                "agent": "Perplexity",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "success": False,
                "error": f"Perplexity error {response.status_code}: {response.text}",
                "agent": "Perplexity"
            }
    
    def collaborative_analysis(
        self,
        topic: str,
        deepseek_task: str,
        perplexity_task: str,
        iterations: int = 2,
        shared_context: Optional[str] = None,
    ) -> List[Dict]:
        """
        Совместный анализ с обменом контекстом
        
        Args:
            topic: Тема анализа
            deepseek_task: Задача для DeepSeek
            perplexity_task: Задача для Perplexity
            iterations: Количество итераций обмена
        """
        results = []
        
        print("=" * 80)
        print(f"COLLABORATIVE ANALYSIS: {topic}")
        print("=" * 80)
        print()
        
        # Итерация 1: Параллельный анализ
        print("🔄 ITERATION 1: Параллельный анализ")
        print()
        
        print("📤 DeepSeek: Технический анализ...")
        deepseek_result = self.deepseek_call(deepseek_task, context=shared_context)
        results.append(deepseek_result)
        
        if deepseek_result["success"]:
            print(f"✅ DeepSeek готов ({len(deepseek_result['content'])} chars)")
        else:
            print(f"❌ DeepSeek failed: {deepseek_result.get('error')}")
            return results
        
        print()
        print("📤 Perplexity: Стратегический анализ...")
        perplexity_result = self.perplexity_call(perplexity_task, context=shared_context)
        results.append(perplexity_result)
        
        if perplexity_result["success"]:
            print(f"✅ Perplexity готов ({len(perplexity_result['content'])} chars)")
            print(f"📚 Citations: {len(perplexity_result.get('citations', []))}")
        else:
            print(f"❌ Perplexity failed: {perplexity_result.get('error')}")
            return results
        
        # Итерация 2+: Обмен контекстом
        for i in range(2, iterations + 1):
            print()
            print(f"🔄 ITERATION {i}: Обмен контекстом и уточнения")
            print()
            
            # DeepSeek анализирует выводы Perplexity
            deepseek_followup = f"""Проанализируй стратегические рекомендации Perplexity и дай технические уточнения:

ЗАДАЧА: {deepseek_task}

Что добавить/изменить в техническом плане на основе стратегии?"""
            
            print("📤 DeepSeek: Технические уточнения на основе стратегии Perplexity...")
            deepseek_result = self.deepseek_call(
                deepseek_followup,
                context=perplexity_result["content"][:2000]  # Первые 2000 символов
            )
            results.append(deepseek_result)
            
            if deepseek_result["success"]:
                print(f"✅ DeepSeek готов ({len(deepseek_result['content'])} chars)")
            else:
                print(f"❌ DeepSeek failed: {deepseek_result.get('error')}")
                break
            
            print()
            
            # Perplexity анализирует технические детали DeepSeek
            perplexity_followup = f"""На основе технического анализа DeepSeek дай стратегические рекомендации:

ЗАДАЧА: {perplexity_task}

Как приоритизировать реализацию? Какие риски?"""
            
            print("📤 Perplexity: Стратегические уточнения на основе технического анализа...")
            perplexity_result = self.perplexity_call(
                perplexity_followup,
                context=deepseek_result["content"][:2000]
            )
            results.append(perplexity_result)
            
            if perplexity_result["success"]:
                print(f"✅ Perplexity готов ({len(perplexity_result['content'])} chars)")
            else:
                print(f"❌ Perplexity failed: {perplexity_result.get('error')}")
                break
        
        return results
    
    def save_session(self, results: List[Dict], filename: str):
        """Сохранение сессии совместной работы"""
        report = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "results": results
        }
        
        output_path = Path(filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        # Создаём также markdown версию
        md_path = output_path.with_suffix('.md')
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(f"# Multi-Agent Collaboration Session\n\n")
            f.write(f"**Session ID:** {self.session_id}\n")
            f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")
            
            for i, result in enumerate(results, 1):
                if not result.get("success"):
                    continue
                    
                agent = result.get("agent", "Unknown")
                content = result.get("content", "")
                timestamp = result.get("timestamp", "")
                
                f.write(f"## {i}. {agent} ({timestamp})\n\n")
                f.write(content)
                f.write("\n\n")
                
                if "citations" in result and result["citations"]:
                    f.write("### Citations\n\n")
                    for j, citation in enumerate(result["citations"], 1):
                        f.write(f"{j}. {citation}\n")
                    f.write("\n")
                
                f.write("---\n\n")
        
        return md_path

    def generate_corrected_spec(
        self,
        tz_context: str,
        collaboration_summary: str,
        focus_notes: Optional[str] = None,
    ) -> Dict:
        """Сформировать обновлённое ТЗ на основе контекста и совместного анализа."""

        guidance = focus_notes or (
            "Сконцентрируйся на функционале, который уже реализован в проекте, "
            "учти улучшения Knowledge Base, Sandbox, MCP оркестратора, и AI-интеграций."
        )

        prompt = f"""Ты главный архитект и технический писатель. На основе нескольких версий ТЗ и результатов 
совместного анализа DeepSeek ↔ Perplexity нужно создать единое обновлённое техническое задание.

ТРЕБОВАНИЯ:
- учитывай, что проект уже продвинулся дальше первоначальных идей;
- явно фиксируй реализованные улучшения (multi-agent оркестр, sandbox, knowledge base, MCP);
- сохрани структуру: 1) Обзор, 2) Архитектура, 3) Функциональные требования, 4) Нефункциональные требования, 5) План тестирования, 6) Метрики успеха;
- пометь блоки статусами (ГОТОВО, В ПРОЦЕССЕ, ПЛАН) и ссылками на соответствующие подсистемы.

ВХОДНЫЕ ДАННЫЕ (сначала оригинальные ТЗ, затем аналитика):

<Оригинальные ТЗ>
{tz_context}

<Аналитика агентов>
{collaboration_summary}

{guidance}

СФОРМИРУЙ обновлённое ТЗ в Markdown с оглавлением, списками задач, и чёткими приоритетами.
"""

        return self.deepseek_call(prompt)

    def save_corrected_spec(self, content: str, output_dir: Path) -> Path:
        """Сохранить откорректированное ТЗ в отдельную директорию."""

        output_dir.mkdir(parents=True, exist_ok=True)
        spec_path = output_dir / f"corrected_tz_{self.session_id}.md"
        with open(spec_path, "w", encoding="utf-8") as f:
            f.write(content)
        return spec_path

    def comparative_review(
        self,
        previous_spec: Optional[str],
        new_spec: Optional[str],
        previous_session_summary: str,
    ) -> List[Dict]:
        """Run a comparative review loop so agents can self-evaluate progress."""

        if not previous_spec or not new_spec:
            return []

        comparison_results: List[Dict] = []

        perplexity_prompt = f"""Сравни две версии технического задания.

<Предыдущая версия>
{previous_spec[:8000]}

<Новая версия>
{new_spec[:8000]}

Требуется:
1. Выявить ключевые улучшения и что всё ещё требует доработки.
2. Оценить качество структуры, KPI, планов и насколько новая версия согласована с реальным прогрессом.
3. Подготовить список метрик/экспериментов, которые подтвердят улучшения (self-learning signals).
"""

        print()
        print("📊 Perplexity: Сравнительный анализ версий ТЗ...")
        perplexity_analysis = self.perplexity_call(perplexity_prompt)
        comparison_results.append(perplexity_analysis)

        deepseek_prompt = f"""Ты технический архитектор. На основе отчёта Perplexity и истории предыдущей сессии предложи план самоусовершенствования.

<Выводы Perplexity>
{perplexity_analysis.get('content', '')[:6000]}

<Резюме предыдущей сессии>
{previous_session_summary[:6000]}

Требуется:
1. Кратко сформулировать дельты (что улучшилось, что нет).
2. Составить roadmap из 5-7 задач self-improvement (автоматизируемых агентами).
3. Указать, какие данные/модули нужно дополнительно подключить в следующий прогон.
"""

        if perplexity_analysis.get("success"):
            print("🧠 DeepSeek: План самоусовершенствования...")
            deepseek_follow = self.deepseek_call(deepseek_prompt)
            comparison_results.append(deepseek_follow)

        return comparison_results


def main():
    """Тестирование канала связи"""
    
    print("=" * 80)
    print("MULTI-AGENT COMMUNICATION CHANNEL TEST")
    print("=" * 80)
    print()
    tz_directory = PROJECT_ROOT / "ai_audit_results"
    tz_context, tz_files = load_tz_context(tz_directory)
    tz_corrected_dir = tz_directory / "tz_corrected"
    previous_spec_text, previous_spec_path = load_latest_corrected_spec(tz_corrected_dir)
    print("📄 Загрузили ТЗ файлы:")
    for path in tz_files:
        print(f"   • {path.name}")
    print()

    shared_context = "Сводка ключевых ТЗ (укороченные версии):\n" + tz_context
    if previous_spec_text and previous_spec_path:
        shared_context += (
            "\n\n<Последняя версия ТЗ>\n"
            f"Файл: {previous_spec_path.name}\n\n{previous_spec_text[:8000]}"
        )

    channel = MultiAgentChannel()

    deepseek_task = """Проанализируй все версии ТЗ и текущее состояние проекта.
1. Определи, какие модули уже реализованы и какие улучшения по сравнению с исходными ТЗ критично зафиксировать.
2. Укажи технические долги и зависимости (MCP ↔ Sandbox ↔ Knowledge Base ↔ Unified Agent Interface).
3. Сформируй рекомендацию по структурным изменениям в ТЗ (что нужно переписать, объединить, удалить)."""

    perplexity_task = """Сфокусируйся на стратегической части актуализированного ТЗ.
1. Сравни версии ТЗ и выбери наиболее зрелые блоки.
2. Определи, какие функции уже превосходят начальные идеи (например, multi-agent orchestration, caching, sandbox, kb).
3. Составь план обновления ТЗ: какие разделы расширить, какие KPI и метрики добавить."""

    results = channel.collaborative_analysis(
        topic="TZ Modernization",
        deepseek_task=deepseek_task,
        perplexity_task=perplexity_task,
        iterations=2,
        shared_context=shared_context,
    )

    collaboration_summary = summarize_results(results)

    print()
    print("=" * 80)
    print("ФОРМИРОВАНИЕ ОБНОВЛЁННОГО ТЗ")
    print("=" * 80)
    print()

    spec_result = channel.generate_corrected_spec(tz_context, collaboration_summary)
    results.append(spec_result)

    tz_output_dir = tz_directory / "tz_corrected"
    if spec_result.get("success"):
        spec_path = channel.save_corrected_spec(spec_result["content"], tz_output_dir)
        print(f"✅ Обновлённое ТЗ сохранено: {spec_path}")
    else:
        print(f"❌ Не удалось сформировать обновлённое ТЗ: {spec_result.get('error')}")

    # Comparative self-improvement stage
    new_spec_text = spec_result.get("content") if spec_result.get("success") else None
    comparison_stage = channel.comparative_review(
        previous_spec=previous_spec_text,
        new_spec=new_spec_text,
        previous_session_summary=collaboration_summary,
    )
    results.extend(comparison_stage)

    print()
    print("=" * 80)
    print("СОХРАНЕНИЕ РЕЗУЛЬТАТОВ")
    print("=" * 80)
    print()

    md_path = channel.save_session(results, "multi_agent_session.json")
    print(f"✅ JSON сохранён: multi_agent_session.json")
    print(f"✅ Markdown сохранён: {md_path}")
    print()

    # Статистика
    success_count = sum(1 for r in results if r.get("success"))
    total_count = len(results)

    print("=" * 80)
    print("СТАТИСТИКА")
    print("=" * 80)
    print(f"Всего запросов: {total_count}")
    print(f"Успешных: {success_count}")
    print(f"Провалено: {total_count - success_count}")
    if total_count:
        print(f"Success Rate: {success_count / total_count * 100:.1f}%")
    print("=" * 80)


if __name__ == "__main__":
    main()
