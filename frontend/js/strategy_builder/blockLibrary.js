/**
 * Block Library — Catalog of all available block types for the Strategy Builder.
 *
 * Pure data — no DOM, no state, no side effects.
 * Extracted from strategy_builder.js (Phase 5 refactor).
 *
 * Used by:
 *   - strategy_builder.js (import, then passed via getBlockLibrary to modules)
 *   - BacktestModule.js  (receives via deps.getBlockLibrary)
 *   - SaveLoadModule.js  (receives via deps.getBlockLibrary)
 */

export const blockLibrary = {
  indicators: [
    // Universal indicator blocks (integrated with AI agents — do not remove)
    { id: 'rsi', name: 'RSI', desc: 'Relative Strength Index (0-100)', icon: 'graph-up' },
    { id: 'stochastic', name: 'Stochastic', desc: 'Stochastic (Range Filter + Cross Signal + K/D Cross)', icon: 'percent' },
    { id: 'macd', name: 'MACD', desc: 'Moving Average Convergence Divergence', icon: 'bar-chart' },
    { id: 'supertrend', name: 'Supertrend', desc: 'Trend following indicator', icon: 'arrow-up-right-circle' },
    { id: 'qqe', name: 'QQE', desc: 'Quantitative Qualitative Estimation', icon: 'activity' },
    { id: 'stoch_rsi', name: 'StochRSI', desc: 'Stochastic RSI Oscillator', icon: 'graph-up' },
    { id: 'cci', name: 'CCI', desc: 'Commodity Channel Index', icon: 'reception-4' },
    { id: 'adx', name: 'ADX', desc: 'Average Directional Index (Trend Strength)', icon: 'bar-chart-line' },
    { id: 'parabolic_sar', name: 'Parabolic SAR', desc: 'Parabolic Stop And Reverse', icon: 'dot' },
    { id: 'sma', name: 'SMA', desc: 'Simple Moving Average', icon: 'graph-up-arrow' },
    { id: 'ema', name: 'EMA', desc: 'Exponential Moving Average', icon: 'graph-up-arrow' },
    { id: 'bollinger', name: 'Bollinger Bands', desc: 'Bollinger Bands (Upper / Middle / Lower)', icon: 'border-outer' },
    { id: 'donchian', name: 'Donchian Channels', desc: 'Donchian Channel (Highest / Lowest over N bars)', icon: 'border-all' },
    { id: 'ichimoku', name: 'Ichimoku', desc: 'Ichimoku Cloud (Tenkan / Kijun / Span A & B)', icon: 'layers' },
    { id: 'pivot_points', name: 'Pivot Points', desc: 'Classic Pivot Points (PP / S1-S3 / R1-R3)', icon: 'grid-3x3' },
    { id: 'obv', name: 'OBV', desc: 'On-Balance Volume', icon: 'bar-chart-steps' },
    { id: 'vwap', name: 'VWAP', desc: 'Volume Weighted Average Price', icon: 'currency-dollar' },
    { id: 'ad_line', name: 'AD Line', desc: 'Accumulation/Distribution Line', icon: 'arrow-left-right' },
    // Universal filters (integrated with AI agents — do not remove)
    { id: 'atr_volatility', name: 'ATR Volatility', desc: 'ATR Volatility Filter (ATR1 <> ATR2)', icon: 'arrows-expand' },
    { id: 'volume_filter', name: 'Volume Filter', desc: 'Volume Filter (VOL1 <> VOL2)', icon: 'bar-chart-steps' },
    { id: 'highest_lowest_bar', name: 'Highest/Lowest Bar', desc: 'Signal on Highest/Lowest Bar + Block if Worse Than', icon: 'arrow-up-short' },
    { id: 'two_mas', name: 'TWO MAs', desc: 'Two Moving Averages (Signal + Filter)', icon: 'graph-up-arrow' },
    { id: 'accumulation_areas', name: 'Accumulation Areas', desc: 'Accumulation Areas Filter or Signal', icon: 'layers' },
    { id: 'keltner_bollinger', name: 'Keltner/Bollinger Channel', desc: 'Keltner Channel / Bollinger Bands Filter', icon: 'border-outer' },
    { id: 'rvi_filter', name: 'RVI', desc: 'Relative Volatility Index Filter', icon: 'speedometer' },
    { id: 'mfi_filter', name: 'MFI', desc: 'Money Flow Index Filter', icon: 'currency-exchange' },
    { id: 'cci_filter', name: 'CCI Filter', desc: 'Commodity Channel Index Filter', icon: 'reception-4' },
    { id: 'momentum_filter', name: 'Momentum', desc: 'Momentum Filter', icon: 'rocket-takeoff' }
  ],
  // (Filters category removed — entire block deprecated)
  conditions: [
    {
      id: 'crossover',
      name: 'Crossover',
      desc: 'When value A crosses above B',
      icon: 'intersect'
    },
    {
      id: 'crossunder',
      name: 'Crossunder',
      desc: 'When value A crosses below B',
      icon: 'intersect'
    },
    {
      id: 'greater_than',
      name: 'Greater Than',
      desc: 'When value A > B',
      icon: 'chevron-double-up'
    },
    {
      id: 'less_than',
      name: 'Less Than',
      desc: 'When value A < B',
      icon: 'chevron-double-down'
    },
    {
      id: 'equals',
      name: 'Equals',
      desc: 'When value A equals B',
      icon: 'dash'
    },
    {
      id: 'between',
      name: 'Between',
      desc: 'When value is in range',
      icon: 'arrows-collapse'
    }
  ],
  entry_mgmt: [
    {
      id: 'dca',
      name: 'DCA',
      desc: 'Dollar Cost Averaging',
      icon: 'grid-3x3'
    },
    {
      id: 'grid_orders',
      name: 'Manual Grid',
      desc: 'Custom offset & volume per order',
      icon: 'grid'
    }
  ],
  // Exits: Standard exit rules (SL/TP, trailing, ATR, session, DCA close)
  exits: [
    {
      id: 'static_sltp',
      name: 'Static SL/TP',
      desc: 'Auto % SL/TP from entry price',
      icon: 'shield-check'
    },
    {
      id: 'trailing_stop_exit',
      name: 'Trailing Stop',
      desc: 'Auto trailing % from entry',
      icon: 'arrow-bar-down'
    },
    {
      id: 'atr_exit',
      name: 'ATR Exit',
      desc: 'Auto ATR-based SL/TP',
      icon: 'arrows-expand'
    },
    {
      id: 'multi_tp_exit',
      name: 'Multi TP Levels',
      desc: 'TP1/TP2/TP3 with % allocation',
      icon: 'stack'
    }
  ],
  // Close Conditions: Indicator-based close rules with profit filter (TradingView-style)
  close_conditions: [
    {
      id: 'close_by_time',
      name: 'Close by Time',
      desc: 'Close after N bars since entry',
      icon: 'clock'
    },
    {
      id: 'close_channel',
      name: 'Channel Close (Keltner/BB)',
      desc: 'Close on Keltner/Bollinger band touch',
      icon: 'bar-chart'
    },
    {
      id: 'close_ma_cross',
      name: 'Two MAs Close',
      desc: 'Close on MA1/MA2 cross',
      icon: 'trending-up'
    },
    {
      id: 'close_rsi',
      name: 'Close by RSI',
      desc: 'Close on RSI reach/cross level',
      icon: 'activity'
    },
    {
      id: 'close_stochastic',
      name: 'Close by Stochastic',
      desc: 'Close on Stoch reach/cross level',
      icon: 'activity'
    },
    {
      id: 'close_psar',
      name: 'Close by Parabolic SAR',
      desc: 'Close on PSAR signal reversal',
      icon: 'git-commit'
    }
  ],
  // Divergence Detection — unified multi-indicator divergence signal block
  divergence: [
    {
      id: 'divergence',
      name: 'Divergence',
      desc: 'Multi-indicator divergence detection (RSI, Stochastic, Momentum, CMF, OBV, MFI)',
      icon: 'arrow-left-right'
    }
  ],
  // Logic Gates — combine multiple condition signals
  logic: [
    {
      id: 'and',
      name: 'AND',
      desc: 'All inputs must be true (combine signals)',
      icon: 'diagram-3'
    },
    {
      id: 'or',
      name: 'OR',
      desc: 'Any input must be true (alternative signals)',
      icon: 'diagram-2'
    },
    {
      id: 'not',
      name: 'NOT',
      desc: 'Invert signal (true → false)',
      icon: 'x-circle'
    }
  ]

  // (Smart Signals category removed — all composite nodes deprecated in favor of universal indicator blocks)
};
