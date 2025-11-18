"""
Автоматическое обновление всех файлов для использования get_decrypted_key()
Заменяет os.getenv() на безопасный get_decrypted_key() для API ключей
"""

import re
from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path(__file__).parent

# Файлы которые нужно обновить (остальные)
FILES_TO_UPDATE = [
    "test_real_ai_workflow_mtf.py",
    "test_real_ai_workflow.py",
    "test_mcp_conceptual_100.py",
    "test_full_90days_mtf_ai_workflow.py",
    "test_comprehensive_p1.py",
    "run_final_p1_optimizations.py",
    "optimize_batch_async.py",
    "generate_phase3_deployment.py",
    "generate_phase2_integration_tests.py",
    "generate_phase2_fixes.py",
    "conduct_project_audit.py",
    "complete_backtest_vectorization.py",
    "apply_p1_optimizations.py",
    "analyze_project_with_mcp.py",
    "analyze_p1_performance.py",
    "adapt_phase2_tests.py",
    "deepseek_self_diagnostic.py",
    "deepseek_verify_fixes.py",
    "deepseek_verify_complete.py",
    "deepseek_final_assessment.py",
    "deepseek_weaknesses_analysis.py",
    "mcp-server/test_perplexity.py",
    "mcp-server/test_deepseek_api.py",
    "scripts/send_ai_review.py",
    "scripts/send_full_tz_review.py",
    "tests/integration/test_mcp_cyclic_dialogue.py",
    "tests/integration/test_simplified_real.py",
]


def update_file(file_path: Path) -> Tuple[bool, str]:
    """
    Обновить файл для использования get_decrypted_key()
    Returns: (success, message)
    """
    
    if not file_path.exists():
        return False, f"File not found: {file_path}"
    
    try:
        # Читаем файл
        content = file_path.read_text(encoding='utf-8')
        original_content = content
        
        # Проверяем нужно ли обновление
        needs_update = False
        
        # Pattern 1: PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
        if 'PERPLEXITY_API_KEY = os.getenv' in content:
            needs_update = True
        
        # Pattern 2: DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
        if 'DEEPSEEK_API_KEY = os.getenv' in content:
            needs_update = True
        
        if not needs_update:
            return True, f"Already updated (no changes needed)"
        
        # Добавляем импорты если их нет
        if 'from security.key_manager import get_decrypted_key' not in content and \
           'from backend.security.key_manager import get_decrypted_key' not in content:
            
            # Найти где добавить import
            import_added = False
            
            # После load_dotenv()
            if 'load_dotenv()' in content:
                content = content.replace(
                    'load_dotenv()',
                    'load_dotenv()\n\n# Import secure key manager\nimport sys\nfrom pathlib import Path\nproject_root = Path(__file__).parent\nsys.path.insert(0, str(project_root / "backend"))\nfrom security.key_manager import get_decrypted_key'
                )
                import_added = True
            
            # После других импортов
            elif 'import os' in content and not import_added:
                # Найти последний import
                import_lines = []
                lines = content.split('\n')
                last_import_idx = 0
                for i, line in enumerate(lines):
                    if line.strip().startswith('import ') or line.strip().startswith('from '):
                        last_import_idx = i
                
                # Вставить после последнего импорта
                lines.insert(last_import_idx + 1, '\n# Import secure key manager')
                lines.insert(last_import_idx + 2, 'import sys')
                lines.insert(last_import_idx + 3, 'from pathlib import Path')
                lines.insert(last_import_idx + 4, 'project_root = Path(__file__).parent')
                lines.insert(last_import_idx + 5, 'sys.path.insert(0, str(project_root / "backend"))')
                lines.insert(last_import_idx + 6, 'from security.key_manager import get_decrypted_key')
                
                content = '\n'.join(lines)
        
        # Заменяем os.getenv() на get_decrypted_key()
        
        # Pattern 1: PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "default")
        content = re.sub(
            r'PERPLEXITY_API_KEY\s*=\s*os\.getenv\(["\']PERPLEXITY_API_KEY["\'],\s*["\'][^"\']*["\']\)',
            'PERPLEXITY_API_KEY = get_decrypted_key("PERPLEXITY_API_KEY")',
            content
        )
        
        # Pattern 2: PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
        content = re.sub(
            r'PERPLEXITY_API_KEY\s*=\s*os\.getenv\(["\']PERPLEXITY_API_KEY["\']\)',
            'PERPLEXITY_API_KEY = get_decrypted_key("PERPLEXITY_API_KEY")',
            content
        )
        
        # Pattern 3: DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "default")
        content = re.sub(
            r'DEEPSEEK_API_KEY\s*=\s*os\.getenv\(["\']DEEPSEEK_API_KEY["\'],\s*["\'][^"\']*["\']\)',
            'DEEPSEEK_API_KEY = get_decrypted_key("DEEPSEEK_API_KEY")',
            content
        )
        
        # Pattern 4: DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
        content = re.sub(
            r'DEEPSEEK_API_KEY\s*=\s*os\.getenv\(["\']DEEPSEEK_API_KEY["\']\)',
            'DEEPSEEK_API_KEY = get_decrypted_key("DEEPSEEK_API_KEY")',
            content
        )
        
        # Pattern 5: os.getenv('PERPLEXITY_API_KEY', '')
        content = re.sub(
            r"os\.getenv\('PERPLEXITY_API_KEY',\s*''\)",
            'get_decrypted_key("PERPLEXITY_API_KEY")',
            content
        )
        
        if content == original_content:
            return True, "No changes made (patterns not matched)"
        
        # Записываем обратно
        file_path.write_text(content, encoding='utf-8')
        
        return True, f"✅ Updated successfully"
        
    except Exception as e:
        return False, f"❌ Error: {str(e)}"


def main():
    """Обновить все файлы"""
    print("\n" + "="*70)
    print("  🔄 АВТОМАТИЧЕСКОЕ ОБНОВЛЕНИЕ ФАЙЛОВ")
    print("="*70 + "\n")
    
    print(f"Обновление {len(FILES_TO_UPDATE)} файлов...\n")
    
    updated = 0
    skipped = 0
    errors = 0
    
    for file_rel_path in FILES_TO_UPDATE:
        file_path = PROJECT_ROOT / file_rel_path
        
        success, message = update_file(file_path)
        
        status = "✅" if success else "❌"
        print(f"{status} {file_rel_path}")
        print(f"   {message}\n")
        
        if success:
            if "Updated successfully" in message:
                updated += 1
            else:
                skipped += 1
        else:
            errors += 1
    
    print("="*70)
    print(f"\n📊 Результаты:")
    print(f"   ✅ Обновлено: {updated}")
    print(f"   ⏭️  Пропущено: {skipped}")
    print(f"   ❌ Ошибок: {errors}")
    print(f"\n   Всего обработано: {len(FILES_TO_UPDATE)}")
    print()


if __name__ == "__main__":
    main()
