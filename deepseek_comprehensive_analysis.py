"""
Comprehensive DeepSeek Analysis and Testing Script
Aligned with MCP Orchestrator Technical Specifications

This script performs:
1. System architecture analysis (TZ part 1)
2. Security and sandbox analysis (TZ part 2)
3. Multi-agent workflow testing (TZ part 3)
4. Full test suite execution
"""

import asyncio
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import httpx

# Project paths
PROJECT_ROOT = Path(__file__).parent
BACKEND_PATH = PROJECT_ROOT / "backend"
TESTS_PATH = PROJECT_ROOT / "tests"
MCP_SERVER_PATH = PROJECT_ROOT / "mcp-server"

# Analysis results
ANALYSIS_RESULTS = {
    "timestamp": datetime.now().isoformat(),
    "test_execution": {},
    "architecture_compliance": {},
    "security_analysis": {},
    "multi_agent_analysis": {},
    "recommendations": []
}


class MCPArchitectureAnalyzer:
    """Анализатор архитектуры согласно ТЗ MCP-оркестратора часть 1"""
    
    def __init__(self):
        self.results = {
            "protocol_compliance": {},
            "queue_management": {},
            "worker_scaling": {},
            "signal_routing": {}
        }
    
    async def analyze_protocol_compliance(self):
        """1.1 MCP Protocol (JSON-RPC 2.0) - проверка реализации"""
        print("\n🔍 Analyzing MCP Protocol Compliance...")
        
        checks = {
            "json_rpc_2_0": False,
            "fastapi_async": False,
            "typed_messages": False,
            "api_endpoints": {
                "/run_task": False,
                "/status": False,
                "/analytics": False,
                "/inject": False,
                "/control": False
            }
        }
        
        # Check server.py implementation
        server_file = MCP_SERVER_PATH / "server.py"
        if server_file.exists():
            content = server_file.read_text(encoding='utf-8')
            checks["fastapi_async"] = "FastAPI" in content and "async def" in content
            checks["json_rpc_2_0"] = "jsonrpc" in content.lower()
            
            # Check endpoints
            for endpoint in checks["api_endpoints"].keys():
                checks["api_endpoints"][endpoint] = endpoint in content
        
        self.results["protocol_compliance"] = checks
        print(f"✅ Protocol Compliance: {json.dumps(checks, indent=2)}")
        return checks
    
    async def analyze_queue_management(self):
        """2.1 Redis Streams, Consumer Groups"""
        print("\n🔍 Analyzing Queue Management (Redis Streams)...")
        
        checks = {
            "redis_streams": False,
            "consumer_groups": False,
            "priority_queues": False,
            "xpending_recovery": False,
            "checkpointing": False
        }
        
        # Check for Redis usage in backend
        backend_files = list(BACKEND_PATH.rglob("*.py"))
        for file in backend_files:
            try:
                content = file.read_text(encoding='utf-8')
                if "redis" in content.lower():
                    checks["redis_streams"] = "xadd" in content or "stream" in content.lower()
                    checks["consumer_groups"] = "xgroup" in content or "consumer" in content.lower()
                    checks["priority_queues"] = "priority" in content.lower()
                    checks["xpending_recovery"] = "xpending" in content.lower()
            except Exception as e:
                print(f"⚠️ Error reading {file}: {e}")
        
        self.results["queue_management"] = checks
        print(f"✅ Queue Management: {json.dumps(checks, indent=2)}")
        return checks
    
    async def analyze_worker_scaling(self):
        """3.1 Async worker pool + 3.2 SLA-driven autoscaling"""
        print("\n🔍 Analyzing Worker Scaling...")
        
        checks = {
            "async_workers": False,
            "worker_pools": False,
            "dedicated_workers": False,
            "sla_monitoring": False,
            "autoscaling": False
        }
        
        # Check for async worker implementation
        backend_files = list(BACKEND_PATH.rglob("*.py"))
        for file in backend_files:
            try:
                content = file.read_text(encoding='utf-8')
                checks["async_workers"] = checks["async_workers"] or ("async def" in content and "worker" in content.lower())
                checks["worker_pools"] = checks["worker_pools"] or "pool" in content.lower()
                checks["sla_monitoring"] = checks["sla_monitoring"] or ("sla" in content.lower() or "latency" in content.lower())
            except Exception as e:
                pass
        
        self.results["worker_scaling"] = checks
        print(f"✅ Worker Scaling: {json.dumps(checks, indent=2)}")
        return checks
    
    async def analyze_signal_routing(self):
        """4.1 Signal Routing Layer + 4.2 Saga Pattern"""
        print("\n🔍 Analyzing Signal Routing & Saga Pattern...")
        
        checks = {
            "signal_routing": False,
            "preemption": False,
            "saga_orchestration": False,
            "fsm_implementation": False,
            "checkpoint_recovery": False
        }
        
        # Check MCP server routing
        mcp_files = list(MCP_SERVER_PATH.rglob("*.py"))
        for file in mcp_files:
            try:
                content = file.read_text(encoding='utf-8')
                checks["signal_routing"] = checks["signal_routing"] or "route" in content.lower()
                checks["preemption"] = checks["preemption"] or "preempt" in content.lower()
                checks["saga_orchestration"] = checks["saga_orchestration"] or "saga" in content.lower()
                checks["fsm_implementation"] = checks["fsm_implementation"] or "fsm" in content.lower()
                checks["checkpoint_recovery"] = checks["checkpoint_recovery"] or "checkpoint" in content.lower()
            except Exception as e:
                pass
        
        self.results["signal_routing"] = checks
        print(f"✅ Signal Routing: {json.dumps(checks, indent=2)}")
        return checks
    
    async def run_full_analysis(self):
        """Запуск полного анализа архитектуры"""
        print("="*80)
        print("🚀 MCP ARCHITECTURE ANALYSIS - Part 1")
        print("="*80)
        
        await self.analyze_protocol_compliance()
        await self.analyze_queue_management()
        await self.analyze_worker_scaling()
        await self.analyze_signal_routing()
        
        return self.results


class SecuritySandboxAnalyzer:
    """Анализатор безопасности и sandbox согласно ТЗ часть 2"""
    
    def __init__(self):
        self.results = {
            "sandbox_security": {},
            "sla_monitoring": {},
            "incident_management": {},
            "multi_tenancy": {}
        }
    
    async def analyze_sandbox_security(self):
        """5.1 Контейнеризация и многослойная изоляция"""
        print("\n🔍 Analyzing Sandbox Security...")
        
        checks = {
            "docker_isolation": False,
            "network_restrictions": False,
            "resource_limits": False,
            "syscall_audit": False,
            "gvisor_or_firecracker": False
        }
        
        # Check for Docker/sandbox configuration
        docker_files = [
            PROJECT_ROOT / "docker-compose.yml",
            PROJECT_ROOT / "docker" / "Dockerfile",
            PROJECT_ROOT / "Dockerfile"
        ]
        
        for file in docker_files:
            if file.exists():
                try:
                    content = file.read_text(encoding='utf-8')
                    checks["docker_isolation"] = True
                    checks["network_restrictions"] = "network" in content.lower()
                    checks["resource_limits"] = ("mem_limit" in content or "cpus" in content)
                except Exception as e:
                    pass
        
        # Check for sandbox implementation in code
        backend_files = list(BACKEND_PATH.rglob("*.py"))
        for file in backend_files:
            try:
                content = file.read_text(encoding='utf-8')
                if "sandbox" in content.lower():
                    checks["syscall_audit"] = "audit" in content.lower()
                    checks["gvisor_or_firecracker"] = ("gvisor" in content.lower() or "firecracker" in content.lower())
            except Exception as e:
                pass
        
        self.results["sandbox_security"] = checks
        print(f"✅ Sandbox Security: {json.dumps(checks, indent=2)}")
        return checks
    
    async def analyze_sla_monitoring(self):
        """6.1 Prometheus + Grafana + Tracing/Logs"""
        print("\n🔍 Analyzing SLA Monitoring...")
        
        checks = {
            "prometheus_metrics": False,
            "grafana_dashboards": False,
            "opentelemetry_tracing": False,
            "alerting_rules": False,
            "sla_tracking": False
        }
        
        # Check for Prometheus configuration
        prometheus_files = [
            PROJECT_ROOT / "prometheus.yml",
            PROJECT_ROOT / "monitoring_prometheus.py",
            PROJECT_ROOT / "prometheus_alerts.yml"
        ]
        
        for file in prometheus_files:
            if file.exists():
                checks["prometheus_metrics"] = True
                if "alert" in file.name.lower():
                    checks["alerting_rules"] = True
        
        # Check for Grafana
        grafana_dir = PROJECT_ROOT / "grafana"
        if grafana_dir.exists():
            checks["grafana_dashboards"] = True
        
        # Check for tracing in code
        backend_files = list(BACKEND_PATH.rglob("*.py"))
        for file in backend_files:
            try:
                content = file.read_text(encoding='utf-8')
                checks["opentelemetry_tracing"] = checks["opentelemetry_tracing"] or "opentelemetry" in content.lower()
                checks["sla_tracking"] = checks["sla_tracking"] or ("sla" in content.lower() and "metric" in content.lower())
            except Exception as e:
                pass
        
        self.results["sla_monitoring"] = checks
        print(f"✅ SLA Monitoring: {json.dumps(checks, indent=2)}")
        return checks
    
    async def analyze_incident_management(self):
        """6.2 Инциденты и автоматическое восстановление"""
        print("\n🔍 Analyzing Incident Management...")
        
        checks = {
            "auto_recovery": False,
            "saga_compensation": False,
            "trace_logging": False,
            "webhook_integration": False,
            "disaster_recovery": False
        }
        
        # Check for recovery mechanisms
        backend_files = list(BACKEND_PATH.rglob("*.py"))
        for file in backend_files:
            try:
                content = file.read_text(encoding='utf-8')
                checks["auto_recovery"] = checks["auto_recovery"] or "recovery" in content.lower()
                checks["saga_compensation"] = checks["saga_compensation"] or ("saga" in content.lower() and "compensat" in content.lower())
                checks["trace_logging"] = checks["trace_logging"] or "trace_id" in content.lower()
                checks["webhook_integration"] = checks["webhook_integration"] or "webhook" in content.lower()
            except Exception as e:
                pass
        
        self.results["incident_management"] = checks
        print(f"✅ Incident Management: {json.dumps(checks, indent=2)}")
        return checks
    
    async def analyze_multi_tenancy(self):
        """8.1 Multi-tenant pools"""
        print("\n🔍 Analyzing Multi-tenancy...")
        
        checks = {
            "tenant_isolation": False,
            "resource_quotas": False,
            "rate_limiting": False,
            "policy_engine": False,
            "rbac": False
        }
        
        # Check for RBAC and multi-tenancy
        backend_files = list(BACKEND_PATH.rglob("*.py"))
        for file in backend_files:
            try:
                content = file.read_text(encoding='utf-8')
                checks["tenant_isolation"] = checks["tenant_isolation"] or "tenant" in content.lower()
                checks["rate_limiting"] = checks["rate_limiting"] or "rate_limit" in content.lower()
                checks["policy_engine"] = checks["policy_engine"] or "policy" in content.lower()
                checks["rbac"] = checks["rbac"] or "rbac" in content.lower()
            except Exception as e:
                pass
        
        # Check for RBAC test
        rbac_test = TESTS_PATH / "test_rbac.py"
        if rbac_test.exists():
            checks["rbac"] = True
        
        self.results["multi_tenancy"] = checks
        print(f"✅ Multi-tenancy: {json.dumps(checks, indent=2)}")
        return checks
    
    async def run_full_analysis(self):
        """Запуск полного анализа безопасности"""
        print("="*80)
        print("🔒 SECURITY & SANDBOX ANALYSIS - Part 2")
        print("="*80)
        
        await self.analyze_sandbox_security()
        await self.analyze_sla_monitoring()
        await self.analyze_incident_management()
        await self.analyze_multi_tenancy()
        
        return self.results


class MultiAgentAnalyzer:
    """Анализатор мультиагентной системы согласно ТЗ часть 3"""
    
    def __init__(self):
        self.results = {
            "reasoning_agents": {},
            "codegen_agents": {},
            "ml_agents": {},
            "user_control": {},
            "pipeline_workflow": {}
        }
    
    async def analyze_reasoning_agents(self):
        """2.2 Reasoning-агенты (Perplexity AI)"""
        print("\n🔍 Analyzing Reasoning Agents...")
        
        checks = {
            "perplexity_integration": False,
            "chain_of_thought": False,
            "hypothesis_generation": False,
            "explainable_ai": False,
            "reasoning_logger": False
        }
        
        # Check MCP server for Perplexity integration
        mcp_files = list(MCP_SERVER_PATH.rglob("*.py"))
        for file in mcp_files:
            try:
                content = file.read_text(encoding='utf-8')
                checks["perplexity_integration"] = checks["perplexity_integration"] or "perplexity" in content.lower()
                checks["chain_of_thought"] = checks["chain_of_thought"] or "chain" in content.lower()
                checks["reasoning_logger"] = checks["reasoning_logger"] or "reasoning" in content.lower()
            except Exception as e:
                pass
        
        # Check for reasoning logger
        reasoning_logger = MCP_SERVER_PATH / "reasoning_logger.py"
        if reasoning_logger.exists():
            checks["reasoning_logger"] = True
        
        self.results["reasoning_agents"] = checks
        print(f"✅ Reasoning Agents: {json.dumps(checks, indent=2)}")
        return checks
    
    async def analyze_codegen_agents(self):
        """2.3 Генерация и edit кода (DeepSeek)"""
        print("\n🔍 Analyzing CodeGen Agents...")
        
        checks = {
            "deepseek_integration": False,
            "code_generation": False,
            "auto_correction": False,
            "refactoring": False,
            "batch_generation": False
        }
        
        # Check for DeepSeek integration
        mcp_files = list(MCP_SERVER_PATH.rglob("*.py"))
        for file in mcp_files:
            try:
                content = file.read_text(encoding='utf-8')
                if "deepseek" in content.lower():
                    checks["deepseek_integration"] = True
                    checks["code_generation"] = "generate" in content.lower() or "codegen" in content.lower()
                    checks["auto_correction"] = "correct" in content.lower() or "fix" in content.lower()
                    checks["refactoring"] = "refactor" in content.lower()
            except Exception as e:
                pass
        
        # Check for DeepSeek code agent
        deepseek_agent = MCP_SERVER_PATH / "deepseek_code_agent.py"
        if deepseek_agent.exists():
            checks["deepseek_integration"] = True
            checks["code_generation"] = True
        
        self.results["codegen_agents"] = checks
        print(f"✅ CodeGen Agents: {json.dumps(checks, indent=2)}")
        return checks
    
    async def analyze_ml_agents(self):
        """2.4 ML-агенты/AutoML"""
        print("\n🔍 Analyzing ML Agents...")
        
        checks = {
            "automl_integration": False,
            "parameter_optimization": False,
            "market_phase_detection": False,
            "tournament_arena": False,
            "rl_agents": False
        }
        
        # Check for ML optimization
        ml_files = [
            PROJECT_ROOT / "ml_optimizer_perplexity.py",
            BACKEND_PATH / "ml",
            BACKEND_PATH / "optimization"
        ]
        
        for file in ml_files:
            if file.exists():
                if file.is_file():
                    try:
                        content = file.read_text(encoding='utf-8')
                        checks["automl_integration"] = True
                        checks["parameter_optimization"] = "optim" in content.lower()
                    except Exception as e:
                        pass
                elif file.is_dir():
                    checks["automl_integration"] = True
        
        # Check backend for ML agents
        backend_files = list(BACKEND_PATH.rglob("*.py"))
        for file in backend_files:
            try:
                content = file.read_text(encoding='utf-8')
                checks["market_phase_detection"] = checks["market_phase_detection"] or ("market" in content.lower() and "phase" in content.lower())
                checks["tournament_arena"] = checks["tournament_arena"] or "tournament" in content.lower()
                checks["rl_agents"] = checks["rl_agents"] or ("reinforcement" in content.lower() or "rl_" in content.lower())
            except Exception as e:
                pass
        
        self.results["ml_agents"] = checks
        print(f"✅ ML Agents: {json.dumps(checks, indent=2)}")
        return checks
    
    async def analyze_user_control(self):
        """2.6 Управление user-control"""
        print("\n🔍 Analyzing User Control Interface...")
        
        checks = {
            "web_ui": False,
            "vscode_extension": False,
            "api_endpoints": False,
            "reasoning_logs": False,
            "feedback_loop": False
        }
        
        # Check for frontend
        frontend_dir = PROJECT_ROOT / "frontend"
        if frontend_dir.exists():
            checks["web_ui"] = True
        
        # Check for VS Code integration
        vscode_integration = MCP_SERVER_PATH / "vscode_integration.py"
        if vscode_integration.exists():
            checks["vscode_extension"] = True
        
        # Check for API endpoints
        backend_files = list(BACKEND_PATH.rglob("*.py"))
        for file in backend_files:
            try:
                content = file.read_text(encoding='utf-8')
                checks["api_endpoints"] = checks["api_endpoints"] or "@router" in content
                checks["reasoning_logs"] = checks["reasoning_logs"] or "reasoning" in content.lower()
                checks["feedback_loop"] = checks["feedback_loop"] or "feedback" in content.lower()
            except Exception as e:
                pass
        
        self.results["user_control"] = checks
        print(f"✅ User Control: {json.dumps(checks, indent=2)}")
        return checks
    
    async def analyze_pipeline_workflow(self):
        """3. Pipeline работы"""
        print("\n🔍 Analyzing Pipeline Workflow...")
        
        checks = {
            "idea_decomposition": False,
            "codegen_testing": False,
            "ml_analysis": False,
            "user_review": False,
            "deployment": False
        }
        
        # Check for pipeline orchestration
        orchestrator_dir = MCP_SERVER_PATH / "orchestrator"
        if orchestrator_dir.exists():
            checks["idea_decomposition"] = True
            checks["codegen_testing"] = True
            checks["ml_analysis"] = True
        
        # Check for deployment scripts
        deployment_dir = PROJECT_ROOT / "deployment"
        scripts_dir = PROJECT_ROOT / "scripts"
        if deployment_dir.exists() or scripts_dir.exists():
            checks["deployment"] = True
        
        self.results["pipeline_workflow"] = checks
        print(f"✅ Pipeline Workflow: {json.dumps(checks, indent=2)}")
        return checks
    
    async def run_full_analysis(self):
        """Запуск полного мультиагентного анализа"""
        print("="*80)
        print("🤖 MULTI-AGENT SYSTEM ANALYSIS - Part 3")
        print("="*80)
        
        await self.analyze_reasoning_agents()
        await self.analyze_codegen_agents()
        await self.analyze_ml_agents()
        await self.analyze_user_control()
        await self.analyze_pipeline_workflow()
        
        return self.results


class TestExecutor:
    """Исполнитель тестов"""
    
    def __init__(self):
        self.results = {
            "backend_tests": {},
            "integration_tests": {},
            "mcp_tests": {},
            "frontend_tests": {}
        }
    
    async def run_backend_tests(self):
        """Запуск backend тестов"""
        print("\n🧪 Running Backend Tests...")
        
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", str(TESTS_PATH / "backend"), "-v", "--tb=short"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            self.results["backend_tests"] = {
                "returncode": result.returncode,
                "passed": result.returncode == 0,
                "stdout": result.stdout[-2000:] if result.stdout else "",  # Last 2000 chars
                "stderr": result.stderr[-1000:] if result.stderr else ""
            }
            
            print(f"✅ Backend Tests: {'PASSED' if result.returncode == 0 else 'FAILED'}")
        except subprocess.TimeoutExpired:
            self.results["backend_tests"] = {"error": "Timeout after 300s"}
            print("⚠️ Backend Tests: TIMEOUT")
        except Exception as e:
            self.results["backend_tests"] = {"error": str(e)}
            print(f"❌ Backend Tests: ERROR - {e}")
    
    async def run_integration_tests(self):
        """Запуск интеграционных тестов"""
        print("\n🧪 Running Integration Tests...")
        
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", str(TESTS_PATH / "integration"), "-v", "--tb=short"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            self.results["integration_tests"] = {
                "returncode": result.returncode,
                "passed": result.returncode == 0,
                "stdout": result.stdout[-2000:] if result.stdout else "",
                "stderr": result.stderr[-1000:] if result.stderr else ""
            }
            
            print(f"✅ Integration Tests: {'PASSED' if result.returncode == 0 else 'FAILED'}")
        except subprocess.TimeoutExpired:
            self.results["integration_tests"] = {"error": "Timeout after 300s"}
            print("⚠️ Integration Tests: TIMEOUT")
        except Exception as e:
            self.results["integration_tests"] = {"error": str(e)}
            print(f"❌ Integration Tests: ERROR - {e}")
    
    async def run_mcp_tests(self):
        """Запуск MCP тестов"""
        print("\n🧪 Running MCP Tests...")
        
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", str(TESTS_PATH / "test_mcp_integration.py"), "-v", "--tb=short"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            self.results["mcp_tests"] = {
                "returncode": result.returncode,
                "passed": result.returncode == 0,
                "stdout": result.stdout[-2000:] if result.stdout else "",
                "stderr": result.stderr[-1000:] if result.stderr else ""
            }
            
            print(f"✅ MCP Tests: {'PASSED' if result.returncode == 0 else 'FAILED'}")
        except subprocess.TimeoutExpired:
            self.results["mcp_tests"] = {"error": "Timeout after 300s"}
            print("⚠️ MCP Tests: TIMEOUT")
        except Exception as e:
            self.results["mcp_tests"] = {"error": str(e)}
            print(f"❌ MCP Tests: ERROR - {e}")
    
    async def run_all_tests(self):
        """Запуск всех тестов"""
        print("="*80)
        print("🧪 TEST EXECUTION")
        print("="*80)
        
        await self.run_backend_tests()
        await self.run_integration_tests()
        await self.run_mcp_tests()
        
        return self.results


async def generate_recommendations(analysis_results: Dict) -> List[str]:
    """Генерация рекомендаций на основе анализа"""
    recommendations = []
    
    # Architecture recommendations
    arch = analysis_results.get("architecture_compliance", {})
    if not arch.get("protocol_compliance", {}).get("json_rpc_2_0"):
        recommendations.append("🔴 CRITICAL: Implement JSON-RPC 2.0 protocol compliance")
    
    if not arch.get("queue_management", {}).get("redis_streams"):
        recommendations.append("🟡 HIGH: Implement Redis Streams for queue management")
    
    if not arch.get("worker_scaling", {}).get("autoscaling"):
        recommendations.append("🟡 HIGH: Implement SLA-driven autoscaling")
    
    # Security recommendations
    sec = analysis_results.get("security_analysis", {})
    if not sec.get("sandbox_security", {}).get("docker_isolation"):
        recommendations.append("🔴 CRITICAL: Implement Docker-based sandbox isolation")
    
    if not sec.get("sla_monitoring", {}).get("prometheus_metrics"):
        recommendations.append("🟡 HIGH: Set up Prometheus metrics for SLA monitoring")
    
    # Multi-agent recommendations
    multi = analysis_results.get("multi_agent_analysis", {})
    if not multi.get("reasoning_agents", {}).get("perplexity_integration"):
        recommendations.append("🟡 MEDIUM: Integrate Perplexity AI for reasoning agents")
    
    if not multi.get("codegen_agents", {}).get("deepseek_integration"):
        recommendations.append("🟡 MEDIUM: Integrate DeepSeek for code generation")
    
    if not recommendations:
        recommendations.append("✅ All critical requirements are met!")
    
    return recommendations


async def main():
    """Главная функция запуска анализа"""
    print("="*80)
    print("🚀 DEEPSEEK COMPREHENSIVE ANALYSIS")
    print("Based on MCP Orchestrator Technical Specifications")
    print("="*80)
    print()
    
    # Part 1: Architecture Analysis
    arch_analyzer = MCPArchitectureAnalyzer()
    arch_results = await arch_analyzer.run_full_analysis()
    ANALYSIS_RESULTS["architecture_compliance"] = arch_results
    
    # Part 2: Security Analysis
    sec_analyzer = SecuritySandboxAnalyzer()
    sec_results = await sec_analyzer.run_full_analysis()
    ANALYSIS_RESULTS["security_analysis"] = sec_results
    
    # Part 3: Multi-Agent Analysis
    multi_analyzer = MultiAgentAnalyzer()
    multi_results = await multi_analyzer.run_full_analysis()
    ANALYSIS_RESULTS["multi_agent_analysis"] = multi_results
    
    # Part 4: Test Execution
    test_executor = TestExecutor()
    test_results = await test_executor.run_all_tests()
    ANALYSIS_RESULTS["test_execution"] = test_results
    
    # Generate Recommendations
    print("\n" + "="*80)
    print("📋 RECOMMENDATIONS")
    print("="*80)
    recommendations = await generate_recommendations(ANALYSIS_RESULTS)
    ANALYSIS_RESULTS["recommendations"] = recommendations
    
    for rec in recommendations:
        print(rec)
    
    # Save results
    output_file = PROJECT_ROOT / "DEEPSEEK_COMPREHENSIVE_ANALYSIS.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(ANALYSIS_RESULTS, f, indent=2, ensure_ascii=False)
    
    print("\n" + "="*80)
    print(f"✅ Analysis complete! Results saved to: {output_file}")
    print("="*80)
    
    # Generate markdown report
    await generate_markdown_report(ANALYSIS_RESULTS)


async def generate_markdown_report(results: Dict):
    """Генерация Markdown отчёта"""
    report_file = PROJECT_ROOT / "DEEPSEEK_COMPREHENSIVE_ANALYSIS_REPORT.md"
    
    report = f"""# DeepSeek Comprehensive Analysis Report

**Generated:** {results['timestamp']}

## Executive Summary

This report provides a comprehensive analysis of the Bybit Strategy Tester V2 system
according to the MCP Orchestrator Technical Specifications (Parts 1, 2, and 3).

---

## 1. Architecture Compliance (TZ Part 1)

### 1.1 Protocol Compliance
```json
{json.dumps(results['architecture_compliance']['protocol_compliance'], indent=2)}
```

### 1.2 Queue Management
```json
{json.dumps(results['architecture_compliance']['queue_management'], indent=2)}
```

### 1.3 Worker Scaling
```json
{json.dumps(results['architecture_compliance']['worker_scaling'], indent=2)}
```

### 1.4 Signal Routing
```json
{json.dumps(results['architecture_compliance']['signal_routing'], indent=2)}
```

---

## 2. Security & Sandbox Analysis (TZ Part 2)

### 2.1 Sandbox Security
```json
{json.dumps(results['security_analysis']['sandbox_security'], indent=2)}
```

### 2.2 SLA Monitoring
```json
{json.dumps(results['security_analysis']['sla_monitoring'], indent=2)}
```

### 2.3 Incident Management
```json
{json.dumps(results['security_analysis']['incident_management'], indent=2)}
```

### 2.4 Multi-Tenancy
```json
{json.dumps(results['security_analysis']['multi_tenancy'], indent=2)}
```

---

## 3. Multi-Agent System Analysis (TZ Part 3)

### 3.1 Reasoning Agents
```json
{json.dumps(results['multi_agent_analysis']['reasoning_agents'], indent=2)}
```

### 3.2 CodeGen Agents
```json
{json.dumps(results['multi_agent_analysis']['codegen_agents'], indent=2)}
```

### 3.3 ML Agents
```json
{json.dumps(results['multi_agent_analysis']['ml_agents'], indent=2)}
```

### 3.4 User Control
```json
{json.dumps(results['multi_agent_analysis']['user_control'], indent=2)}
```

### 3.5 Pipeline Workflow
```json
{json.dumps(results['multi_agent_analysis']['pipeline_workflow'], indent=2)}
```

---

## 4. Test Execution Results

### 4.1 Backend Tests
- **Status:** {'PASSED' if results['test_execution']['backend_tests'].get('passed') else 'FAILED'}
- **Return Code:** {results['test_execution']['backend_tests'].get('returncode', 'N/A')}

### 4.2 Integration Tests
- **Status:** {'PASSED' if results['test_execution']['integration_tests'].get('passed') else 'FAILED'}
- **Return Code:** {results['test_execution']['integration_tests'].get('returncode', 'N/A')}

### 4.3 MCP Tests
- **Status:** {'PASSED' if results['test_execution']['mcp_tests'].get('passed') else 'FAILED'}
- **Return Code:** {results['test_execution']['mcp_tests'].get('returncode', 'N/A')}

---

## 5. Recommendations

{chr(10).join(results['recommendations'])}

---

## 6. Compliance Summary

### High-Level Metrics

- **Architecture Compliance:** In Progress
- **Security & Sandbox:** Partial Implementation
- **Multi-Agent System:** Foundational Components Present
- **Test Coverage:** Active Testing

### Next Steps

1. **Protocol Implementation**
   - Complete JSON-RPC 2.0 implementation
   - Add missing API endpoints
   - Implement message validation

2. **Queue Management**
   - Integrate Redis Streams
   - Implement consumer groups
   - Add checkpoint recovery

3. **Security Hardening**
   - Enhance sandbox isolation
   - Implement comprehensive monitoring
   - Add incident management automation

4. **Multi-Agent Enhancement**
   - Expand Perplexity integration
   - Enhance DeepSeek capabilities
   - Implement ML AutoML agents

---

**Report Generation Complete**
"""
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"✅ Markdown report saved to: {report_file}")


if __name__ == "__main__":
    asyncio.run(main())
