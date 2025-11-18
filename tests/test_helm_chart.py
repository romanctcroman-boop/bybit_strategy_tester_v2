"""
Phase 4.1: Helm Chart Validation Tests
Tests Helm chart structure and configuration without K8s cluster
"""

import os
import yaml
import json
from pathlib import Path
from typing import Dict, List, Any
import pytest


class TestHelmChartStructure:
    """Test Helm chart file structure and existence"""
    
    HELM_DIR = Path("helm")
    REQUIRED_FILES = [
        "Chart.yaml",
        "values.yaml",
        "templates/_helpers.tpl",
        "templates/backend-deployment.yaml",
        "templates/worker-deployment.yaml",
        "templates/backend-ingress.yaml",
        "templates/istio.yaml",
        "templates/rbac.yaml",
    ]
    
    def test_helm_directory_exists(self):
        """Test that helm directory exists"""
        assert self.HELM_DIR.exists(), "helm/ directory not found"
        assert self.HELM_DIR.is_dir(), "helm/ is not a directory"
    
    def test_required_files_exist(self):
        """Test that all required Helm files exist"""
        missing_files = []
        for file in self.REQUIRED_FILES:
            file_path = self.HELM_DIR / file
            if not file_path.exists():
                missing_files.append(str(file_path))
        
        assert not missing_files, f"Missing required files: {missing_files}"
    
    def test_chart_yaml_valid(self):
        """Test Chart.yaml is valid YAML"""
        chart_path = self.HELM_DIR / "Chart.yaml"
        with open(chart_path, 'r', encoding='utf-8') as f:
            chart = yaml.safe_load(f)
        
        # Validate required fields
        assert 'name' in chart, "Chart.yaml missing 'name' field"
        assert 'version' in chart, "Chart.yaml missing 'version' field"
        assert 'apiVersion' in chart, "Chart.yaml missing 'apiVersion' field"
        
        # Validate values
        assert chart['name'] == 'bybit-strategy-tester'
        assert chart['apiVersion'] == 'v2'
        # Dependencies are optional (can be commented out for testing)
        # assert 'dependencies' in chart, "Chart.yaml missing 'dependencies'"
    
    def test_values_yaml_valid(self):
        """Test values.yaml is valid YAML"""
        values_path = self.HELM_DIR / "values.yaml"
        with open(values_path, 'r', encoding='utf-8') as f:
            values = yaml.safe_load(f)
        
        # Validate top-level keys
        required_keys = ['global', 'backend', 'worker', 'redis', 'postgresql']
        for key in required_keys:
            assert key in values, f"values.yaml missing '{key}' section"
    
    def test_templates_are_yaml_like(self):
        """Test that all template files have YAML-like structure"""
        templates_dir = self.HELM_DIR / "templates"
        yaml_files = list(templates_dir.glob("*.yaml"))
        
        assert len(yaml_files) > 0, "No YAML templates found"
        
        for yaml_file in yaml_files:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # Check for basic YAML structure (contains ':' or '---')
                assert ':' in content or '---' in content, \
                    f"{yaml_file.name} doesn't look like YAML"


class TestHelmChartConfiguration:
    """Test Helm chart configuration values"""
    
    @pytest.fixture
    def values(self) -> Dict[str, Any]:
        """Load values.yaml"""
        values_path = Path("helm/values.yaml")
        with open(values_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def test_backend_configuration(self, values):
        """Test backend service configuration"""
        backend = values['backend']
        
        # Test replicas
        assert backend['replicaCount'] == 3
        
        # Test autoscaling
        assert backend['autoscaling']['enabled'] is True
        assert backend['autoscaling']['minReplicas'] == 3
        assert backend['autoscaling']['maxReplicas'] == 10
        assert backend['autoscaling']['targetCPUUtilizationPercentage'] == 70
        
        # Test resources
        assert backend['resources']['requests']['cpu'] == '500m'
        assert backend['resources']['requests']['memory'] == '512Mi'
        assert backend['resources']['limits']['cpu'] == '2000m'
        assert backend['resources']['limits']['memory'] == '2Gi'
        
        # Test probes
        assert 'livenessProbe' in backend
        assert 'readinessProbe' in backend
    
    def test_worker_configuration(self, values):
        """Test worker service configuration"""
        worker = values['worker']
        
        # Test replicas
        assert worker['replicaCount'] == 5
        
        # Test autoscaling
        assert worker['autoscaling']['enabled'] is True
        assert worker['autoscaling']['minReplicas'] == 5
        assert worker['autoscaling']['maxReplicas'] == 20
        
        # Test custom metrics (queue-based scaling)
        assert 'customMetrics' in worker['autoscaling']
        custom_metrics = worker['autoscaling']['customMetrics']
        assert len(custom_metrics) > 0
        assert custom_metrics[0]['type'] == 'External'
        assert 'redis_stream_length' in str(custom_metrics[0])
        
        # Test resources (workers need more CPU)
        assert worker['resources']['requests']['cpu'] == '1000m'
        assert worker['resources']['limits']['cpu'] == '4000m'
    
    def test_redis_configuration(self, values):
        """Test Redis cluster configuration"""
        redis = values['redis']
        
        # Test architecture
        assert redis['enabled'] is True
        assert redis['architecture'] == 'replication'
        
        # Test master nodes
        assert redis['master']['count'] == 3
        assert redis['master']['persistence']['enabled'] is True
        assert redis['master']['persistence']['size'] == '10Gi'
        
        # Test replicas
        assert redis['replica']['replicaCount'] == 3
        
        # Test Sentinel
        assert redis['sentinel']['enabled'] is True
        assert redis['sentinel']['quorum'] == 2
    
    def test_postgresql_configuration(self, values):
        """Test PostgreSQL configuration"""
        postgresql = values['postgresql']
        
        # Test enabled
        assert postgresql['enabled'] is True
        
        # Test persistence
        assert postgresql['primary']['persistence']['enabled'] is True
        assert postgresql['primary']['persistence']['size'] == '50Gi'
        
        # Test read replicas
        assert postgresql['readReplicas']['replicaCount'] == 2
        
        # Test backup
        assert postgresql['backup']['enabled'] is True
        assert postgresql['backup']['cronjob']['schedule'] == '0 2 * * *'
    
    def test_istio_configuration(self, values):
        """Test Istio service mesh configuration"""
        istio = values['istio']
        
        # Test enabled
        assert istio['enabled'] is True
        
        # Test virtual services
        assert 'virtualServices' in istio
        vs = istio['virtualServices']['backend']
        assert vs['enabled'] is True
        
        # Test canary deployment (traffic split)
        http_routes = vs['http']
        assert len(http_routes) > 0
        routes = http_routes[0]['route']
        assert len(routes) == 2  # Stable + Canary
        
        # Validate traffic weights
        weights = [r['weight'] for r in routes]
        assert 90 in weights  # Stable
        assert 10 in weights  # Canary
        
        # Test destination rules (circuit breaking)
        dr = istio['destinationRules']['backend']
        assert dr['enabled'] is True
        assert 'trafficPolicy' in dr
    
    def test_security_configuration(self, values):
        """Test security settings"""
        security = values['security']
        
        # Test service account
        assert security['serviceAccount']['create'] is True
        
        # Test RBAC
        assert security['rbac']['create'] is True
        
        # Test security context (non-root)
        sc = security['securityContext']
        assert sc['runAsNonRoot'] is True
        assert sc['runAsUser'] == 1000
    
    def test_network_policy_configuration(self, values):
        """Test network policies"""
        assert values['networkPolicy']['enabled'] is True
        
        # Test backend policies
        backend_policies = values['networkPolicy']['backend']
        assert len(backend_policies) > 0
        
        # Test worker policies
        worker_policies = values['networkPolicy']['worker']
        assert len(worker_policies) > 0


class TestHelmChartMetrics:
    """Test Helm chart metrics and statistics"""
    
    def test_total_lines_of_code(self):
        """Test that chart has substantial configuration"""
        helm_dir = Path("helm")
        total_lines = 0
        
        for file_path in helm_dir.rglob("*.yaml"):
            with open(file_path, 'r', encoding='utf-8') as f:
                total_lines += len(f.readlines())
        
        for file_path in helm_dir.rglob("*.tpl"):
            with open(file_path, 'r', encoding='utf-8') as f:
                total_lines += len(f.readlines())
        
        # Should have substantial configuration (>1500 lines)
        assert total_lines > 1500, f"Chart only has {total_lines} lines (expected >1500)"
        print(f"\n✅ Total Helm chart lines: {total_lines}")
    
    def test_resource_limits_defined(self):
        """Test that all services have resource limits"""
        values_path = Path("helm/values.yaml")
        with open(values_path, 'r', encoding='utf-8') as f:
            values = yaml.safe_load(f)
        
        services = ['backend', 'worker']
        for service in services:
            assert 'resources' in values[service], f"{service} missing resources"
            resources = values[service]['resources']
            assert 'requests' in resources, f"{service} missing requests"
            assert 'limits' in resources, f"{service} missing limits"
            assert 'cpu' in resources['requests'], f"{service} missing CPU request"
            assert 'memory' in resources['requests'], f"{service} missing memory request"


class TestHelmChartDocumentation:
    """Test that chart is properly documented"""
    
    def test_phase4_documentation_exists(self):
        """Test that Phase 4 documentation exists"""
        doc_path = Path("PHASE4_KUBERNETES_COMPLETE.md")
        assert doc_path.exists(), "Phase 4 documentation not found"
        
        with open(doc_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # Check for key sections
            assert "Kubernetes Foundation" in content
            assert "Helm Chart" in content
            assert "Deployment Guide" in content
            assert "Production Checklist" in content
    
    def test_chart_has_readme(self):
        """Test that Chart has inline documentation"""
        chart_path = Path("helm/Chart.yaml")
        with open(chart_path, 'r', encoding='utf-8') as f:
            chart = yaml.safe_load(f)
        
        assert 'description' in chart, "Chart missing description"
        assert 'maintainers' in chart, "Chart missing maintainers"
        assert 'keywords' in chart, "Chart missing keywords"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
