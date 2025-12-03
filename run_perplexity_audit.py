"""
🔍 Perplexity Agent - Audit & Analysis Script

Выполняет полный аудит проекта через существующую инфраструктуру:
- backend/agents/agent_to_agent_communicator.py
- backend/agents/unified_agent_interface.py
- mcp-server/tools/
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime
from loguru import logger

# Импортируем существующую инфраструктуру
try:
    from backend.agents.agent_to_agent_communicator import (
        AgentToAgentCommunicator,
        AgentMessage,
        AgentType,
        MessageType
    )
    from backend.agents.unified_agent_interface import (
        get_agent_interface,
        AgentRequest,
        AgentType as UnifiedAgentType
    )
    INFRASTRUCTURE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Infrastructure not available: {e}")
    INFRASTRUCTURE_AVAILABLE = False


class PerplexityAuditAgent:
    """
    Perplexity Agent для аудита проекта
    
    Использует существующую инфраструктуру для:
    1. Анализа архитектуры проекта
    2. Оценки качества кода
    3. Проверки best practices
    4. Генерации рекомендаций
    """
    
    def __init__(self):
        """Инициализация агента"""
        self.project_root = Path(__file__).parent
        self.audit_results = {}
        
        if INFRASTRUCTURE_AVAILABLE:
            self.communicator = AgentToAgentCommunicator()
            self.agent_interface = get_agent_interface()
            logger.info("✅ Infrastructure loaded successfully")
        else:
            logger.warning("⚠️ Running in standalone mode")
    
    async def run_full_audit(self) -> dict:
        """
        Выполнить полный аудит проекта
        
        Returns:
            dict: Результаты аудита
        """
        logger.info("🔍 Starting Perplexity Agent Full Project Audit")
        
        # 1. Анализ структуры проекта
        await self._audit_project_structure()
        
        # 2. Анализ AI Agents инфраструктуры
        await self._audit_ai_agents_infrastructure()
        
        # 3. Анализ MCP Server
        await self._audit_mcp_server()
        
        # 4. Анализ Backend Services
        await self._audit_backend_services()
        
        # 5. Анализ Integration & Communication
        await self._audit_communication_layer()
        
        # 6. Генерация рекомендаций
        await self._generate_recommendations()
        
        # Сохранить результаты
        self._save_audit_results()
        
        return self.audit_results
    
    async def _audit_project_structure(self):
        """Аудит структуры проекта"""
        logger.info("📁 Auditing project structure...")
        
        structure = {
            "backend_agents": self.project_root / "backend" / "agents",
            "mcp_server": self.project_root / "mcp-server",
            "backend_services": self.project_root / "backend" / "services",
            "backend_tasks": self.project_root / "backend" / "tasks",
            "tests": self.project_root / "tests",
        }
        
        analysis = {
            "structure_found": {},
            "key_files": {},
            "missing_components": []
        }
        
        for name, path in structure.items():
            exists = path.exists()
            analysis["structure_found"][name] = exists
            
            if exists and path.is_dir():
                files = list(path.glob("*.py"))
                analysis["key_files"][name] = [f.name for f in files]
        
        # Проверка обязательных компонентов
        required = [
            "backend/agents/agent_to_agent_communicator.py",
            "backend/agents/unified_agent_interface.py",
            "backend/agents/deepseek.py",
            "mcp-server/server.py",
        ]
        
        for req in required:
            req_path = self.project_root / req
            if not req_path.exists():
                analysis["missing_components"].append(req)
        
        self.audit_results["project_structure"] = analysis
        logger.info(f"✅ Project structure audit complete: {len(analysis['key_files'])} components found")
    
    async def _audit_ai_agents_infrastructure(self):
        """Аудит AI Agents инфраструктуры"""
        logger.info("🤖 Auditing AI Agents infrastructure...")
        
        agents_path = self.project_root / "backend" / "agents"
        
        analysis = {
            "agents_available": {},
            "communication_layer": {
                "agent_to_agent_communicator": False,
                "unified_interface": False,
                "background_service": False
            },
            "integration_status": "Unknown"
        }
        
        # Проверка файлов агентов
        agent_files = {
            "DeepSeek Agent": "deepseek.py",
            "Agent Communicator": "agent_to_agent_communicator.py",
            "Unified Interface": "unified_agent_interface.py",
            "Background Service": "agent_background_service.py"
        }
        
        for name, filename in agent_files.items():
            file_path = agents_path / filename
            analysis["agents_available"][name] = file_path.exists()
        
        # Проверка communication layer
        if (agents_path / "agent_to_agent_communicator.py").exists():
            analysis["communication_layer"]["agent_to_agent_communicator"] = True
            analysis["integration_status"] = "Partial"
        
        if (agents_path / "unified_agent_interface.py").exists():
            analysis["communication_layer"]["unified_interface"] = True
            analysis["integration_status"] = "Available"

        if (agents_path / "agent_background_service.py").exists():
            analysis["communication_layer"]["background_service"] = True
        
        if all(analysis["communication_layer"].values()):
            analysis["integration_status"] = "Fully Integrated"
        
        self.audit_results["ai_agents_infrastructure"] = analysis
        logger.info(f"✅ AI Agents infrastructure audit: {analysis['integration_status']}")
    
    async def _audit_mcp_server(self):
        """Аудит MCP Server"""
        logger.info("🔌 Auditing MCP Server...")
        
        mcp_path = self.project_root / "mcp-server"
        
        analysis = {
            "mcp_server_exists": mcp_path.exists(),
            "tools_available": {},
            "configuration": {},
            "status": "Unknown"
        }
        
        if mcp_path.exists():
            # Проверка структуры tools
            tools_path = mcp_path / "tools"
            if tools_path.exists():
                tool_categories = list(tools_path.glob("*/"))
                analysis["tools_available"] = {
                    cat.name: len(list(cat.glob("*.py")))
                    for cat in tool_categories if cat.is_dir()
                }
            
            # Проверка конфигурации
            config_files = ["config.json", ".env", "requirements.txt"]
            for cfg in config_files:
                cfg_path = mcp_path / cfg
                analysis["configuration"][cfg] = cfg_path.exists()
            
            # Определение статуса
            if analysis["tools_available"] and any(analysis["configuration"].values()):
                analysis["status"] = "Configured"
            else:
                analysis["status"] = "Partial"
        else:
            analysis["status"] = "Not Found"
        
        self.audit_results["mcp_server"] = analysis
        logger.info(f"✅ MCP Server audit: {analysis['status']}")
    
    async def _audit_backend_services(self):
        """Аудит Backend Services"""
        logger.info("⚙️ Auditing Backend Services...")
        
        services_path = self.project_root / "backend" / "services"
        tasks_path = self.project_root / "backend" / "tasks"
        
        analysis = {
            "services": [],
            "tasks": [],
            "key_components": {
                "data_service": False,
                "backtest_tasks": False,
                "optimize_tasks": False
            }
        }
        
        # Сканируем services
        if services_path.exists():
            services = list(services_path.glob("*.py"))
            analysis["services"] = [s.name for s in services if s.name != "__init__.py"]
            
            if (services_path / "data_service.py").exists():
                analysis["key_components"]["data_service"] = True
        
        # Сканируем tasks
        if tasks_path.exists():
            tasks = list(tasks_path.glob("*.py"))
            analysis["tasks"] = [t.name for t in tasks if t.name != "__init__.py"]
            
            if (tasks_path / "backtest_tasks.py").exists():
                analysis["key_components"]["backtest_tasks"] = True
            
            if (tasks_path / "optimize_tasks.py").exists():
                analysis["key_components"]["optimize_tasks"] = True
        
        self.audit_results["backend_services"] = analysis
        logger.info(f"✅ Backend services audit: {len(analysis['services'])} services, {len(analysis['tasks'])} tasks")
    
    async def _audit_communication_layer(self):
        """Аудит коммуникационного слоя"""
        logger.info("📡 Auditing communication layer...")
        
        analysis = {
            "agent_to_agent": False,
            "mcp_integration": False,
            "direct_api": False,
            "redis_support": False,
            "status": "Unknown"
        }
        
        # Проверяем agent_to_agent_communicator
        comm_file = self.project_root / "backend" / "agents" / "agent_to_agent_communicator.py"
        if comm_file.exists():
            try:
                content = comm_file.read_text(encoding='utf-8', errors='ignore')
                analysis["agent_to_agent"] = True
                analysis["redis_support"] = "redis" in content.lower()
            except Exception as e:
                logger.warning(f"Could not read {comm_file}: {e}")
                analysis["agent_to_agent"] = comm_file.exists()
        
        # Проверяем unified_agent_interface
        unified_file = self.project_root / "backend" / "agents" / "unified_agent_interface.py"
        if unified_file.exists():
            try:
                content = unified_file.read_text(encoding='utf-8', errors='ignore')
                analysis["mcp_integration"] = "mcp_server" in content.lower()
                analysis["direct_api"] = "direct_api" in content.lower()
            except Exception as e:
                logger.warning(f"Could not read {unified_file}: {e}")
                analysis["mcp_integration"] = unified_file.exists()
                analysis["direct_api"] = unified_file.exists()
        
        # Определяем статус
        if all([analysis["agent_to_agent"], analysis["mcp_integration"], analysis["direct_api"]]):
            analysis["status"] = "Fully Integrated"
        elif analysis["agent_to_agent"] or analysis["mcp_integration"]:
            analysis["status"] = "Partial"
        else:
            analysis["status"] = "Not Configured"
        
        self.audit_results["communication_layer"] = analysis
        logger.info(f"✅ Communication layer audit: {analysis['status']}")
    
    async def _generate_recommendations(self):
        """Генерация рекомендаций на основе аудита"""
        logger.info("💡 Generating recommendations...")
        
        recommendations = {
            "immediate_actions": [],
            "improvements": [],
            "optimizations": [],
            "documentation_needed": []
        }
        
        # Анализ результатов
        structure = self.audit_results.get("project_structure", {})
        ai_agents = self.audit_results.get("ai_agents_infrastructure", {})
        mcp = self.audit_results.get("mcp_server", {})
        communication = self.audit_results.get("communication_layer", {})
        
        # Immediate actions
        if structure.get("missing_components"):
            recommendations["immediate_actions"].append({
                "priority": "HIGH",
                "action": "Create missing components",
                "components": structure["missing_components"]
            })
        
        if ai_agents.get("integration_status") != "Fully Integrated":
            recommendations["immediate_actions"].append({
                "priority": "HIGH",
                "action": "Complete AI Agents integration",
                "status": ai_agents.get("integration_status", "Unknown")
            })
        
        # Improvements
        if mcp.get("status") != "Configured":
            recommendations["improvements"].append({
                "priority": "MEDIUM",
                "action": "Configure MCP Server properly",
                "current_status": mcp.get("status", "Unknown")
            })
        
        if not communication.get("redis_support"):
            recommendations["improvements"].append({
                "priority": "MEDIUM",
                "action": "Add Redis support for agent communication",
                "benefit": "Better scalability and async messaging"
            })
        
        # Optimizations
        recommendations["optimizations"].append({
            "priority": "LOW",
            "action": "Implement caching layer for agent responses",
            "benefit": "Reduce API calls and improve performance"
        })
        
        # Documentation
        recommendations["documentation_needed"].extend([
            "Agent-to-Agent Communication Guide",
            "Perplexity Agent Usage Examples",
            "DeepSeek Agent Integration Tutorial",
            "MCP Server Configuration Guide"
        ])
        
        self.audit_results["recommendations"] = recommendations
        logger.info(f"✅ Generated {len(recommendations['immediate_actions'])} immediate actions")
    
    def _save_audit_results(self):
        """Сохранить результаты аудита"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.project_root / f"PERPLEXITY_AUDIT_RESULTS_{timestamp}.json"
        
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(self.audit_results, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Audit results saved to: {output_file}")
        except Exception as e:
            logger.error(f"❌ Failed to save audit results: {e}")
    
    def print_summary(self):
        """Вывести краткую сводку аудита"""
        print("\n" + "="*80)
        print("🔍 PERPLEXITY AGENT - PROJECT AUDIT SUMMARY")
        print("="*80)
        
        # Project Structure
        structure = self.audit_results.get("project_structure", {})
        print("\n📁 PROJECT STRUCTURE:")
        for component, found in structure.get("structure_found", {}).items():
            status = "✅" if found else "❌"
            print(f"  {status} {component}")
        
        # AI Agents
        ai_agents = self.audit_results.get("ai_agents_infrastructure", {})
        print(f"\n🤖 AI AGENTS INFRASTRUCTURE: {ai_agents.get('integration_status', 'Unknown')}")
        for agent, available in ai_agents.get("agents_available", {}).items():
            status = "✅" if available else "❌"
            print(f"  {status} {agent}")
        
        # MCP Server
        mcp = self.audit_results.get("mcp_server", {})
        print(f"\n🔌 MCP SERVER: {mcp.get('status', 'Unknown')}")
        for category, count in mcp.get("tools_available", {}).items():
            print(f"  📦 {category}: {count} tools")
        
        # Communication Layer
        communication = self.audit_results.get("communication_layer", {})
        print(f"\n📡 COMMUNICATION LAYER: {communication.get('status', 'Unknown')}")
        print(f"  Agent-to-Agent: {'✅' if communication.get('agent_to_agent') else '❌'}")
        print(f"  MCP Integration: {'✅' if communication.get('mcp_integration') else '❌'}")
        print(f"  Direct API: {'✅' if communication.get('direct_api') else '❌'}")
        print(f"  Redis Support: {'✅' if communication.get('redis_support') else '❌'}")
        
        # Recommendations
        recommendations = self.audit_results.get("recommendations", {})
        print(f"\n💡 IMMEDIATE ACTIONS: {len(recommendations.get('immediate_actions', []))}")
        for action in recommendations.get("immediate_actions", []):
            print(f"  🔴 [{action['priority']}] {action['action']}")
        
        print("\n" + "="*80)
        print("✅ Full audit results saved to JSON file")
        print("="*80 + "\n")


async def main():
    """Main entry point"""
    logger.info("🚀 Starting Perplexity Agent Audit")
    
    agent = PerplexityAuditAgent()
    
    try:
        # Запуск полного аудита
        await agent.run_full_audit()
        
        # Вывод сводки
        agent.print_summary()
        
        logger.info("✅ Audit completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Audit failed: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
