"""
Security Validator - Static analysis of code before execution
Detects potentially dangerous operations
"""

import ast
import re
from typing import Dict, List, Set
from enum import Enum
import logging

logger = logging.getLogger('sandbox.security')


class SecurityLevel(Enum):
    """Security risk levels"""
    SAFE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class SecurityValidator:
    """
    Static security analysis for code before sandbox execution.
    
    Detects:
    - File system operations
    - Network operations
    - System calls
    - Process spawning
    - Import of dangerous modules
    """
    
    # Dangerous operations patterns
    DANGEROUS_IMPORTS = {
        'os', 'sys', 'subprocess', 'socket', 'urllib', 'requests',
        'shutil', 'pathlib', 'glob', 'tempfile', 'pickle', 'shelve',
        'multiprocessing', 'threading', 'asyncio.subprocess'
    }
    
    DANGEROUS_FUNCTIONS = {
        'eval', 'exec', 'compile', '__import__', 'open', 'input',
        'system', 'popen', 'spawn', 'fork', 'execv', 'execl'
    }
    
    DANGEROUS_ATTRIBUTES = {
        '__dict__', '__class__', '__bases__', '__subclasses__',
        '__code__', '__globals__', '__builtins__'
    }
    
    def __init__(self, strict_mode: bool = True):
        """
        Initialize validator.
        
        Args:
            strict_mode: If True, reject code with any dangerous operations
        """
        self.strict_mode = strict_mode
    
    def validate_code(self, code: str, language: str = 'python') -> Dict:
        """
        Validate code for security issues.
        
        Args:
            code: Code to validate
            language: Programming language
            
        Returns:
            Dict with validation results:
            {
                "safe": bool,
                "security_level": SecurityLevel,
                "issues": List[Dict],
                "score": int (0-100, higher is safer)
            }
        """
        if language.lower() == 'python':
            return self._validate_python(code)
        elif language.lower() in ['javascript', 'typescript']:
            return self._validate_javascript(code)
        else:
            # For unknown languages, do basic pattern matching
            return self._validate_generic(code)
    
    def _validate_python(self, code: str) -> Dict:
        """Validate Python code using AST analysis"""
        issues = []
        max_severity = SecurityLevel.SAFE
        
        try:
            tree = ast.parse(code)
            
            # Analyze AST
            for node in ast.walk(tree):
                # Check imports
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in self.DANGEROUS_IMPORTS:
                            issues.append({
                                'type': 'dangerous_import',
                                'severity': SecurityLevel.HIGH,
                                'module': alias.name,
                                'line': node.lineno,
                                'message': f"Import of dangerous module: {alias.name}"
                            })
                            if SecurityLevel.HIGH.value > max_severity.value:
                                max_severity = SecurityLevel.HIGH
                
                if isinstance(node, ast.ImportFrom):
                    if node.module in self.DANGEROUS_IMPORTS:
                        issues.append({
                            'type': 'dangerous_import',
                            'severity': SecurityLevel.HIGH,
                            'module': node.module,
                            'line': node.lineno,
                            'message': f"Import from dangerous module: {node.module}"
                        })
                        if SecurityLevel.HIGH.value > max_severity.value:
                            max_severity = SecurityLevel.HIGH
                
                # Check function calls
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in self.DANGEROUS_FUNCTIONS:
                            issues.append({
                                'type': 'dangerous_function',
                                'severity': SecurityLevel.CRITICAL,
                                'function': node.func.id,
                                'line': node.lineno,
                                'message': f"Call to dangerous function: {node.func.id}"
                            })
                            if SecurityLevel.CRITICAL.value > max_severity.value:
                                max_severity = SecurityLevel.CRITICAL
                
                # Check attribute access
                if isinstance(node, ast.Attribute):
                    if node.attr in self.DANGEROUS_ATTRIBUTES:
                        issues.append({
                            'type': 'dangerous_attribute',
                            'severity': SecurityLevel.MEDIUM,
                            'attribute': node.attr,
                            'line': node.lineno,
                            'message': f"Access to dangerous attribute: {node.attr}"
                        })
                        if SecurityLevel.MEDIUM.value > max_severity.value:
                            max_severity = SecurityLevel.MEDIUM
            
            # Calculate safety score (0-100)
            score = 100 - (len(issues) * 10) - (max_severity.value * 15)
            score = max(0, min(100, score))
            
            safe = (max_severity.value < SecurityLevel.HIGH.value) if self.strict_mode else (max_severity.value < SecurityLevel.CRITICAL.value)
            
            return {
                'safe': safe,
                'security_level': max_severity,
                'issues': issues,
                'score': score,
                'language': 'python'
            }
            
        except SyntaxError as e:
            logger.warning(f"Syntax error in Python code: {e}")
            return {
                'safe': False,
                'security_level': SecurityLevel.CRITICAL,
                'issues': [{
                    'type': 'syntax_error',
                    'severity': SecurityLevel.CRITICAL,
                    'line': e.lineno,
                    'message': f"Syntax error: {str(e)}"
                }],
                'score': 0,
                'language': 'python'
            }
    
    def _validate_javascript(self, code: str) -> Dict:
        """Validate JavaScript/TypeScript code using regex patterns"""
        issues = []
        max_severity = SecurityLevel.SAFE
        
        # Dangerous patterns in JavaScript
        patterns = [
            (r'\beval\s*\(', 'eval() call', SecurityLevel.CRITICAL),
            (r'\bFunction\s*\(', 'Function() constructor', SecurityLevel.CRITICAL),
            (r'\brequire\s*\(', 'require() import', SecurityLevel.HIGH),
            (r'\bfs\b', 'File system module', SecurityLevel.HIGH),
            (r'\bchild_process\b', 'Child process module', SecurityLevel.CRITICAL),
            (r'\bnet\b', 'Network module', SecurityLevel.HIGH),
            (r'\bhttp\b', 'HTTP module', SecurityLevel.MEDIUM),
        ]
        
        for pattern, description, severity in patterns:
            matches = re.finditer(pattern, code)
            for match in matches:
                line_num = code[:match.start()].count('\n') + 1
                issues.append({
                    'type': 'dangerous_pattern',
                    'severity': severity,
                    'pattern': description,
                    'line': line_num,
                    'message': f"Detected: {description}"
                })
                if severity.value > max_severity.value:
                    max_severity = severity
        
        score = 100 - (len(issues) * 10) - (max_severity.value * 15)
        score = max(0, min(100, score))
        
        safe = max_severity.value < SecurityLevel.HIGH.value if self.strict_mode else max_severity.value < SecurityLevel.CRITICAL.value
        
        return {
            'safe': safe,
            'security_level': max_severity,
            'issues': issues,
            'score': score,
            'language': 'javascript'
        }
    
    def _validate_generic(self, code: str) -> Dict:
        """Generic validation using keyword patterns"""
        dangerous_keywords = [
            'system', 'exec', 'eval', 'shell', 'subprocess',
            'popen', 'spawn', 'fork', 'file', 'open', 'write'
        ]
        
        issues = []
        max_severity = SecurityLevel.SAFE
        
        for keyword in dangerous_keywords:
            if re.search(rf'\b{keyword}\b', code, re.IGNORECASE):
                issues.append({
                    'type': 'dangerous_keyword',
                    'severity': SecurityLevel.MEDIUM,
                    'keyword': keyword,
                    'message': f"Detected dangerous keyword: {keyword}"
                })
                if SecurityLevel.MEDIUM.value > max_severity.value:
                    max_severity = SecurityLevel.MEDIUM
        
        score = 100 - (len(issues) * 20)
        score = max(0, score)
        
        return {
            'safe': len(issues) == 0,
            'security_level': max_severity,
            'issues': issues,
            'score': score,
            'language': 'unknown'
        }
    
    def format_report(self, validation: Dict) -> str:
        """Format validation report as human-readable string"""
        report = []
        report.append(f"Security Analysis Report")
        report.append(f"{'=' * 50}")
        report.append(f"Safe: {'✅ YES' if validation['safe'] else '❌ NO'}")
        report.append(f"Security Level: {validation['security_level'].name}")
        report.append(f"Safety Score: {validation['score']}/100")
        report.append(f"Language: {validation['language']}")
        report.append(f"\nIssues Found: {len(validation['issues'])}")
        
        if validation['issues']:
            report.append(f"\nDetailed Issues:")
            for i, issue in enumerate(validation['issues'], 1):
                report.append(f"\n{i}. {issue['message']}")
                report.append(f"   Severity: {issue['severity'].name}")
                if 'line' in issue:
                    report.append(f"   Line: {issue['line']}")
        
        return '\n'.join(report)
