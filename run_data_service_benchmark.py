"""
🧪 RUN DATA SERVICE ASYNC PRODUCTION BENCHMARK
==============================================

Запуск встроенных бенчмарков для валидации производительности
"""

import sys
import asyncio
from pathlib import Path

# Добавить путь к optimizations_output
sys.path.insert(0, str(Path(__file__).parent / "optimizations_output"))

# Импортировать production версию (убрать markdown обёртку если есть)
import importlib.util

# Загрузить модуль динамически
spec = importlib.util.spec_from_file_location(
    "data_service_async_production",
    Path(__file__).parent / "optimizations_output" / "data_service_async_PRODUCTION.py"
)

if spec and spec.loader:
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    
    try:
        # Попытка загрузить - может быть markdown обёртка
        spec.loader.exec_module(module)
        
        # Запустить benchmark
        print("=" * 80)
        print("🧪 RUNNING DATA SERVICE ASYNC PRODUCTION BENCHMARK")
        print("=" * 80)
        print()
        
        if hasattr(module, 'benchmark_performance'):
            asyncio.run(module.benchmark_performance())
        else:
            print("❌ benchmark_performance function not found")
            print("⚠️ File may have markdown wrapper - extracting code...")
            
            # Читаем файл и извлекаем код
            file_path = Path(__file__).parent / "optimizations_output" / "data_service_async_PRODUCTION.py"
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Проверяем на markdown обёртку
            if content.startswith("# DATA SERVICE ASYNC") and "```python" in content:
                print("✅ Found markdown wrapper - extracting Python code...")
                
                # Извлечь код между ```python и ```
                import re
                code_match = re.search(r'```python\n(.*?)```', content, re.DOTALL)
                
                if code_match:
                    python_code = code_match.group(1)
                    
                    # Сохранить чистую версию
                    clean_file = Path(__file__).parent / "optimizations_output" / "data_service_async_PRODUCTION_clean.py"
                    with open(clean_file, 'w', encoding='utf-8') as f:
                        f.write(python_code)
                    
                    print(f"✅ Saved clean version: {clean_file}")
                    print("🔄 Re-running with clean version...")
                    
                    # Загрузить чистую версию
                    spec_clean = importlib.util.spec_from_file_location(
                        "data_service_async_clean",
                        clean_file
                    )
                    
                    if spec_clean and spec_clean.loader:
                        module_clean = importlib.util.module_from_spec(spec_clean)
                        spec_clean.loader.exec_module(module_clean)
                        
                        if hasattr(module_clean, 'benchmark_performance'):
                            asyncio.run(module_clean.benchmark_performance())
                        else:
                            print("❌ Still no benchmark_performance found")
                else:
                    print("❌ Could not extract Python code from markdown")
            else:
                print("❌ File format not recognized")
                
    except SyntaxError as e:
        print(f"❌ SyntaxError loading module: {e}")
        print("⚠️ File likely has markdown wrapper - need to extract clean code")
        
        # Читаем файл
        file_path = Path(__file__).parent / "optimizations_output" / "data_service_async_PRODUCTION.py"
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        print(f"\n📄 First 10 lines of file:")
        for i, line in enumerate(lines[:10], 1):
            print(f"{i}: {line.rstrip()}")
        
        print("\n💡 Solution: Remove markdown wrapper manually or run extraction")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
else:
    print("❌ Could not load module spec")
