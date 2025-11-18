"""
Project Context Model for Enhanced Agent Awareness

Provides agents with comprehensive project metadata including:
- Directory structure
- Dependencies
- Test coverage statistics
- Code quality metrics
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ProjectContext:
    """
    Comprehensive project context for AI agents
    
    Enables agents to understand:
    - Project architecture
    - Code organization
    - Quality metrics
    - Test coverage
    """
    
    # Project structure
    root_path: Path
    structure: dict[str, list[str]] = field(default_factory=dict)
    
    # Dependencies
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    
    # Test coverage
    test_coverage: dict[str, float] = field(default_factory=dict)
    
    # Code quality metrics
    code_quality_metrics: dict[str, Any] = field(default_factory=dict)
    
    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_project_root(cls, root_path: Path) -> "ProjectContext":
        """Build ProjectContext by analyzing project directory"""
        context = cls(root_path=root_path)
        
        # Analyze structure
        context.structure = context._analyze_structure()
        
        # Parse dependencies
        context.dependencies = context._parse_dependencies()
        
        # Load test coverage (if available)
        context.test_coverage = context._load_test_coverage()
        
        # Load code quality metrics (if available)
        context.code_quality_metrics = context._load_code_quality()
        
        # Populate metadata
        context.metadata = context._gather_metadata()
        
        return context
    
    def _analyze_structure(self) -> dict[str, list[str]]:
        """Analyze project directory structure"""
        structure = {
            "backend": [],
            "frontend": [],
            "tests": [],
            "docs": [],
            "scripts": [],
            "other": []
        }
        
        try:
            for category in structure:
                category_path = self.root_path / category
                if category_path.exists() and category_path.is_dir():
                    # List subdirectories
                    structure[category] = [
                        str(p.relative_to(category_path))
                        for p in category_path.iterdir()
                        if p.is_dir() and not p.name.startswith('.')
                    ]
        except Exception as e:
            structure["_error"] = str(e)
        
        return structure
    
    def _parse_dependencies(self) -> dict[str, list[str]]:
        """Parse project dependencies from requirements files"""
        dependencies = {
            "backend": [],
            "frontend": [],
            "dev": []
        }
        
        # Backend dependencies
        backend_req = self.root_path / "backend" / "requirements.txt"
        if backend_req.exists():
            try:
                with open(backend_req, encoding='utf-8') as f:
                    dependencies["backend"] = [
                        line.strip().split('==')[0]
                        for line in f
                        if line.strip() and not line.startswith('#')
                    ]
            except Exception:
                pass
        
        # Dev dependencies
        dev_req = self.root_path / "requirements-dev.txt"
        if dev_req.exists():
            try:
                with open(dev_req, encoding='utf-8') as f:
                    dependencies["dev"] = [
                        line.strip().split('==')[0]
                        for line in f
                        if line.strip() and not line.startswith('#')
                    ]
            except Exception:
                pass
        
        # Frontend dependencies (package.json)
        package_json = self.root_path / "frontend" / "package.json"
        if package_json.exists():
            try:
                with open(package_json, encoding='utf-8') as f:
                    data = json.load(f)
                    dependencies["frontend"] = list(data.get("dependencies", {}).keys())
            except Exception:
                pass
        
        return dependencies
    
    def _load_test_coverage(self) -> dict[str, float]:
        """Load test coverage statistics from .coverage data"""
        coverage_data = {}
        
        # Try to load from coverage.xml (if exists)
        coverage_xml = self.root_path / "coverage.xml"
        if coverage_xml.exists():
            try:
                # Secure XML parsing: use defusedxml instead of xml.etree (Bandit B314)
                from defusedxml import ElementTree as ET  # type: ignore
                tree = ET.parse(coverage_xml)  # nosec B314 - defusedxml mitigates common XML attacks
                root = tree.getroot()
                
                # Parse coverage by module
                for package in root.findall('.//package'):
                    package_name = package.get('name', 'unknown')
                    line_rate = float(package.get('line-rate', 0))
                    coverage_data[package_name] = round(line_rate * 100, 2)
            except Exception:
                pass
        
        return coverage_data
    
    def _load_code_quality(self) -> dict[str, Any]:
        """Load code quality metrics from various tools"""
        quality = {
            "ruff_issues": None,
            "black_compliant": None,
            "bandit_issues": None
        }
        
        # Try to load Ruff report (if exists)
        ruff_report = self.root_path / "ruff-report.json"
        if ruff_report.exists():
            try:
                with open(ruff_report, encoding='utf-8') as f:
                    data = json.load(f)
                    quality["ruff_issues"] = len(data)
            except Exception:
                pass
        
        # Try to load Bandit report (if exists)
        bandit_report = self.root_path / "bandit-report.json"
        if bandit_report.exists():
            try:
                with open(bandit_report, encoding='utf-8') as f:
                    data = json.load(f)
                    quality["bandit_issues"] = len(data.get("results", []))
            except Exception:
                pass
        
        return quality
    
    def _gather_metadata(self) -> dict[str, Any]:
        """Gather additional project metadata"""
        metadata = {}
        
        # Project name (from directory name)
        metadata["project_name"] = self.root_path.name
        
        # Check for common files
        metadata["has_dockerfile"] = (self.root_path / "Dockerfile").exists()
        metadata["has_docker_compose"] = (self.root_path / "docker-compose.yml").exists()
        metadata["has_ci_cd"] = (self.root_path / ".github" / "workflows").exists()
        metadata["has_tests"] = (self.root_path / "tests").exists()
        
        # Count Python files
        try:
            py_files = list(self.root_path.rglob("*.py"))
            metadata["python_files_count"] = len(py_files)
        except Exception:
            metadata["python_files_count"] = 0
        
        return metadata
    
    def to_dict(self) -> dict[str, Any]:
        """Convert ProjectContext to dictionary for serialization"""
        return {
            "root_path": str(self.root_path),
            "structure": self.structure,
            "dependencies": self.dependencies,
            "test_coverage": self.test_coverage,
            "code_quality_metrics": self.code_quality_metrics,
            "metadata": self.metadata
        }
    
    def to_json(self) -> str:
        """Convert ProjectContext to JSON string"""
        return json.dumps(self.to_dict(), indent=2)
    
    def summary(self) -> str:
        """Generate human-readable summary for agents"""
        lines = [
            f"Project: {self.metadata.get('project_name', 'Unknown')}",
            f"Root: {self.root_path}",
            "",
            "Structure:",
        ]
        
        for category, items in self.structure.items():
            if items and not category.startswith('_'):
                lines.append(f"  {category}: {len(items)} directories")
        
        lines.append("")
        lines.append("Dependencies:")
        for dep_type, deps in self.dependencies.items():
            if deps:
                lines.append(f"  {dep_type}: {len(deps)} packages")
        
        if self.test_coverage:
            lines.append("")
            lines.append("Test Coverage:")
            for module, coverage in list(self.test_coverage.items())[:5]:
                lines.append(f"  {module}: {coverage}%")
        
        lines.append("")
        lines.append("Metadata:")
        lines.append(f"  Python files: {self.metadata.get('python_files_count', 0)}")
        lines.append(f"  Has CI/CD: {self.metadata.get('has_ci_cd', False)}")
        lines.append(f"  Has Docker: {self.metadata.get('has_dockerfile', False)}")
        
        return "\n".join(lines)


def get_project_context() -> ProjectContext:
    """Convenience function to get ProjectContext for current project"""
    # Assume this module is in backend/models/
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent
    return ProjectContext.from_project_root(project_root)
