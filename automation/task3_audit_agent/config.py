"""
Конфигурация аудит-агента
"""

import os
from pathlib import Path
from typing import List


class AuditConfig:
    """Конфигурация аудит-агента"""
    
    def __init__(self):
        # Основные настройки
        self.project_root = Path(__file__).parent.parent.parent
        self.check_interval = 5  # минут
        
        # Создаём директорию logs если её нет
        self.logs_dir = self.project_root / "logs"
        self.logs_dir.mkdir(exist_ok=True)
        
        # Файлы и пути
        self.history_file = self.project_root / "audit_history.json"
        self.log_file = self.logs_dir / "audit_agent.log"
        self.audit_script = self.project_root / "full_ai_audit_deepseek_perplexity_deepseek.py"
        
        # Пороги и условия
        self.coverage_threshold = 80.0  # процент
        
        # Паттерны файлов маркеров
        self.marker_patterns = [
            "*_COMPLETE.md",
            "*_COMPLETION_REPORT.md",
            "PHASE_*.md", 
            "MILESTONE_*.md",
            "TASK*_COMPLETION_REPORT.md"
        ]
        
        # Настройки Git
        self.git_monitoring_enabled = True
        
        # Настройки мониторинга
        self.enable_file_monitoring = True
        self.enable_periodic_checks = True
        
        # Валидация конфигурации
        self._validate_config()
    
    def _validate_config(self):
        """Валидация конфигурации"""
        if not self.project_root.exists():
            raise ValueError(f"Project root does not exist: {self.project_root}")
        
        if self.check_interval < 1:
            raise ValueError("Check interval must be at least 1 minute")
        
        if not (0 <= self.coverage_threshold <= 100):
            raise ValueError("Coverage threshold must be between 0 and 100")


# Альтернативная конфигурация через переменные окружения
class EnvironmentConfig(AuditConfig):
    """Конфигурация через переменные окружения"""
    
    def __init__(self):
        super().__init__()
        
        # Переопределение настроек из переменных окружения
        project_root = os.getenv('AUDIT_PROJECT_ROOT')
        if project_root:
            self.project_root = Path(project_root)
        
        check_interval = os.getenv('AUDIT_CHECK_INTERVAL')
        if check_interval:
            self.check_interval = int(check_interval)
        
        coverage_threshold = os.getenv('AUDIT_COVERAGE_THRESHOLD')
        if coverage_threshold:
            self.coverage_threshold = float(coverage_threshold)
        
        audit_script = os.getenv('AUDIT_SCRIPT_PATH')
        if audit_script:
            self.audit_script = Path(audit_script)
        
        self._validate_config()
