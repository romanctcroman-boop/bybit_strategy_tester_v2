#!/usr/bin/env python3
"""
Test Alert Firing Script
Sends test metrics to trigger alerts for validation
"""

import time
import requests
from prometheus_client import Counter, Gauge, push_to_gateway, CollectorRegistry


class AlertTester:
    def __init__(self, pushgateway_url='localhost:9091'):
        self.pushgateway_url = pushgateway_url
        self.registry = CollectorRegistry()
        
        # Define test metrics
        self.test_watcher_running = Gauge(
            'test_watcher_is_running',
            'TestWatcher running status',
            registry=self.registry
        )
        self.test_watcher_errors = Counter(
            'test_watcher_errors_total',
            'TestWatcher errors',
            registry=self.registry
        )
        self.api_errors = Counter(
            'api_errors_total',
            'API errors',
            registry=self.registry
        )
        self.cpu_percent = Gauge(
            'system_cpu_percent',
            'CPU usage percent',
            registry=self.registry
        )
        self.memory_percent = Gauge(
            'system_memory_percent',
            'Memory usage percent',
            registry=self.registry
        )
        self.coverage_percent = Gauge(
            'audit_agent_coverage_percent',
            'Test coverage percent',
            registry=self.registry
        )
    
    def push_metrics(self):
        """Push metrics to Prometheus pushgateway"""
        try:
            push_to_gateway(
                self.pushgateway_url,
                job='alert_test',
                registry=self.registry
            )
            return True
        except Exception as e:
            print(f"Error pushing metrics: {e}")
            return False
    
    def test_testwatcher_down_alert(self):
        """Test TestWatcherDown alert (CRITICAL)"""
        print("\n🔴 Testing: TestWatcherDown (Critical)")
        print("Setting test_watcher_is_running = 0")
        
        self.test_watcher_running.set(0)
        
        if self.push_metrics():
            print("✓ Metrics pushed successfully")
            print("Alert should fire after 2 minutes")
            print("Check: http://localhost:9093/#/alerts")
        else:
            print("✗ Failed to push metrics")
    
    def test_high_error_rate_alert(self):
        """Test TestWatcherHighErrorRate alert (CRITICAL)"""
        print("\n🔴 Testing: TestWatcherHighErrorRate (Critical)")
        print("Incrementing errors rapidly...")
        
        for i in range(100):
            self.test_watcher_errors.inc()
            if i % 10 == 0:
                self.push_metrics()
                time.sleep(0.5)
        
        print("✓ Error rate increased")
        print("Alert should fire after 5 minutes if rate > 0.1/s")
        print("Check: http://localhost:9093/#/alerts")
    
    def test_high_cpu_alert(self):
        """Test HighCPUUsage alert (CRITICAL)"""
        print("\n🔴 Testing: HighCPUUsage (Critical)")
        print("Setting system_cpu_percent = 95")
        
        self.cpu_percent.set(95)
        
        if self.push_metrics():
            print("✓ Metrics pushed successfully")
            print("Alert should fire after 5 minutes")
            print("Check: http://localhost:9093/#/alerts")
    
    def test_high_memory_alert(self):
        """Test HighMemoryUsage alert (CRITICAL)"""
        print("\n🔴 Testing: HighMemoryUsage (Critical)")
        print("Setting system_memory_percent = 92")
        
        self.memory_percent.set(92)
        
        if self.push_metrics():
            print("✓ Metrics pushed successfully")
            print("Alert should fire after 5 minutes")
            print("Check: http://localhost:9093/#/alerts")
    
    def test_coverage_drop_alert(self):
        """Test TestCoverageDrop alert (CRITICAL)"""
        print("\n🔴 Testing: TestCoverageDrop (Critical)")
        print("Setting audit_agent_coverage_percent = 65 (from 85)")
        
        # First set normal coverage
        self.coverage_percent.set(85)
        self.push_metrics()
        print("✓ Set baseline coverage: 85%")
        time.sleep(5)
        
        # Then drop coverage
        self.coverage_percent.set(65)
        self.push_metrics()
        print("✓ Dropped coverage to: 65%")
        print("Alert should fire after 10 minutes")
        print("Check: http://localhost:9093/#/alerts")
    
    def test_api_errors_alert(self):
        """Test APIHighErrorRate alert (WARNING)"""
        print("\n🟡 Testing: APIHighErrorRate (Warning)")
        print("Incrementing API errors...")
        
        for i in range(50):
            self.api_errors.inc()
            if i % 10 == 0:
                self.push_metrics()
                time.sleep(0.5)
        
        print("✓ API error rate increased")
        print("Alert should fire after 10 minutes if rate > 10%")
        print("Check: http://localhost:9093/#/alerts")
    
    def test_warning_alerts(self):
        """Test warning-level alerts"""
        print("\n🟡 Testing: Warning Alerts")
        
        print("Setting elevated CPU: 75%")
        self.cpu_percent.set(75)
        
        print("Setting elevated memory: 80%")
        self.memory_percent.set(80)
        
        print("Setting low coverage: 75%")
        self.coverage_percent.set(75)
        
        if self.push_metrics():
            print("✓ Metrics pushed successfully")
            print("Alerts should fire after 10-15 minutes")
            print("Check: http://localhost:9093/#/alerts")
    
    def reset_to_normal(self):
        """Reset all metrics to normal values"""
        print("\n✅ Resetting to normal values...")
        
        self.test_watcher_running.set(1)
        self.cpu_percent.set(30)
        self.memory_percent.set(50)
        self.coverage_percent.set(85)
        
        if self.push_metrics():
            print("✓ Metrics reset to normal")
            print("Alerts should resolve automatically")
    
    def check_alertmanager_status(self):
        """Check AlertManager status"""
        print("\n📊 Checking AlertManager Status...")
        
        try:
            # Check AlertManager health
            response = requests.get('http://localhost:9093/-/healthy', timeout=5)
            if response.status_code == 200:
                print("✓ AlertManager is healthy")
            else:
                print(f"✗ AlertManager unhealthy: {response.status_code}")
            
            # Check active alerts
            response = requests.get('http://localhost:9093/api/v1/alerts', timeout=5)
            if response.status_code == 200:
                alerts = response.json()
                if alerts['data']:
                    print(f"\n🔔 Active alerts: {len(alerts['data'])}")
                    for alert in alerts['data'][:5]:  # Show first 5
                        print(f"  - {alert['labels']['alertname']} [{alert['labels']['severity']}]")
                else:
                    print("✓ No active alerts")
            else:
                print(f"✗ Could not fetch alerts: {response.status_code}")
        
        except requests.exceptions.ConnectionError:
            print("✗ Cannot connect to AlertManager")
            print("Make sure AlertManager is running: docker-compose up -d")
        except Exception as e:
            print(f"✗ Error checking AlertManager: {e}")
    
    def check_prometheus_rules(self):
        """Check Prometheus alert rules"""
        print("\n📋 Checking Prometheus Alert Rules...")
        
        try:
            response = requests.get('http://localhost:9090/api/v1/rules', timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'success':
                    groups = data['data']['groups']
                    print(f"✓ Loaded alert rule groups: {len(groups)}")
                    
                    total_rules = 0
                    for group in groups:
                        rules = [r for r in group['rules'] if r['type'] == 'alerting']
                        total_rules += len(rules)
                        print(f"  - {group['name']}: {len(rules)} rules")
                    
                    print(f"\nTotal alert rules: {total_rules}")
                else:
                    print("✗ Error fetching rules from Prometheus")
            else:
                print(f"✗ Prometheus returned status {response.status_code}")
        
        except requests.exceptions.ConnectionError:
            print("✗ Cannot connect to Prometheus")
            print("Make sure Prometheus is running: docker-compose up -d")
        except Exception as e:
            print(f"✗ Error checking Prometheus rules: {e}")


def main():
    """Main test menu"""
    tester = AlertTester()
    
    print("=" * 60)
    print("Alert Testing Script - Bybit Strategy Tester")
    print("=" * 60)
    
    while True:
        print("\n📋 Test Menu:")
        print("1. Check system status")
        print("2. Test CRITICAL: TestWatcherDown")
        print("3. Test CRITICAL: High error rate")
        print("4. Test CRITICAL: High CPU usage")
        print("5. Test CRITICAL: High memory usage")
        print("6. Test CRITICAL: Coverage drop")
        print("7. Test WARNING: API errors")
        print("8. Test WARNING: Elevated resources")
        print("9. Reset all to normal")
        print("0. Exit")
        
        choice = input("\nSelect test (0-9): ").strip()
        
        if choice == '0':
            print("\n👋 Exiting...")
            break
        elif choice == '1':
            tester.check_alertmanager_status()
            tester.check_prometheus_rules()
        elif choice == '2':
            tester.test_testwatcher_down_alert()
        elif choice == '3':
            tester.test_high_error_rate_alert()
        elif choice == '4':
            tester.test_high_cpu_alert()
        elif choice == '5':
            tester.test_high_memory_alert()
        elif choice == '6':
            tester.test_coverage_drop_alert()
        elif choice == '7':
            tester.test_api_errors_alert()
        elif choice == '8':
            tester.test_warning_alerts()
        elif choice == '9':
            tester.reset_to_normal()
        else:
            print("❌ Invalid choice")
        
        input("\nPress Enter to continue...")


if __name__ == '__main__':
    main()
