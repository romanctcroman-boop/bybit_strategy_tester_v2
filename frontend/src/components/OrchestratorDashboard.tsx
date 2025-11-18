import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { RefreshCw, CheckCircle, XCircle, AlertTriangle } from './icons';

/**
 * 📊 Orchestrator Dashboard
 *
 * Displays real-time status of:
 * - Plugin Manager (loaded plugins, active/disabled)
 * - Priority System (statistics, metrics)
 * - System health
 */

interface Plugin {
  metadata: {
    name: string;
    version: string;
    author: string;
    description: string;
  };
  lifecycle: string;
  loaded_at: string;
  error_count: number;
  last_error: string | null;
}

interface PluginStats {
  total_plugins: number;
  active_plugins: number;
  disabled_plugins: number;
  hooks_registered: Record<string, number>;
  auto_reload: boolean;
}

interface SystemStatus {
  success: boolean;
  timestamp: string;
  plugin_manager: {
    initialized: boolean;
    statistics: PluginStats;
  };
  priority_system: {
    intelligent_prioritization: string;
    features: string[];
  };
  mcp_server: {
    version: string;
    providers_ready: boolean;
    deepseek_agent: boolean;
  };
}

export default function OrchestratorDashboard() {
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [loading, setLoading] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  // Fetch system status
  const fetchSystemStatus = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/orchestrator/system-status');
      const data = await response.json();
      setSystemStatus(data);
      setLastUpdate(new Date());
    } catch (error) {
      console.error('Failed to fetch system status:', error);
    } finally {
      setLoading(false);
    }
  };

  // Fetch plugins list
  const fetchPlugins = async () => {
    try {
      const response = await fetch('/api/orchestrator/plugins');
      const data = await response.json();
      if (data.success) {
        setPlugins(data.plugins);
      }
    } catch (error) {
      console.error('Failed to fetch plugins:', error);
    }
  };

  // Reload specific plugin
  const reloadPlugin = async (pluginName: string) => {
    try {
      const response = await fetch(`/api/orchestrator/plugins/${pluginName}/reload`, {
        method: 'POST',
      });
      const data = await response.json();
      if (data.success) {
        // Refresh plugins list
        await fetchPlugins();
      }
    } catch (error) {
      console.error(`Failed to reload plugin ${pluginName}:`, error);
    }
  };

  // Auto-refresh every 30 seconds
  useEffect(() => {
    fetchSystemStatus();
    fetchPlugins();

    const interval = setInterval(() => {
      fetchSystemStatus();
      fetchPlugins();
    }, 30000); // 30 seconds

    return () => clearInterval(interval);
  }, []);

  const getLifecycleBadge = (lifecycle: string) => {
    switch (lifecycle.toLowerCase()) {
      case 'active':
        return (
          <Badge className="bg-green-500">
            <CheckCircle className="w-3 h-3 mr-1" /> Active
          </Badge>
        );
      case 'disabled':
        return (
          <Badge className="bg-gray-500">
            <XCircle className="w-3 h-3 mr-1" /> Disabled
          </Badge>
        );
      case 'error':
        return (
          <Badge className="bg-red-500">
            <AlertTriangle className="w-3 h-3 mr-1" /> Error
          </Badge>
        );
      default:
        return <Badge>{lifecycle}</Badge>;
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">🎯 Orchestrator Dashboard</h1>
          <p className="text-gray-500">Plugin Manager & Priority System Monitoring</p>
        </div>
        <div className="flex gap-2 items-center">
          {lastUpdate && (
            <span className="text-sm text-gray-500">
              Last update: {lastUpdate.toLocaleTimeString()}
            </span>
          )}
          <Button onClick={fetchSystemStatus} disabled={loading}>
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* System Status Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">🔌 Plugin Manager</CardTitle>
          </CardHeader>
          <CardContent>
            {systemStatus?.plugin_manager.initialized ? (
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-gray-600">Total Plugins:</span>
                  <span className="font-bold">
                    {systemStatus.plugin_manager.statistics.total_plugins}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Active:</span>
                  <span className="font-bold text-green-600">
                    {systemStatus.plugin_manager.statistics.active_plugins}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Disabled:</span>
                  <span className="font-bold text-gray-600">
                    {systemStatus.plugin_manager.statistics.disabled_plugins}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Auto-Reload:</span>
                  <span className="font-bold">
                    {systemStatus.plugin_manager.statistics.auto_reload
                      ? '✅ Enabled'
                      : '❌ Disabled'}
                  </span>
                </div>
              </div>
            ) : (
              <p className="text-yellow-600">Not initialized</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">⚡ Priority System</CardTitle>
          </CardHeader>
          <CardContent>
            {systemStatus?.priority_system ? (
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-gray-600">Status:</span>
                  <Badge className="bg-green-500">
                    {systemStatus.priority_system.intelligent_prioritization}
                  </Badge>
                </div>
                <div className="text-sm text-gray-600 mt-3">
                  <strong>Features:</strong>
                  <ul className="list-disc list-inside mt-1 space-y-1">
                    {systemStatus.priority_system.features.slice(0, 3).map((feature, idx) => (
                      <li key={idx} className="text-xs">
                        {feature}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            ) : (
              <p className="text-gray-500">Loading...</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">💚 MCP Server</CardTitle>
          </CardHeader>
          <CardContent>
            {systemStatus?.mcp_server ? (
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-gray-600">Version:</span>
                  <span className="font-bold">{systemStatus.mcp_server.version}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Providers:</span>
                  <Badge
                    className={
                      systemStatus.mcp_server.providers_ready ? 'bg-green-500' : 'bg-red-500'
                    }
                  >
                    {systemStatus.mcp_server.providers_ready ? 'Ready' : 'Not Ready'}
                  </Badge>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">DeepSeek:</span>
                  <Badge
                    className={
                      systemStatus.mcp_server.deepseek_agent ? 'bg-green-500' : 'bg-red-500'
                    }
                  >
                    {systemStatus.mcp_server.deepseek_agent ? 'Active' : 'Inactive'}
                  </Badge>
                </div>
              </div>
            ) : (
              <p className="text-gray-500">Loading...</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Plugins List */}
      <Card>
        <CardHeader>
          <CardTitle>📦 Loaded Plugins</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {plugins.length > 0 ? (
              plugins.map((plugin, idx) => (
                <div key={idx} className="border rounded-lg p-4 flex justify-between items-center">
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="font-bold text-lg">{plugin.metadata.name}</h3>
                      {getLifecycleBadge(plugin.lifecycle)}
                      <span className="text-sm text-gray-500">v{plugin.metadata.version}</span>
                    </div>
                    <p className="text-sm text-gray-600 mt-1">{plugin.metadata.description}</p>
                    <div className="flex gap-4 mt-2 text-xs text-gray-500">
                      <span>Author: {plugin.metadata.author}</span>
                      <span>Loaded: {new Date(plugin.loaded_at).toLocaleString()}</span>
                      {plugin.error_count > 0 && (
                        <span className="text-red-500">Errors: {plugin.error_count}</span>
                      )}
                    </div>
                    {plugin.last_error && (
                      <div className="mt-2 text-xs text-red-500 bg-red-50 p-2 rounded">
                        Last error: {plugin.last_error}
                      </div>
                    )}
                  </div>
                  <div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => reloadPlugin(plugin.metadata.name)}
                    >
                      <RefreshCw className="w-3 h-3 mr-1" />
                      Reload
                    </Button>
                  </div>
                </div>
              ))
            ) : (
              <p className="text-gray-500 text-center py-4">No plugins loaded</p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Hooks Registration */}
      {systemStatus?.plugin_manager.statistics.hooks_registered && (
        <Card>
          <CardHeader>
            <CardTitle>🎣 Hook Registration</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {Object.entries(systemStatus.plugin_manager.statistics.hooks_registered).map(
                ([hook, count]) => (
                  <div key={hook} className="border rounded p-3">
                    <div className="text-sm text-gray-600">{hook}</div>
                    <div className="text-2xl font-bold">{count}</div>
                    <div className="text-xs text-gray-500">plugins subscribed</div>
                  </div>
                )
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
