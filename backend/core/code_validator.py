"""
Code Validator для проверки безопасности сгенерированного кода
AST-based analysis для блокировки опасных операций
"""

import ast
import logging
from typing import Dict, List, Tuple, Optional, Set
from enum import Enum

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Уровни риска кода"""
    LOW = "low"           # < 30 points: автоматический запуск
    MEDIUM = "medium"     # 30-70 points: требуется ревью
    HIGH = "high"         # > 70 points: блокировка
    CRITICAL = "critical" # > 90 points: автоматический reject


class ValidationResult:
    """Результат валидации кода"""
    
    def __init__(
        self,
        is_valid: bool,
        risk_score: int,
        risk_level: RiskLevel,
        violations: List[Dict[str, any]],
        warnings: List[str],
        recommendations: List[str]
    ):
        self.is_valid = is_valid
        self.risk_score = risk_score
        self.risk_level = risk_level
        self.violations = violations
        self.warnings = warnings
        self.recommendations = recommendations
    
    def to_dict(self) -> Dict:
        """Сериализация в dict"""
        return {
            "is_valid": self.is_valid,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "violations": self.violations,
            "warnings": self.warnings,
            "recommendations": self.recommendations
        }


class CodeValidator:
    """
    Валидатор кода на основе AST анализа
    
    Проверки:
        - Blacklist модулей/функций (os, subprocess, socket, eval, exec)
        - File I/O операции (open, read, write)
        - Network операции (requests, urllib, socket)
        - Dangerous builtins (eval, exec, compile, __import__)
        - Метод вызовов (getattr, setattr, delattr)
        - Sys/os операции (sys.exit, os.system)
    
    Scoring:
        - Критичные нарушения: +30 points
        - Опасные операции: +15 points
        - Подозрительные паттерны: +5 points
        - Warnings: +1 point
    """
    
    # Blacklist модулей (критично)
    BLACKLIST_MODULES = {
        'os', 'sys', 'subprocess', 'socket', 'urllib', 'urllib2', 'urllib3',
        'requests', 'httpx', 'aiohttp', 'http', 'ftplib', 'smtplib',
        'pickle', 'shelve', 'marshal', 'ctypes', 'multiprocessing',
        'threading', 'asyncio', 'signal', 'pty', 'tty', 'atexit'
    }
    
    # Blacklist builtin функций (критично)
    BLACKLIST_BUILTINS = {
        'eval', 'exec', 'compile', '__import__', 'open', 'input',
        'execfile', 'file', 'reload'
    }
    
    # Опасные атрибуты/методы
    DANGEROUS_ATTRIBUTES = {
        '__dict__', '__class__', '__bases__', '__subclasses__',
        '__globals__', '__code__', '__closure__', '__builtins__'
    }
    
    # Разрешённые модули (whitelist)
    WHITELIST_MODULES = {
        'numpy', 'pandas', 'ta', 'talib', 'datetime', 'math',
        'random', 'json', 'orjson', 'typing', 'enum', 'dataclasses',
        'decimal', 'fractions', 'statistics', 'collections',
        'itertools', 'functools', 'operator', 'time', 'calendar',
        'warnings', 'logging', 'traceback', 're'
    }
    
    def __init__(self):
        self.violations: List[Dict] = []
        self.warnings: List[str] = []
        self.recommendations: List[str] = []
        self.risk_score = 0
    
    def validate(self, code: str) -> ValidationResult:
        """
        Валидация Python кода
        
        Args:
            code: Исходный код для проверки
        
        Returns:
            ValidationResult с деталями проверки
        """
        # Reset state
        self.violations = []
        self.warnings = []
        self.recommendations = []
        self.risk_score = 0
        
        # Проверка пустого кода
        if not code or not code.strip():
            self._add_violation("empty_code", "Empty code provided", 0, critical=False)
            return self._build_result()
        
        # Parse AST
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            self._add_violation(
                "syntax_error",
                f"Syntax error: {str(e)}",
                5,
                lineno=e.lineno,
                critical=False
            )
            return self._build_result()
        
        # Анализ AST
        self._analyze_imports(tree)
        self._analyze_function_calls(tree)
        self._analyze_attributes(tree)
        self._analyze_assignments(tree)
        self._analyze_dangerous_patterns(tree)
        
        return self._build_result()
    
    def _analyze_imports(self, tree: ast.AST):
        """Анализ import statements"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split('.')[0]
                    self._check_module(module_name, node.lineno)
            
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.split('.')[0]
                    self._check_module(module_name, node.lineno)
    
    def _check_module(self, module_name: str, lineno: int):
        """Проверка импорта модуля"""
        if module_name in self.BLACKLIST_MODULES:
            self._add_violation(
                "blacklist_module",
                f"Blacklisted module: {module_name}",
                30,
                lineno=lineno,
                critical=True
            )
        elif module_name not in self.WHITELIST_MODULES:
            self._add_warning(
                f"Unknown module '{module_name}' on line {lineno}. "
                f"May not be available in sandbox."
            )
            self.risk_score += 1
    
    def _analyze_function_calls(self, tree: ast.AST):
        """Анализ вызовов функций"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = self._get_function_name(node.func)
                
                if func_name in self.BLACKLIST_BUILTINS:
                    self._add_violation(
                        "blacklist_builtin",
                        f"Dangerous builtin function: {func_name}",
                        30,
                        lineno=node.lineno,
                        critical=True
                    )
                
                # Проверка file operations
                if func_name in {'open', 'read', 'write'}:
                    self._add_violation(
                        "file_io",
                        f"File I/O operation: {func_name}",
                        30,
                        lineno=node.lineno,
                        critical=True
                    )
                
                # Проверка reflection
                if func_name in {'getattr', 'setattr', 'delattr', 'hasattr'}:
                    self._add_violation(
                        "reflection",
                        f"Reflection operation: {func_name}",
                        15,
                        lineno=node.lineno,
                        critical=False
                    )
    
    def _analyze_attributes(self, tree: ast.AST):
        """Анализ доступа к атрибутам"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                attr_name = node.attr
                
                if attr_name in self.DANGEROUS_ATTRIBUTES:
                    self._add_violation(
                        "dangerous_attribute",
                        f"Dangerous attribute access: {attr_name}",
                        20,
                        lineno=node.lineno,
                        critical=True
                    )
    
    def _analyze_assignments(self, tree: ast.AST):
        """Анализ присваиваний"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                # Проверка переопределения встроенных
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if target.id in self.BLACKLIST_BUILTINS:
                            self._add_violation(
                                "builtin_override",
                                f"Overriding builtin: {target.id}",
                                10,
                                lineno=node.lineno,
                                critical=False
                            )
    
    def _analyze_dangerous_patterns(self, tree: ast.AST):
        """Анализ опасных паттернов"""
        for node in ast.walk(tree):
            # Lambda с exec/eval
            if isinstance(node, ast.Lambda):
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        func_name = self._get_function_name(child.func)
                        if func_name in {'eval', 'exec'}:
                            self._add_violation(
                                "lambda_exec",
                                "Lambda with exec/eval",
                                25,
                                lineno=node.lineno,
                                critical=True
                            )
            
            # Бесконечные циклы (эвристика)
            if isinstance(node, ast.While):
                if isinstance(node.test, ast.Constant) and node.test.value is True:
                    self._add_warning(
                        f"Potential infinite loop on line {node.lineno}"
                    )
                    self.risk_score += 5
    
    def _get_function_name(self, node) -> str:
        """Извлечь имя функции из AST node"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        elif isinstance(node, ast.Call):
            return self._get_function_name(node.func)
        else:
            return ""
    
    def _add_violation(
        self,
        violation_type: str,
        message: str,
        points: int,
        lineno: Optional[int] = None,
        critical: bool = False
    ):
        """Добавить нарушение"""
        self.violations.append({
            "type": violation_type,
            "message": message,
            "points": points,
            "lineno": lineno,
            "critical": critical
        })
        self.risk_score += points
        
        logger.warning(f"Violation: {message} (line {lineno}, +{points} points)")
    
    def _add_warning(self, message: str):
        """Добавить предупреждение"""
        self.warnings.append(message)
        logger.info(f"Warning: {message}")
    
    def _add_recommendation(self, message: str):
        """Добавить рекомендацию"""
        self.recommendations.append(message)
    
    def _build_result(self) -> ValidationResult:
        """Построить ValidationResult"""
        # Определить risk level
        if self.risk_score >= 90:
            risk_level = RiskLevel.CRITICAL
        elif self.risk_score >= 70:
            risk_level = RiskLevel.HIGH
        elif self.risk_score >= 30:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW
        
        # Проверить критичные нарушения
        has_critical = any(v.get("critical", False) for v in self.violations)
        is_valid = not has_critical and risk_level != RiskLevel.CRITICAL
        
        # Добавить рекомендации
        if not is_valid:
            self._add_recommendation(
                "Code contains critical security violations. "
                "Remove blacklisted modules/functions."
            )
        elif risk_level == RiskLevel.HIGH:
            self._add_recommendation(
                "High risk score. Consider manual review before execution."
            )
        elif risk_level == RiskLevel.MEDIUM:
            self._add_recommendation(
                "Medium risk score. Review warnings and consider refactoring."
            )
        
        return ValidationResult(
            is_valid=is_valid,
            risk_score=self.risk_score,
            risk_level=risk_level,
            violations=self.violations,
            warnings=self.warnings,
            recommendations=self.recommendations
        )


# =============================================================================
# Convenience Functions
# =============================================================================

def validate_code(code: str) -> ValidationResult:
    """
    Быстрая валидация кода
    
    Args:
        code: Python код для проверки
    
    Returns:
        ValidationResult
    """
    validator = CodeValidator()
    return validator.validate(code)


def is_code_safe(code: str, max_risk_score: int = 30) -> bool:
    """
    Проверка безопасности кода (простая версия)
    
    Args:
        code: Python код
        max_risk_score: Максимальный допустимый risk score
    
    Returns:
        True если код безопасен
    """
    result = validate_code(code)
    return result.is_valid and result.risk_score <= max_risk_score
