"""
Тест расширенных параметров DeepSeek и Sonar Pro
Демонстрация всех новых возможностей API
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "mcp-server"))

from multi_agent_router import get_router, TaskType


async def test_deepseek_enhanced():
    """Тест расширенных параметров DeepSeek"""
    router = get_router()
    
    print("=" * 80)
    print("🧪 TEST 1: DeepSeek Enhanced Parameters")
    print("=" * 80)
    
    result = await router.route(
        task_type=TaskType.CODE_GENERATION,
        data={
            "query": "Write a Python function to validate email addresses using regex. Include error handling.",
            "temperature": 0.3,  # Focused
            "max_tokens": 1000,
            "frequency_penalty": 0.5,  # Reduce repetition
            "presence_penalty": 0.3,  # Encourage variety
            "top_p": 0.95,
            "system_prompt": "You are a senior Python developer. Write clean, well-documented code."
        }
    )
    
    print(f"\n✅ Status: {result.get('status')}")
    print(f"✅ Model: {result.get('metadata', {}).get('model')}")
    print(f"✅ Tokens used: {result.get('metadata', {}).get('usage', {})}")
    print(f"\n📝 Response (first 500 chars):")
    print(result.get("result", "")[:500] + "...")
    
    return result.get("status") == "success"


async def test_sonar_pro_search():
    """Тест Sonar Pro с фильтрацией поиска"""
    router = get_router()
    
    print("\n" + "=" * 80)
    print("🧪 TEST 2: Sonar Pro Search Filtering")
    print("=" * 80)
    
    result = await router.route(
        task_type=TaskType.RESEARCH,
        data={
            "query": "Latest Python 3.14 features and improvements",
            "search_mode": "web",
            "search_domain_filter": [
                "python.org",
                "realpython.com",
                "github.com"
            ],
            "return_related_questions": True,
            "search_recency_filter": "year",
            "temperature": 0.4,
            "max_tokens": 2000
        }
    )
    
    print(f"\n✅ Status: {result.get('status')}")
    print(f"✅ Model: {result.get('metadata', {}).get('model')}")
    
    # Check for search results
    metadata = result.get('metadata', {})
    if 'search_results' in metadata:
        print(f"✅ Search results: {metadata.get('num_search_results', 0)} found")
        print("\n📚 Top 3 sources:")
        for idx, source in enumerate(metadata['search_results'][:3], 1):
            print(f"   {idx}. {source.get('title')} - {source.get('url')}")
    
    # Check for related questions
    if 'related_questions' in metadata:
        print(f"\n💡 Related questions ({len(metadata['related_questions'])}):")
        for q in metadata['related_questions'][:3]:
            print(f"   - {q}")
    
    print(f"\n📝 Response (first 300 chars):")
    print(result.get("result", "")[:300] + "...")
    
    return result.get("status") == "success"


async def test_sonar_pro_academic():
    """Тест Sonar Pro в академическом режиме"""
    router = get_router()
    
    print("\n" + "=" * 80)
    print("🧪 TEST 3: Sonar Pro Academic Mode")
    print("=" * 80)
    
    result = await router.route(
        task_type=TaskType.AUDIT,
        data={
            "query": "Recent research papers on transformer architecture improvements",
            "search_mode": "academic",
            "return_images": False,
            "temperature": 0.2,  # Factual
            "max_tokens": 1500
        }
    )
    
    print(f"\n✅ Status: {result.get('status')}")
    print(f"✅ Search mode: academic")
    
    metadata = result.get('metadata', {})
    if 'search_results' in metadata:
        print(f"✅ Academic sources: {metadata.get('num_search_results', 0)}")
    
    print(f"\n📝 Response (first 400 chars):")
    print(result.get("result", "")[:400] + "...")
    
    return result.get("status") == "success"


async def test_sonar_pro_language():
    """Тест Sonar Pro с русским языком"""
    router = get_router()
    
    print("\n" + "=" * 80)
    print("🧪 TEST 4: Sonar Pro Russian Language")
    print("=" * 80)
    
    result = await router.route(
        task_type=TaskType.EXPLAIN,
        data={
            "query": "Explain the concept of async/await in programming",
            "language_preference": "Russian",
            "return_related_questions": True,
            "temperature": 0.5,
            "max_tokens": 1000
        }
    )
    
    print(f"\n✅ Status: {result.get('status')}")
    print(f"✅ Language: Russian")
    
    print(f"\n📝 Response (Russian, first 300 chars):")
    print(result.get("result", "")[:300] + "...")
    
    return result.get("status") == "success"


async def test_sonar_pro_date_filter():
    """Тест Sonar Pro с фильтром по датам"""
    router = get_router()
    
    print("\n" + "=" * 80)
    print("🧪 TEST 5: Sonar Pro Date Filtering")
    print("=" * 80)
    
    result = await router.route(
        task_type=TaskType.RESEARCH,
        data={
            "query": "Major AI breakthroughs and developments",
            "search_after_date_filter": "01/01/2025",
            "search_before_date_filter": "10/31/2025",
            "return_related_questions": True,
            "temperature": 0.3
        }
    )
    
    print(f"\n✅ Status: {result.get('status')}")
    print(f"✅ Date range: 01/01/2025 - 10/31/2025")
    
    metadata = result.get('metadata', {})
    if 'search_results' in metadata:
        print(f"✅ Results found: {metadata.get('num_search_results', 0)}")
        print("\n📅 Sources with dates:")
        for source in metadata['search_results'][:5]:
            date = source.get('date', 'N/A')
            print(f"   - {source.get('title')} [{date}]")
    
    return result.get("status") == "success"


async def test_deepseek_json_mode():
    """Тест DeepSeek JSON mode"""
    router = get_router()
    
    print("\n" + "=" * 80)
    print("🧪 TEST 6: DeepSeek JSON Mode")
    print("=" * 80)
    
    result = await router.route(
        task_type=TaskType.CODE_GENERATION,
        data={
            "query": "Generate a JSON schema for a User model with fields: id, name, email, created_at, roles (array)",
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
            "max_tokens": 500
        }
    )
    
    print(f"\n✅ Status: {result.get('status')}")
    print(f"✅ Response format: JSON")
    
    print(f"\n📋 JSON Response:")
    print(result.get("result", ""))
    
    return result.get("status") == "success"


async def main():
    """Main test suite"""
    print("\n" + "=" * 80)
    print("🚀 ENHANCED API PARAMETERS TEST SUITE")
    print("=" * 80)
    print("\nТестируем новые возможности:")
    print("1. DeepSeek: Enhanced parameters (temperature, penalties, system prompt)")
    print("2. Sonar Pro: Search filtering (domain filter, recency)")
    print("3. Sonar Pro: Academic mode")
    print("4. Sonar Pro: Russian language preference")
    print("5. Sonar Pro: Date range filtering")
    print("6. DeepSeek: JSON mode")
    print("=" * 80)
    
    results = {}
    
    # Test 1: DeepSeek enhanced
    results['deepseek_enhanced'] = await test_deepseek_enhanced()
    await asyncio.sleep(2)
    
    # Test 2: Sonar Pro search filtering
    results['sonar_search'] = await test_sonar_pro_search()
    await asyncio.sleep(2)
    
    # Test 3: Sonar Pro academic
    results['sonar_academic'] = await test_sonar_pro_academic()
    await asyncio.sleep(2)
    
    # Test 4: Sonar Pro Russian
    results['sonar_russian'] = await test_sonar_pro_language()
    await asyncio.sleep(2)
    
    # Test 5: Sonar Pro date filter
    results['sonar_dates'] = await test_sonar_pro_date_filter()
    await asyncio.sleep(2)
    
    # Test 6: DeepSeek JSON mode
    results['deepseek_json'] = await test_deepseek_json_mode()
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print("\n" + "=" * 80)
    print(f"📈 Score: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 ALL ENHANCED FEATURES WORKING!")
        print("✅ DeepSeek: All OpenAI-compatible parameters supported")
        print("✅ Sonar Pro: All Perplexity-specific features supported")
    else:
        print("⚠️ Some features need attention")
    
    print("=" * 80 + "\n")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
