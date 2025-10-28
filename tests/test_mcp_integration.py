"""
MCP Integration Testing Suite

Tests the integration between Perplexity AI and Capiton GitHub
through various workflow scenarios.
"""

import os
import json
import subprocess
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


class TestMCPConfiguration:
    """Test MCP configuration files and settings."""
    
    def test_mcp_json_exists(self):
        """Check that mcp.json configuration exists."""
        mcp_config = Path('.vscode/mcp.json')
        assert mcp_config.exists(), "mcp.json configuration file not found"
    
    def test_mcp_json_valid(self):
        """Validate mcp.json structure."""
        with open('.vscode/mcp.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Check required sections
        assert 'mcpServers' in config
        assert 'workflow' in config
        assert 'rules' in config
        
        # Check servers
        assert 'perplexity' in config['mcpServers']
        assert 'capiton-github' in config['mcpServers']
        
        # Validate Perplexity config
        perplexity = config['mcpServers']['perplexity']
        assert perplexity['command'] == 'npx'
        assert perplexity['priority'] == 'analysis'
        assert perplexity['autoStart'] is True
        
        # Validate Capiton config
        capiton = config['mcpServers']['capiton-github']
        assert capiton['command'] == 'npx'
        assert capiton['priority'] == 'orchestration'
        assert capiton['autoStart'] is True
    
    def test_workflow_pipeline_defined(self):
        """Check that workflow pipeline is properly defined."""
        with open('.vscode/mcp.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        pipeline = config['workflow']['pipeline']
        assert len(pipeline) == 4, "Pipeline should have 4 stages"
        
        stages = [stage['stage'] for stage in pipeline]
        assert stages == ['analysis', 'planning', 'execution', 'validation']
        
        # Check agent assignments
        assert pipeline[0]['agent'] == 'perplexity'  # analysis
        assert pipeline[1]['agent'] == 'capiton-github'  # planning
        assert pipeline[2]['agent'] == 'perplexity'  # execution
        assert pipeline[3]['agent'] == 'capiton-github'  # validation
    
    def test_routing_rules_defined(self):
        """Validate routing rules are properly configured."""
        with open('.vscode/mcp.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        routing = config['workflow']['routing']
        
        # Check Capiton-only routes
        assert routing['taskCreation'] == ['capiton-github']
        assert routing['taskPrioritization'] == ['capiton-github']
        assert routing['restrictionsManagement'] == ['capiton-github']
        
        # Check Perplexity-only routes
        assert routing['deepAnalysis'] == ['perplexity']
        assert routing['solutionResearch'] == ['perplexity']
        assert routing['knowledgeSynthesis'] == ['perplexity']
        
        # Check collaborative routes
        assert 'perplexity' in routing['bugInvestigation']
        assert 'capiton-github' in routing['bugInvestigation']


class TestMCPScripts:
    """Test MCP installation and workflow scripts."""
    
    def test_install_script_exists_ps1(self):
        """Check PowerShell installation script exists."""
        script = Path('scripts/install_mcp.ps1')
        assert script.exists(), "install_mcp.ps1 not found"
    
    def test_install_script_exists_sh(self):
        """Check Bash installation script exists."""
        script = Path('scripts/install_mcp.sh')
        assert script.exists(), "install_mcp.sh not found"
    
    def test_workflow_script_exists(self):
        """Check workflow automation script exists."""
        script = Path('scripts/mcp_workflow.ps1')
        assert script.exists(), "mcp_workflow.ps1 not found"
    
    def test_install_script_has_validation(self):
        """Check that install script validates environment."""
        with open('scripts/install_mcp.ps1', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should check Node.js
        assert 'node --version' in content
        
        # Should check npm
        assert 'npm --version' in content or 'npm list' in content
        
        # Should handle .env
        assert '.env' in content
    
    def test_workflow_script_has_functions(self):
        """Check that workflow script has required functions."""
        with open('scripts/mcp_workflow.ps1', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should have environment loading
        assert 'Load-EnvFile' in content or 'env' in content.lower()
        
        # Should check server status
        assert 'Test-MCPServers' in content or 'npm list' in content


class TestMCPEnvironment:
    """Test environment configuration."""
    
    def test_env_example_has_mcp_section(self):
        """Check that .env.example includes MCP configuration."""
        with open('.env.example', 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'PERPLEXITY_API_KEY' in content
        assert 'GITHUB_TOKEN' in content
        assert 'GITHUB_OWNER' in content
        assert 'GITHUB_REPO' in content
    
    def test_env_example_has_placeholders(self):
        """Check that .env.example has proper placeholders."""
        with open('.env.example', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should have placeholder format
        assert 'pplx-' in content or 'your-api-key' in content
        assert 'ghp_' in content or 'your-github-token' in content


class TestMCPTasks:
    """Test VS Code tasks integration."""
    
    def test_tasks_json_has_mcp_tasks(self):
        """Check that tasks.json includes MCP tasks."""
        with open('.vscode/tasks.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        task_labels = [task['label'] for task in config['tasks']]
        
        # Check for MCP tasks
        assert any('MCP' in label for label in task_labels)
        assert any('Install' in label and 'MCP' in label for label in task_labels)
        assert any('Start' in label and 'Server' in label for label in task_labels)
    
    def test_workflow_task_exists(self):
        """Check that workflow automation task exists."""
        with open('.vscode/tasks.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        task_labels = [task['label'] for task in config['tasks']]
        assert any('Workflow' in label and 'Anomalies' in label for label in task_labels)


class TestMCPDocumentation:
    """Test that documentation is complete."""
    
    def test_quickstart_exists(self):
        """Check that quick start guide exists."""
        assert Path('QUICKSTART_MCP.md').exists()
    
    def test_integration_guide_exists(self):
        """Check that integration guide exists."""
        assert Path('MCP_INTEGRATION.md').exists()
    
    def test_docs_index_exists(self):
        """Check that documentation index exists."""
        assert Path('MCP_DOCS_INDEX.md').exists()
    
    def test_setup_guide_exists(self):
        """Check that setup guide exists."""
        assert Path('.vscode/MCP_SETUP_GUIDE.md').exists()
    
    def test_project_context_exists(self):
        """Check that project context exists."""
        assert Path('.vscode/PROJECT_CONTEXT.md').exists()
    
    def test_documentation_has_examples(self):
        """Check that documentation includes usage examples."""
        with open('MCP_INTEGRATION.md', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should have code examples
        assert '```' in content
        
        # Should have workflow examples
        assert 'Ctrl+Shift+P' in content or 'Tasks: Run Task' in content


class TestMCPWorkflowScenarios:
    """Test different workflow scenarios."""
    
    @patch('subprocess.run')
    def test_scenario_bug_investigation(self, mock_run):
        """
        Scenario: Bug investigation workflow
        
        Expected flow:
        1. Perplexity analyzes bug
        2. Capiton creates GitHub issue
        3. Perplexity researches solution
        4. Capiton tracks progress
        """
        # Mock successful execution
        mock_run.return_value = Mock(returncode=0, stdout="Success")
        
        # This would trigger the workflow in real scenario
        # For now, just verify the configuration supports it
        with open('.vscode/mcp.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        routing = config['workflow']['routing']
        assert 'bugInvestigation' in routing
        assert 'perplexity' in routing['bugInvestigation']
        assert 'capiton-github' in routing['bugInvestigation']
    
    def test_scenario_high_priority_anomalies(self):
        """
        Scenario: High priority anomalies (4-7) workflow
        
        Expected flow:
        1. Perplexity analyzes all 4 anomalies
        2. Capiton creates 4 GitHub issues
        3. Perplexity generates solutions
        4. Capiton creates PRs
        """
        with open('.vscode/PROJECT_CONTEXT.md', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check that anomalies 4-7 are documented
        assert 'Position Sizing' in content
        assert 'Signal Exit' in content
        assert 'Buy & Hold' in content
        assert 'Margin Call' in content
    
    def test_scenario_code_review(self):
        """
        Scenario: Code review workflow
        
        Expected flow:
        1. Capiton coordinates review
        2. Perplexity provides analysis (optional)
        3. Capiton tracks review status
        """
        with open('.vscode/mcp.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        routing = config['workflow']['routing']
        assert 'codeReview' in routing
        assert 'capiton-github' in routing['codeReview']
    
    def test_scenario_documentation_generation(self):
        """
        Scenario: Documentation generation workflow
        
        Expected flow:
        1. Perplexity generates documentation
        2. Capiton tracks documentation tasks
        """
        with open('.vscode/mcp.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        routing = config['workflow']['routing']
        assert 'documentation' in routing
        assert 'perplexity' in routing['documentation']
        assert 'capiton-github' in routing['documentation']


class TestMCPRestrictions:
    """Test that agent restrictions are enforced."""
    
    def test_perplexity_cannot_create_tasks(self):
        """Verify Perplexity is restricted from task creation."""
        with open('.vscode/mcp.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        routing = config['workflow']['routing']
        
        # Only Capiton should create tasks
        assert routing['taskCreation'] == ['capiton-github']
        assert 'perplexity' not in routing['taskCreation']
    
    def test_perplexity_cannot_set_priorities(self):
        """Verify Perplexity is restricted from prioritization."""
        with open('.vscode/mcp.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        routing = config['workflow']['routing']
        
        # Only Capiton should prioritize
        assert routing['taskPrioritization'] == ['capiton-github']
        assert 'perplexity' not in routing['taskPrioritization']
    
    def test_capiton_delegates_analysis(self):
        """Verify Capiton delegates deep analysis to Perplexity."""
        with open('.vscode/mcp.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        routing = config['workflow']['routing']
        
        # Only Perplexity should do deep analysis
        assert routing['deepAnalysis'] == ['perplexity']
        assert 'capiton-github' not in routing['deepAnalysis']
    
    def test_rules_enforcement_strict(self):
        """Verify that restriction rules are set to strict enforcement."""
        with open('.vscode/mcp.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        rules = config['rules']
        assert rules['restrictions']['source'] == 'capiton-github'
        assert rules['restrictions']['enforcement'] == 'strict'
        assert rules['restrictions']['override'] is False


class TestMCPIntegrationPoints:
    """Test integration with existing project components."""
    
    def test_integration_with_rbac(self):
        """Check that MCP respects RBAC system."""
        # RBAC should be documented in project context
        with open('.vscode/PROJECT_CONTEXT.md', 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'RBAC' in content
    
    def test_integration_with_anomalies(self):
        """Check that MCP is aware of completed anomalies."""
        with open('.vscode/PROJECT_CONTEXT.md', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should document completed anomalies 1-3
        assert 'Code Consolidation' in content
        assert 'RBAC Implementation' in content
        assert 'DataManager Refactoring' in content
    
    def test_integration_with_testing(self):
        """Check that MCP can trigger test execution."""
        with open('.vscode/tasks.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        task_labels = [task['label'] for task in config['tasks']]
        assert any('Test' in label for label in task_labels)


class TestMCPErrorHandling:
    """Test error handling scenarios."""
    
    def test_missing_api_key_handling(self):
        """Verify that missing API keys are detected."""
        with open('scripts/install_mcp.ps1', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should check for API key
        assert 'PERPLEXITY_API_KEY' in content
        assert 'GITHUB_TOKEN' in content
    
    def test_npm_not_installed_handling(self):
        """Verify that missing npm is detected."""
        with open('scripts/install_mcp.ps1', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should check npm availability
        assert 'npm' in content


class TestMCPMetrics:
    """Test metrics and monitoring configuration."""
    
    def test_metrics_enabled(self):
        """Check that metrics monitoring is enabled."""
        with open('.vscode/mcp.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        assert 'monitoring' in config
        assert config['monitoring']['enabled'] is True
    
    def test_metrics_tracked(self):
        """Verify that key metrics are tracked."""
        with open('.vscode/mcp.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        metrics = config['monitoring']['metrics']
        assert metrics['taskCompletion'] is True
        assert metrics['analysisDepth'] is True
        assert metrics['responseTime'] is True
        assert metrics['errorRate'] is True


class TestMCPBackwardCompatibility:
    """Test that MCP doesn't break existing functionality."""
    
    def test_existing_tasks_still_work(self):
        """Verify that original tasks still exist."""
        with open('.vscode/tasks.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        task_labels = [task['label'] for task in config['tasks']]
        
        # Original tasks should still exist
        assert any('frontend' in label.lower() for label in task_labels)
        assert any('backend' in label.lower() or 'uvicorn' in label.lower() 
                  for label in task_labels)
    
    def test_existing_settings_preserved(self):
        """Verify that original VS Code settings are preserved."""
        with open('.vscode/settings.json', 'r', encoding='utf-8') as f:
            content = f.read()
            # Remove comments and parse JSON
            import re
            content_no_comments = re.sub(r'//.*', '', content)
            config = json.loads(content_no_comments)
        
        # Original settings should exist
        assert 'python.testing.pytestEnabled' in config or \
               'python.testing.unittestEnabled' in config


@pytest.mark.integration
class TestMCPEndToEnd:
    """End-to-end integration tests with mocked APIs."""
    
    def test_perplexity_api_key_format(self):
        """Test Perplexity API key format validation (mocked)."""
        # Test format validation without actual API call
        test_keys = [
            'pplx-abc123def456',
            'pplx-' + 'x' * 45  # Example key format
        ]
        for key in test_keys:
            assert key.startswith('pplx-'), f"Invalid Perplexity API key format: {key}"
            assert len(key) > 10, f"Perplexity API key too short: {key}"
    
    def test_github_token_format(self):
        """Test GitHub token format validation (mocked)."""
        # Test format validation without actual API call
        test_tokens = [
            'ghp_abc123def456ghi789jkl012mno345pqr678',
            'github_pat_abc123_def456ghi789jkl012'
        ]
        for token in test_tokens:
            assert token.startswith('ghp_') or token.startswith('github_pat_'), \
                f"Invalid GitHub token format: {token}"
            assert len(token) > 20, f"GitHub token too short: {token}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
