/**
 * 📄 Ml Models Page JavaScript
 * 
 * Page-specific scripts for ml_models.html
 * Extracted during Phase 1 Week 3: JS Extraction
 * 
 * @version 1.0.0
 * @date 2025-12-21
 */

// Import shared utilities
import { apiClient, API_CONFIG } from '../api.js';
import { formatNumber, formatCurrency, formatDate, debounce } from '../utils.js';

// Sample data
        const models = [
            {
                id: 'mdl_001',
                name: 'BTC_Trend_Classifier',
                type: 'XGBoost',
                taskType: 'classification',
                status: 'active',
                accuracy: 0.892,
                predictions: 15234,
                lastUpdated: '2025-12-13T10:30:00Z',
                features: ['rsi', 'macd', 'volume', 'price_change'],
                version: '2.1.0'
            },
            {
                id: 'mdl_002',
                name: 'ETH_Price_Regressor',
                type: 'LightGBM',
                taskType: 'regression',
                status: 'active',
                accuracy: 0.856,
                predictions: 12456,
                lastUpdated: '2025-12-13T09:15:00Z',
                features: ['rsi', 'bollinger', 'volume'],
                version: '1.5.0'
            },
            {
                id: 'mdl_003',
                name: 'Multi_Asset_Ensemble',
                type: 'Ensemble',
                taskType: 'classification',
                status: 'training',
                accuracy: 0.823,
                predictions: 8934,
                lastUpdated: '2025-12-13T08:00:00Z',
                features: ['rsi', 'macd', 'atr', 'obv'],
                version: '3.0.0'
            },
            {
                id: 'mdl_004',
                name: 'SOL_LSTM_Predictor',
                type: 'LSTM',
                taskType: 'regression',
                status: 'active',
                accuracy: 0.871,
                predictions: 5678,
                lastUpdated: '2025-12-12T22:45:00Z',
                features: ['price_sequence', 'volume_sequence'],
                version: '1.0.0'
            },
            {
                id: 'mdl_005',
                name: 'Volatility_Detector',
                type: 'Random Forest',
                taskType: 'classification',
                status: 'inactive',
                accuracy: 0.765,
                predictions: 3421,
                lastUpdated: '2025-12-10T14:20:00Z',
                features: ['atr', 'bollinger_width', 'volume_std'],
                version: '1.2.0'
            }
        ];

        const trainingHistory = [
            { id: 1, model: 'BTC_Trend_Classifier', status: 'success', time: '10 minutes ago', message: 'Training completed - accuracy improved to 89.2%' },
            { id: 2, model: 'Multi_Asset_Ensemble', status: 'warning', time: '2 hours ago', message: 'Training in progress - 67% complete' },
            { id: 3, model: 'ETH_Price_Regressor', status: 'success', time: '5 hours ago', message: 'Model retrained with new data' },
            { id: 4, model: 'Volatility_Detector', status: 'error', time: '1 day ago', message: 'Training failed - insufficient data' }
        ];

        const recentPredictions = [
            { symbol: 'BTCUSDT', direction: 'long', confidence: 0.87, target: 105000, model: 'BTC_Trend_Classifier' },
            { symbol: 'ETHUSDT', direction: 'short', confidence: 0.72, target: 3800, model: 'ETH_Price_Regressor' },
            { symbol: 'SOLUSDT', direction: 'long', confidence: 0.81, target: 250, model: 'SOL_LSTM_Predictor' }
        ];

        let selectedModel = null;

        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            renderModelsTable();
            renderTrainingHistory();
            renderRecentPredictions();
            setupEventListeners();
        });

        function setupEventListeners() {
            document.getElementById('modelSearch').addEventListener('input', filterModels);
            document.getElementById('modelTypeFilter').addEventListener('change', filterModels);
        }

        function renderModelsTable() {
            const tbody = document.getElementById('modelsTableBody');
            tbody.innerHTML = models.map(model => `
                <tr onclick="selectModel('${model.id}')" style="cursor: pointer">
                    <td>
                        <div class="model-name">
                            <div class="model-icon">
                                <i class="bi bi-${getModelIcon(model.type)}"></i>
                            </div>
                            <div class="model-info">
                                <span class="model-title">${model.name}</span>
                                <span class="model-type">${model.type}</span>
                            </div>
                        </div>
                    </td>
                    <td>
                        <span class="status-badge ${model.status}">${capitalize(model.status)}</span>
                    </td>
                    <td>
                        <div class="d-flex align-items-center gap-2">
                            <div class="accuracy-bar">
                                <div class="accuracy-fill ${getAccuracyClass(model.accuracy)}" style="width: ${model.accuracy * 100}%"></div>
                            </div>
                            <span>${(model.accuracy * 100).toFixed(1)}%</span>
                        </div>
                    </td>
                    <td>${formatNumber(model.predictions)}</td>
                    <td>${formatRelativeTime(model.lastUpdated)}</td>
                    <td>
                        <div class="d-flex gap-1">
                            <button class="btn btn-secondary btn-sm" onclick="event.stopPropagation(); trainModel('${model.id}')" title="Train">
                                <i class="bi bi-play-fill"></i>
                            </button>
                            <button class="btn btn-secondary btn-sm" onclick="event.stopPropagation(); viewMetrics('${model.id}')" title="Metrics">
                                <i class="bi bi-graph-up"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `).join('');
        }

        function selectModel(modelId) {
            selectedModel = models.find(m => m.id === modelId);
            renderModelDetails();
        }

        function renderModelDetails() {
            if (!selectedModel) return;

            const content = document.getElementById('modelDetailsContent');
            content.innerHTML = `
                <div class="model-details">
                    <div class="detail-item">
                        <span class="detail-label">Name</span>
                        <span class="detail-value">${selectedModel.name}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Type</span>
                        <span class="detail-value">${selectedModel.type}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Task</span>
                        <span class="detail-value">${capitalize(selectedModel.taskType)}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Version</span>
                        <span class="detail-value">${selectedModel.version}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Accuracy</span>
                        <span class="detail-value">${(selectedModel.accuracy * 100).toFixed(1)}%</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Features</span>
                        <span class="detail-value">${selectedModel.features.length} features</span>
                    </div>
                </div>
                <div class="d-flex gap-2">
                    <button class="btn btn-primary flex-grow-1" onclick="trainModel('${selectedModel.id}')">
                        <i class="bi bi-play-fill"></i> Train
                    </button>
                    <button class="btn btn-secondary flex-grow-1" onclick="deployModel('${selectedModel.id}')">
                        <i class="bi bi-cloud-upload"></i> Deploy
                    </button>
                </div>
            `;
        }

        function renderTrainingHistory() {
            const container = document.getElementById('trainingHistory');
            container.innerHTML = trainingHistory.map(item => `
                <div class="training-item">
                    <div class="training-icon ${item.status}">
                        <i class="bi bi-${getStatusIcon(item.status)}"></i>
                    </div>
                    <div class="training-info">
                        <div class="training-title">${item.model}</div>
                        <div class="training-time">${item.time} - ${item.message}</div>
                    </div>
                </div>
            `).join('');
        }

        function renderRecentPredictions() {
            const container = document.getElementById('recentPredictions');
            container.innerHTML = recentPredictions.map(pred => `
                <div class="prediction-card">
                    <div class="prediction-header">
                        <span class="prediction-symbol">${pred.symbol}</span>
                        <span class="prediction-direction ${pred.direction}">
                            <i class="bi bi-arrow-${pred.direction === 'long' ? 'up' : 'down'}-circle-fill"></i>
                            ${pred.direction.toUpperCase()}
                        </span>
                    </div>
                    <div class="prediction-metrics">
                        <div class="prediction-metric">
                            <div class="prediction-metric-value">${(pred.confidence * 100).toFixed(0)}%</div>
                            <div class="prediction-metric-label">Confidence</div>
                        </div>
                        <div class="prediction-metric">
                            <div class="prediction-metric-value">$${formatNumber(pred.target)}</div>
                            <div class="prediction-metric-label">Target</div>
                        </div>
                    </div>
                </div>
            `).join('');
        }

        function filterModels() {
            const search = document.getElementById('modelSearch').value.toLowerCase();
            const typeFilter = document.getElementById('modelTypeFilter').value;
            
            const filtered = models.filter(model => {
                const matchesSearch = model.name.toLowerCase().includes(search) || 
                                     model.type.toLowerCase().includes(search);
                const matchesType = !typeFilter || model.taskType === typeFilter;
                return matchesSearch && matchesType;
            });

            renderFilteredModels(filtered);
        }

        function renderFilteredModels(filteredModels) {
            const tbody = document.getElementById('modelsTableBody');
            if (filteredModels.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="text-center text-secondary p-4">No models found</td></tr>';
                return;
            }
            
            tbody.innerHTML = filteredModels.map(model => `
                <tr onclick="selectModel('${model.id}')" style="cursor: pointer">
                    <td>
                        <div class="model-name">
                            <div class="model-icon">
                                <i class="bi bi-${getModelIcon(model.type)}"></i>
                            </div>
                            <div class="model-info">
                                <span class="model-title">${model.name}</span>
                                <span class="model-type">${model.type}</span>
                            </div>
                        </div>
                    </td>
                    <td>
                        <span class="status-badge ${model.status}">${capitalize(model.status)}</span>
                    </td>
                    <td>
                        <div class="d-flex align-items-center gap-2">
                            <div class="accuracy-bar">
                                <div class="accuracy-fill ${getAccuracyClass(model.accuracy)}" style="width: ${model.accuracy * 100}%"></div>
                            </div>
                            <span>${(model.accuracy * 100).toFixed(1)}%</span>
                        </div>
                    </td>
                    <td>${formatNumber(model.predictions)}</td>
                    <td>${formatRelativeTime(model.lastUpdated)}</td>
                    <td>
                        <div class="d-flex gap-1">
                            <button class="btn btn-secondary btn-sm" onclick="event.stopPropagation(); trainModel('${model.id}')" title="Train">
                                <i class="bi bi-play-fill"></i>
                            </button>
                            <button class="btn btn-secondary btn-sm" onclick="event.stopPropagation(); viewMetrics('${model.id}')" title="Metrics">
                                <i class="bi bi-graph-up"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `).join('');
        }

        // Modal functions
        function openNewModelModal() {
            document.getElementById('newModelModal').classList.add('active');
        }

        function closeNewModelModal() {
            document.getElementById('newModelModal').classList.remove('active');
        }

        async function createModel() {
            const name = document.getElementById('modelName').value;
            const type = document.getElementById('modelType').value;
            const taskType = document.getElementById('taskType').value;
            const symbol = document.getElementById('targetSymbol').value;
            const description = document.getElementById('modelDescription').value;

            if (!name) {
                alert('Please enter a model name');
                return;
            }

            try {
                const response = await fetch('/api/enhanced-ml/registry/models', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name,
                        model_type: type,
                        task_type: taskType,
                        symbol,
                        description
                    })
                });

                if (response.ok) {
                    alert('Model created successfully!');
                    closeNewModelModal();
                    refreshModels();
                } else {
                    const error = await response.json();
                    alert(`Error: ${error.detail || 'Failed to create model'}`);
                }
            } catch (err) {
                console.error('Error creating model:', err);
                alert('Model created (demo mode)');
                closeNewModelModal();
            }
        }

        async function trainModel(modelId) {
            const model = models.find(m => m.id === modelId);
            alert(`Starting training for ${model.name}...`);
        }

        async function deployModel(modelId) {
            const model = models.find(m => m.id === modelId);
            alert(`Deploying ${model.name} to production...`);
        }

        function viewMetrics(modelId) {
            const model = models.find(m => m.id === modelId);
            selectModel(modelId);
        }

        function refreshModels() {
            renderModelsTable();
            renderTrainingHistory();
            renderRecentPredictions();
        }

        // Helper functions
        function getModelIcon(type) {
            const icons = {
                'XGBoost': 'diagram-3',
                'LightGBM': 'lightning',
                'Random Forest': 'tree',
                'LSTM': 'layers',
                'Neural Network': 'cpu',
                'Ensemble': 'collection'
            };
            return icons[type] || 'box';
        }

        function getAccuracyClass(accuracy) {
            if (accuracy >= 0.85) return 'high';
            if (accuracy >= 0.70) return 'medium';
            return 'low';
        }

        function getStatusIcon(status) {
            const icons = {
                'success': 'check-circle-fill',
                'warning': 'clock-fill',
                'error': 'x-circle-fill'
            };
            return icons[status] || 'circle';
        }

        function capitalize(str) {
            return str.charAt(0).toUpperCase() + str.slice(1);
        }
        // formatNumber - using imported version from utils.js

        function formatRelativeTime(dateStr) {
            const date = new Date(dateStr);
            const now = new Date();
            const diff = now - date;
            
            const minutes = Math.floor(diff / 60000);
            const hours = Math.floor(diff / 3600000);
            const days = Math.floor(diff / 86400000);
            
            if (minutes < 60) return `${minutes}m ago`;
            if (hours < 24) return `${hours}h ago`;
            return `${days}d ago`;
        }

// ============================================
// EXPORTS
// ============================================

// Export functions for potential external use
// Exported functions: setupEventListeners, renderModelsTable, selectModel, renderModelDetails, renderTrainingHistory

// Attach to window for backwards compatibility
if (typeof window !== 'undefined') {
    window.mlmodelsPage = {
        // Add public methods here
    };
}
