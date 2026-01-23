/**
 * 🤖 AI Assistant Module
 *
 * Provides AI-powered features for the frontend:
 * 1. AI Assistant floating panel for questions
 * 2. AI Backtest Analysis integration
 * 3. AI Optimization Analysis integration
 *
 * @version 1.0.0
 * @date 2026-01-18
 */

const AI_API_BASE = '/api/v1/agents/advanced';

/**
 * AI Analysis Result Interface
 */
class AIAnalysisResult {
    constructor(data) {
        this.metrics = data.metrics || {};
        this.ai_analysis = data.ai_analysis || {};
        this.metadata = data.metadata || {};
    }

    get summary() { return this.ai_analysis.summary || ''; }
    get riskAssessment() { return this.ai_analysis.risk_assessment || ''; }
    get recommendations() { return this.ai_analysis.recommendations || []; }
    get confidence() { return this.ai_analysis.confidence || 0; }
    get overfittingRisk() { return this.ai_analysis.overfitting_risk || 'unknown'; }
    get marketRegime() { return this.ai_analysis.market_regime_fit || 'unknown'; }
}

/**
 * AI Assistant Panel Manager
 */
class AIAssistant {
    constructor() {
        this.isOpen = false;
        this.isLoading = false;
        this.messages = [];
        this.panel = null;
        this.init();
    }

    init() {
        this.createPanel();
        this.createToggleButton();
        this.bindEvents();
    }

    createPanel() {
        const panel = document.createElement('div');
        panel.id = 'aiAssistantPanel';
        panel.className = 'ai-assistant-panel';
        panel.innerHTML = `
            <div class="ai-panel-header">
                <div class="ai-panel-title">
                    <span class="ai-icon">🤖</span>
                    <span>AI Trading Assistant</span>
                </div>
                <button class="ai-panel-close" id="aiPanelClose">×</button>
            </div>
            <div class="ai-panel-status">
                <span class="ai-status-dot online"></span>
                <span id="aiStatusText">DeepSeek + Perplexity Online</span>
            </div>
            <div class="ai-panel-messages" id="aiMessages">
                <div class="ai-message assistant">
                    <div class="ai-message-content">
                        👋 Привет! Я AI Trading Assistant.
                        Задайте мне вопрос о торговле, стратегиях, или попросите проанализировать результаты бэктеста.
                    </div>
                </div>
            </div>
            <div class="ai-panel-input">
                <textarea id="aiInput" placeholder="Спросите о стратегиях, индикаторах, рисках..." rows="2"></textarea>
                <button id="aiSend" class="ai-send-btn">
                    <i class="bi bi-send-fill"></i>
                </button>
            </div>
            <div class="ai-panel-suggestions">
                <button class="ai-suggestion" data-q="Какие индикаторы лучше для BTC?">📊 Индикаторы BTC</button>
                <button class="ai-suggestion" data-q="Оптимальные стоп-лоссы для фьючерсов">📉 Stop-Loss</button>
                <button class="ai-suggestion" data-q="Как определить тренд на рынке?">📈 Тренды</button>
            </div>
        `;

        document.body.appendChild(panel);
        this.panel = panel;
    }

    createToggleButton() {
        const btn = document.createElement('button');
        btn.id = 'aiAssistantToggle';
        btn.className = 'ai-toggle-btn';
        btn.innerHTML = '🤖';
        btn.title = 'AI Trading Assistant';
        document.body.appendChild(btn);
    }

    bindEvents() {
        // Toggle button
        document.getElementById('aiAssistantToggle').addEventListener('click', () => this.toggle());

        // Close button
        document.getElementById('aiPanelClose').addEventListener('click', () => this.close());

        // Send button
        document.getElementById('aiSend').addEventListener('click', () => this.sendMessage());

        // Enter key
        document.getElementById('aiInput').addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Suggestions
        document.querySelectorAll('.ai-suggestion').forEach(btn => {
            btn.addEventListener('click', () => {
                document.getElementById('aiInput').value = btn.dataset.q;
                this.sendMessage();
            });
        });
    }

    toggle() {
        this.isOpen ? this.close() : this.open();
    }

    open() {
        this.panel.classList.add('open');
        this.isOpen = true;
        document.getElementById('aiInput').focus();
    }

    close() {
        this.panel.classList.remove('open');
        this.isOpen = false;
    }

    async sendMessage() {
        const input = document.getElementById('aiInput');
        const question = input.value.trim();

        if (!question || this.isLoading) return;

        // Add user message
        this.addMessage('user', question);
        input.value = '';

        // Show loading
        this.isLoading = true;
        const loadingId = this.addMessage('assistant', '🤔 Анализирую...', true);

        try {
            const response = await fetch(`${AI_API_BASE}/deliberate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    question: question,
                    agents: ['deepseek'],
                    max_rounds: 1,
                    min_confidence: 0.5,
                    voting_strategy: 'weighted'
                })
            });

            const data = await response.json();

            // Remove loading message
            this.removeMessage(loadingId);

            if (response.ok) {
                const answer = data.decision || 'Не удалось получить ответ';
                const confidence = (data.confidence * 100).toFixed(0);
                this.addMessage('assistant', `${answer}\n\n📊 Уверенность: ${confidence}%`);
            } else {
                this.addMessage('assistant', `❌ Ошибка: ${data.detail || 'Неизвестная ошибка'}`);
            }
        } catch (error) {
            this.removeMessage(loadingId);
            this.addMessage('assistant', `❌ Ошибка соединения: ${error.message}`);
        }

        this.isLoading = false;
    }

    addMessage(role, content, isLoading = false) {
        const messagesContainer = document.getElementById('aiMessages');
        const id = `msg-${Date.now()}`;

        const msg = document.createElement('div');
        msg.id = id;
        msg.className = `ai-message ${role}${isLoading ? ' loading' : ''}`;
        msg.innerHTML = `<div class="ai-message-content">${content.replace(/\n/g, '<br>')}</div>`;

        messagesContainer.appendChild(msg);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        return id;
    }

    removeMessage(id) {
        const msg = document.getElementById(id);
        if (msg) msg.remove();
    }
}

/**
 * AI Backtest Analysis Manager
 */
class AIBacktestAnalyzer {
    constructor() {
        this.currentAnalysis = null;
    }

    /**
     * Analyze backtest results with AI
     * @param {Object} metrics - Backtest metrics
     * @param {Object} config - Backtest config (strategy, symbol, etc.)
     * @returns {Promise<AIAnalysisResult>}
     */
    async analyze(metrics, config) {
        const requestBody = {
            metrics: {
                net_pnl: metrics.net_pnl || metrics.netPnl || 0,
                total_return_pct: metrics.total_return_pct || metrics.totalReturnPct || 0,
                sharpe_ratio: metrics.sharpe_ratio || metrics.sharpeRatio || 0,
                max_drawdown_pct: metrics.max_drawdown_pct || metrics.maxDrawdownPct || 0,
                win_rate: metrics.win_rate || metrics.winRate || 0,
                profit_factor: metrics.profit_factor || metrics.profitFactor || 1,
                total_trades: metrics.total_trades || metrics.totalTrades || 0
            },
            strategy_name: config.strategyName || config.strategy_name || 'Unknown',
            symbol: config.symbol || 'BTCUSDT',
            timeframe: config.timeframe || config.interval || '1h',
            period: config.period || 'Unknown',
            agents: ['deepseek']
        };

        try {
            const response = await fetch(`${AI_API_BASE}/analyze-backtest`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestBody)
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            this.currentAnalysis = new AIAnalysisResult(data);
            return this.currentAnalysis;
        } catch (error) {
            console.error('AI Analysis failed:', error);
            throw error;
        }
    }

    /**
     * Create AI Analysis button for backtest results
     * @param {HTMLElement} container - Container element
     * @param {Object} metrics - Backtest metrics
     * @param {Object} config - Backtest config
     */
    createAnalysisButton(container, metrics, config) {
        const btn = document.createElement('button');
        btn.className = 'ai-analysis-btn';
        btn.innerHTML = '🤖 AI Analysis';
        btn.title = 'Get AI-powered analysis of this backtest';

        btn.addEventListener('click', async () => {
            btn.disabled = true;
            btn.innerHTML = '🤖 Analyzing...';

            try {
                const result = await this.analyze(metrics, config);
                this.showAnalysisModal(result, config);
            } catch (error) {
                alert('AI Analysis failed: ' + error.message);
            }

            btn.disabled = false;
            btn.innerHTML = '🤖 AI Analysis';
        });

        container.appendChild(btn);
        return btn;
    }

    /**
     * Show analysis result in modal
     * @param {AIAnalysisResult} result
     * @param {Object} config
     */
    showAnalysisModal(result, config) {
        // Remove existing modal
        const existing = document.getElementById('aiAnalysisModal');
        if (existing) existing.remove();

        const overfitClass = {
            'low': 'success',
            'medium': 'warning',
            'high': 'danger'
        }[result.overfittingRisk] || 'info';

        const modal = document.createElement('div');
        modal.id = 'aiAnalysisModal';
        modal.className = 'ai-modal';
        modal.innerHTML = `
            <div class="ai-modal-content">
                <div class="ai-modal-header">
                    <h2>🤖 AI Analysis: ${config.strategyName || 'Strategy'}</h2>
                    <button class="ai-modal-close" onclick="this.closest('.ai-modal').remove()">×</button>
                </div>
                <div class="ai-modal-body">
                    <div class="ai-section">
                        <h3>📊 Summary</h3>
                        <p>${result.summary || 'No summary available'}</p>
                    </div>

                    <div class="ai-section">
                        <h3>⚠️ Risk Assessment</h3>
                        <p>${result.riskAssessment || 'No risk assessment available'}</p>
                    </div>

                    <div class="ai-section">
                        <h3>💡 Recommendations</h3>
                        <ul>
                            ${result.recommendations.map(r => `<li>${r}</li>`).join('') || '<li>No recommendations</li>'}
                        </ul>
                    </div>

                    <div class="ai-metrics-grid">
                        <div class="ai-metric">
                            <span class="ai-metric-label">Overfitting Risk</span>
                            <span class="ai-metric-value badge ${overfitClass}">${result.overfittingRisk}</span>
                        </div>
                        <div class="ai-metric">
                            <span class="ai-metric-label">Market Regime Fit</span>
                            <span class="ai-metric-value">${result.marketRegime}</span>
                        </div>
                        <div class="ai-metric">
                            <span class="ai-metric-label">AI Confidence</span>
                            <span class="ai-metric-value">${(result.confidence * 100).toFixed(0)}%</span>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Close on backdrop click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.remove();
        });

        // Close on Escape
        document.addEventListener('keydown', function closeOnEsc(e) {
            if (e.key === 'Escape') {
                modal.remove();
                document.removeEventListener('keydown', closeOnEsc);
            }
        });
    }
}

// Global instances
let aiAssistant = null;
let aiBacktestAnalyzer = null;

/**
 * Initialize AI features
 */
function initAIFeatures() {
    // Initialize AI Assistant
    aiAssistant = new AIAssistant();

    // Initialize AI Backtest Analyzer
    aiBacktestAnalyzer = new AIBacktestAnalyzer();

    console.log('🤖 AI Features initialized');
}

// Auto-init on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAIFeatures);
} else {
    initAIFeatures();
}

// Export for use in other modules
window.aiAssistant = () => aiAssistant;
window.aiBacktestAnalyzer = () => aiBacktestAnalyzer;
window.AIBacktestAnalyzer = AIBacktestAnalyzer;
window.AIAssistant = AIAssistant;