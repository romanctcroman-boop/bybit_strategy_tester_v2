/**
 * Strategy Builder Templates
 *
 * P1-3: Centralized template definitions extracted from strategy_builder.js
 * for reuse across pages and easier maintenance.
 *
 * Each template describes a visual block-based strategy configuration.
 * The `id` must match a handler in the strategy_builder apply-template logic.
 *
 * @version 1.0.0
 * @date 2026-02-27
 */

/**
 * @typedef {Object} StrategyTemplate
 * @property {string} id           - Unique template identifier
 * @property {string} name         - Display name
 * @property {string} desc         - Short description
 * @property {string} icon         - Bootstrap Icons name (without bi-)
 * @property {string} iconColor    - CSS color variable
 * @property {number} blocks       - Number of visual blocks
 * @property {number} connections  - Number of connections
 * @property {string} category     - Category: Mean Reversion | Trend Following | Momentum | DCA | Grid | Volatility | Advanced | Scalping
 * @property {string} difficulty   - Beginner | Intermediate | Advanced | Expert
 * @property {string} expectedWinRate - Win-rate range string e.g. "45-55%"
 */

/** @type {StrategyTemplate[]} */
export const STRATEGY_TEMPLATES = [
    // =============================================
    // MEAN REVERSION STRATEGIES
    // =============================================
    {
        id: 'rsi_oversold',
        name: 'RSI Cross Level',
        desc: 'Long when RSI crosses up through 30, short when crosses down through 70',
        icon: 'graph-up',
        iconColor: 'var(--accent-blue)',
        blocks: 2,
        connections: 4,
        category: 'Mean Reversion',
        difficulty: 'Beginner',
        expectedWinRate: '45-55%'
    },
    {
        id: 'rsi_long_short',
        name: 'RSI Range Filter',
        desc: 'Long when RSI in low range (1-30), Short when RSI in high range (70-100)',
        icon: 'arrow-up-down',
        iconColor: 'var(--accent-green)',
        blocks: 2,
        connections: 4,
        category: 'Mean Reversion',
        difficulty: 'Beginner',
        expectedWinRate: '40-50%'
    },
    {
        id: 'bollinger_bounce',
        name: 'Bollinger Bounce',
        desc: 'Trade bounces off Bollinger Band boundaries',
        icon: 'distribute-vertical',
        iconColor: 'var(--accent-yellow)',
        blocks: 5,
        connections: 8,
        category: 'Mean Reversion',
        difficulty: 'Intermediate',
        expectedWinRate: '50-60%'
    },
    {
        id: 'stochastic_oversold',
        name: 'Stochastic Reversal',
        desc: 'Trade oversold/overbought with K/D crossover confirmation',
        icon: 'percent',
        iconColor: 'var(--accent-cyan)',
        blocks: 10,
        connections: 16,
        category: 'Mean Reversion',
        difficulty: 'Intermediate',
        expectedWinRate: '45-55%'
    },

    // =============================================
    // TREND FOLLOWING STRATEGIES
    // =============================================
    {
        id: 'macd_crossover',
        name: 'MACD Crossover',
        desc: 'Trade MACD line crossovers with signal line',
        icon: 'bar-chart',
        iconColor: 'var(--accent-purple)',
        blocks: 4,
        connections: 8,
        category: 'Trend Following',
        difficulty: 'Beginner',
        expectedWinRate: '40-50%'
    },
    {
        id: 'ema_crossover',
        name: 'EMA Crossover',
        desc: 'Classic dual EMA crossover strategy',
        icon: 'graph-up-arrow',
        iconColor: 'var(--accent-green)',
        blocks: 5,
        connections: 8,
        category: 'Trend Following',
        difficulty: 'Beginner',
        expectedWinRate: '35-45%'
    },
    {
        id: 'supertrend_follow',
        name: 'SuperTrend Follower',
        desc: 'Follow SuperTrend direction with ATR-based stops',
        icon: 'arrow-up-right-circle',
        iconColor: 'var(--accent-teal)',
        blocks: 5,
        connections: 8,
        category: 'Trend Following',
        difficulty: 'Beginner',
        expectedWinRate: '40-50%'
    },
    {
        id: 'triple_ema',
        name: 'Triple EMA System',
        desc: 'EMA 9/21/55 with trend confirmation',
        icon: 'layers',
        iconColor: 'var(--accent-indigo)',
        blocks: 10,
        connections: 16,
        category: 'Trend Following',
        difficulty: 'Intermediate',
        expectedWinRate: '45-55%'
    },
    {
        id: 'ichimoku_cloud',
        name: 'Ichimoku Cloud Strategy',
        desc: 'Trade with Ichimoku cloud, TK cross and Chikou confirmation',
        icon: 'cloud',
        iconColor: 'var(--accent-pink)',
        blocks: 9,
        connections: 16,
        category: 'Trend Following',
        difficulty: 'Advanced',
        expectedWinRate: '50-60%'
    },

    // =============================================
    // MOMENTUM STRATEGIES
    // =============================================
    {
        id: 'breakout',
        name: 'Breakout Strategy',
        desc: 'Trade breakouts from consolidation ranges',
        icon: 'arrows-expand',
        iconColor: 'var(--accent-orange)',
        blocks: 5,
        connections: 8,
        category: 'Momentum',
        difficulty: 'Intermediate',
        expectedWinRate: '35-45%'
    },
    {
        id: 'donchian_breakout',
        name: 'Donchian Channel Breakout',
        desc: 'Classic turtle trading - buy 20-day high, sell 10-day low',
        icon: 'box-arrow-up',
        iconColor: 'var(--accent-amber)',
        blocks: 8,
        connections: 12,
        category: 'Momentum',
        difficulty: 'Intermediate',
        expectedWinRate: '35-45%'
    },
    {
        id: 'volume_breakout',
        name: 'Volume Breakout',
        desc: 'Enter on price breakout with volume confirmation',
        icon: 'bar-chart-steps',
        iconColor: 'var(--accent-lime)',
        blocks: 11,
        connections: 16,
        category: 'Momentum',
        difficulty: 'Intermediate',
        expectedWinRate: '40-50%'
    },

    // =============================================
    // DCA STRATEGIES
    // =============================================
    {
        id: 'simple_dca',
        name: 'Simple DCA Bot',
        desc: 'Dollar cost averaging with safety orders on price drops',
        icon: 'grid-3x3',
        iconColor: 'var(--accent-blue)',
        blocks: 6,
        connections: 8,
        category: 'DCA',
        difficulty: 'Intermediate',
        expectedWinRate: '65-75%'
    },
    {
        id: 'rsi_dca',
        name: 'RSI DCA Strategy',
        desc: 'DCA entries only when RSI is oversold',
        icon: 'plus-circle',
        iconColor: 'var(--accent-green)',
        blocks: 9,
        connections: 12,
        category: 'DCA',
        difficulty: 'Intermediate',
        expectedWinRate: '60-70%'
    },

    // =============================================
    // GRID STRATEGIES
    // =============================================
    {
        id: 'grid_trading',
        name: 'Grid Trading Bot',
        desc: 'Place grid of orders within price range',
        icon: 'grid',
        iconColor: 'var(--accent-purple)',
        blocks: 7,
        connections: 12,
        category: 'Grid',
        difficulty: 'Advanced',
        expectedWinRate: '55-65%'
    },

    // =============================================
    // VOLATILITY STRATEGIES
    // =============================================
    {
        id: 'atr_breakout',
        name: 'ATR Volatility Breakout',
        desc: 'Enter when volatility expands beyond threshold',
        icon: 'arrows-fullscreen',
        iconColor: 'var(--accent-orange)',
        blocks: 10,
        connections: 14,
        category: 'Volatility',
        difficulty: 'Intermediate',
        expectedWinRate: '40-50%'
    },
    {
        id: 'bb_squeeze',
        name: 'Bollinger Squeeze',
        desc: 'Trade breakout after BB width contraction',
        icon: 'arrows-collapse',
        iconColor: 'var(--accent-cyan)',
        blocks: 9,
        connections: 14,
        category: 'Volatility',
        difficulty: 'Intermediate',
        expectedWinRate: '45-55%'
    },

    // =============================================
    // ADVANCED / MULTI-INDICATOR
    // =============================================
    {
        id: 'multi_indicator',
        name: 'Multi-Indicator Confluence',
        desc: 'Combine multiple indicators for confirmation',
        icon: 'layers',
        iconColor: 'var(--accent-red)',
        blocks: 17,
        connections: 24,
        category: 'Advanced',
        difficulty: 'Advanced',
        expectedWinRate: '50-60%'
    },
    {
        id: 'divergence_hunter',
        name: 'Divergence Hunter',
        desc: 'Find RSI/MACD divergences with price',
        icon: 'arrow-left-right',
        iconColor: 'var(--accent-violet)',
        blocks: 12,
        connections: 16,
        category: 'Advanced',
        difficulty: 'Advanced',
        expectedWinRate: '55-65%'
    },
    {
        id: 'smart_money',
        name: 'Smart Money Concept',
        desc: 'Trade order blocks, FVG and liquidity sweeps',
        icon: 'bank',
        iconColor: 'var(--accent-gold)',
        blocks: 18,
        connections: 24,
        category: 'Advanced',
        difficulty: 'Expert',
        expectedWinRate: '50-60%'
    },

    // =============================================
    // SCALPING
    // =============================================
    {
        id: 'scalping_pro',
        name: 'Scalping Pro',
        desc: 'Quick entries with tight stops on small timeframes',
        icon: 'lightning',
        iconColor: 'var(--accent-yellow)',
        blocks: 17,
        connections: 24,
        category: 'Scalping',
        difficulty: 'Expert',
        expectedWinRate: '55-65%'
    }
];

/**
 * Get all unique template categories in display order.
 * @returns {string[]}
 */
export function getTemplateCategories() {
    const order = [
        'Mean Reversion',
        'Trend Following',
        'Momentum',
        'DCA',
        'Grid',
        'Volatility',
        'Advanced',
        'Scalping'
    ];
    const present = new Set(STRATEGY_TEMPLATES.map((t) => t.category));
    return order.filter((c) => present.has(c));
}

/**
 * Get templates filtered by category.
 * @param {string} category
 * @returns {StrategyTemplate[]}
 */
export function getTemplatesByCategory(category) {
    return STRATEGY_TEMPLATES.filter((t) => t.category === category);
}

/**
 * Get a single template by id.
 * @param {string} id
 * @returns {StrategyTemplate|undefined}
 */
export function getTemplateById(id) {
    return STRATEGY_TEMPLATES.find((t) => t.id === id);
}

// Default export for convenience
export default STRATEGY_TEMPLATES;
