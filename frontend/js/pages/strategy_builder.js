/**
 * 📄 Strategy Builder Page JavaScript
 *
 * Page-specific scripts for strategy_builder.html
 * Extracted during Phase 1 Week 3: JS Extraction
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

// Import shared utilities
import { apiClient, API_CONFIG } from '../api.js';
import {
  formatNumber,
  formatCurrency,
  formatDate,
  debounce
} from '../utils.js';

// Import WebSocket validation module
import * as wsValidation from './strategy_builder_ws.js';

// Block Library Data
const blockLibrary = {
  indicators: [
    // Momentum Indicators
    { id: 'rsi', name: 'RSI', desc: 'Relative Strength Index (0-100)', icon: 'graph-up' },
    { id: 'stochastic', name: 'Stochastic', desc: 'Stochastic Oscillator %K/%D', icon: 'percent' },
    { id: 'stoch_rsi', name: 'StochRSI', desc: 'Stochastic RSI (0-100)', icon: 'percent' },
    { id: 'williams_r', name: 'Williams %R', desc: 'Williams Percent Range', icon: 'graph-down' },
    { id: 'roc', name: 'ROC', desc: 'Rate of Change', icon: 'arrow-up-right' },
    { id: 'mfi', name: 'MFI', desc: 'Money Flow Index', icon: 'currency-exchange' },
    { id: 'cmo', name: 'CMO', desc: 'Chande Momentum Oscillator', icon: 'activity' },
    { id: 'cci', name: 'CCI', desc: 'Commodity Channel Index', icon: 'arrows-expand' },
    // Trend Indicators
    { id: 'sma', name: 'SMA', desc: 'Simple Moving Average', icon: 'graph-up-arrow' },
    { id: 'ema', name: 'EMA', desc: 'Exponential Moving Average', icon: 'graph-up-arrow' },
    { id: 'wma', name: 'WMA', desc: 'Weighted Moving Average', icon: 'graph-up-arrow' },
    { id: 'dema', name: 'DEMA', desc: 'Double Exponential MA', icon: 'layers' },
    { id: 'tema', name: 'TEMA', desc: 'Triple Exponential MA', icon: 'layers-fill' },
    { id: 'hull_ma', name: 'Hull MA', desc: 'Hull Moving Average', icon: 'graph-up-arrow' },
    { id: 'macd', name: 'MACD', desc: 'Moving Average Convergence Divergence', icon: 'bar-chart' },
    { id: 'adx', name: 'ADX', desc: 'Average Directional Index', icon: 'activity' },
    { id: 'supertrend', name: 'Supertrend', desc: 'Trend following indicator', icon: 'arrow-up-right-circle' },
    { id: 'ichimoku', name: 'Ichimoku', desc: 'Ichimoku Cloud (5 lines)', icon: 'cloud' },
    { id: 'parabolic_sar', name: 'Parabolic SAR', desc: 'Stop and Reverse', icon: 'circle' },
    { id: 'aroon', name: 'Aroon', desc: 'Aroon Up/Down/Oscillator', icon: 'arrow-down-up' },
    { id: 'qqe', name: 'QQE', desc: 'Quantitative Qualitative Estimation', icon: 'activity' },
    // Volatility Indicators
    { id: 'atr', name: 'ATR', desc: 'Average True Range', icon: 'arrows-expand' },
    { id: 'atrp', name: 'ATR%', desc: 'ATR as percentage of price', icon: 'percent' },
    { id: 'bollinger', name: 'Bollinger Bands', desc: 'Upper/Middle/Lower bands', icon: 'distribute-vertical' },
    { id: 'keltner', name: 'Keltner Channel', desc: 'EMA-based channel', icon: 'distribute-vertical' },
    { id: 'donchian', name: 'Donchian Channel', desc: 'High/Low channel', icon: 'distribute-vertical' },
    { id: 'stddev', name: 'StdDev', desc: 'Standard Deviation', icon: 'graph-up' },
    // Volume Indicators
    { id: 'obv', name: 'OBV', desc: 'On Balance Volume', icon: 'bar-chart-steps' },
    { id: 'vwap', name: 'VWAP', desc: 'Volume Weighted Avg Price', icon: 'currency-dollar' },
    { id: 'cmf', name: 'CMF', desc: 'Chaikin Money Flow', icon: 'water' },
    { id: 'ad_line', name: 'A/D Line', desc: 'Accumulation/Distribution', icon: 'graph-up' },
    { id: 'pvt', name: 'PVT', desc: 'Price Volume Trend', icon: 'graph-up' },
    // Support/Resistance
    { id: 'pivot_points', name: 'Pivot Points', desc: 'PP, R1-R3, S1-S3', icon: 'arrows-collapse' },
    // Multi-Timeframe
    { id: 'mtf', name: 'MTF', desc: 'Multi-Timeframe indicator', icon: 'layers-half' }
  ],
  filters: [
    { id: 'rsi_filter', name: 'RSI Filter', desc: 'RSI range/cross filter', icon: 'funnel' },
    { id: 'supertrend_filter', name: 'SuperTrend Filter', desc: 'Trend filter with signal modes', icon: 'arrow-up-right-circle' },
    { id: 'two_ma_filter', name: 'TWO MAs Filter', desc: 'MA cross & price filter', icon: 'arrows-angle-contract' },
    { id: 'stochastic_filter', name: 'Stochastic Filter', desc: 'Range/cross/K-D filter', icon: 'percent' },
    { id: 'macd_filter', name: 'MACD Filter', desc: 'Zero/signal line cross', icon: 'bar-chart' },
    { id: 'qqe_filter', name: 'QQE Filter', desc: 'QQE signals with RSI smoothing', icon: 'activity' },
    { id: 'cci_filter', name: 'CCI Filter', desc: 'CCI range filter', icon: 'graph-up-arrow' },
    { id: 'momentum_filter', name: 'Momentum Filter', desc: 'Momentum range filter', icon: 'speedometer2' },
    { id: 'dmi_filter', name: 'DMI/ADX Filter', desc: 'DI+/DI- cross with ADX', icon: 'arrows-move' },
    { id: 'cmf_filter', name: 'CMF Filter', desc: 'Chaikin Money Flow', icon: 'water' },
    { id: 'bop_filter', name: 'Balance of Power', desc: 'Bulls vs Bears power', icon: 'scale' },
    { id: 'levels_filter', name: 'Levels Break Filter', desc: 'Pivot/S&R breaks', icon: 'rulers' },
    { id: 'atr_filter', name: 'ATR Volatility Filter', desc: 'ATR threshold filter', icon: 'arrows-fullscreen' },
    { id: 'volume_compare_filter', name: 'Volume Compare Filter', desc: 'Volume vs MA comparison', icon: 'bar-chart-line' },
    { id: 'highest_lowest_filter', name: 'Highest/Lowest Bar', desc: 'N-bar high/low breakout', icon: 'arrow-up-short' },
    { id: 'accumulation_filter', name: 'Accumulation Areas', desc: 'Volume accumulation zones', icon: 'layers-half' },
    { id: 'linreg_filter', name: 'Linear Regression', desc: 'LinReg channel filter', icon: 'graph-up' },
    { id: 'rvi_filter', name: 'RVI Filter', desc: 'Relative Volatility Index', icon: 'activity' },
    { id: 'divergence_filter', name: 'Divergence Filter', desc: 'Price/indicator divergence', icon: 'arrow-left-right' },
    { id: 'price_action_filter', name: 'Price Action', desc: 'Candlestick patterns', icon: 'fire' },
    { id: 'trend_filter', name: 'Trend Filter', desc: 'EMA slope / ADX direction', icon: 'arrow-up-right' },
    { id: 'volume_filter', name: 'Volume Filter', desc: 'Volume above/below average', icon: 'bar-chart-steps' },
    { id: 'volatility_filter', name: 'Volatility Filter', desc: 'ATR/BB width threshold', icon: 'arrows-expand' },
    { id: 'time_filter', name: 'Time Filter', desc: 'Trading sessions/days', icon: 'clock' },
    { id: 'price_filter', name: 'Price Filter', desc: 'Price above/below level', icon: 'currency-dollar' },
    { id: 'block_worse_filter', name: 'Block if Worse', desc: 'Block entry if price moved X%', icon: 'shield-x' }
  ],
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
  actions: [
    // Entry Management
    {
      id: 'buy',
      name: 'Buy',
      desc: 'Open long position',
      icon: 'arrow-up-circle'
    },
    {
      id: 'sell',
      name: 'Sell',
      desc: 'Open short position',
      icon: 'arrow-down-circle'
    },
    {
      id: 'limit_entry',
      name: 'Limit Entry',
      desc: 'Entry at specific price',
      icon: 'bookmark'
    },
    {
      id: 'stop_entry',
      name: 'Stop Entry',
      desc: 'Entry on breakout',
      icon: 'box-arrow-up'
    },
    {
      id: 'indent_order',
      name: 'Indent Order',
      desc: 'Limit entry with offset',
      icon: 'arrow-right-circle'
    },
    // Exit Management
    {
      id: 'close',
      name: 'Close Position',
      desc: 'Close current position',
      icon: 'x-circle'
    },
    {
      id: 'close_long',
      name: 'Close Long',
      desc: 'Close only long positions',
      icon: 'x-circle'
    },
    {
      id: 'close_short',
      name: 'Close Short',
      desc: 'Close only short positions',
      icon: 'x-circle'
    },
    {
      id: 'close_all',
      name: 'Close All',
      desc: 'Close all positions',
      icon: 'x-octagon'
    },
    // Risk Management
    {
      id: 'stop_loss',
      name: 'Stop Loss',
      desc: 'Set stop loss level',
      icon: 'shield-x'
    },
    {
      id: 'take_profit',
      name: 'Take Profit',
      desc: 'Set take profit level',
      icon: 'trophy'
    },
    {
      id: 'trailing_stop',
      name: 'Trailing Stop',
      desc: 'Dynamic trailing stop',
      icon: 'arrow-bar-down'
    },
    {
      id: 'atr_stop',
      name: 'ATR Stop',
      desc: 'ATR-based stop loss',
      icon: 'shield-exclamation'
    },
    {
      id: 'chandelier_stop',
      name: 'Chandelier Stop',
      desc: 'From highest high - ATR',
      icon: 'lamp'
    },
    // Break-even & Protection
    {
      id: 'break_even',
      name: 'Break Even',
      desc: 'Move stop to entry price',
      icon: 'dash-circle'
    },
    {
      id: 'profit_lock',
      name: 'Profit Lock',
      desc: 'Lock minimum profit',
      icon: 'lock'
    },
    // Partial Exits
    {
      id: 'scale_out',
      name: 'Scale Out',
      desc: 'Partial position close',
      icon: 'layers'
    },
    {
      id: 'multi_tp',
      name: 'Multi Take Profit',
      desc: 'TP1, TP2, TP3 levels',
      icon: 'stack'
    }
  ],
  // NEW CATEGORY: Close Conditions (Exit Rules)
  exits: [
    {
      id: 'tp_percent',
      name: 'Take Profit %',
      desc: 'Exit at % profit',
      icon: 'trophy'
    },
    {
      id: 'sl_percent',
      name: 'Stop Loss %',
      desc: 'Exit at % loss',
      icon: 'shield-x'
    },
    {
      id: 'trailing_stop_exit',
      name: 'Trailing Stop',
      desc: 'Dynamic trailing exit',
      icon: 'arrow-bar-down'
    },
    {
      id: 'atr_exit',
      name: 'ATR Exit',
      desc: 'ATR-based TP/SL',
      icon: 'arrows-expand'
    },
    {
      id: 'time_exit',
      name: 'Time Exit',
      desc: 'Exit after N bars/hours',
      icon: 'clock-history'
    },
    {
      id: 'session_exit',
      name: 'Session Exit',
      desc: 'Exit at session end',
      icon: 'calendar-event'
    },
    {
      id: 'signal_exit',
      name: 'Signal Exit',
      desc: 'Exit on opposite signal',
      icon: 'signpost'
    },
    {
      id: 'indicator_exit',
      name: 'Indicator Exit',
      desc: 'Exit on indicator condition',
      icon: 'activity'
    },
    {
      id: 'break_even_exit',
      name: 'Break Even Move',
      desc: 'Move SL to entry after profit',
      icon: 'dash-circle'
    },
    {
      id: 'partial_close',
      name: 'Partial Close',
      desc: 'Close % at targets',
      icon: 'pie-chart'
    },
    {
      id: 'multi_tp_exit',
      name: 'Multi TP Levels',
      desc: 'TP1/TP2/TP3 with % allocation',
      icon: 'stack'
    },
    {
      id: 'chandelier_exit',
      name: 'Chandelier Exit',
      desc: 'ATR from highest/lowest',
      icon: 'lamp'
    },
    // ===== DCA CLOSE CONDITIONS =====
    {
      id: 'rsi_close',
      name: 'RSI Close',
      desc: 'Close on RSI reach/cross level',
      icon: 'graph-up'
    },
    {
      id: 'stoch_close',
      name: 'Stochastic Close',
      desc: 'Close on Stoch reach/cross level',
      icon: 'percent'
    },
    {
      id: 'channel_close',
      name: 'Channel Close',
      desc: 'Close on Keltner/BB breakout',
      icon: 'distribute-vertical'
    },
    {
      id: 'ma_close',
      name: 'Two MAs Close',
      desc: 'Close on MA cross',
      icon: 'graph-up-arrow'
    },
    {
      id: 'psar_close',
      name: 'PSAR Close',
      desc: 'Close on Parabolic SAR flip',
      icon: 'circle'
    },
    {
      id: 'time_bars_close',
      name: 'Time/Bars Close',
      desc: 'Close after X bars with profit filter',
      icon: 'clock-history'
    }
  ],
  // NEW CATEGORY: Position Sizing
  position_sizing: [
    {
      id: 'fixed_size',
      name: 'Fixed Size',
      desc: 'Fixed position size',
      icon: 'hash'
    },
    {
      id: 'percent_balance',
      name: '% of Balance',
      desc: 'Percentage of account balance',
      icon: 'percent'
    },
    {
      id: 'risk_percent',
      name: 'Risk %',
      desc: 'Risk percentage per trade',
      icon: 'shield-check'
    },
    {
      id: 'atr_sizing',
      name: 'ATR Sizing',
      desc: 'Size based on volatility',
      icon: 'arrows-expand'
    },
    {
      id: 'kelly_criterion',
      name: 'Kelly Criterion',
      desc: 'Optimal mathematical sizing',
      icon: 'calculator'
    }
  ],
  // NEW CATEGORY: Entry Refinement
  entry_refinement: [
    {
      id: 'dca',
      name: 'DCA',
      desc: 'Dollar Cost Averaging',
      icon: 'grid-3x3'
    },
    {
      id: 'pyramiding',
      name: 'Pyramiding',
      desc: 'Add to winning position',
      icon: 'triangle'
    },
    {
      id: 'grid_orders',
      name: 'Grid Orders',
      desc: 'Grid of entry orders',
      icon: 'grid'
    },
    {
      id: 'average_down',
      name: 'Average Down',
      desc: 'Average losing long',
      icon: 'arrow-down-square'
    },
    {
      id: 'reentry',
      name: 'Re-entry',
      desc: 'Re-enter after exit',
      icon: 'arrow-repeat'
    },
    {
      id: 'martingale',
      name: 'Martingale',
      desc: 'Double size after loss',
      icon: 'arrow-up-right-circle'
    },
    {
      id: 'anti_martingale',
      name: 'Anti-Martingale',
      desc: 'Increase size after win',
      icon: 'arrow-down-left-circle'
    },
    {
      id: 'dca_by_signal',
      name: 'DCA by Signal',
      desc: 'Add on repeated signal',
      icon: 'plus-circle'
    },
    {
      id: 'dca_by_percent',
      name: 'DCA by % Drop',
      desc: 'Add when price drops %',
      icon: 'percent'
    },
    {
      id: 'scale_in',
      name: 'Scale In',
      desc: 'Gradual position building',
      icon: 'bar-chart-steps'
    }
  ],
  // NEW CATEGORY: Risk Controls (Circuit Breakers)
  risk_controls: [
    {
      id: 'max_daily_loss',
      name: 'Max Daily Loss',
      desc: 'Stop trading after daily loss limit',
      icon: 'exclamation-triangle'
    },
    {
      id: 'max_drawdown',
      name: 'Max Drawdown',
      desc: 'Stop at max drawdown',
      icon: 'graph-down-arrow'
    },
    {
      id: 'max_trades_day',
      name: 'Max Trades/Day',
      desc: 'Limit daily trades',
      icon: 'calendar-check'
    },
    {
      id: 'consecutive_loss',
      name: 'Consecutive Loss',
      desc: 'Pause after X losses',
      icon: 'pause-circle'
    },
    {
      id: 'cooloff_period',
      name: 'Cool-off Period',
      desc: 'Pause after losses',
      icon: 'hourglass'
    }
  ],
  // NEW CATEGORY: Session Management
  session_mgmt: [
    {
      id: 'active_hours',
      name: 'Active Hours',
      desc: 'Trading hours filter',
      icon: 'clock'
    },
    {
      id: 'trading_days',
      name: 'Trading Days',
      desc: 'Allowed weekdays',
      icon: 'calendar-week'
    },
    {
      id: 'session_filter',
      name: 'Session Filter',
      desc: 'London/NY/Asia sessions',
      icon: 'globe'
    },
    {
      id: 'news_filter',
      name: 'News Filter',
      desc: 'Avoid news events',
      icon: 'newspaper'
    },
    {
      id: 'weekend_close',
      name: 'Weekend Close',
      desc: 'Close before weekend',
      icon: 'calendar-x'
    }
  ],
  // NEW CATEGORY: Time Management
  time_mgmt: [
    {
      id: 'time_stop',
      name: 'Time Stop',
      desc: 'Close after X hours',
      icon: 'stopwatch'
    },
    {
      id: 'max_duration',
      name: 'Max Duration',
      desc: 'Max trade duration',
      icon: 'hourglass-split'
    },
    {
      id: 'session_close',
      name: 'Session Close',
      desc: 'Close at session end',
      icon: 'door-closed'
    },
    {
      id: 'intraday_only',
      name: 'Intraday Only',
      desc: 'No overnight positions',
      icon: 'sun'
    }
  ],
  logic: [
    {
      id: 'and',
      name: 'AND',
      desc: 'All conditions must be true',
      icon: 'union'
    },
    {
      id: 'or',
      name: 'OR',
      desc: 'Any condition must be true',
      icon: 'exclude'
    },
    { id: 'not', name: 'NOT', desc: 'Inverse condition', icon: 'slash-circle' },
    { id: 'delay', name: 'Delay', desc: 'Wait N bars', icon: 'clock-history' },
    { id: 'filter', name: 'Filter', desc: 'Filter signals', icon: 'funnel' }
  ],
  inputs: [
    {
      id: 'price',
      name: 'Price',
      desc: 'OHLCV price data',
      icon: 'currency-dollar'
    },
    {
      id: 'volume',
      name: 'Volume',
      desc: 'Trading volume',
      icon: 'bar-chart-steps'
    },
    {
      id: 'constant',
      name: 'Constant',
      desc: 'Fixed numeric value',
      icon: 'hash'
    },
    {
      id: 'timeframe',
      name: 'Timeframe',
      desc: 'Chart timeframe',
      icon: 'calendar'
    }
  ],
  // NEW CATEGORY: Correlation & Multi-Symbol
  correlation: [
    {
      id: 'correlation_filter',
      name: 'Correlation Filter',
      desc: 'Filter by symbol correlation',
      icon: 'link-45deg'
    },
    {
      id: 'btc_dominance',
      name: 'BTC Dominance',
      desc: 'Filter by BTC dominance',
      icon: 'currency-bitcoin'
    },
    {
      id: 'sector_strength',
      name: 'Sector Strength',
      desc: 'Compare to sector/index',
      icon: 'pie-chart'
    },
    {
      id: 'relative_strength',
      name: 'Relative Strength',
      desc: 'RS vs benchmark',
      icon: 'graph-up-arrow'
    }
  ],
  // NEW CATEGORY: Alert System
  alerts: [
    {
      id: 'price_alert',
      name: 'Price Alert',
      desc: 'Alert at price level',
      icon: 'bell'
    },
    {
      id: 'indicator_alert',
      name: 'Indicator Alert',
      desc: 'Alert on indicator condition',
      icon: 'bell-fill'
    },
    {
      id: 'trade_alert',
      name: 'Trade Alert',
      desc: 'Alert on entry/exit',
      icon: 'megaphone'
    },
    {
      id: 'pnl_alert',
      name: 'P&L Alert',
      desc: 'Alert on profit/loss threshold',
      icon: 'exclamation-triangle'
    },
    {
      id: 'drawdown_alert',
      name: 'Drawdown Alert',
      desc: 'Alert on drawdown level',
      icon: 'graph-down-arrow'
    }
  ],
  // NEW CATEGORY: Visualization
  visualization: [
    {
      id: 'show_entries',
      name: 'Show Entries',
      desc: 'Display entry markers on chart',
      icon: 'geo-alt'
    },
    {
      id: 'show_exits',
      name: 'Show Exits',
      desc: 'Display exit markers on chart',
      icon: 'geo-alt-fill'
    },
    {
      id: 'show_sl_tp',
      name: 'Show SL/TP Lines',
      desc: 'Display stop loss & take profit',
      icon: 'rulers'
    },
    {
      id: 'show_indicators',
      name: 'Show Indicators',
      desc: 'Overlay indicators on chart',
      icon: 'graph-up'
    },
    {
      id: 'show_equity',
      name: 'Show Equity Curve',
      desc: 'Display equity curve panel',
      icon: 'bar-chart-line'
    },
    {
      id: 'show_trades_table',
      name: 'Trades Table',
      desc: 'Show trades in table format',
      icon: 'table'
    }
  ],
  // NEW CATEGORY: DCA Grid (from TradingView Multi DCA Strategy)
  dca_grid: [
    {
      id: 'dca_grid_enable',
      name: 'DCA Grid Mode',
      desc: 'Enable DCA grid trading with multiple orders',
      icon: 'grid-3x3-gap'
    },
    {
      id: 'dca_grid_settings',
      name: 'Grid Settings',
      desc: 'Configure grid size, order count, leverage',
      icon: 'sliders'
    },
    {
      id: 'dca_martingale_config',
      name: 'Martingale Config',
      desc: 'Order size multiplier (1.0-1.8)',
      icon: 'arrow-up-right-circle'
    },
    {
      id: 'dca_log_steps',
      name: 'Logarithmic Steps',
      desc: 'Order step progression (0.8-1.4)',
      icon: 'bar-chart-steps'
    },
    {
      id: 'dca_dynamic_tp',
      name: 'Dynamic TP',
      desc: 'Adjust TP when many orders active',
      icon: 'bullseye'
    },
    {
      id: 'dca_safety_close',
      name: 'Safety Close',
      desc: 'Close all on max drawdown',
      icon: 'shield-x'
    }
  ],
  // NEW CATEGORY: Multiple Take Profits
  multiple_tp: [
    {
      id: 'multi_tp_enable',
      name: 'Enable Multi-TP',
      desc: 'Use TP1-TP4 instead of single TP',
      icon: 'layers'
    },
    {
      id: 'tp1_config',
      name: 'TP1 Level',
      desc: 'First take profit level and %',
      icon: 'trophy'
    },
    {
      id: 'tp2_config',
      name: 'TP2 Level',
      desc: 'Second take profit level and %',
      icon: 'trophy-fill'
    },
    {
      id: 'tp3_config',
      name: 'TP3 Level',
      desc: 'Third take profit level and %',
      icon: 'award'
    },
    {
      id: 'tp4_config',
      name: 'TP4 Level',
      desc: 'Final take profit (close all)',
      icon: 'award-fill'
    }
  ],
  // NEW CATEGORY: ATR-based Exit
  atr_exit: [
    {
      id: 'atr_sl',
      name: 'ATR Stop Loss',
      desc: 'Stop loss based on ATR multiplier',
      icon: 'shield-exclamation'
    },
    {
      id: 'atr_tp',
      name: 'ATR Take Profit',
      desc: 'Take profit based on ATR multiplier',
      icon: 'bullseye'
    },
    {
      id: 'atr_wicks_mode',
      name: 'ATR Wicks Mode',
      desc: 'Consider wicks or only close price',
      icon: 'candle'
    }
  ],
  // NEW CATEGORY: Signal Memory
  signal_memory: [
    {
      id: 'signal_memory_enable',
      name: 'Signal Memory',
      desc: 'Remember signal for N bars',
      icon: 'clock-history'
    },
    {
      id: 'cross_memory',
      name: 'Cross Memory',
      desc: 'Remember indicator cross signals',
      icon: 'arrow-left-right'
    },
    {
      id: 'pattern_memory',
      name: 'Pattern Memory',
      desc: 'Remember price patterns',
      icon: 'lightning'
    }
  ],
  // NEW CATEGORY: Close Conditions (from TradingView)
  close_conditions: [
    {
      id: 'close_by_time',
      name: 'Close by Time',
      desc: 'Close after N bars since entry',
      icon: 'clock'
    },
    {
      id: 'close_rsi_reach',
      name: 'RSI Reach Level',
      desc: 'Close when RSI reaches level',
      icon: 'graph-up'
    },
    {
      id: 'close_rsi_cross',
      name: 'RSI Cross Level',
      desc: 'Close when RSI crosses level',
      icon: 'arrow-left-right'
    },
    {
      id: 'close_stoch_reach',
      name: 'Stochastic Reach',
      desc: 'Close when Stoch reaches level',
      icon: 'percent'
    },
    {
      id: 'close_stoch_cross',
      name: 'Stochastic Cross',
      desc: 'Close when Stoch crosses level',
      icon: 'arrow-left-right'
    },
    {
      id: 'close_channel_break',
      name: 'Channel Breakout',
      desc: 'Close on Keltner/BB breakout',
      icon: 'distribute-vertical'
    },
    {
      id: 'close_ma_cross',
      name: 'MA Cross Close',
      desc: 'Close on MA1/MA2 cross',
      icon: 'graph-up-arrow'
    },
    {
      id: 'close_psar',
      name: 'Parabolic SAR Close',
      desc: 'Close on PSAR signal',
      icon: 'circle'
    },
    {
      id: 'close_profit_only',
      name: 'Close Only in Profit',
      desc: 'Require minimum profit to close',
      icon: 'cash-coin'
    }
  ],
  // NEW CATEGORY: Price Action Patterns (from TradingView)
  price_action: [
    {
      id: 'engulfing',
      name: 'Engulfing',
      desc: 'Bullish/Bearish engulfing pattern',
      icon: 'arrow-up-down'
    },
    {
      id: 'hammer_hangman',
      name: 'Hammer/Hanging Man',
      desc: 'Reversal candle patterns',
      icon: 'hammer'
    },
    {
      id: 'doji_patterns',
      name: 'Doji Patterns',
      desc: 'Doji, Doji Star, Dragonfly, Gravestone',
      icon: 'dash-lg'
    },
    {
      id: 'shooting_star',
      name: 'Shooting Star',
      desc: 'Bearish reversal pattern',
      icon: 'star'
    },
    {
      id: 'marubozu',
      name: 'Marubozu',
      desc: 'Strong momentum candle',
      icon: 'square-fill'
    },
    {
      id: 'tweezer',
      name: 'Tweezer Top/Bottom',
      desc: 'Double reversal pattern',
      icon: 'arrows-collapse'
    },
    {
      id: 'three_methods',
      name: 'Three Methods',
      desc: 'Rising/Falling three methods',
      icon: 'three-dots'
    },
    {
      id: 'piercing_darkcloud',
      name: 'Piercing/Dark Cloud',
      desc: 'Two-candle reversal patterns',
      icon: 'cloud-moon'
    },
    {
      id: 'harami',
      name: 'Harami',
      desc: 'Inside bar reversal pattern',
      icon: 'square'
    }
  ],
  // NEW CATEGORY: Divergence Detection
  divergence: [
    {
      id: 'rsi_divergence',
      name: 'RSI Divergence',
      desc: 'Detect RSI divergence signals',
      icon: 'graph-up'
    },
    {
      id: 'macd_divergence',
      name: 'MACD Divergence',
      desc: 'Detect MACD divergence signals',
      icon: 'bar-chart'
    },
    {
      id: 'stoch_divergence',
      name: 'Stochastic Divergence',
      desc: 'Detect Stochastic divergence',
      icon: 'percent'
    },
    {
      id: 'obv_divergence',
      name: 'OBV Divergence',
      desc: 'Detect On Balance Volume divergence',
      icon: 'bar-chart-steps'
    },
    {
      id: 'mfi_divergence',
      name: 'MFI Divergence',
      desc: 'Detect Money Flow Index divergence',
      icon: 'currency-exchange'
    }
  ]
};

// Strategy Templates - EXPANDED
const templates = [
  // =============================================
  // MEAN REVERSION STRATEGIES
  // =============================================
  {
    id: 'rsi_oversold',
    name: 'RSI Oversold Strategy',
    desc: 'Buy when RSI is oversold, sell when overbought',
    icon: 'graph-up',
    iconColor: 'var(--accent-blue)',
    blocks: 4,
    connections: 3,
    category: 'Mean Reversion',
    difficulty: 'Beginner',
    expectedWinRate: '45-55%'
  },
  {
    id: 'rsi_long_short',
    name: 'RSI Long then Short',
    desc: 'Enter Long when RSI < 30, exit and enter Short when RSI > 70',
    icon: 'arrow-up-down',
    iconColor: 'var(--accent-green)',
    blocks: 6,
    connections: 7,
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
    blocks: 6,
    connections: 5,
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
    blocks: 5,
    connections: 4,
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
    blocks: 5,
    connections: 4,
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
    blocks: 4,
    connections: 3,
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
    connections: 4,
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
    blocks: 7,
    connections: 6,
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
    blocks: 8,
    connections: 7,
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
    blocks: 7,
    connections: 6,
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
    blocks: 6,
    connections: 5,
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
    blocks: 6,
    connections: 5,
    category: 'Momentum',
    difficulty: 'Intermediate',
    expectedWinRate: '40-50%'
  },

  // =============================================
  // DCA & GRID STRATEGIES
  // =============================================
  {
    id: 'simple_dca',
    name: 'Simple DCA Bot',
    desc: 'Dollar cost averaging with safety orders on price drops',
    icon: 'grid-3x3',
    iconColor: 'var(--accent-blue)',
    blocks: 8,
    connections: 7,
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
    connections: 8,
    category: 'DCA',
    difficulty: 'Intermediate',
    expectedWinRate: '60-70%'
  },
  {
    id: 'grid_trading',
    name: 'Grid Trading Bot',
    desc: 'Place grid of orders within price range',
    icon: 'grid',
    iconColor: 'var(--accent-purple)',
    blocks: 7,
    connections: 6,
    category: 'Grid',
    difficulty: 'Advanced',
    expectedWinRate: '55-65%'
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
    blocks: 10,
    connections: 9,
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
    blocks: 8,
    connections: 7,
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
    blocks: 12,
    connections: 11,
    category: 'Advanced',
    difficulty: 'Expert',
    expectedWinRate: '50-60%'
  },
  {
    id: 'scalping_pro',
    name: 'Scalping Pro',
    desc: 'Quick entries with tight stops on small timeframes',
    icon: 'lightning',
    iconColor: 'var(--accent-yellow)',
    blocks: 9,
    connections: 8,
    category: 'Scalping',
    difficulty: 'Expert',
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
    blocks: 6,
    connections: 5,
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
    blocks: 7,
    connections: 6,
    category: 'Volatility',
    difficulty: 'Intermediate',
    expectedWinRate: '45-55%'
  }
];

// State
let strategyBlocks = [];
const connections = [];
let lastAutoSavePayload = null;
const AUTOSAVE_INTERVAL_MS = 30000;
let selectedBlockId = null;
let selectedBlockIds = []; // Multi-selection array
let selectedTemplate = null;
let zoom = 1;
let isDragging = false;
let dragOffset = { x: 0, y: 0 };

// Marquee selection variables
let isMarqueeSelecting = false;
let marqueeStart = { x: 0, y: 0 };
let marqueeElement = null;

// Group dragging variables
let isGroupDragging = false;
let groupDragOffsets = {}; // blockId -> {x, y} offset from mouse

// Initialize
document.addEventListener('DOMContentLoaded', function () {
  console.log('[Strategy Builder] Initializing...');

  try {
    // Check if strategy ID in URL
    const urlParams = new URLSearchParams(window.location.search);
    const strategyId = urlParams.get('id');

    if (strategyId) {
      console.log('[Strategy Builder] Loading strategy:', strategyId);
      // Load existing strategy
      loadStrategy(strategyId).then(() => {
        // After loading, ensure main node exists
        const mainNode = strategyBlocks.find((b) => b.isMain);
        if (!mainNode) {
          createMainStrategyNode();
        }
        console.log('[Strategy Builder] Strategy loaded');
      }).catch((err) => {
        console.error('[Strategy Builder] Error loading strategy:', err);
        // Create new strategy if load fails
        createMainStrategyNode();
      });
    } else {
      // Create new strategy - create main Strategy node
      console.log('[Strategy Builder] Creating new strategy');
      createMainStrategyNode();
    }

    console.log('[Strategy Builder] Rendering block library...');
    renderBlockLibrary();

    console.log('[Strategy Builder] Rendering templates...');
    renderTemplates();

    console.log('[Strategy Builder] Setting up event listeners...');
    setupEventListeners();

    console.log('[Strategy Builder] Initializing connection system...');
    initConnectionSystem();

    console.log('[Strategy Builder] Rendering blocks...');
    renderBlocks();

    // Раскрыть первую секцию Properties по умолчанию
    setTimeout(() => {
      const firstSection = document.querySelector('.properties-section');
      if (firstSection) {
        firstSection.classList.remove('collapsed');
        console.log('[Strategy Builder] First properties section expanded');
      }
    }, 100);

    // Periodic autosave to localStorage and server
    setInterval(autoSaveStrategy, AUTOSAVE_INTERVAL_MS);

    console.log('[Strategy Builder] Initialization complete!');
  } catch (error) {
    console.error('[Strategy Builder] Initialization error:', error);
    alert('Ошибка инициализации Strategy Builder. Проверьте консоль браузера (F12) для деталей.');
  }
});

// Create the main Strategy node that cannot be deleted
function createMainStrategyNode() {
  const mainNode = {
    id: 'main_strategy',
    type: 'strategy',
    category: 'main',
    name: 'Strategy',
    icon: 'diagram-3',
    x: 400,
    y: 200,
    isMain: true,
    params: {}
  };
  strategyBlocks.push(mainNode);
}

function renderBlockLibrary() {
  const container = document.getElementById('blockCategories');
  if (!container) {
    console.error('[Strategy Builder] Block categories container not found!');
    return;
  }
  container.innerHTML = '';

  const categories = [
    { key: 'indicators', name: 'Indicators', iconType: 'indicator' },
    { key: 'filters', name: 'Filters', iconType: 'filter' },
    { key: 'conditions', name: 'Conditions', iconType: 'condition' },
    { key: 'actions', name: 'Actions', iconType: 'action' },
    { key: 'exits', name: 'Close Conditions', iconType: 'exit' },
    { key: 'position_sizing', name: 'Position Sizing', iconType: 'sizing' },
    { key: 'entry_refinement', name: 'Entry Refinement', iconType: 'entry' },
    { key: 'risk_controls', name: 'Risk Controls', iconType: 'risk' },
    { key: 'session_mgmt', name: 'Session Management', iconType: 'session' },
    { key: 'time_mgmt', name: 'Time Management', iconType: 'time' },
    { key: 'logic', name: 'Logic', iconType: 'logic' },
    { key: 'inputs', name: 'Inputs', iconType: 'input' }
  ];

  categories.forEach((cat) => {
    const blocks = blockLibrary[cat.key];
    const html = `
                    <div class="block-category collapsed">
                        <div class="category-header">
                            <i class="bi bi-chevron-right"></i>
                            <span class="category-count">(${blocks.length})</span>
                            <span class="category-title">${cat.name}</span>
                        </div>
                        <div class="block-list">
                            ${blocks
        .map(
          (block) => `
                                <div class="block-item" 
                                     draggable="true" 
                                     data-block-id="${block.id}"
                                     data-block-type="${cat.iconType}">
                                    <div class="block-icon ${cat.iconType}">
                                        <i class="bi bi-${block.icon}"></i>
                                    </div>
                                    <div class="block-info">
                                        <div class="block-name">${block.name}</div>
                                        <div class="block-desc">${block.desc}</div>
                                    </div>
                                </div>
                            `
        )
        .join('')}
                        </div>
                    </div>
                `;
    container.innerHTML += html;
  });

  console.log('[Strategy Builder] Block library rendered. Categories in DOM:',
    document.querySelectorAll('.block-category').length);
}

function renderTemplates() {
  console.log('[Strategy Builder] Rendering templates, count:', templates.length);
  const container = document.getElementById('templatesGrid');
  if (!container) {
    console.error('[Strategy Builder] Templates grid container not found!');
    return;
  }

  if (templates.length === 0) {
    console.warn('[Strategy Builder] No templates available!');
    container.innerHTML = '<div class="text-center py-4"><p class="text-secondary">No templates available</p></div>';
    return;
  }

  container.innerHTML = templates
    .map(
      (template) => `
                <div class="template-card ${selectedTemplate === template.id ? 'selected' : ''}" 
                     data-template-id="${template.id}">
                    <div class="template-icon" style="background: ${template.iconColor}15; color: ${template.iconColor}">
                        <i class="bi bi-${template.icon}"></i>
                    </div>
                    <div class="template-name">${template.name}</div>
                    <div class="template-desc">${template.desc}</div>
                    <div class="template-meta">
                        <span><i class="bi bi-box"></i> ${template.blocks} blocks</span>
                        <span><i class="bi bi-link"></i> ${template.connections} connections</span>
                        <span><i class="bi bi-tag"></i> ${template.category}</span>
                    </div>
                </div>
            `
    )
    .join('');

  console.log(
    '[Strategy Builder] Templates rendered, HTML length:',
    container.innerHTML.length,
    'Templates in DOM:',
    container.querySelectorAll('.template-card').length
  );
}

function setupEventListeners() {
  console.log('[Strategy Builder] Setting up event listeners...');

  // Canvas drop zone
  const canvas = document.getElementById('canvasContainer');
  if (canvas) {
    canvas.addEventListener('dragover', (e) => e.preventDefault());
    canvas.addEventListener('drop', onCanvasDrop);
    console.log('[Strategy Builder] Canvas event listeners attached');
  } else {
    console.error('[Strategy Builder] Canvas container not found!');
  }

  // Block search
  document
    .getElementById('blockSearch')
    .addEventListener('input', filterBlocks);

  // Block library - drag start (event delegation for CSP compliance)
  const blockCategories = document.getElementById('blockCategories');
  if (blockCategories) {
    blockCategories.addEventListener('dragstart', function (e) {
      const blockItem = e.target.closest('.block-item');
      if (blockItem) {
        const blockId = blockItem.dataset.blockId;
        const blockType = blockItem.dataset.blockType;
        e.dataTransfer.setData('blockId', blockId);
        e.dataTransfer.setData('blockType', blockType);
        e.dataTransfer.effectAllowed = 'copy';
      }
    });

    // Block click to add (event delegation)
    blockCategories.addEventListener('click', function (e) {
      console.log('[Strategy Builder] Block categories clicked:', e.target, e.target.className);

      // Check if clicking on category header - don't prevent default, let sidebar-toggle handle it
      const categoryHeader = e.target.closest('.category-header');
      if (categoryHeader) {
        console.log('[Strategy Builder] Category header clicked - letting sidebar-toggle handle');
        return; // Let sidebar-toggle.js handle category toggle
      }

      // Check if clicking on block item
      const blockItem = e.target.closest('.block-item');
      if (blockItem) {
        const blockId = blockItem.dataset.blockId;
        const blockType = blockItem.dataset.blockType;
        console.log(`[Strategy Builder] Block item clicked: ${blockId}, type: ${blockType}`);
        e.preventDefault();
        e.stopPropagation();
        addBlockToCanvas(blockId, blockType);
        return;
      }

      // Check if clicking on block icon or name inside block-item
      const blockIcon = e.target.closest('.block-icon');
      const blockName = e.target.closest('.block-name');
      if (blockIcon || blockName) {
        const blockItem = (blockIcon || blockName).closest('.block-item');
        if (blockItem) {
          const blockId = blockItem.dataset.blockId;
          const blockType = blockItem.dataset.blockType;
          console.log(`[Strategy Builder] Block icon/name clicked: ${blockId}, type: ${blockType}`);
          e.preventDefault();
          e.stopPropagation();
          addBlockToCanvas(blockId, blockType);
        }
      }
    });
  }

  // Canvas blocks - event delegation for drag and select
  const blocksContainer = document.getElementById('blocksContainer');
  if (blocksContainer) {
    // Block selection
    blocksContainer.addEventListener('click', function (e) {
      const block = e.target.closest('.strategy-block');
      if (block && !e.target.closest('.block-header-menu') && !e.target.closest('.block-action-btn')) {
        selectBlock(block.id);
      }
    });

    // Block menu - show params popup
    blocksContainer.addEventListener('click', function (e) {
      const menuBtn = e.target.closest('.block-header-menu');
      if (menuBtn) {
        e.stopPropagation();
        const block = menuBtn.closest('.strategy-block');
        if (block) {
          showBlockParamsPopup(block.id);
        }
      }
    });

    // Block action buttons (Delete, Duplicate)
    blocksContainer.addEventListener('click', function (e) {
      const actionBtn = e.target.closest('.block-action-btn');
      if (actionBtn) {
        e.stopPropagation();
        const block = actionBtn.closest('.strategy-block');
        const action = actionBtn.dataset.action;
        console.log('[Strategy Builder] Action button clicked:', action, 'block:', block?.id);
        if (block && action) {
          if (action === 'delete') {
            deleteBlock(block.id);
          } else if (action === 'duplicate') {
            duplicateBlock(block.id);
          }
        }
      }
    });

    // Block dragging
    blocksContainer.addEventListener('mousedown', function (e) {
      const block = e.target.closest('.strategy-block');
      if (
        block &&
        !e.target.closest('.block-param-input') &&
        !e.target.closest('.port') &&
        !e.target.closest('.block-header-menu') &&
        !e.target.closest('.block-action-btn') &&
        !e.target.closest('.block-params-popup')
      ) {
        // Check if this block is part of multi-selection for group drag
        if (selectedBlockIds.length > 1 && selectedBlockIds.includes(block.id)) {
          startGroupDrag(e);
        } else {
          startDragBlock(e, block.id);
        }
      }
    });

    // Marquee selection on canvas (click on empty area)
    const canvasContainer = document.getElementById('canvasContainer');
    canvasContainer.addEventListener('mousedown', function (e) {
      // Only start marquee if clicking on empty canvas area (not on a block or popup)
      if (!e.target.closest('.strategy-block') &&
        !e.target.closest('.block-params-popup') &&
        !e.target.closest('.zoom-controls') &&
        !e.target.closest('.canvas-toolbar')) {
        e.preventDefault();
        startMarqueeSelection(e);
      }
    });
  }

  // Keyboard shortcuts
  document.addEventListener('keydown', function (e) {
    // Delete selected block
    if ((e.key === 'Delete' || e.key === 'Backspace') && selectedBlockId) {
      // Don't delete if typing in an input
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')
        return;
      e.preventDefault();
      deleteSelected();
    }
    // Duplicate with Ctrl+D
    if (e.key === 'd' && e.ctrlKey && selectedBlockId) {
      e.preventDefault();
      duplicateSelected();
    }
  });

  // =====================================================
  // Navbar buttons (CSP-compliant event listeners by ID)
  // =====================================================

  // Templates button - MUST be set up BEFORE overlay handler
  const btnTemplates = document.getElementById('btnTemplates');
  if (btnTemplates) {
    // Flag to prevent overlay from closing modal when opening via button
    let openingViaButton = false;

    btnTemplates.addEventListener('click', function (e) {
      console.log('[Strategy Builder] Templates button clicked');
      e.preventDefault();
      e.stopImmediatePropagation(); // Stop ALL event propagation immediately

      const modal = document.getElementById('templatesModal');
      const isCurrentlyOpen = modal && modal.classList.contains('active');

      if (isCurrentlyOpen) {
        console.log('[Strategy Builder] Modal already open, closing');
        openingViaButton = false;
        closeTemplatesModal();
      } else {
        console.log('[Strategy Builder] Opening modal via button');
        openingViaButton = true;

        // Update open time before opening
        if (window._updateTemplatesModalOpenTime) {
          window._updateTemplatesModalOpenTime();
        }

        // Open modal immediately using requestAnimationFrame to ensure DOM is ready
        requestAnimationFrame(() => {
          openTemplatesModal();

          // Double-check modal is still open after a short delay
          setTimeout(() => {
            if (!modal.classList.contains('active')) {
              console.warn('[Strategy Builder] Modal closed unexpectedly, reopening...');
              modal.classList.add('active');
            }
          }, 50);
        });

        // Reset flag after a delay to allow modal to fully open
        setTimeout(() => {
          openingViaButton = false;
          console.log('[Strategy Builder] Opening flag reset');
        }, 800); // Increased delay to ensure modal is fully opened
      }
    }, true); // Use capture phase to handle BEFORE overlay handler

    console.log('[Strategy Builder] Templates button listener attached');

    // Store flag in window for overlay handler to check
    window._templatesModalOpeningViaButton = () => openingViaButton;
  } else {
    console.error('[Strategy Builder] Templates button not found!');
  }

  // Validation panel auto-close timer
  let validationAutoCloseTimer = null;
  let validationIsHovered = false;
  const VALIDATION_AUTO_CLOSE_MS = 5000; // 5 seconds for initial show
  const VALIDATION_AFTER_HOVER_MS = 1000; // 1 second after mouse leaves

  function showValidationPanel() {
    const validationPanel = document.querySelector('.validation-panel');
    if (!validationPanel) return;

    // If already visible, just restart the timer (don't re-add classes)
    if (validationPanel.classList.contains('visible') && !validationPanel.classList.contains('closing')) {
      startValidationAutoClose();
      return;
    }

    validationPanel.classList.remove('closing');
    validationPanel.classList.add('visible');

    // Start auto-close timer
    startValidationAutoClose();
  }

  function hideValidationPanel() {
    const validationPanel = document.querySelector('.validation-panel');
    if (!validationPanel) return;
    if (!validationPanel.classList.contains('visible')) return;

    clearTimeout(validationAutoCloseTimer);
    validationAutoCloseTimer = null;
    validationPanel.classList.add('closing');
    setTimeout(() => {
      validationPanel.classList.remove('visible', 'closing');
    }, 300);
  }

  function startValidationAutoClose() {
    // Always clear previous timer first
    if (validationAutoCloseTimer) {
      clearTimeout(validationAutoCloseTimer);
      validationAutoCloseTimer = null;
    }

    // Only start new timer if not hovered
    if (!validationIsHovered) {
      validationAutoCloseTimer = setTimeout(() => {
        if (!validationIsHovered) {
          hideValidationPanel();
        }
      }, VALIDATION_AUTO_CLOSE_MS);
    }
  }

  // Setup validation panel hover events
  const validationPanel = document.querySelector('.validation-panel');
  if (validationPanel) {
    validationPanel.addEventListener('mouseenter', () => {
      validationIsHovered = true;
      // Cancel any pending close timer
      if (validationAutoCloseTimer) {
        clearTimeout(validationAutoCloseTimer);
        validationAutoCloseTimer = null;
      }
    });
    validationPanel.addEventListener('mouseleave', () => {
      validationIsHovered = false;
      // Start 1-second timer when mouse leaves
      if (validationAutoCloseTimer) {
        clearTimeout(validationAutoCloseTimer);
        validationAutoCloseTimer = null;
      }
      validationAutoCloseTimer = setTimeout(() => {
        if (!validationIsHovered) {
          hideValidationPanel();
        }
      }, VALIDATION_AFTER_HOVER_MS);
    });
  }

  // Validate button - shows validation panel with auto-close
  const btnValidate = document.getElementById('btnValidate');
  if (btnValidate) {
    btnValidate.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      console.log('[Strategy Builder] Validate button clicked');
      try {
        validateStrategy();
        showValidationPanel();
      } catch (err) {
        console.error('[Strategy Builder] Validate error:', err);
        alert(`Validate error: ${err.message}`);
      }
    });
    console.log('[Strategy Builder] Validate button listener attached');
  } else {
    console.error('[Strategy Builder] Validate button not found!');
  }

  // Generate Code button
  const btnGenerateCode = document.getElementById('btnGenerateCode');
  if (btnGenerateCode) {
    btnGenerateCode.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      console.log('[Strategy Builder] Generate Code button clicked');
      try {
        generateCode();
      } catch (err) {
        console.error('[Strategy Builder] Generate Code error:', err);
        alert(`Generate Code error: ${err.message}`);
      }
    });
    console.log('[Strategy Builder] Generate Code button listener attached');
  } else {
    console.error('[Strategy Builder] Generate Code button not found!');
  }

  // Save button
  const btnSave = document.getElementById('btnSave');
  if (btnSave) {
    btnSave.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      console.log('[Strategy Builder] Save button clicked');
      try {
        saveStrategy();
      } catch (err) {
        console.error('[Strategy Builder] Save error:', err);
        alert(`Save error: ${err.message}`);
      }
    });
    console.log('[Strategy Builder] Save button listener attached');
  } else {
    console.error('[Strategy Builder] Save button not found!');
  }

  // Backtest button
  const btnBacktest = document.getElementById('btnBacktest');
  if (btnBacktest) {
    btnBacktest.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      console.log('[Strategy Builder] Backtest button clicked');
      try {
        runBacktest();
      } catch (err) {
        console.error('[Strategy Builder] Backtest error:', err);
        alert(`Backtest error: ${err.message}`);
      }
    });
    console.log('[Strategy Builder] Backtest button listener attached');
  } else {
    console.error('[Strategy Builder] Backtest button not found!');
  }

  // Toolbar buttons
  document.querySelectorAll('[onclick*="undo()"]').forEach((btn) => {
    btn.removeAttribute('onclick');
    btn.addEventListener('click', undo);
  });

  document.querySelectorAll('[onclick*="redo()"]').forEach((btn) => {
    btn.removeAttribute('onclick');
    btn.addEventListener('click', redo);
  });

  document.querySelectorAll('[onclick*="deleteSelected"]').forEach((btn) => {
    btn.removeAttribute('onclick');
    btn.addEventListener('click', deleteSelected);
  });

  document.querySelectorAll('[onclick*="duplicateSelected"]').forEach((btn) => {
    btn.removeAttribute('onclick');
    btn.addEventListener('click', duplicateSelected);
  });

  document.querySelectorAll('[onclick*="alignBlocks"]').forEach((btn) => {
    const match = btn
      .getAttribute('onclick')
      .match(/alignBlocks\(['"](\w+)['"]\)/);
    const direction = match ? match[1] : 'left';
    btn.removeAttribute('onclick');
    btn.addEventListener('click', () => alignBlocks(direction));
  });

  document.querySelectorAll('[onclick*="autoLayout"]').forEach((btn) => {
    btn.removeAttribute('onclick');
    btn.addEventListener('click', autoLayout);
  });

  document.querySelectorAll('[onclick*="fitToScreen"]').forEach((btn) => {
    btn.removeAttribute('onclick');
    btn.addEventListener('click', fitToScreen);
  });

  // Zoom buttons
  document.querySelectorAll('[onclick*="zoomIn"]').forEach((btn) => {
    btn.removeAttribute('onclick');
    btn.addEventListener('click', zoomIn);
  });

  document.querySelectorAll('[onclick*="zoomOut"]').forEach((btn) => {
    btn.removeAttribute('onclick');
    btn.addEventListener('click', zoomOut);
  });

  document.querySelectorAll('[onclick*="resetZoom"]').forEach((btn) => {
    btn.removeAttribute('onclick');
    btn.addEventListener('click', resetZoom);
  });

  // Modal buttons by ID
  const btnCloseModal = document.getElementById('btnCloseModal');
  if (btnCloseModal) {
    btnCloseModal.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      console.log('[Strategy Builder] Close button clicked');
      closeTemplatesModal();
    });
  } else {
    console.warn('[Strategy Builder] Close modal button not found');
  }

  const btnCancelModal = document.getElementById('btnCancelModal');
  if (btnCancelModal) {
    btnCancelModal.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      console.log('[Strategy Builder] Cancel button clicked');
      closeTemplatesModal();
    });
  } else {
    console.warn('[Strategy Builder] Cancel modal button not found');
  }

  const btnLoadTemplate = document.getElementById('btnLoadTemplate');
  if (btnLoadTemplate) {
    btnLoadTemplate.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      console.log('[Strategy Builder] Load Template button clicked');
      loadSelectedTemplate();
    });
  } else {
    console.warn('[Strategy Builder] Load Template button not found');
  }

  // Templates grid - event delegation for template selection
  const templatesGrid = document.getElementById('templatesGrid');
  if (templatesGrid) {
    templatesGrid.addEventListener('click', function (e) {
      const card = e.target.closest('.template-card');
      if (card) {
        const templateId = card.dataset.templateId;
        if (templateId) {
          selectTemplate(templateId);
        }
      }
    });
  }

  // Templates modal: do NOT close on overlay click (caused immediate close / invisible content).
  // Close only via Close (X), Cancel, or Use Template buttons.
  const templatesModal = document.getElementById('templatesModal');
  if (templatesModal) {
    // No overlay click handler - modal closes only via btnCloseModal, btnCancelModal, btnLoadTemplate
    window._updateTemplatesModalOpenTime = () => { }; // no-op for compatibility

    // Prevent modal content clicks from bubbling to overlay
    const modalContent = templatesModal.querySelector('.modal');
    if (modalContent) {
      modalContent.addEventListener('click', function (e) {
        console.log('[Strategy Builder] Modal content click, stopping propagation');
        e.stopPropagation();
      });
    } else {
      console.warn('[Strategy Builder] Modal content (.modal) not found!');
    }
  } else {
    console.error('[Strategy Builder] Templates modal not found during setup!');
  }
}

function toggleCategory(header) {
  const category = header.parentElement;
  const wasCollapsed = category.classList.contains('collapsed');

  // Toggle collapsed state
  category.classList.toggle('collapsed');

  // Update icon
  const icon = header.querySelector('i');
  icon.classList.toggle('bi-chevron-down');
  icon.classList.toggle('bi-chevron-right');

  // If opening category, scroll it to the top of the container
  if (wasCollapsed) {
    setTimeout(() => {
      const container = category.closest('.block-categories');
      if (container) {
        // Scroll category to top of container
        const categoryTop = category.offsetTop - container.offsetTop;
        container.scrollTo({
          top: categoryTop,
          behavior: 'smooth'
        });
      }
    }, 50);
  }
}

function filterBlocks() {
  const search = document.getElementById('blockSearch').value.toLowerCase();
  const items = document.querySelectorAll('.block-item');

  items.forEach((item) => {
    const name = item.querySelector('.block-name').textContent.toLowerCase();
    const desc = item.querySelector('.block-desc').textContent.toLowerCase();
    item.style.display =
      name.includes(search) || desc.includes(search) ? 'flex' : 'none';
  });
}

function onBlockDragStart(event, blockId, blockType) {
  event.dataTransfer.setData('blockId', blockId);
  event.dataTransfer.setData('blockType', blockType);
}

function onCanvasDrop(event) {
  event.preventDefault();
  console.log('[Strategy Builder] Canvas drop event');
  const blockId = event.dataTransfer.getData('blockId');
  const blockType = event.dataTransfer.getData('blockType');
  console.log(`[Strategy Builder] Dropped block: ${blockId}, type: ${blockType}`);

  if (blockId && blockType) {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    console.log(`[Strategy Builder] Drop position: x=${x}, y=${y}`);
    addBlockToCanvas(blockId, blockType, x, y);
  } else {
    console.warn('[Strategy Builder] Drop data missing');
  }
}

function addBlockToCanvas(blockId, blockType, x = null, y = null) {
  console.log(`[Strategy Builder] addBlockToCanvas called: blockId=${blockId}, blockType=${blockType}`);

  // Find block definition
  let blockDef = null;
  Object.values(blockLibrary).forEach((category) => {
    const found = category.find((b) => b.id === blockId);
    if (found) blockDef = found;
  });

  if (!blockDef) {
    console.error(`[Strategy Builder] Block definition not found for: ${blockId}`);
    showNotification(`Блок "${blockId}" не найден`, 'error');
    return;
  }

  console.log('[Strategy Builder] Block definition found:', blockDef);

  // Create block
  const block = {
    id: `block_${Date.now()}`,
    type: blockId,
    category: blockType,
    name: blockDef.name,
    icon: blockDef.icon,
    x: x || 100 + strategyBlocks.length * 50,
    y: y || 100 + strategyBlocks.length * 30,
    params: getDefaultParams(blockId),
    optimizationParams: {} // For optimization ranges
  };

  console.log('[Strategy Builder] Created block:', block);
  strategyBlocks.push(block);
  console.log(`[Strategy Builder] Total blocks: ${strategyBlocks.length}`);

  renderBlocks();
  selectBlock(block.id);

  // Notify optimization panels about block changes
  dispatchBlocksChanged();

  console.log('[Strategy Builder] Block added to canvas successfully');
  showNotification(`Блок "${blockDef.name}" добавлен`, 'success');
}

function getDefaultParams(blockType) {
  const params = {
    // =============================================
    // MOMENTUM INDICATORS
    // =============================================
    rsi: {
      period: 14,
      source: 'close',
      timeframe: 'Chart',
      overbought: 70,
      oversold: 30
    },
    stochastic: {
      k_period: 14,
      d_period: 3,
      smooth_k: 3,
      timeframe: 'Chart',
      overbought: 80,
      oversold: 20
    },
    stoch_rsi: {
      rsi_period: 14,
      stoch_period: 14,
      k_period: 3,
      d_period: 3,
      overbought: 80,
      oversold: 20
    },
    williams_r: {
      period: 14,
      overbought: -20,
      oversold: -80
    },
    roc: {
      period: 12,
      source: 'close'
    },
    mfi: {
      period: 14,
      overbought: 80,
      oversold: 20
    },
    cmo: {
      period: 14,
      overbought: 50,
      oversold: -50
    },
    cci: {
      period: 20,
      overbought: 100,
      oversold: -100
    },

    // =============================================
    // TREND INDICATORS
    // =============================================
    sma: {
      period: 50,
      source: 'close',
      offset: 0
    },
    ema: {
      period: 20,
      source: 'close',
      offset: 0
    },
    wma: {
      period: 20,
      source: 'close'
    },
    dema: {
      period: 20,
      source: 'close'
    },
    tema: {
      period: 20,
      source: 'close'
    },
    hull_ma: {
      period: 16,
      source: 'close'
    },
    macd: {
      fast_period: 12,
      slow_period: 26,
      signal_period: 9,
      source: 'close'
    },
    adx: {
      period: 14,
      threshold: 25
    },
    supertrend: {
      period: 10,
      multiplier: 3.0,
      source: 'hl2'
    },
    ichimoku: {
      tenkan_period: 9,
      kijun_period: 26,
      senkou_b_period: 52,
      displacement: 26
    },
    parabolic_sar: {
      start: 0.02,
      increment: 0.02,
      max_value: 0.2
    },
    aroon: {
      period: 25,
      threshold: 70
    },
    qqe: {
      rsi_period: 14,
      qqe_factor: 4.238,
      smoothing_period: 5,
      source: 'close',
      timeframe: 'Chart'
    },

    // =============================================
    // VOLATILITY INDICATORS
    // =============================================
    atr: {
      period: 14
    },
    atrp: {
      period: 14
    },
    bollinger: {
      period: 20,
      std_dev: 2.0,
      source: 'close'
    },
    keltner: {
      ema_period: 20,
      atr_period: 10,
      multiplier: 2.0
    },
    donchian: {
      period: 20
    },
    stddev: {
      period: 20,
      source: 'close'
    },

    // =============================================
    // VOLUME INDICATORS
    // =============================================
    obv: {},
    vwap: {
      anchor: 'session'
    },
    cmf: {
      period: 20
    },
    ad_line: {},
    pvt: {},

    // =============================================
    // SUPPORT/RESISTANCE
    // =============================================
    pivot_points: {
      type: 'traditional',
      timeframe: '1D'
    },

    // =============================================
    // MULTI-TIMEFRAME
    // =============================================
    mtf: {
      indicator: 'ema',
      period: 20,
      source: 'close',
      timeframe: '1h',
      show_on_chart: true
    },

    // =============================================
    // FILTERS
    // =============================================
    rsi_filter: {
      // RSI TF1
      rsi_period: 14,
      rsi_timeframe: 'chart',
      use_btcusdt_source: false,
      use_long_range: false,
      long_rsi_more: 1,
      long_rsi_less: 50,
      use_short_range: false,
      short_rsi_less: 100,
      short_rsi_more: 50,
      use_cross_level: false,
      cross_level_long: 30,
      cross_level_short: 70,
      opposite_signal: false,
      use_signal_memory: false,
      signal_memory_bars: 5,
      // RSI TF2
      use_rsi_tf2: false,
      rsi_tf2_period: 14,
      rsi_tf2_timeframe: '1h',
      rsi_tf2_long_more: 1,
      rsi_tf2_long_less: 50,
      rsi_tf2_short_more: 50,
      rsi_tf2_short_less: 100,
      // RSI TF3
      use_rsi_tf3: false,
      rsi_tf3_period: 14,
      rsi_tf3_timeframe: '4h',
      rsi_tf3_long_more: 1,
      rsi_tf3_long_less: 50,
      rsi_tf3_short_more: 50,
      rsi_tf3_short_less: 100
    },
    supertrend_filter: {
      // SuperTrend TF1
      use_supertrend: false,
      generate_on_trend_change: false,
      use_btc_source: false,
      opposite_signal: false,
      show_supertrend: false,
      atr_period: 10,
      atr_multiplier: 3.0,
      timeframe: 'Chart',
      // SuperTrend TF2
      use_supertrend_tf2: false,
      supertrend_tf2_btc_source: false,
      supertrend_tf2_opposite: false,
      supertrend_tf2_show: false,
      supertrend_tf2_period: 10,
      supertrend_tf2_multiplier: 3.0,
      supertrend_tf2_timeframe: '1h',
      // SuperTrend TF3
      use_supertrend_tf3: false,
      supertrend_tf3_opposite: false,
      supertrend_tf3_show: false,
      supertrend_tf3_period: 10,
      supertrend_tf3_multiplier: 3.0,
      supertrend_tf3_timeframe: '4h'
    },
    // =============================================
    // TWO MA's MOV [SIGNAL AND FILTER]
    // =============================================
    two_ma_filter: {
      // MA1 Settings
      ma1_length: 50,
      ma1_type: 'WMA',
      ma1_source: 'close',
      // MA2 Settings
      ma2_length: 100,
      ma2_type: 'EMA',
      ma2_source: 'close',
      // Visualization
      show_two_mas: false,
      // MA1/MA2 Cross Mode
      use_ma_cross: false,
      opposite_ma_cross: false,
      activate_ma_cross_memory: false,
      ma_cross_memory_bars: 5,
      // MA1 as Filter Mode
      use_ma1_filter: false,
      opposite_ma1_filter: false,
      // TimeFrame
      two_ma_timeframe: 'Chart'
    },
    // =============================================
    // STOCHASTIC [RANGE FILTER]
    // =============================================
    stochastic_filter: {
      // Basic Settings
      stoch_k_length: 14,
      stoch_k_smoothing: 3,
      stoch_d_smoothing: 3,
      stoch_timeframe: 'Chart',
      use_btcusdt_source: false,
      // Range Filter Mode
      use_stoch_range_filter: false,
      long_stoch_d_more: 0,
      long_stoch_d_less: 20,
      short_stoch_d_less: 100,
      short_stoch_d_more: 80,
      // Cross Level Mode
      use_stoch_cross_level: false,
      stoch_cross_level_long: 20,
      stoch_cross_level_short: 80,
      activate_stoch_cross_memory: false,
      stoch_cross_memory_bars: 5,
      // K/D Cross Mode
      use_stoch_kd_cross: false,
      opposite_stoch_kd: false,
      activate_stoch_kd_memory: false,
      stoch_kd_memory_bars: 5
    },
    // =============================================
    // MACD [SIGNALS, CROSS X LINE OR CROSS SIGNAL LINE]
    // =============================================
    macd_filter: {
      // Basic Settings
      macd_fast_length: 12,
      macd_slow_length: 26,
      macd_signal_smoothing: 9,
      macd_source: 'close',
      macd_timeframe: 'Chart',
      use_btcusdt_source: false,
      // Visualization
      enable_macd_visualization: false,
      // Cross with Zero Level Mode
      use_macd_cross_zero: false,
      opposite_macd_cross_zero: false,
      macd_cross_zero_level: 0,
      // Cross with Signal Line Mode
      use_macd_cross_signal: false,
      signal_only_if_macd_positive: false,
      opposite_macd_cross_signal: false,
      // Signal Memory
      disable_macd_signal_memory: false,
      macd_signal_memory_bars: 5
    },
    // =============================================
    // QQE [SIGNALS]
    // =============================================
    qqe_filter: {
      use_qqe: false,
      opposite_qqe: false,
      enable_qqe_visualization: false,
      disable_qqe_signal_memory: false,
      qqe_rsi_length: 14,
      qqe_rsi_smoothing: 5,
      qqe_delta_multiplier: 5.1
    },
    // =============================================
    // CCI [TIMEFRAME]
    // =============================================
    cci_filter: {
      cci_length: 14,
      cci_timeframe: 'Chart',
      use_btcusdt_source: false,
      // Long Range
      use_cci_long_range: false,
      long_cci_more: -400,
      long_cci_less: 400,
      // Short Range
      use_cci_short_range: false,
      short_cci_less: 400,
      short_cci_more: -400
    },
    // =============================================
    // MOMENTUM
    // =============================================
    momentum_filter: {
      momentum_length: 14,
      momentum_timeframe: 'Chart',
      momentum_source: 'close',
      use_btcusdt_source: false,
      // Long Range
      use_momentum_long_range: false,
      long_momentum_more: 100,
      long_momentum_less: 180,
      // Short Range
      use_momentum_short_range: false,
      short_momentum_less: 100,
      short_momentum_more: -180
    },
    // =============================================
    // DMI (ADX)
    // =============================================
    dmi_filter: {
      dmi_period: 14,
      adx_smoothing: 14,
      dmi_timeframe: 'Chart',
      use_btcusdt_source: false,
      // Long using DMI
      use_dmi_long: false,
      dmi_long_di_plus: true,
      dmi_long_threshold: 0,
      // Short using DMI
      use_dmi_short: false,
      dmi_short_di_minus: true,
      dmi_short_threshold: 0,
      // ADX Filter
      use_adx_filter: false,
      adx_threshold: 25
    },
    // =============================================
    // CMF Filter (Chaikin Money Flow)
    // =============================================
    cmf_filter: {
      use_cmf: false,
      opposite_cmf: false,
      cmf_length: 20,
      cmf_timeframe: 'Chart',
      use_btcusdt_source: false,
      // Long range
      cmf_long_min: 0,
      cmf_long_max: 100,
      // Short range
      cmf_short_min: -100,
      cmf_short_max: 0
    },
    // =============================================
    // Balance of Power Filter (Extended DCA)
    // =============================================
    bop_filter: {
      use_bop: false,
      opposite_bop: false,
      bop_smoothing: 14,
      bop_triple_smooth_length: 4,
      bop_timeframe: 'Chart',
      use_btcusdt_source: false,
      // Cross line mode
      bop_cross_line_enable: false,
      bop_disable_memory: false,
      bop_cross_level: 0,
      // Long range
      bop_long_min: 0,
      bop_long_max: 100,
      // Short range
      bop_short_min: -100,
      bop_short_max: 0
    },
    // =============================================
    // Block if Worse Than Filter (DCA)
    // =============================================
    block_worse_filter: {
      block_worse_enable: false,
      block_worse_percent: 0.5
    },
    // =============================================
    // Levels Break Filter (Pivot S&R) - Extended DCA
    // =============================================
    levels_filter: {
      use_levels: false,
      levels_pivot_bars: 10,
      levels_search_period: 100,
      levels_channel_width: 0.5,
      levels_test_count: 2,
      levels_opposite: false,
      levels_memory_enable: false,
      levels_memory_bars: 5,
      pivot_type: 'Traditional',
      levels_timeframe: 'D',
      // Long conditions
      long_above_s1: false,
      long_above_pivot: false,
      long_break_r1: false,
      // Short conditions
      short_below_r1: false,
      short_below_pivot: false,
      short_break_s1: false
    },
    // =============================================
    // ATR Volatility Filter
    // =============================================
    atr_filter: {
      use_atr_filter: false,
      atr_length: 14,
      atr_multiplier: 1.0,
      atr_timeframe: 'Chart',
      use_btcusdt_source: false,
      // Min/Max ATR % range
      atr_min_percent: 0.5,
      atr_max_percent: 5.0,
      // Filter mode
      atr_filter_mode: 'between'
    },
    // =============================================
    // Volume Compare Filter
    // =============================================
    volume_compare_filter: {
      use_vol_compare: false,
      vol_ma_length: 20,
      vol_ma_type: 'SMA',
      vol_timeframe: 'Chart',
      use_btcusdt_source: false,
      // Volume threshold
      vol_multiplier: 1.5,
      vol_compare_mode: 'above',
      // Consecutive bars
      vol_consecutive_bars: 1
    },
    // =============================================
    // Highest/Lowest Bar Filter
    // =============================================
    highest_lowest_filter: {
      use_highest_lowest: false,
      lookback_period: 20,
      hl_timeframe: 'Chart',
      use_btcusdt_source: false,
      // Long conditions
      long_break_highest: true,
      long_above_lowest: false,
      // Short conditions
      short_break_lowest: true,
      short_below_highest: false
    },
    // =============================================
    // Accumulation Areas Filter - Extended DCA
    // =============================================
    accumulation_filter: {
      use_accumulation: false,
      acc_backtrack_interval: 50,
      acc_min_bars: 3,
      acc_breakout_signal: true,
      acc_opposite_direction: false,
      volume_threshold: 2.0,
      price_range_percent: 1.0,
      min_bars_in_range: 5,
      acc_timeframe: 'Chart',
      // Entry conditions
      enter_on_breakout: true,
      enter_in_range: false
    },
    // =============================================
    // Linear Regression Channel Filter (Extended DCA)
    // =============================================
    linreg_filter: {
      use_linreg: false,
      disable_linreg_memory: false,
      linreg_memory_bars: 5,
      linreg_length: 100,
      linreg_offset: 0,
      channel_mult: 2.0,
      linreg_timeframe: 'Chart',
      linreg_source: 'close',
      linreg_breakout_rebound: 'Breakout',
      linreg_slope_direction: 'Allow_Any',
      show_linreg_extend_lines: false,
      show_broken_channel: false,
      // Long conditions
      long_above_lower: true,
      long_slope_up: false,
      // Short conditions
      short_below_upper: true,
      short_slope_down: false
    },
    // =============================================
    // RVI Filter (Relative Volatility Index)
    // =============================================
    rvi_filter: {
      use_rvi: false,
      rvi_length: 10,
      rvi_timeframe: 'Chart',
      rvi_ma_type: 'WMA',
      rvi_ma_length: 14,
      // Long range
      use_rvi_long_range: false,
      rvi_long_more: 50,
      rvi_long_less: 100,
      // Short range
      use_rvi_short_range: false,
      rvi_short_more: 0,
      rvi_short_less: 50
    },
    // =============================================
    // Divergence Filter
    // =============================================
    divergence_filter: {
      use_divergence: false,
      div_indicator: 'RSI',
      div_period: 14,
      div_timeframe: 'Chart',
      pivot_lookback: 5,
      // Types
      use_regular_bullish: true,
      use_regular_bearish: true,
      use_hidden_bullish: false,
      use_hidden_bearish: false
    },
    // =============================================
    // Price Action Filter (47 Candlestick Patterns)
    // =============================================
    price_action_filter: {
      use_price_action: false,
      pa_timeframe: 'Chart',
      // ===== BULLISH REVERSAL (for LONG) =====
      // Classic patterns
      use_hammer: true,
      use_inverted_hammer: false,
      use_engulfing_bull: true,
      use_morning_star: false,
      use_piercing_line: false,
      use_three_white: false,
      use_tweezer_bottom: false,
      use_dragonfly_doji: false,
      use_bullish_harami: false,
      use_rising_three: false,
      use_bullish_marubozu: false,
      // Exotic bullish
      use_pin_bar_bullish: false,
      use_three_line_strike_bull: false,
      use_kicker_bullish: false,
      use_abandoned_baby_bull: false,
      use_belt_hold_bullish: false,
      use_counterattack_bull: false,
      use_ladder_bottom: false,
      use_stick_sandwich_bull: false,
      use_homing_pigeon: false,
      use_matching_low: false,
      // ===== BEARISH REVERSAL (for SHORT) =====
      // Classic patterns
      use_shooting_star: true,
      use_hanging_man: false,
      use_engulfing_bear: true,
      use_evening_star: false,
      use_dark_cloud: false,
      use_three_black: false,
      use_tweezer_top: false,
      use_gravestone_doji: false,
      use_bearish_harami: false,
      use_falling_three: false,
      use_bearish_marubozu: false,
      // Exotic bearish
      use_pin_bar_bearish: false,
      use_three_line_strike_bear: false,
      use_kicker_bearish: false,
      use_abandoned_baby_bear: false,
      use_belt_hold_bearish: false,
      use_counterattack_bear: false,
      use_ladder_top: false,
      use_stick_sandwich_bear: false,
      use_matching_high: false,
      // ===== NEUTRAL / STRUCTURE =====
      use_doji: false,
      use_spinning_top: false,
      use_inside_bar: false,
      use_outside_bar: false,
      // ===== GAP PATTERNS =====
      use_gap_up: false,
      use_gap_down: false,
      use_gap_up_filled: false,
      use_gap_down_filled: false
    },
    trend_filter: {
      ema_period: 50,
      use_ema_slope: true,
      slope_threshold: 0,
      use_adx: false,
      adx_period: 14,
      adx_threshold: 25
    },
    volume_filter: {
      ma_period: 20,
      volume_multiplier: 1.5,
      filter_type: 'above'
    },
    volatility_filter: {
      atr_period: 14,
      atr_multiplier: 1.0,
      use_bb_width: false,
      bb_period: 20,
      bb_threshold: 0.02
    },
    time_filter: {
      start_hour: 9,
      end_hour: 17,
      use_days: false,
      trading_days: [1, 2, 3, 4, 5]
    },
    price_filter: {
      level: 0,
      filter_type: 'above',
      use_ema: false,
      ema_period: 200
    },

    // =============================================
    // CONDITIONS
    // =============================================
    crossover: {
      source_a: 'input_a',
      source_b: 'input_b'
    },
    crossunder: {
      source_a: 'input_a',
      source_b: 'input_b'
    },
    greater_than: {
      value: 0,
      use_input: true
    },
    less_than: {
      value: 0,
      use_input: true
    },
    equals: {
      value: 0,
      tolerance: 0.001
    },
    between: {
      min_value: 0,
      max_value: 100
    },

    // =============================================
    // ACTIONS
    // =============================================
    buy: {
      quantity: 100,
      order_type: 'market',
      use_percent: true
    },
    sell: {
      quantity: 100,
      order_type: 'market',
      use_percent: true
    },
    close: {
      close_percent: 100
    },
    stop_loss: {
      percent: 2.0,
      use_atr: false,
      atr_multiplier: 1.5
    },
    take_profit: {
      percent: 5.0,
      use_atr: false,
      atr_multiplier: 3.0
    },
    trailing_stop: {
      percent: 1.0,
      activation_percent: 1.0,
      use_atr: false,
      atr_multiplier: 2.0
    },

    // =============================================
    // NEW ENTRY TYPES
    // =============================================
    limit_entry: {
      price_offset: 0,
      offset_type: 'percent',
      time_in_force: 'GTC'
    },
    stop_entry: {
      price_offset: 0,
      offset_type: 'percent',
      time_in_force: 'GTC'
    },
    // Indent Order (DCA Feature)
    indent_order: {
      indent_enable: false,
      indent_show_lines: true,
      indent_percent: 0.1,
      indent_cancel_bars: 10
    },

    // =============================================
    // EXIT MANAGEMENT
    // =============================================
    close_long: {
      close_percent: 100
    },
    close_short: {
      close_percent: 100
    },
    close_all: {},

    // =============================================
    // ADVANCED STOPS (Extended DCA)
    // =============================================
    atr_stop: {
      // ATR Stop Loss
      atr_sl_enable: true,
      atr_sl_wicks: true,
      atr_sl_method: 'RMA',
      atr_sl_period: 14,
      atr_sl_multiplier: 2.0,
      // ATR Take Profit
      atr_tp_enable: false,
      atr_tp_wicks: true,
      atr_tp_method: 'RMA',
      atr_tp_period: 14,
      atr_tp_multiplier: 3.0,
      from_entry: true
    },
    chandelier_stop: {
      period: 22,
      atr_multiplier: 3.0
    },

    // =============================================
    // BREAK-EVEN & PROTECTION
    // =============================================
    break_even: {
      trigger_percent: 1.0,
      offset: 0,
      include_commission: true
    },
    profit_lock: {
      trigger_percent: 2.0,
      lock_percent: 1.0,
      step_mode: false,
      step_size: 1.0
    },

    // =============================================
    // PARTIAL EXITS
    // =============================================
    scale_out: {
      exit_percent: 50,
      trigger_type: 'profit_percent',
      trigger_value: 2.0
    },
    multi_tp: {
      tp1_percent: 50,
      tp1_target: 1.0,
      tp2_percent: 30,
      tp2_target: 2.0,
      tp3_percent: 20,
      tp3_target: 3.0,
      use_tp3: true
    },

    // =============================================
    // CLOSE CONDITIONS (EXIT RULES)
    // =============================================
    tp_percent: {
      take_profit_percent: 3.0,
      use_for_long: true,
      use_for_short: true
    },
    sl_percent: {
      stop_loss_percent: 1.5,
      use_for_long: true,
      use_for_short: true
    },
    trailing_stop_exit: {
      activation_percent: 1.0,
      trailing_percent: 0.5,
      trail_type: 'percent'
    },
    atr_exit: {
      atr_period: 14,
      tp_atr_multiplier: 3.0,
      sl_atr_multiplier: 1.5,
      use_atr_tp: true,
      use_atr_sl: true
    },
    time_exit: {
      exit_after_bars: 10,
      exit_after_hours: 0,
      exit_type: 'bars'
    },
    session_exit: {
      exit_session: 'NY_close',
      custom_hour: 16,
      custom_minute: 0,
      use_utc: true
    },
    signal_exit: {
      exit_on_opposite: true,
      exit_on_any_signal: false,
      confirm_bars: 1
    },
    indicator_exit: {
      indicator: 'rsi',
      condition: 'crosses_above',
      threshold: 70,
      exit_long_only: false,
      exit_short_only: false
    },
    break_even_exit: {
      activation_profit_percent: 1.0,
      move_to_profit_percent: 0.1,
      use_for_long: true,
      use_for_short: true
    },
    partial_close: {
      close_percent_1: 50,
      trigger_profit_1: 1.0,
      close_percent_2: 25,
      trigger_profit_2: 2.0,
      use_second_partial: true
    },
    multi_tp_exit: {
      tp1_percent: 1.0,
      tp1_close_percent: 33,
      tp2_percent: 2.0,
      tp2_close_percent: 33,
      tp3_percent: 3.0,
      tp3_close_percent: 34,
      use_tp2: true,
      use_tp3: true
    },
    chandelier_exit: {
      atr_period: 22,
      atr_multiplier: 3.0,
      use_close: true,
      use_for_long: true,
      use_for_short: true
    },

    // =============================================
    // DCA CLOSE CONDITIONS
    // =============================================
    rsi_close: {
      rsi_close_enable: false,
      rsi_close_length: 14,
      rsi_close_timeframe: 'Chart',
      rsi_close_only_profit: true,
      rsi_close_min_profit: 0.5,
      // Reach mode
      rsi_close_reach_enable: false,
      rsi_close_reach_long_more: 70,
      rsi_close_reach_long_less: 0,
      rsi_close_reach_short_more: 100,
      rsi_close_reach_short_less: 30,
      // Cross mode
      rsi_close_cross_enable: false,
      rsi_close_cross_long_level: 70,
      rsi_close_cross_short_level: 30
    },
    stoch_close: {
      stoch_close_enable: false,
      stoch_close_k_length: 14,
      stoch_close_k_smooth: 1,
      stoch_close_d_smooth: 3,
      stoch_close_timeframe: 'Chart',
      stoch_close_only_profit: true,
      stoch_close_min_profit: 0.5,
      // Reach mode
      stoch_close_reach_enable: false,
      stoch_close_reach_long_more: 80,
      stoch_close_reach_long_less: 0,
      stoch_close_reach_short_more: 100,
      stoch_close_reach_short_less: 20,
      // Cross mode
      stoch_close_cross_enable: false,
      stoch_close_cross_long_level: 80,
      stoch_close_cross_short_level: 20
    },
    channel_close: {
      channel_close_enable: false,
      channel_close_timeframe: 'Chart',
      channel_close_band: 'Breakout',
      channel_close_type: 'Keltner',
      channel_close_condition: 'long_upper_short_lower',
      // Keltner params
      channel_close_keltner_length: 20,
      channel_close_keltner_mult: 2.0,
      // Bollinger params
      channel_close_bb_length: 20,
      channel_close_bb_deviation: 2.0
    },
    ma_close: {
      ma_close_enable: false,
      ma_close_show_lines: true,
      ma_close_only_profit: true,
      ma_close_min_profit: 0.5,
      ma_close_ma1_length: 9,
      ma_close_ma1_type: 'EMA',
      ma_close_ma2_length: 21,
      ma_close_ma2_type: 'EMA'
    },
    psar_close: {
      psar_close_enable: false,
      psar_close_opposite: true,
      psar_close_only_profit: true,
      psar_close_min_profit: 0.5,
      psar_close_start: 0.02,
      psar_close_increment: 0.02,
      psar_close_maximum: 0.2,
      psar_close_nth_bar: 0
    },
    time_bars_close: {
      time_bars_close_enable: false,
      close_after_bars: 20,
      close_only_profit: true,
      close_min_profit: 0.5,
      close_max_bars: 100
    },

    // =============================================
    // POSITION SIZING
    // =============================================
    fixed_size: {
      size: 0.1,
      size_type: 'base_currency'
    },
    percent_balance: {
      percent: 10,
      use_available: true
    },
    risk_percent: {
      risk_percent: 2.0,
      stop_distance: 1.0
    },
    atr_sizing: {
      risk_percent: 2.0,
      atr_period: 14,
      atr_multiplier: 2.0
    },
    kelly_criterion: {
      win_rate: 0.5,
      reward_risk: 2.0,
      fraction: 0.5
    },

    // =============================================
    // ENTRY REFINEMENT
    // =============================================
    dca: {
      orders_count: 5,
      price_step: 1.0,
      size_multiplier: 1.0,
      total_size: 100
    },
    pyramiding: {
      max_adds: 3,
      add_size_percent: 50,
      profit_trigger: 1.0
    },
    grid_orders: {
      grid_levels: 5,
      grid_step: 1.0,
      size_per_level: 20
    },
    average_down: {
      max_adds: 3,
      loss_trigger: 2.0,
      add_size_percent: 100
    },
    reentry: {
      wait_bars: 5,
      max_reentries: 2,
      same_direction: true
    },
    martingale: {
      multiplier: 2.0,
      max_steps: 5,
      reset_on_win: true,
      max_position_size: 1000
    },
    anti_martingale: {
      multiplier: 1.5,
      max_steps: 3,
      reset_on_loss: true,
      base_size_percent: 10
    },
    dca_by_signal: {
      max_dca_orders: 5,
      size_multiplier: 1.0,
      same_signal_required: true,
      min_bars_between: 3
    },
    dca_by_percent: {
      price_drop_percent: 2.0,
      max_dca_orders: 5,
      size_per_order: 20,
      size_multiplier: 1.5,
      use_multiplier: true
    },
    scale_in: {
      total_orders: 3,
      first_order_percent: 50,
      interval_type: 'bars',
      interval_value: 5,
      price_condition: 'any'
    },

    // =============================================
    // RISK CONTROLS (CIRCUIT BREAKERS)
    // =============================================
    max_daily_loss: {
      max_loss_percent: 5.0,
      max_loss_amount: 0,
      use_percent: true,
      reset_hour: 0
    },
    max_drawdown: {
      max_dd_percent: 10.0,
      from_peak: true,
      stop_all_trading: true
    },
    max_trades_day: {
      max_trades: 10,
      reset_hour: 0
    },
    consecutive_loss: {
      max_consecutive: 3,
      cooloff_hours: 24
    },
    cooloff_period: {
      cooloff_hours: 24,
      trigger_type: 'loss_count',
      trigger_value: 3
    },

    // =============================================
    // SESSION MANAGEMENT
    // =============================================
    active_hours: {
      start_hour: 9,
      end_hour: 17,
      timezone: 'UTC'
    },
    trading_days: {
      monday: true,
      tuesday: true,
      wednesday: true,
      thursday: true,
      friday: true,
      saturday: false,
      sunday: false
    },
    session_filter: {
      london: true,
      new_york: true,
      tokyo: false,
      sydney: false,
      overlap_only: false
    },
    news_filter: {
      high_impact: true,
      medium_impact: false,
      minutes_before: 30,
      minutes_after: 30
    },
    weekend_close: {
      close_friday_hour: 21,
      close_all: true
    },

    // =============================================
    // TIME MANAGEMENT
    // =============================================
    time_stop: {
      hours: 24,
      close_in_profit: false,
      close_in_loss: true
    },
    max_duration: {
      max_hours: 48,
      action: 'close'
    },
    session_close: {
      close_hour: 16,
      close_minute: 0,
      timezone: 'UTC'
    },
    intraday_only: {
      close_hour: 23,
      close_minute: 0
    },

    // =============================================
    // LOGIC
    // =============================================
    and: {},
    or: {},
    not: {},
    delay: {
      bars: 1,
      delay_type: 'bars'
    },
    filter: {
      filter_type: 'pass'
    },

    // =============================================
    // INPUTS
    // =============================================
    price: {
      source: 'close'
    },
    volume: {},
    constant: {
      value: 0
    },

    // =============================================
    // CORRELATION & MULTI-SYMBOL
    // =============================================
    correlation_filter: {
      use_correlation: false,
      correlated_symbol: 'BTCUSDT',
      correlation_period: 20,
      min_correlation: 0.7,
      max_correlation: 1.0,
      correlation_mode: 'positive',
      use_for_long: true,
      use_for_short: true
    },
    btc_dominance: {
      use_btc_dom: false,
      btc_dom_threshold: 50,
      condition: 'above',
      use_trend: false,
      trend_period: 10
    },
    sector_strength: {
      use_sector: false,
      benchmark_symbol: 'BTCUSDT',
      lookback_period: 20,
      min_outperformance: 5,
      use_for_long: true,
      use_for_short: true
    },
    relative_strength: {
      use_rs: false,
      benchmark: 'BTCUSDT',
      rs_period: 14,
      rs_threshold: 50,
      rs_condition: 'above'
    },

    // =============================================
    // ALERT SYSTEM
    // =============================================
    price_alert: {
      enabled: false,
      alert_type: 'crossing',
      price_level: 0,
      send_notification: true,
      sound_alert: true,
      webhook_url: ''
    },
    indicator_alert: {
      enabled: false,
      indicator: 'rsi',
      condition: 'crosses_above',
      threshold: 70,
      send_notification: true,
      sound_alert: true
    },
    trade_alert: {
      enabled: false,
      on_entry: true,
      on_exit: true,
      on_sl_hit: true,
      on_tp_hit: true,
      send_notification: true,
      webhook_url: ''
    },
    pnl_alert: {
      enabled: false,
      profit_threshold: 5.0,
      loss_threshold: -3.0,
      use_percent: true,
      send_notification: true
    },
    drawdown_alert: {
      enabled: false,
      drawdown_threshold: 10.0,
      send_notification: true,
      pause_trading: false
    },

    // =============================================
    // VISUALIZATION
    // =============================================
    show_entries: {
      enabled: true,
      long_color: '#22c55e',
      short_color: '#ef4444',
      marker_size: 'medium',
      show_label: true
    },
    show_exits: {
      enabled: true,
      profit_color: '#22c55e',
      loss_color: '#ef4444',
      marker_size: 'medium',
      show_pnl: true
    },
    show_sl_tp: {
      enabled: true,
      sl_color: '#ef4444',
      tp_color: '#22c55e',
      line_style: 'dashed',
      show_price: true
    },
    show_indicators: {
      enabled: true,
      main_pane: ['ema', 'sma', 'bollinger'],
      separate_pane: ['rsi', 'macd', 'volume'],
      custom_colors: {}
    },
    show_equity: {
      enabled: true,
      show_drawdown: true,
      show_benchmark: false,
      benchmark_symbol: 'BTCUSDT'
    },
    show_trades_table: {
      enabled: true,
      columns: ['entry_time', 'exit_time', 'side', 'entry_price', 'exit_price', 'pnl', 'pnl_percent'],
      max_rows: 100,
      highlight_winners: true
    },

    // =============================================
    // DCA GRID (from TradingView Multi DCA Strategy)
    // =============================================
    dca_grid_enable: {
      enabled: false,
      direction: 'long',
      deposit: 1000,
      leverage: 1
    },
    dca_grid_settings: {
      grid_size_percent: 15,
      order_count: 5,
      leverage: 1,
      use_isolated_margin: true
    },
    dca_martingale_config: {
      martingale_multiplier: 1.0,
      min_multiplier: 1.0,
      max_multiplier: 1.8,
      step: 0.1
    },
    dca_log_steps: {
      log_steps_multiplier: 1.0,
      min_multiplier: 0.8,
      max_multiplier: 1.4,
      step: 0.05
    },
    dca_dynamic_tp: {
      enabled: false,
      trigger_order_count: 3,
      new_tp_percent: 0.5
    },
    dca_safety_close: {
      enabled: false,
      max_drawdown_amount: 95,
      use_percent: false
    },

    // =============================================
    // MULTIPLE TAKE PROFITS
    // =============================================
    multi_tp_enable: {
      enabled: false,
      use_main_tp: true
    },
    tp1_config: {
      percent: 0.5,
      close_percent: 25,
      enabled: true
    },
    tp2_config: {
      percent: 1.0,
      close_percent: 25,
      enabled: true
    },
    tp3_config: {
      percent: 1.5,
      close_percent: 25,
      enabled: true
    },
    tp4_config: {
      percent: 2.0,
      close_percent: 25,
      enabled: true
    },

    // =============================================
    // ATR-BASED EXIT
    // =============================================
    atr_sl: {
      enabled: false,
      atr_period: 14,
      atr_multiplier: 2.0,
      smoothing_method: 'RMA',
      use_wicks: false
    },
    atr_tp: {
      enabled: false,
      atr_period: 14,
      atr_multiplier: 3.0,
      smoothing_method: 'RMA',
      use_wicks: false
    },
    atr_wicks_mode: {
      check_wicks: false,
      description: 'If disabled, ATR SL/TP checked only on bar close'
    },

    // =============================================
    // SIGNAL MEMORY
    // =============================================
    signal_memory_enable: {
      enabled: false,
      memory_bars: 5,
      execute_on_conditions_met: true
    },
    cross_memory: {
      enabled: false,
      memory_bars: 5,
      indicator: 'ma_cross'
    },
    pattern_memory: {
      enabled: false,
      memory_bars: 3,
      pattern_type: 'any'
    },

    // =============================================
    // CLOSE CONDITIONS (from TradingView)
    // =============================================
    close_by_time: {
      enabled: false,
      bars_since_entry: 10,
      profit_only: false,
      min_profit_percent: 0
    },
    close_rsi_reach: {
      enabled: false,
      rsi_period: 14,
      long_close_above: 70,
      short_close_below: 30,
      profit_only: false,
      min_profit_percent: 0
    },
    close_rsi_cross: {
      enabled: false,
      rsi_period: 14,
      long_cross_level: 70,
      short_cross_level: 30,
      profit_only: false
    },
    close_stoch_reach: {
      enabled: false,
      stoch_period: 14,
      long_close_above: 80,
      short_close_below: 20,
      profit_only: false,
      min_profit_percent: 0
    },
    close_stoch_cross: {
      enabled: false,
      stoch_period: 14,
      long_cross_level: 80,
      short_cross_level: 20,
      profit_only: false
    },
    close_channel_break: {
      enabled: false,
      channel_type: 'bollinger',
      channel_period: 20,
      channel_mult: 2.0,
      close_mode: 'rebound',
      profit_only: false
    },
    close_ma_cross: {
      enabled: false,
      ma1_period: 9,
      ma2_period: 21,
      profit_only: false,
      min_profit_percent: 0
    },
    close_psar: {
      enabled: false,
      psar_start: 0.02,
      psar_increment: 0.02,
      psar_max: 0.2,
      close_on_nth_bar: 1,
      profit_only: false
    },
    close_profit_only: {
      enabled: false,
      min_profit_percent: 0.5
    },

    // =============================================
    // PRICE ACTION PATTERNS
    // =============================================
    engulfing: {
      enabled: false,
      use_bullish: true,
      use_bearish: true,
      confirmation_bars: 0
    },
    hammer_hangman: {
      enabled: false,
      use_hammer: true,
      use_hanging_man: true,
      body_ratio: 0.3
    },
    doji_patterns: {
      enabled: false,
      use_doji: true,
      use_doji_star: true,
      use_dragonfly: true,
      use_gravestone: true,
      body_ratio: 0.1
    },
    shooting_star: {
      enabled: false,
      min_upper_shadow: 2.0,
      max_body_ratio: 0.3
    },
    marubozu: {
      enabled: false,
      use_white: true,
      use_black: true,
      min_body_ratio: 0.9
    },
    tweezer: {
      enabled: false,
      use_top: true,
      use_bottom: true,
      tolerance_percent: 0.1
    },
    three_methods: {
      enabled: false,
      use_rising: true,
      use_falling: true
    },
    piercing_darkcloud: {
      enabled: false,
      use_piercing: true,
      use_dark_cloud: true,
      min_penetration: 0.5
    },
    harami: {
      enabled: false,
      use_bullish: true,
      use_bearish: true
    },

    // =============================================
    // DIVERGENCE DETECTION
    // =============================================
    rsi_divergence: {
      enabled: false,
      rsi_period: 14,
      pivot_lookback: 5,
      use_regular: true,
      use_hidden: false
    },
    macd_divergence: {
      enabled: false,
      fast_period: 12,
      slow_period: 26,
      signal_period: 9,
      pivot_lookback: 5,
      use_regular: true,
      use_hidden: false
    },
    stoch_divergence: {
      enabled: false,
      k_period: 14,
      d_period: 3,
      pivot_lookback: 5,
      use_regular: true,
      use_hidden: false
    },
    obv_divergence: {
      enabled: false,
      pivot_lookback: 5,
      use_regular: true,
      use_hidden: false
    },
    mfi_divergence: {
      enabled: false,
      mfi_period: 14,
      pivot_lookback: 5,
      use_regular: true,
      use_hidden: false
    }
  };
  return params[blockType] || {};
}

/**
 * Render grouped params for complex blocks like RSI Filter
 * Returns HTML with grouped sections
 */
/**
 * Render params like TradingView - simple vertical layout
 * Supports both Default and Optimization modes
 */
function renderGroupedParams(block, optimizationMode = false) {
  const blockId = block.id;
  const params = block.params || {};
  const optParams = block.optimizationParams || {};

  // Define custom layouts for complex blocks
  const customLayouts = {
    // =============================================
    // MOMENTUM INDICATORS
    // =============================================
    rsi: {
      title: 'RSI Settings',
      fields: [
        { key: 'period', label: 'Length', type: 'number', optimizable: true },
        { key: 'source', label: 'Source', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3', 'ohlc4'] },
        { key: 'timeframe', label: 'TimeFrame', type: 'select', options: ['Chart', '1m', '5m', '15m', '30m', '1h', '4h', '1D'] },
        { key: 'overbought', label: 'Overbought Level', type: 'number', optimizable: true },
        { key: 'oversold', label: 'Oversold Level', type: 'number', optimizable: true }
      ]
    },
    stochastic: {
      title: 'Stochastic Settings',
      fields: [
        { key: 'k_period', label: '%K Length', type: 'number', optimizable: true },
        { key: 'd_period', label: '%D Smoothing', type: 'number', optimizable: true },
        { key: 'smooth_k', label: '%K Smoothing', type: 'number', optimizable: true },
        { key: 'timeframe', label: 'TimeFrame', type: 'select', options: ['Chart', '1m', '5m', '15m', '30m', '1h', '4h', '1D'] },
        { key: 'overbought', label: 'Overbought', type: 'number', optimizable: true },
        { key: 'oversold', label: 'Oversold', type: 'number', optimizable: true }
      ]
    },
    stoch_rsi: {
      title: 'Stochastic RSI Settings',
      fields: [
        { key: 'rsi_period', label: 'RSI Length', type: 'number', optimizable: true },
        { key: 'stoch_period', label: 'Stochastic Length', type: 'number', optimizable: true },
        { key: 'k_period', label: '%K Smoothing', type: 'number', optimizable: true },
        { key: 'd_period', label: '%D Smoothing', type: 'number', optimizable: true },
        { key: 'overbought', label: 'Overbought', type: 'number', optimizable: true },
        { key: 'oversold', label: 'Oversold', type: 'number', optimizable: true }
      ]
    },
    williams_r: {
      title: 'Williams %R Settings',
      fields: [
        { key: 'period', label: 'Length', type: 'number', optimizable: true },
        { key: 'overbought', label: 'Overbought', type: 'number', optimizable: true },
        { key: 'oversold', label: 'Oversold', type: 'number', optimizable: true }
      ]
    },
    roc: {
      title: 'ROC Settings',
      fields: [
        { key: 'period', label: 'Length', type: 'number', optimizable: true },
        { key: 'source', label: 'Source', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3'] }
      ]
    },
    mfi: {
      title: 'MFI Settings',
      fields: [
        { key: 'period', label: 'Length', type: 'number', optimizable: true },
        { key: 'overbought', label: 'Overbought', type: 'number', optimizable: true },
        { key: 'oversold', label: 'Oversold', type: 'number', optimizable: true }
      ]
    },
    cmo: {
      title: 'CMO Settings',
      fields: [
        { key: 'period', label: 'Length', type: 'number', optimizable: true },
        { key: 'overbought', label: 'Overbought', type: 'number', optimizable: true },
        { key: 'oversold', label: 'Oversold', type: 'number', optimizable: true }
      ]
    },
    cci: {
      title: 'CCI Settings',
      fields: [
        { key: 'period', label: 'Length', type: 'number', optimizable: true },
        { key: 'overbought', label: 'Overbought', type: 'number', optimizable: true },
        { key: 'oversold', label: 'Oversold', type: 'number', optimizable: true }
      ]
    },

    // =============================================
    // TREND INDICATORS
    // =============================================
    sma: {
      title: 'SMA Settings',
      fields: [
        { key: 'period', label: 'Length', type: 'number', optimizable: true },
        { key: 'source', label: 'Source', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3', 'ohlc4'] },
        { key: 'offset', label: 'Offset', type: 'number', optimizable: false }
      ]
    },
    ema: {
      title: 'EMA Settings',
      fields: [
        { key: 'period', label: 'Length', type: 'number', optimizable: true },
        { key: 'source', label: 'Source', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3', 'ohlc4'] },
        { key: 'offset', label: 'Offset', type: 'number', optimizable: false }
      ]
    },
    wma: {
      title: 'WMA Settings',
      fields: [
        { key: 'period', label: 'Length', type: 'number', optimizable: true },
        { key: 'source', label: 'Source', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3'] }
      ]
    },
    dema: {
      title: 'DEMA Settings',
      fields: [
        { key: 'period', label: 'Length', type: 'number', optimizable: true },
        { key: 'source', label: 'Source', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3'] }
      ]
    },
    tema: {
      title: 'TEMA Settings',
      fields: [
        { key: 'period', label: 'Length', type: 'number', optimizable: true },
        { key: 'source', label: 'Source', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3'] }
      ]
    },
    hull_ma: {
      title: 'Hull MA Settings',
      fields: [
        { key: 'period', label: 'Length', type: 'number', optimizable: true },
        { key: 'source', label: 'Source', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3'] }
      ]
    },
    macd: {
      title: 'MACD Settings',
      fields: [
        { key: 'fast_period', label: 'Fast Length', type: 'number', optimizable: true },
        { key: 'slow_period', label: 'Slow Length', type: 'number', optimizable: true },
        { key: 'signal_period', label: 'Signal Smoothing', type: 'number', optimizable: true },
        { key: 'source', label: 'Source', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3'] }
      ]
    },
    adx: {
      title: 'ADX Settings',
      fields: [
        { key: 'period', label: 'ADX Smoothing', type: 'number', optimizable: true },
        { key: 'threshold', label: 'Trend Threshold', type: 'number', optimizable: true }
      ]
    },
    supertrend: {
      title: 'Supertrend Settings',
      fields: [
        { key: 'period', label: 'ATR Period', type: 'number', optimizable: true },
        { key: 'multiplier', label: 'Factor', type: 'number', optimizable: true },
        { key: 'source', label: 'Source', type: 'select', options: ['hl2', 'hlc3', 'close'] }
      ]
    },
    ichimoku: {
      title: 'Ichimoku Cloud Settings',
      fields: [
        { key: 'tenkan_period', label: 'Tenkan-sen (Conversion)', type: 'number', optimizable: true },
        { key: 'kijun_period', label: 'Kijun-sen (Base)', type: 'number', optimizable: true },
        { key: 'senkou_b_period', label: 'Senkou Span B', type: 'number', optimizable: true },
        { key: 'displacement', label: 'Displacement', type: 'number', optimizable: false }
      ]
    },
    parabolic_sar: {
      title: 'Parabolic SAR Settings',
      fields: [
        { key: 'start', label: 'Start', type: 'number', optimizable: true },
        { key: 'increment', label: 'Increment', type: 'number', optimizable: true },
        { key: 'max_value', label: 'Max Value', type: 'number', optimizable: true }
      ]
    },
    aroon: {
      title: 'Aroon Settings',
      fields: [
        { key: 'period', label: 'Length', type: 'number', optimizable: true },
        { key: 'threshold', label: 'Threshold', type: 'number', optimizable: true }
      ]
    },
    qqe: {
      title: 'QQE Settings',
      fields: [
        { key: 'rsi_period', label: 'RSI Period', type: 'number', optimizable: true },
        { key: 'qqe_factor', label: 'QQE Factor', type: 'number', optimizable: true },
        { key: 'smoothing_period', label: 'Smoothing Period', type: 'number', optimizable: true },
        { key: 'source', label: 'Source', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3'] },
        { key: 'timeframe', label: 'TimeFrame', type: 'select', options: ['Chart', '1m', '5m', '15m', '30m', '1h', '4h', '1D'] }
      ]
    },

    // =============================================
    // VOLATILITY INDICATORS
    // =============================================
    atr: {
      title: 'ATR Settings',
      fields: [
        { key: 'period', label: 'Length', type: 'number', optimizable: true }
      ]
    },
    atrp: {
      title: 'ATR% Settings',
      fields: [
        { key: 'period', label: 'Length', type: 'number', optimizable: true }
      ]
    },
    bollinger: {
      title: 'Bollinger Bands Settings',
      fields: [
        { key: 'period', label: 'Length', type: 'number', optimizable: true },
        { key: 'std_dev', label: 'StdDev Multiplier', type: 'number', optimizable: true },
        { key: 'source', label: 'Source', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3'] }
      ]
    },
    keltner: {
      title: 'Keltner Channel Settings',
      fields: [
        { key: 'ema_period', label: 'EMA Length', type: 'number', optimizable: true },
        { key: 'atr_period', label: 'ATR Length', type: 'number', optimizable: true },
        { key: 'multiplier', label: 'Multiplier', type: 'number', optimizable: true }
      ]
    },
    donchian: {
      title: 'Donchian Channel Settings',
      fields: [
        { key: 'period', label: 'Length', type: 'number', optimizable: true }
      ]
    },
    stddev: {
      title: 'Standard Deviation Settings',
      fields: [
        { key: 'period', label: 'Length', type: 'number', optimizable: true },
        { key: 'source', label: 'Source', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3'] }
      ]
    },

    // =============================================
    // VOLUME INDICATORS
    // =============================================
    obv: {
      title: 'OBV Settings',
      fields: []
    },
    vwap: {
      title: 'VWAP Settings',
      fields: [
        { key: 'anchor', label: 'Anchor Period', type: 'select', options: ['session', 'week', 'month'] }
      ]
    },
    cmf: {
      title: 'Chaikin Money Flow Settings',
      fields: [
        { key: 'period', label: 'Length', type: 'number', optimizable: true }
      ]
    },
    ad_line: {
      title: 'A/D Line Settings',
      fields: []
    },
    pvt: {
      title: 'PVT Settings',
      fields: []
    },

    // =============================================
    // SUPPORT/RESISTANCE
    // =============================================
    pivot_points: {
      title: 'Pivot Points Settings',
      fields: [
        { key: 'type', label: 'Type', type: 'select', options: ['traditional', 'fibonacci', 'woodie', 'classic', 'demark', 'camarilla'] },
        { key: 'timeframe', label: 'Timeframe', type: 'select', options: ['1D', '1W', '1M'] }
      ]
    },

    // =============================================
    // MULTI-TIMEFRAME
    // =============================================
    mtf: {
      title: 'Multi-Timeframe Settings',
      fields: [
        { key: 'indicator', label: 'Indicator', type: 'select', options: ['ema', 'sma', 'wma', 'rsi', 'macd', 'stochastic', 'adx', 'atr', 'bollinger'] },
        { key: 'period', label: 'Period', type: 'number', optimizable: true },
        { key: 'source', label: 'Source', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3', 'ohlc4'] },
        { key: 'timeframe', label: 'Timeframe', type: 'select', options: ['1m', '5m', '15m', '30m', '1h', '4h', '1D', '1W'] },
        { key: 'show_on_chart', label: 'Show on Chart', type: 'checkbox' }
      ]
    },

    // =============================================
    // FILTERS
    // =============================================
    rsi_filter: {
      title: 'RSI - MTF [IN RANGE FILTER OR CROSS SIGNAL]',
      fields: [
        // TF1 (Main)
        { type: 'separator', label: '━━━ RSI TF1 (Main) ━━━' },
        { key: 'rsi_period', label: 'RSI Length', type: 'number', optimizable: true },
        { key: 'rsi_timeframe', label: 'RSI TimeFrame', type: 'select', options: ['Chart', '1m', '5m', '15m', '30m', '1h', '4h', '1D'] },
        { key: 'use_btcusdt_source', label: 'Use BTCUSDT as Source for RSI?', type: 'checkbox' },
        { key: 'use_long_range', label: 'Use RSI LONG Range', type: 'checkbox' },
        {
          type: 'inline',
          fields: [
            { key: 'long_rsi_more', label: '(LONG) RSI >', type: 'number', width: '70px', optimizable: true },
            { label: '& RSI <', type: 'label' },
            { key: 'long_rsi_less', type: 'number', width: '70px', optimizable: true }
          ]
        },
        { key: 'use_short_range', label: 'Use RSI SHORT Range', type: 'checkbox' },
        {
          type: 'inline',
          fields: [
            { key: 'short_rsi_less', label: '(SHORT) RSI <', type: 'number', width: '70px', optimizable: true },
            { label: '& RSI >', type: 'label' },
            { key: 'short_rsi_more', type: 'number', width: '70px', optimizable: true }
          ]
        },
        { key: 'use_cross_level', label: 'Use RSI Cross Level', type: 'checkbox', hasTooltip: true },
        { key: 'cross_level_long', label: 'Cross Level for LONG', type: 'number', optimizable: true },
        { key: 'cross_level_short', label: 'Cross Level for SHORT', type: 'number', optimizable: true },
        { key: 'opposite_signal', label: 'Opposite Signal', type: 'checkbox', hasTooltip: true },
        { key: 'use_signal_memory', label: 'Activate Signal Memory', type: 'checkbox', hasTooltip: true },
        { key: 'signal_memory_bars', label: 'Signal Memory Bars', type: 'number', hasTooltip: true, optimizable: true },
        // TF2
        { type: 'separator', label: '━━━ RSI TF2 ━━━' },
        { key: 'use_rsi_tf2', label: 'Use RSI TF2?', type: 'checkbox' },
        { key: 'rsi_tf2_period', label: 'RSI Length', type: 'number', optimizable: true },
        { key: 'rsi_tf2_timeframe', label: 'TimeFrame', type: 'select', options: ['Chart', '1m', '5m', '15m', '30m', '1h', '4h', '1D'] },
        {
          type: 'inline',
          fields: [
            { key: 'rsi_tf2_long_more', label: '(LONG) RSI >', type: 'number', width: '70px', optimizable: true },
            { label: '& <', type: 'label' },
            { key: 'rsi_tf2_long_less', type: 'number', width: '70px', optimizable: true }
          ]
        },
        {
          type: 'inline',
          fields: [
            { key: 'rsi_tf2_short_less', label: '(SHORT) RSI <', type: 'number', width: '70px', optimizable: true },
            { label: '& >', type: 'label' },
            { key: 'rsi_tf2_short_more', type: 'number', width: '70px', optimizable: true }
          ]
        },
        // TF3
        { type: 'separator', label: '━━━ RSI TF3 ━━━' },
        { key: 'use_rsi_tf3', label: 'Use RSI TF3?', type: 'checkbox' },
        { key: 'rsi_tf3_period', label: 'RSI Length', type: 'number', optimizable: true },
        { key: 'rsi_tf3_timeframe', label: 'TimeFrame', type: 'select', options: ['Chart', '1m', '5m', '15m', '30m', '1h', '4h', '1D'] },
        {
          type: 'inline',
          fields: [
            { key: 'rsi_tf3_long_more', label: '(LONG) RSI >', type: 'number', width: '70px', optimizable: true },
            { label: '& <', type: 'label' },
            { key: 'rsi_tf3_long_less', type: 'number', width: '70px', optimizable: true }
          ]
        },
        {
          type: 'inline',
          fields: [
            { key: 'rsi_tf3_short_less', label: '(SHORT) RSI <', type: 'number', width: '70px', optimizable: true },
            { label: '& >', type: 'label' },
            { key: 'rsi_tf3_short_more', type: 'number', width: '70px', optimizable: true }
          ]
        }
      ]
    },
    supertrend_filter: {
      title: 'SUPER TREND [FILTER] [SIGNAL] - MTF (3 Timeframes)',
      fields: [
        // TF1 (Main)
        { type: 'separator', label: '━━━ SuperTrend TF1 (Main) ━━━' },
        { key: 'use_supertrend', label: 'Use SuperTrend TF1?', type: 'checkbox' },
        { key: 'generate_on_trend_change', label: 'Generate Signals on Trend Change?', type: 'checkbox', hasTooltip: true },
        { key: 'use_btc_source', label: 'Use BTCUSDT as Source for TF1?', type: 'checkbox' },
        { key: 'opposite_signal', label: 'Opposite Signal? (Sell on UPtrend..)', type: 'checkbox' },
        { key: 'show_supertrend', label: 'Show SuperTrend TF1?', type: 'checkbox' },
        { key: 'atr_period', label: 'ATR Period', type: 'number', optimizable: true },
        { key: 'atr_multiplier', label: 'ATR Multiplier', type: 'number', step: 0.1, optimizable: true },
        { key: 'timeframe', label: 'TimeFrame:', type: 'select', options: ['Chart', '1m', '5m', '15m', '30m', '1h', '4h', '1D'] },
        // TF2
        { type: 'separator', label: '━━━ SuperTrend TF2 ━━━' },
        { key: 'use_supertrend_tf2', label: 'Use SuperTrend TF2?', type: 'checkbox' },
        { key: 'supertrend_tf2_btc_source', label: 'Use BTCUSDT as Source?', type: 'checkbox' },
        { key: 'supertrend_tf2_opposite', label: 'Opposite Signal?', type: 'checkbox' },
        { key: 'supertrend_tf2_show', label: 'Show SuperTrend TF2?', type: 'checkbox' },
        { key: 'supertrend_tf2_period', label: 'ATR Period', type: 'number', optimizable: true },
        { key: 'supertrend_tf2_multiplier', label: 'ATR Multiplier', type: 'number', step: 0.1, optimizable: true },
        { key: 'supertrend_tf2_timeframe', label: 'TimeFrame:', type: 'select', options: ['Chart', '1m', '5m', '15m', '30m', '1h', '4h', '1D'] },
        // TF3
        { type: 'separator', label: '━━━ SuperTrend TF3 ━━━' },
        { key: 'use_supertrend_tf3', label: 'Use SuperTrend TF3?', type: 'checkbox' },
        { key: 'supertrend_tf3_opposite', label: 'Opposite Signal?', type: 'checkbox' },
        { key: 'supertrend_tf3_show', label: 'Show SuperTrend TF3?', type: 'checkbox' },
        { key: 'supertrend_tf3_period', label: 'ATR Period', type: 'number', optimizable: true },
        { key: 'supertrend_tf3_multiplier', label: 'ATR Multiplier', type: 'number', step: 0.1, optimizable: true },
        { key: 'supertrend_tf3_timeframe', label: 'TimeFrame:', type: 'select', options: ['Chart', '1m', '5m', '15m', '30m', '1h', '4h', '1D'] }
      ]
    },
    // =============================================
    // TWO MA's MOV [SIGNAL AND FILTER]
    // =============================================
    two_ma_filter: {
      title: 'TWO MAs MOV [SIGNAL AND FILTER]',
      fields: [
        { key: 'ma1_length', label: 'Moving Average 1 length (50)', type: 'number', optimizable: true },
        { key: 'ma1_type', label: 'MA 1 Smoothing Type', type: 'select', options: ['SMA', 'EMA', 'WMA', 'VWMA', 'HMA', 'DEMA', 'TEMA'] },
        { key: 'ma1_source', label: 'MA1 Source', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3', 'ohlc4'] },
        { key: 'ma2_length', label: 'Moving Average 2 length (100)', type: 'number', optimizable: true },
        { key: 'ma2_type', label: 'MA 2 Smoothing Type', type: 'select', options: ['SMA', 'EMA', 'WMA', 'VWMA', 'HMA', 'DEMA', 'TEMA'] },
        { key: 'ma2_source', label: 'MA2 Source', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3', 'ohlc4'] },
        { key: 'show_two_mas', label: 'Show TWO MAs (MA1 - green, MA2 - red)', type: 'checkbox' },
        { type: 'separator', label: '------- Use MA1 / MA2 Cross -------' },
        { key: 'use_ma_cross', label: 'Use MA1 / MA2 Cross', type: 'checkbox' },
        { key: 'opposite_ma_cross', label: "Opposite Signal - 'MA1 / MA2 Cross'", type: 'checkbox' },
        { key: 'activate_ma_cross_memory', label: "Activate 'MA1 / MA2 Cross' Signal Memory", type: 'checkbox' },
        { key: 'ma_cross_memory_bars', label: "Keep 'MA1 / MA2 Cross' Signal Memory for XX bars", type: 'number', hasTooltip: true },
        { type: 'separator', label: '------ Use MA1 as Filter. Long if Price > MA 1 ------' },
        { key: 'use_ma1_filter', label: 'Use MA1 as Filter', type: 'checkbox' },
        { key: 'opposite_ma1_filter', label: "Opposite Signal - 'MA1 as Filter'", type: 'checkbox' },
        { key: 'two_ma_timeframe', label: 'TWO MAs TimeFrame:', type: 'select', options: ['Chart', '1m', '5m', '15m', '30m', '1h', '4h', '1D'] }
      ]
    },
    // =============================================
    // STOCHASTIC [RANGE FILTER]
    // =============================================
    stochastic_filter: {
      title: 'STOCHASTIC [RANGE FILTER]',
      fields: [
        { key: 'stoch_k_length', label: 'Stochastic %K Length (14)', type: 'number', optimizable: true },
        { key: 'stoch_k_smoothing', label: 'Stochastic %K Smoothing (3)', type: 'number', optimizable: true },
        { key: 'stoch_d_smoothing', label: 'Stochastic %D Smoothing (3)', type: 'number', optimizable: true },
        { key: 'stoch_timeframe', label: 'Stochastic TimeFrame:', type: 'select', options: ['Chart', '1m', '5m', '15m', '30m', '1h', '4h', '1D'] },
        { key: 'use_btcusdt_source', label: 'Use BTCUSDT as Source for Stochastic?', type: 'checkbox' },
        { type: 'separator', label: '------- Use Stochastic Range Filter -------' },
        { key: 'use_stoch_range_filter', label: 'Use Stochastic Range Filter', type: 'checkbox' },
        {
          type: 'inline',
          fields: [
            { key: 'long_stoch_d_more', label: '(LONG) Stoch %D is More', type: 'number', width: '60px', optimizable: true },
            { label: '& Stoch %D Less', type: 'label' },
            { key: 'long_stoch_d_less', type: 'number', width: '60px', optimizable: true }
          ]
        },
        {
          type: 'inline',
          fields: [
            { key: 'short_stoch_d_less', label: '(SHORT) Stoch %D is Less', type: 'number', width: '60px', optimizable: true },
            { label: '& Stoch %D More', type: 'label' },
            { key: 'short_stoch_d_more', type: 'number', width: '60px', optimizable: true }
          ]
        },
        { type: 'separator', label: '------- Use Stochastic Cross Level -------' },
        { key: 'use_stoch_cross_level', label: 'Use Stochastic Cross Level', type: 'checkbox' },
        { key: 'stoch_cross_level_long', label: 'Level to Cross Stochastic for LONG', type: 'number', optimizable: true },
        { key: 'stoch_cross_level_short', label: 'Level to Cross Stochastic for SHORT', type: 'number', optimizable: true },
        { key: 'activate_stoch_cross_memory', label: 'Activate Stochastic Cross Signal Memory', type: 'checkbox' },
        { key: 'stoch_cross_memory_bars', label: 'Keep Stochastic Cross Signal Memory for XX bars', type: 'number', hasTooltip: true },
        { type: 'separator', label: '------- Use Stochastic Cross K/D -------' },
        { key: 'use_stoch_kd_cross', label: 'Use Stochastic Cross K/D', type: 'checkbox' },
        { key: 'opposite_stoch_kd', label: 'Opposite Signal - Stochastic Cross K/D', type: 'checkbox' },
        { key: 'activate_stoch_kd_memory', label: 'Activate Stochastic Cross K/D Signal Memory', type: 'checkbox' },
        { key: 'stoch_kd_memory_bars', label: 'Keep Stochastic Cross K/D Signal Memory for XX bars', type: 'number', hasTooltip: true }
      ]
    },
    // =============================================
    // MACD [SIGNALS, CROSS X LINE OR CROSS SIGNAL LINE]
    // =============================================
    macd_filter: {
      title: 'MACD [SIGNALS, CROSS X LINE OR CROSS SIGNAL LINE]',
      fields: [
        { key: 'macd_fast_length', label: 'MACD Fast Length (12)', type: 'number', optimizable: true },
        { key: 'macd_slow_length', label: 'MACD Slow Length (26)', type: 'number', optimizable: true },
        { key: 'macd_signal_smoothing', label: 'MACD Signal Smoothing (9)', type: 'number', optimizable: true },
        { key: 'macd_source', label: 'MACD Source', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3', 'ohlc4'] },
        { key: 'macd_timeframe', label: 'MACD TimeFrame:', type: 'select', options: ['Chart', '1m', '5m', '15m', '30m', '1h', '4h', '1D'] },
        { key: 'use_btcusdt_source', label: 'Use BTCUSDT as Source for MACD?', type: 'checkbox' },
        { key: 'enable_macd_visualization', label: 'Enable Visualization MACD', type: 'checkbox' },
        { type: 'separator', label: '------- Use MACD Cross with Level (0) -------' },
        { key: 'use_macd_cross_zero', label: 'Use MACD Cross with Level (0)', type: 'checkbox' },
        { key: 'opposite_macd_cross_zero', label: 'Opposite Signal - MACD Cross with Level (0)', type: 'checkbox', hasTooltip: true },
        { key: 'macd_cross_zero_level', label: 'Cross Line Level (0)', type: 'number', optimizable: true },
        { type: 'separator', label: '------- Use MACD Cross with Signal Line -------' },
        { key: 'use_macd_cross_signal', label: 'Use MACD Cross with Signal Line', type: 'checkbox' },
        { key: 'signal_only_if_macd_positive', label: 'Signal only if MACD > 0 (Long) or < 0 (Short)', type: 'checkbox', hasTooltip: true },
        { key: 'opposite_macd_cross_signal', label: 'Opposite Signal - MACD Cross with Signal Line', type: 'checkbox' },
        { type: 'separator', label: '------- Signal Memory -------' },
        { key: 'disable_macd_signal_memory', label: '--Disable Signal Memory (for both MACD Crosses)--', type: 'checkbox' },
        { key: 'macd_signal_memory_bars', label: 'Keep MACD Signal Memory for XX bars', type: 'number', hasTooltip: true }
      ]
    },
    // =============================================
    // QQE [SIGNALS]
    // =============================================
    qqe_filter: {
      title: 'QQE [SIGNALS]',
      fields: [
        { key: 'use_qqe', label: 'Use QQE?', type: 'checkbox' },
        { key: 'opposite_qqe', label: 'Opposite QQE?', type: 'checkbox' },
        { key: 'enable_qqe_visualization', label: 'Enable QQE Visualization', type: 'checkbox' },
        { key: 'disable_qqe_signal_memory', label: 'Disable QQE Signal Memory', type: 'checkbox' },
        { key: 'qqe_rsi_length', label: 'QQE RSI Length(14)', type: 'number', optimizable: true },
        { key: 'qqe_rsi_smoothing', label: 'QQE RSI Smoothing(5)', type: 'number', optimizable: true },
        { key: 'qqe_delta_multiplier', label: 'Delta Multiplier(5.1)', type: 'number', step: 0.1, optimizable: true }
      ]
    },
    // =============================================
    // CCI [TIMEFRAME]
    // =============================================
    cci_filter: {
      title: 'CCI [TIMEFRAME]',
      fields: [
        { key: 'cci_length', label: 'CCI TF Long(14)', type: 'number', optimizable: true },
        { key: 'cci_timeframe', label: 'CCI TimeFrame:', type: 'select', options: ['Chart', '1m', '5m', '15m', '30m', '1h', '4h', '1D'] },
        { key: 'use_btcusdt_source', label: 'Use BTCUSDT as Source for CCI?', type: 'checkbox' },
        { type: 'separator', label: '------- Use CCI LONG Range -------' },
        { key: 'use_cci_long_range', label: 'Use CCI LONG Range', type: 'checkbox' },
        {
          type: 'inline',
          fields: [
            { key: 'long_cci_more', label: '(LONG) CCI is More', type: 'number', width: '70px', optimizable: true },
            { label: '& CCI Less', type: 'label' },
            { key: 'long_cci_less', type: 'number', width: '70px', optimizable: true }
          ]
        },
        { type: 'separator', label: '------- Use CCI SHORT Range -------' },
        { key: 'use_cci_short_range', label: 'Use CCI SHORT Range', type: 'checkbox' },
        {
          type: 'inline',
          fields: [
            { key: 'short_cci_less', label: '(SHORT) CCI is Less', type: 'number', width: '70px', optimizable: true },
            { label: '& CCI More', type: 'label' },
            { key: 'short_cci_more', type: 'number', width: '70px', optimizable: true }
          ]
        }
      ]
    },
    // =============================================
    // MOMENTUM
    // =============================================
    momentum_filter: {
      title: 'MOMENTUM',
      fields: [
        { key: 'momentum_length', label: 'Momentum TF Long(14)', type: 'number', optimizable: true },
        { key: 'momentum_timeframe', label: 'Momentum TimeFrame:', type: 'select', options: ['Chart', '1m', '5m', '15m', '30m', '1h', '4h', '1D'] },
        { key: 'momentum_source', label: 'Momentum Source', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3', 'ohlc4'] },
        { key: 'use_btcusdt_source', label: 'Use BTCUSDT as Source for Momentum?', type: 'checkbox' },
        { type: 'separator', label: '------- Use Momentum LONG Range -------' },
        { key: 'use_momentum_long_range', label: 'Use Momentum LONG Range', type: 'checkbox' },
        {
          type: 'inline',
          fields: [
            { key: 'long_momentum_more', label: '(LONG) Momentum is More', type: 'number', width: '70px', optimizable: true },
            { label: '& Momentum Less', type: 'label' },
            { key: 'long_momentum_less', type: 'number', width: '70px', optimizable: true }
          ]
        },
        { type: 'separator', label: '------- Use Momentum SHORT Range -------' },
        { key: 'use_momentum_short_range', label: 'Use Momentum SHORT Range', type: 'checkbox' },
        {
          type: 'inline',
          fields: [
            { key: 'short_momentum_less', label: '(SHORT) Momentum is Less', type: 'number', width: '70px', optimizable: true },
            { label: '& Momentum More', type: 'label' },
            { key: 'short_momentum_more', type: 'number', width: '70px', optimizable: true }
          ]
        }
      ]
    },
    // =============================================
    // DMI (ADX)
    // =============================================
    dmi_filter: {
      title: 'DMI (ADX)',
      fields: [
        { key: 'dmi_period', label: 'D Period Length (14)', type: 'number', optimizable: true },
        { key: 'adx_smoothing', label: 'ADX Smoothing Period (14)', type: 'number', optimizable: true },
        { key: 'dmi_timeframe', label: 'DMI TimeFrame:', type: 'select', options: ['Chart', '1m', '5m', '15m', '30m', '1h', '4h', '1D'] },
        { key: 'use_btcusdt_source', label: 'Use BTCUSDT as Source for DMI?', type: 'checkbox' },
        { type: 'separator', label: '------- Far Long using DMI Line -------' },
        { key: 'use_dmi_long', label: 'Far Long using DMI Line', type: 'checkbox' },
        { key: 'dmi_long_di_plus', label: 'DI+ > DI- for LONG', type: 'checkbox' },
        { key: 'dmi_long_threshold', label: 'DI+ Threshold for LONG', type: 'number', optimizable: true },
        { type: 'separator', label: '------- Far Shorts using DMI Line -------' },
        { key: 'use_dmi_short', label: 'Far Shorts using DMI Line', type: 'checkbox' },
        { key: 'dmi_short_di_minus', label: 'DI- > DI+ for SHORT', type: 'checkbox' },
        { key: 'dmi_short_threshold', label: 'DI- Threshold for SHORT', type: 'number', optimizable: true },
        { type: 'separator', label: '------- ADX Filter -------' },
        { key: 'use_adx_filter', label: 'Use ADX Filter (ADX > threshold)', type: 'checkbox' },
        { key: 'adx_threshold', label: 'ADX Threshold', type: 'number', optimizable: true }
      ]
    },
    // =============================================
    // CMF Filter (Chaikin Money Flow)
    // =============================================
    cmf_filter: {
      title: 'CHAIKIN MONEY FLOW (CMF)',
      fields: [
        { key: 'use_cmf', label: 'Use CMF Filter', type: 'checkbox' },
        { key: 'opposite_cmf', label: 'Opposite CMF Signal', type: 'checkbox' },
        { key: 'cmf_length', label: 'CMF Length (20)', type: 'number', optimizable: true },
        { key: 'cmf_timeframe', label: 'CMF TimeFrame:', type: 'select', options: ['Chart', '1m', '5m', '15m', '30m', '1h', '4h', '1D'] },
        { key: 'use_btcusdt_source', label: 'Use BTCUSDT as Source for CMF?', type: 'checkbox' },
        { type: 'separator', label: '------- CMF LONG Range -------' },
        {
          type: 'inline',
          fields: [
            { key: 'cmf_long_min', label: '(LONG) CMF >', type: 'number', width: '70px', optimizable: true },
            { label: '& CMF <', type: 'label' },
            { key: 'cmf_long_max', type: 'number', width: '70px', optimizable: true }
          ]
        },
        { type: 'separator', label: '------- CMF SHORT Range -------' },
        {
          type: 'inline',
          fields: [
            { key: 'cmf_short_min', label: '(SHORT) CMF >', type: 'number', width: '70px', optimizable: true },
            { label: '& CMF <', type: 'label' },
            { key: 'cmf_short_max', type: 'number', width: '70px', optimizable: true }
          ]
        }
      ]
    },
    // =============================================
    // Balance of Power Filter
    // =============================================
    bop_filter: {
      title: 'BALANCE OF POWER (Extended)',
      fields: [
        { key: 'use_bop', label: 'Use Balance of Power Filter', type: 'checkbox' },
        { key: 'opposite_bop', label: 'Opposite BoP Signal', type: 'checkbox' },
        { key: 'bop_smoothing', label: 'BoP Smoothing (14)', type: 'number', optimizable: true },
        { key: 'bop_triple_smooth_length', label: 'Triple Smooth Length (4)', type: 'number', optimizable: true },
        { key: 'bop_timeframe', label: 'BoP TimeFrame:', type: 'select', options: ['Chart', '1m', '5m', '15m', '30m', '1h', '4h', '1D'] },
        { key: 'use_btcusdt_source', label: 'Use BTCUSDT as Source for BoP?', type: 'checkbox' },
        { type: 'separator', label: '------- Cross Line Mode -------' },
        { key: 'bop_cross_line_enable', label: 'Use Cross Line Signal', type: 'checkbox' },
        { key: 'bop_disable_memory', label: 'Disable Signal Memory', type: 'checkbox' },
        { key: 'bop_cross_level', label: 'Cross Level (0)', type: 'number', optimizable: true },
        { type: 'separator', label: '------- BoP LONG Range -------' },
        {
          type: 'inline',
          fields: [
            { key: 'bop_long_min', label: '(LONG) BoP >', type: 'number', width: '70px', optimizable: true },
            { label: '& BoP <', type: 'label' },
            { key: 'bop_long_max', type: 'number', width: '70px', optimizable: true }
          ]
        },
        { type: 'separator', label: '------- BoP SHORT Range -------' },
        {
          type: 'inline',
          fields: [
            { key: 'bop_short_min', label: '(SHORT) BoP >', type: 'number', width: '70px', optimizable: true },
            { label: '& BoP <', type: 'label' },
            { key: 'bop_short_max', type: 'number', width: '70px', optimizable: true }
          ]
        }
      ]
    },
    // =============================================
    // Levels Break Filter (Pivot S&R)
    // =============================================
    levels_filter: {
      title: 'LEVELS BREAK (PIVOT S&R) - Extended',
      fields: [
        { key: 'use_levels', label: 'Use Levels Break Filter', type: 'checkbox' },
        { key: 'levels_pivot_bars', label: 'Bars to Find Pivot', type: 'number', optimizable: true },
        { key: 'levels_search_period', label: 'Search Period', type: 'number', optimizable: true },
        { key: 'levels_channel_width', label: 'Channel Width %', type: 'number', optimizable: true },
        { key: 'levels_test_count', label: 'Test Count', type: 'number', optimizable: true },
        { key: 'levels_opposite', label: 'Opposite Signal', type: 'checkbox' },
        { key: 'levels_memory_enable', label: 'Enable Signal Memory', type: 'checkbox' },
        { key: 'levels_memory_bars', label: 'Signal Memory Bars', type: 'number', optimizable: true },
        { key: 'pivot_type', label: 'Pivot Type', type: 'select', options: ['Traditional', 'Fibonacci', 'Woodie', 'Classic', 'DeMark', 'Camarilla'] },
        { key: 'levels_timeframe', label: 'Levels TimeFrame:', type: 'select', options: ['D', 'W', 'M'] },
        { type: 'separator', label: '------- LONG Conditions -------' },
        { key: 'long_above_s1', label: 'Price > S1 for LONG', type: 'checkbox' },
        { key: 'long_above_pivot', label: 'Price > Pivot for LONG', type: 'checkbox' },
        { key: 'long_break_r1', label: 'Break Above R1 for LONG', type: 'checkbox' },
        { type: 'separator', label: '------- SHORT Conditions -------' },
        { key: 'short_below_r1', label: 'Price < R1 for SHORT', type: 'checkbox' },
        { key: 'short_below_pivot', label: 'Price < Pivot for SHORT', type: 'checkbox' },
        { key: 'short_break_s1', label: 'Break Below S1 for SHORT', type: 'checkbox' }
      ]
    },
    // =============================================
    // ATR Volatility Filter
    // =============================================
    atr_filter: {
      title: 'ATR VOLATILITY FILTER',
      fields: [
        { key: 'use_atr_filter', label: 'Use ATR Volatility Filter', type: 'checkbox' },
        { key: 'atr_length', label: 'ATR Length (14)', type: 'number', optimizable: true },
        { key: 'atr_multiplier', label: 'ATR Multiplier', type: 'number', optimizable: true },
        { key: 'atr_timeframe', label: 'ATR TimeFrame:', type: 'select', options: ['Chart', '1m', '5m', '15m', '30m', '1h', '4h', '1D'] },
        { key: 'use_btcusdt_source', label: 'Use BTCUSDT as Source for ATR?', type: 'checkbox' },
        { type: 'separator', label: '------- ATR % Range -------' },
        {
          type: 'inline',
          fields: [
            { key: 'atr_min_percent', label: 'ATR % Min', type: 'number', width: '70px', optimizable: true },
            { label: 'ATR % Max', type: 'label' },
            { key: 'atr_max_percent', type: 'number', width: '70px', optimizable: true }
          ]
        },
        { key: 'atr_filter_mode', label: 'Filter Mode', type: 'select', options: ['between', 'above', 'below'] }
      ]
    },
    // =============================================
    // Volume Compare Filter
    // =============================================
    volume_compare_filter: {
      title: 'VOLUME COMPARE',
      fields: [
        { key: 'use_vol_compare', label: 'Use Volume Compare Filter', type: 'checkbox' },
        { key: 'vol_ma_length', label: 'Volume MA Length (20)', type: 'number', optimizable: true },
        { key: 'vol_ma_type', label: 'Volume MA Type', type: 'select', options: ['SMA', 'EMA', 'WMA', 'VWMA'] },
        { key: 'vol_timeframe', label: 'Volume TimeFrame:', type: 'select', options: ['Chart', '1m', '5m', '15m', '30m', '1h', '4h', '1D'] },
        { key: 'use_btcusdt_source', label: 'Use BTCUSDT as Source for Volume?', type: 'checkbox' },
        { type: 'separator', label: '------- Volume Threshold -------' },
        { key: 'vol_multiplier', label: 'Volume Multiplier (1.5)', type: 'number', optimizable: true },
        { key: 'vol_compare_mode', label: 'Compare Mode', type: 'select', options: ['above', 'below', 'between'] },
        { key: 'vol_consecutive_bars', label: 'Consecutive Bars Required', type: 'number', optimizable: true }
      ]
    },
    // =============================================
    // Highest/Lowest Bar Filter
    // =============================================
    highest_lowest_filter: {
      title: 'HIGHEST/LOWEST BAR',
      fields: [
        { key: 'use_highest_lowest', label: 'Use Highest/Lowest Filter', type: 'checkbox' },
        { key: 'lookback_period', label: 'Lookback Period (20)', type: 'number', optimizable: true },
        { key: 'hl_timeframe', label: 'TimeFrame:', type: 'select', options: ['Chart', '1m', '5m', '15m', '30m', '1h', '4h', '1D'] },
        { key: 'use_btcusdt_source', label: 'Use BTCUSDT as Source?', type: 'checkbox' },
        { type: 'separator', label: '------- LONG Conditions -------' },
        { key: 'long_break_highest', label: 'Break Above Highest (N-bar high)', type: 'checkbox' },
        { key: 'long_above_lowest', label: 'Price > Lowest (N-bar low)', type: 'checkbox' },
        { type: 'separator', label: '------- SHORT Conditions -------' },
        { key: 'short_break_lowest', label: 'Break Below Lowest (N-bar low)', type: 'checkbox' },
        { key: 'short_below_highest', label: 'Price < Highest (N-bar high)', type: 'checkbox' }
      ]
    },
    // =============================================
    // Accumulation Areas Filter
    // =============================================
    accumulation_filter: {
      title: 'ACCUMULATION AREAS - Extended',
      fields: [
        { key: 'use_accumulation', label: 'Use Accumulation Filter', type: 'checkbox' },
        { key: 'acc_backtrack_interval', label: 'Backtrack Interval', type: 'number', optimizable: true },
        { key: 'acc_min_bars', label: 'Min Bars to Execute', type: 'number', optimizable: true },
        { key: 'acc_breakout_signal', label: 'Breakout Signal', type: 'checkbox' },
        { key: 'acc_opposite_direction', label: 'Opposite Direction', type: 'checkbox' },
        { key: 'volume_threshold', label: 'Volume Threshold (x avg)', type: 'number', optimizable: true },
        { key: 'price_range_percent', label: 'Price Range %', type: 'number', optimizable: true },
        { key: 'min_bars_in_range', label: 'Min Bars in Range', type: 'number', optimizable: true },
        { key: 'acc_timeframe', label: 'TimeFrame:', type: 'select', options: ['Chart', '1m', '5m', '15m', '30m', '1h', '4h', '1D'] },
        { type: 'separator', label: '------- Entry Conditions -------' },
        { key: 'enter_on_breakout', label: 'Enter on Breakout', type: 'checkbox' },
        { key: 'enter_in_range', label: 'Enter Inside Range', type: 'checkbox' }
      ]
    },
    // =============================================
    // Linear Regression Channel Filter (Extended DCA)
    // =============================================
    linreg_filter: {
      title: 'LINEAR REGRESSION CHANNEL',
      fields: [
        { key: 'use_linreg', label: 'Use LinReg Filter', type: 'checkbox' },
        { key: 'disable_linreg_memory', label: 'Disable Signal Memory', type: 'checkbox' },
        { key: 'linreg_memory_bars', label: 'Signal Memory Bars', type: 'number', optimizable: true },
        { key: 'linreg_length', label: 'LinReg Length (100)', type: 'number', optimizable: true },
        { key: 'linreg_offset', label: 'Offset', type: 'number', optimizable: true },
        { key: 'channel_mult', label: 'Channel Deviation (2.0)', type: 'number', optimizable: true },
        { key: 'linreg_timeframe', label: 'TimeFrame:', type: 'select', options: ['Chart', '1m', '5m', '15m', '30m', '1h', '4h', '1D'] },
        { key: 'linreg_source', label: 'Source', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3', 'ohlc4', 'hlcc4'] },
        { key: 'linreg_breakout_rebound', label: 'Band Action', type: 'select', options: ['Breakout', 'Rebound'] },
        { key: 'linreg_slope_direction', label: 'Slope Direction', type: 'select', options: ['Allow_Any', 'Follow', 'Opposite'] },
        { key: 'show_linreg_extend_lines', label: 'Show Extended Lines', type: 'checkbox' },
        { key: 'show_broken_channel', label: 'Show Broken Channel', type: 'checkbox' },
        { type: 'separator', label: '------- LONG Conditions -------' },
        { key: 'long_above_lower', label: 'Price > Lower Channel', type: 'checkbox' },
        { key: 'long_slope_up', label: 'LinReg Slope Up', type: 'checkbox' },
        { type: 'separator', label: '------- SHORT Conditions -------' },
        { key: 'short_below_upper', label: 'Price < Upper Channel', type: 'checkbox' },
        { key: 'short_slope_down', label: 'LinReg Slope Down', type: 'checkbox' }
      ]
    },
    // =============================================
    // RVI Filter (Relative Volatility Index)
    // =============================================
    rvi_filter: {
      title: 'RVI - RELATIVE VOLATILITY INDEX',
      fields: [
        { key: 'use_rvi', label: 'Use RVI Filter', type: 'checkbox' },
        { key: 'rvi_length', label: 'RVI Length (10)', type: 'number', optimizable: true },
        { key: 'rvi_timeframe', label: 'TimeFrame:', type: 'select', options: ['Chart', '1m', '5m', '15m', '30m', '1h', '4h', '1D'] },
        { key: 'rvi_ma_type', label: 'MA Smoothing Type', type: 'select', options: ['WMA', 'RMA', 'SMA', 'EMA'] },
        { key: 'rvi_ma_length', label: 'MA Length (14)', type: 'number', optimizable: true },
        { type: 'separator', label: '------- LONG Range -------' },
        { key: 'use_rvi_long_range', label: 'Use RVI LONG Range', type: 'checkbox' },
        {
          type: 'inline',
          fields: [
            { key: 'rvi_long_more', label: '(LONG) RVI >', type: 'number', width: '70px', optimizable: true },
            { label: '& RVI <', type: 'label' },
            { key: 'rvi_long_less', type: 'number', width: '70px', optimizable: true }
          ]
        },
        { type: 'separator', label: '------- SHORT Range -------' },
        { key: 'use_rvi_short_range', label: 'Use RVI SHORT Range', type: 'checkbox' },
        {
          type: 'inline',
          fields: [
            { key: 'rvi_short_more', label: '(SHORT) RVI >', type: 'number', width: '70px', optimizable: true },
            { label: '& RVI <', type: 'label' },
            { key: 'rvi_short_less', type: 'number', width: '70px', optimizable: true }
          ]
        }
      ]
    },
    // =============================================
    // Divergence Filter
    // =============================================
    divergence_filter: {
      title: 'DIVERGENCE FILTER',
      fields: [
        { key: 'use_divergence', label: 'Use Divergence Filter', type: 'checkbox' },
        { key: 'div_indicator', label: 'Indicator', type: 'select', options: ['RSI', 'MACD', 'Stochastic', 'CCI', 'OBV', 'MFI'] },
        { key: 'div_period', label: 'Indicator Period', type: 'number', optimizable: true },
        { key: 'div_timeframe', label: 'TimeFrame:', type: 'select', options: ['Chart', '1m', '5m', '15m', '30m', '1h', '4h', '1D'] },
        { key: 'pivot_lookback', label: 'Pivot Lookback', type: 'number', optimizable: true },
        { type: 'separator', label: '------- Divergence Types -------' },
        { key: 'use_regular_bullish', label: 'Regular Bullish (for LONG)', type: 'checkbox' },
        { key: 'use_regular_bearish', label: 'Regular Bearish (for SHORT)', type: 'checkbox' },
        { key: 'use_hidden_bullish', label: 'Hidden Bullish (trend continuation)', type: 'checkbox' },
        { key: 'use_hidden_bearish', label: 'Hidden Bearish (trend continuation)', type: 'checkbox' }
      ]
    },
    // =============================================
    // Price Action Filter
    // =============================================
    price_action_filter: {
      title: 'PRICE ACTION (47 CANDLESTICK PATTERNS)',
      fields: [
        { key: 'use_price_action', label: 'Use Price Action Filter', type: 'checkbox' },
        { key: 'pa_timeframe', label: 'TimeFrame:', type: 'select', options: ['Chart', '1m', '5m', '15m', '30m', '1h', '4h', '1D'] },
        // ===== BULLISH REVERSAL (LONG) =====
        { type: 'separator', label: '━━━ Bullish Reversal (LONG) ━━━' },
        { key: 'use_hammer', label: 'Hammer', type: 'checkbox' },
        { key: 'use_inverted_hammer', label: 'Inverted Hammer', type: 'checkbox' },
        { key: 'use_engulfing_bull', label: 'Bullish Engulfing', type: 'checkbox' },
        { key: 'use_morning_star', label: 'Morning Star', type: 'checkbox' },
        { key: 'use_piercing_line', label: 'Piercing Line', type: 'checkbox' },
        { key: 'use_three_white', label: 'Three White Soldiers', type: 'checkbox' },
        { key: 'use_tweezer_bottom', label: 'Tweezer Bottom', type: 'checkbox' },
        { key: 'use_dragonfly_doji', label: 'Dragonfly Doji', type: 'checkbox' },
        { key: 'use_bullish_harami', label: 'Bullish Harami', type: 'checkbox' },
        { key: 'use_rising_three', label: 'Rising Three Methods', type: 'checkbox' },
        { key: 'use_bullish_marubozu', label: 'Bullish Marubozu', type: 'checkbox' },
        // Exotic Bullish
        { type: 'separator', label: '── Exotic Bullish ──' },
        { key: 'use_pin_bar_bullish', label: 'Pin Bar Bullish', type: 'checkbox' },
        { key: 'use_three_line_strike_bull', label: 'Three Line Strike (Bull)', type: 'checkbox' },
        { key: 'use_kicker_bullish', label: 'Kicker Bullish', type: 'checkbox' },
        { key: 'use_abandoned_baby_bull', label: 'Abandoned Baby (Bull)', type: 'checkbox' },
        { key: 'use_belt_hold_bullish', label: 'Belt Hold Bullish', type: 'checkbox' },
        { key: 'use_counterattack_bull', label: 'Counterattack Bullish', type: 'checkbox' },
        { key: 'use_ladder_bottom', label: 'Ladder Bottom', type: 'checkbox' },
        { key: 'use_stick_sandwich_bull', label: 'Stick Sandwich (Bull)', type: 'checkbox' },
        { key: 'use_homing_pigeon', label: 'Homing Pigeon', type: 'checkbox' },
        { key: 'use_matching_low', label: 'Matching Low', type: 'checkbox' },
        // ===== BEARISH REVERSAL (SHORT) =====
        { type: 'separator', label: '━━━ Bearish Reversal (SHORT) ━━━' },
        { key: 'use_shooting_star', label: 'Shooting Star', type: 'checkbox' },
        { key: 'use_hanging_man', label: 'Hanging Man', type: 'checkbox' },
        { key: 'use_engulfing_bear', label: 'Bearish Engulfing', type: 'checkbox' },
        { key: 'use_evening_star', label: 'Evening Star', type: 'checkbox' },
        { key: 'use_dark_cloud', label: 'Dark Cloud Cover', type: 'checkbox' },
        { key: 'use_three_black', label: 'Three Black Crows', type: 'checkbox' },
        { key: 'use_tweezer_top', label: 'Tweezer Top', type: 'checkbox' },
        { key: 'use_gravestone_doji', label: 'Gravestone Doji', type: 'checkbox' },
        { key: 'use_bearish_harami', label: 'Bearish Harami', type: 'checkbox' },
        { key: 'use_falling_three', label: 'Falling Three Methods', type: 'checkbox' },
        { key: 'use_bearish_marubozu', label: 'Bearish Marubozu', type: 'checkbox' },
        // Exotic Bearish
        { type: 'separator', label: '── Exotic Bearish ──' },
        { key: 'use_pin_bar_bearish', label: 'Pin Bar Bearish', type: 'checkbox' },
        { key: 'use_three_line_strike_bear', label: 'Three Line Strike (Bear)', type: 'checkbox' },
        { key: 'use_kicker_bearish', label: 'Kicker Bearish', type: 'checkbox' },
        { key: 'use_abandoned_baby_bear', label: 'Abandoned Baby (Bear)', type: 'checkbox' },
        { key: 'use_belt_hold_bearish', label: 'Belt Hold Bearish', type: 'checkbox' },
        { key: 'use_counterattack_bear', label: 'Counterattack Bearish', type: 'checkbox' },
        { key: 'use_ladder_top', label: 'Ladder Top', type: 'checkbox' },
        { key: 'use_stick_sandwich_bear', label: 'Stick Sandwich (Bear)', type: 'checkbox' },
        { key: 'use_matching_high', label: 'Matching High', type: 'checkbox' },
        // ===== NEUTRAL / STRUCTURE =====
        { type: 'separator', label: '━━━ Neutral / Structure ━━━' },
        { key: 'use_doji', label: 'Standard Doji', type: 'checkbox' },
        { key: 'use_spinning_top', label: 'Spinning Top', type: 'checkbox' },
        { key: 'use_inside_bar', label: 'Inside Bar', type: 'checkbox' },
        { key: 'use_outside_bar', label: 'Outside Bar', type: 'checkbox' },
        // ===== GAP PATTERNS =====
        { type: 'separator', label: '━━━ Gap Patterns ━━━' },
        { key: 'use_gap_up', label: 'Gap Up', type: 'checkbox' },
        { key: 'use_gap_down', label: 'Gap Down', type: 'checkbox' },
        { key: 'use_gap_up_filled', label: 'Gap Up Filled', type: 'checkbox' },
        { key: 'use_gap_down_filled', label: 'Gap Down Filled', type: 'checkbox' }
      ]
    },
    trend_filter: {
      title: 'Trend Filter Settings',
      fields: [
        { key: 'ema_period', label: 'EMA Period', type: 'number', optimizable: true },
        { key: 'use_ema_slope', label: 'Use EMA Slope', type: 'checkbox' },
        { key: 'slope_threshold', label: 'Slope Threshold', type: 'number', optimizable: true },
        { key: 'use_adx', label: 'Use ADX Filter', type: 'checkbox' },
        { key: 'adx_period', label: 'ADX Period', type: 'number', optimizable: true },
        { key: 'adx_threshold', label: 'ADX Threshold', type: 'number', optimizable: true }
      ]
    },
    volume_filter: {
      title: 'Volume Filter Settings',
      fields: [
        { key: 'ma_period', label: 'MA Period', type: 'number', optimizable: true },
        { key: 'volume_multiplier', label: 'Volume Multiplier', type: 'number', optimizable: true },
        { key: 'filter_type', label: 'Filter Type', type: 'select', options: ['above', 'below'] }
      ]
    },
    volatility_filter: {
      title: 'Volatility Filter Settings',
      fields: [
        { key: 'atr_period', label: 'ATR Period', type: 'number', optimizable: true },
        { key: 'atr_multiplier', label: 'ATR Multiplier', type: 'number', optimizable: true },
        { key: 'use_bb_width', label: 'Use BB Width', type: 'checkbox' },
        { key: 'bb_period', label: 'BB Period', type: 'number', optimizable: true },
        { key: 'bb_threshold', label: 'BB Width Threshold', type: 'number', optimizable: true }
      ]
    },
    time_filter: {
      title: 'Time Filter Settings',
      fields: [
        { key: 'start_hour', label: 'Start Hour (UTC)', type: 'number', optimizable: false },
        { key: 'end_hour', label: 'End Hour (UTC)', type: 'number', optimizable: false },
        { key: 'use_days', label: 'Filter by Days', type: 'checkbox' }
      ]
    },
    price_filter: {
      title: 'Price Filter Settings',
      fields: [
        { key: 'level', label: 'Price Level', type: 'number', optimizable: true },
        { key: 'filter_type', label: 'Filter Type', type: 'select', options: ['above', 'below'] },
        { key: 'use_ema', label: 'Use EMA instead', type: 'checkbox' },
        { key: 'ema_period', label: 'EMA Period', type: 'number', optimizable: true }
      ]
    },
    block_worse_filter: {
      title: 'BLOCK IF WORSE THAN',
      fields: [
        { key: 'block_worse_enable', label: 'Enable Block if Worse Filter', type: 'checkbox' },
        { key: 'block_worse_percent', label: 'Max Price Change % (block entry if exceeded)', type: 'number', optimizable: true }
      ]
    },

    // =============================================
    // CONDITIONS
    // =============================================
    crossover: {
      title: 'Crossover Condition',
      fields: [
        { key: 'source_a', label: 'Source A', type: 'select', options: ['input_a', 'input_b', 'value'] },
        { key: 'source_b', label: 'Source B', type: 'select', options: ['input_a', 'input_b', 'value'] }
      ]
    },
    crossunder: {
      title: 'Crossunder Condition',
      fields: [
        { key: 'source_a', label: 'Source A', type: 'select', options: ['input_a', 'input_b', 'value'] },
        { key: 'source_b', label: 'Source B', type: 'select', options: ['input_a', 'input_b', 'value'] }
      ]
    },
    greater_than: {
      title: 'Greater Than Condition',
      fields: [
        { key: 'value', label: 'Compare Value', type: 'number', optimizable: true },
        { key: 'use_input', label: 'Use Input B', type: 'checkbox' }
      ]
    },
    less_than: {
      title: 'Less Than Condition',
      fields: [
        { key: 'value', label: 'Compare Value', type: 'number', optimizable: true },
        { key: 'use_input', label: 'Use Input B', type: 'checkbox' }
      ]
    },
    equals: {
      title: 'Equals Condition',
      fields: [
        { key: 'value', label: 'Compare Value', type: 'number', optimizable: true },
        { key: 'tolerance', label: 'Tolerance', type: 'number', optimizable: false }
      ]
    },
    between: {
      title: 'Between Condition',
      fields: [
        { key: 'min_value', label: 'Min Value', type: 'number', optimizable: true },
        { key: 'max_value', label: 'Max Value', type: 'number', optimizable: true }
      ]
    },

    // =============================================
    // ACTIONS
    // =============================================
    buy: {
      title: 'Buy Order Settings',
      fields: [
        { key: 'quantity', label: 'Quantity (%)', type: 'number', optimizable: false },
        { key: 'order_type', label: 'Order Type', type: 'select', options: ['market', 'limit'] },
        { key: 'use_percent', label: 'Use % of Capital', type: 'checkbox' }
      ]
    },
    sell: {
      title: 'Sell Order Settings',
      fields: [
        { key: 'quantity', label: 'Quantity (%)', type: 'number', optimizable: false },
        { key: 'order_type', label: 'Order Type', type: 'select', options: ['market', 'limit'] },
        { key: 'use_percent', label: 'Use % of Capital', type: 'checkbox' }
      ]
    },
    close: {
      title: 'Close Position Settings',
      fields: [
        { key: 'close_percent', label: 'Close %', type: 'number', optimizable: false }
      ]
    },
    stop_loss: {
      title: 'Stop Loss Settings',
      fields: [
        { key: 'percent', label: 'Stop Loss %', type: 'number', optimizable: true },
        { key: 'use_atr', label: 'Use ATR-based SL', type: 'checkbox' },
        { key: 'atr_multiplier', label: 'ATR Multiplier', type: 'number', optimizable: true }
      ]
    },
    take_profit: {
      title: 'Take Profit Settings',
      fields: [
        { key: 'percent', label: 'Take Profit %', type: 'number', optimizable: true },
        { key: 'use_atr', label: 'Use ATR-based TP', type: 'checkbox' },
        { key: 'atr_multiplier', label: 'ATR Multiplier', type: 'number', optimizable: true }
      ]
    },
    trailing_stop: {
      title: 'Trailing Stop Settings',
      fields: [
        { key: 'percent', label: 'Trail %', type: 'number', optimizable: true },
        { key: 'activation_percent', label: 'Activation %', type: 'number', optimizable: true },
        { key: 'use_atr', label: 'Use ATR-based', type: 'checkbox' },
        { key: 'atr_multiplier', label: 'ATR Multiplier', type: 'number', optimizable: true }
      ]
    },

    // =============================================
    // LOGIC
    // =============================================
    and: {
      title: 'AND Logic',
      fields: []
    },
    or: {
      title: 'OR Logic',
      fields: []
    },
    not: {
      title: 'NOT Logic',
      fields: []
    },
    delay: {
      title: 'Delay Settings',
      fields: [
        { key: 'bars', label: 'Bars to Wait', type: 'number', optimizable: true },
        { key: 'delay_type', label: 'Delay Type', type: 'select', options: ['bars', 'time'] }
      ]
    },
    filter: {
      title: 'Signal Filter',
      fields: [
        { key: 'filter_type', label: 'Filter Type', type: 'select', options: ['pass', 'block', 'once_per_bar'] }
      ]
    },

    // =============================================
    // INPUTS
    // =============================================
    price: {
      title: 'Price Input',
      fields: [
        { key: 'source', label: 'Price Source', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3', 'ohlc4'] }
      ]
    },
    volume: {
      title: 'Volume Input',
      fields: []
    },
    constant: {
      title: 'Constant Value',
      fields: [
        { key: 'value', label: 'Value', type: 'number', optimizable: true }
      ]
    },

    // =============================================
    // NEW ENTRY TYPES
    // =============================================
    limit_entry: {
      title: 'Limit Entry Order',
      fields: [
        { key: 'price_offset', label: 'Price Offset', type: 'number', optimizable: true },
        { key: 'offset_type', label: 'Offset Type', type: 'select', options: ['percent', 'points', 'atr'] },
        { key: 'time_in_force', label: 'Time in Force', type: 'select', options: ['GTC', 'IOC', 'FOK'] }
      ]
    },
    stop_entry: {
      title: 'Stop Entry Order',
      fields: [
        { key: 'price_offset', label: 'Price Offset', type: 'number', optimizable: true },
        { key: 'offset_type', label: 'Offset Type', type: 'select', options: ['percent', 'points', 'atr'] },
        { key: 'time_in_force', label: 'Time in Force', type: 'select', options: ['GTC', 'IOC', 'FOK'] }
      ]
    },
    // Indent Order (DCA Feature)
    indent_order: {
      title: 'INDENT ORDER (Limit Entry Offset)',
      fields: [
        { key: 'indent_enable', label: 'Enable Indent Order', type: 'checkbox' },
        { key: 'indent_show_lines', label: 'Show Last Signal Lines', type: 'checkbox' },
        { key: 'indent_percent', label: 'Indent % (0.01 - 10)', type: 'number', optimizable: true },
        { key: 'indent_cancel_bars', label: 'Cancel if Not Executed After X Bars', type: 'number', optimizable: true }
      ]
    },

    // =============================================
    // EXIT MANAGEMENT
    // =============================================
    close_long: {
      title: 'Close Long Position',
      fields: [
        { key: 'close_percent', label: 'Close %', type: 'number', optimizable: false }
      ]
    },
    close_short: {
      title: 'Close Short Position',
      fields: [
        { key: 'close_percent', label: 'Close %', type: 'number', optimizable: false }
      ]
    },
    close_all: {
      title: 'Close All Positions',
      fields: []
    },

    // =============================================
    // ADVANCED STOPS (Extended DCA)
    // =============================================
    atr_stop: {
      title: 'ATR-BASED SL/TP (Extended)',
      fields: [
        { type: 'separator', label: '━━━ ATR Stop Loss ━━━' },
        { key: 'atr_sl_enable', label: 'Enable ATR Stop Loss', type: 'checkbox' },
        { key: 'atr_sl_wicks', label: 'Consider Wicks?', type: 'checkbox' },
        { key: 'atr_sl_method', label: 'Smoothing Method', type: 'select', options: ['WMA', 'RMA', 'SMA', 'EMA'] },
        { key: 'atr_sl_period', label: 'ATR Period', type: 'number', optimizable: true },
        { key: 'atr_sl_multiplier', label: 'ATR Multiplier', type: 'number', optimizable: true },
        { type: 'separator', label: '━━━ ATR Take Profit ━━━' },
        { key: 'atr_tp_enable', label: 'Enable ATR Take Profit', type: 'checkbox' },
        { key: 'atr_tp_wicks', label: 'Consider Wicks?', type: 'checkbox' },
        { key: 'atr_tp_method', label: 'Smoothing Method', type: 'select', options: ['WMA', 'RMA', 'SMA', 'EMA'] },
        { key: 'atr_tp_period', label: 'ATR Period', type: 'number', optimizable: true },
        { key: 'atr_tp_multiplier', label: 'ATR Multiplier', type: 'number', optimizable: true },
        { type: 'separator', label: '━━━ Common ━━━' },
        { key: 'from_entry', label: 'Calculate From Entry Price', type: 'checkbox' }
      ]
    },
    chandelier_stop: {
      title: 'Chandelier Exit',
      fields: [
        { key: 'period', label: 'Period', type: 'number', optimizable: true },
        { key: 'atr_multiplier', label: 'ATR Multiplier', type: 'number', optimizable: true }
      ]
    },

    // =============================================
    // BREAK-EVEN & PROTECTION
    // =============================================
    break_even: {
      title: 'Break Even Stop',
      fields: [
        { key: 'trigger_percent', label: 'Trigger at Profit %', type: 'number', optimizable: true },
        { key: 'offset', label: 'Offset (pips)', type: 'number', optimizable: false },
        { key: 'include_commission', label: 'Include Commission', type: 'checkbox' }
      ]
    },
    profit_lock: {
      title: 'Profit Lock',
      fields: [
        { key: 'trigger_percent', label: 'Trigger at Profit %', type: 'number', optimizable: true },
        { key: 'lock_percent', label: 'Lock Profit %', type: 'number', optimizable: true },
        { key: 'step_mode', label: 'Step Mode', type: 'checkbox' },
        { key: 'step_size', label: 'Step Size %', type: 'number', optimizable: true }
      ]
    },

    // =============================================
    // PARTIAL EXITS
    // =============================================
    scale_out: {
      title: 'Scale Out',
      fields: [
        { key: 'exit_percent', label: 'Exit %', type: 'number', optimizable: true },
        { key: 'trigger_type', label: 'Trigger Type', type: 'select', options: ['profit_percent', 'profit_amount', 'price_level'] },
        { key: 'trigger_value', label: 'Trigger Value', type: 'number', optimizable: true }
      ]
    },
    multi_tp: {
      title: 'Multiple Take Profits',
      fields: [
        { key: 'tp1_percent', label: 'TP1 Size %', type: 'number', optimizable: false },
        { key: 'tp1_target', label: 'TP1 Target %', type: 'number', optimizable: true },
        { key: 'tp2_percent', label: 'TP2 Size %', type: 'number', optimizable: false },
        { key: 'tp2_target', label: 'TP2 Target %', type: 'number', optimizable: true },
        { key: 'tp3_percent', label: 'TP3 Size %', type: 'number', optimizable: false },
        { key: 'tp3_target', label: 'TP3 Target %', type: 'number', optimizable: true },
        { key: 'use_tp3', label: 'Use TP3', type: 'checkbox' }
      ]
    },

    // =============================================
    // CLOSE CONDITIONS (EXIT RULES)
    // =============================================
    tp_percent: {
      title: 'TAKE PROFIT %',
      fields: [
        { key: 'take_profit_percent', label: 'Take Profit %', type: 'number', optimizable: true },
        { key: 'use_for_long', label: 'Use for LONG positions', type: 'checkbox' },
        { key: 'use_for_short', label: 'Use for SHORT positions', type: 'checkbox' }
      ]
    },
    sl_percent: {
      title: 'STOP LOSS %',
      fields: [
        { key: 'stop_loss_percent', label: 'Stop Loss %', type: 'number', optimizable: true },
        { key: 'use_for_long', label: 'Use for LONG positions', type: 'checkbox' },
        { key: 'use_for_short', label: 'Use for SHORT positions', type: 'checkbox' }
      ]
    },
    trailing_stop_exit: {
      title: 'TRAILING STOP',
      fields: [
        { key: 'activation_percent', label: 'Activation Profit %', type: 'number', optimizable: true },
        { key: 'trailing_percent', label: 'Trail Distance %', type: 'number', optimizable: true },
        { key: 'trail_type', label: 'Trail Type', type: 'select', options: ['percent', 'atr', 'points'] }
      ]
    },
    atr_exit: {
      title: 'ATR-BASED EXIT',
      fields: [
        { key: 'atr_period', label: 'ATR Period', type: 'number', optimizable: true },
        { type: 'separator', label: '------- Take Profit -------' },
        { key: 'use_atr_tp', label: 'Use ATR for Take Profit', type: 'checkbox' },
        { key: 'tp_atr_multiplier', label: 'TP ATR Multiplier', type: 'number', optimizable: true },
        { type: 'separator', label: '------- Stop Loss -------' },
        { key: 'use_atr_sl', label: 'Use ATR for Stop Loss', type: 'checkbox' },
        { key: 'sl_atr_multiplier', label: 'SL ATR Multiplier', type: 'number', optimizable: true }
      ]
    },
    time_exit: {
      title: 'TIME-BASED EXIT',
      fields: [
        { key: 'exit_type', label: 'Exit Type', type: 'select', options: ['bars', 'hours', 'minutes'] },
        { key: 'exit_after_bars', label: 'Exit After N Bars', type: 'number', optimizable: true },
        { key: 'exit_after_hours', label: 'Exit After N Hours', type: 'number', optimizable: true }
      ]
    },
    session_exit: {
      title: 'SESSION EXIT',
      fields: [
        { key: 'exit_session', label: 'Exit at Session', type: 'select', options: ['NY_close', 'London_close', 'Tokyo_close', 'Sydney_close', 'custom'] },
        { type: 'separator', label: '------- Custom Time -------' },
        { key: 'custom_hour', label: 'Custom Hour (0-23)', type: 'number', optimizable: false },
        { key: 'custom_minute', label: 'Custom Minute (0-59)', type: 'number', optimizable: false },
        { key: 'use_utc', label: 'Use UTC Time', type: 'checkbox' }
      ]
    },
    signal_exit: {
      title: 'SIGNAL EXIT',
      fields: [
        { key: 'exit_on_opposite', label: 'Exit on Opposite Signal', type: 'checkbox' },
        { key: 'exit_on_any_signal', label: 'Exit on Any Signal', type: 'checkbox' },
        { key: 'confirm_bars', label: 'Confirm Bars', type: 'number', optimizable: true }
      ]
    },
    indicator_exit: {
      title: 'INDICATOR EXIT',
      fields: [
        { key: 'indicator', label: 'Indicator', type: 'select', options: ['rsi', 'stochastic', 'cci', 'macd', 'bb_percent'] },
        { key: 'condition', label: 'Condition', type: 'select', options: ['crosses_above', 'crosses_below', 'above', 'below'] },
        { key: 'threshold', label: 'Threshold Value', type: 'number', optimizable: true },
        { type: 'separator', label: '------- Apply To -------' },
        { key: 'exit_long_only', label: 'Exit LONG Only', type: 'checkbox' },
        { key: 'exit_short_only', label: 'Exit SHORT Only', type: 'checkbox' }
      ]
    },
    break_even_exit: {
      title: 'BREAK EVEN MOVE',
      fields: [
        { key: 'activation_profit_percent', label: 'Activate at Profit %', type: 'number', optimizable: true },
        { key: 'move_to_profit_percent', label: 'Move SL to Profit %', type: 'number', optimizable: true },
        { type: 'separator', label: '------- Apply To -------' },
        { key: 'use_for_long', label: 'Use for LONG', type: 'checkbox' },
        { key: 'use_for_short', label: 'Use for SHORT', type: 'checkbox' }
      ]
    },
    partial_close: {
      title: 'PARTIAL CLOSE',
      fields: [
        { type: 'separator', label: '------- First Partial Close -------' },
        { key: 'trigger_profit_1', label: 'Trigger at Profit %', type: 'number', optimizable: true },
        { key: 'close_percent_1', label: 'Close % of Position', type: 'number', optimizable: false },
        { type: 'separator', label: '------- Second Partial Close -------' },
        { key: 'use_second_partial', label: 'Use Second Partial', type: 'checkbox' },
        { key: 'trigger_profit_2', label: 'Trigger at Profit %', type: 'number', optimizable: true },
        { key: 'close_percent_2', label: 'Close % of Position', type: 'number', optimizable: false }
      ]
    },
    multi_tp_exit: {
      title: 'MULTI TAKE PROFIT LEVELS',
      fields: [
        { type: 'separator', label: '------- TP1 -------' },
        { key: 'tp1_percent', label: 'TP1 Target %', type: 'number', optimizable: true },
        { key: 'tp1_close_percent', label: 'TP1 Close %', type: 'number', optimizable: false },
        { type: 'separator', label: '------- TP2 -------' },
        { key: 'use_tp2', label: 'Use TP2', type: 'checkbox' },
        { key: 'tp2_percent', label: 'TP2 Target %', type: 'number', optimizable: true },
        { key: 'tp2_close_percent', label: 'TP2 Close %', type: 'number', optimizable: false },
        { type: 'separator', label: '------- TP3 -------' },
        { key: 'use_tp3', label: 'Use TP3', type: 'checkbox' },
        { key: 'tp3_percent', label: 'TP3 Target %', type: 'number', optimizable: true },
        { key: 'tp3_close_percent', label: 'TP3 Close %', type: 'number', optimizable: false }
      ]
    },
    chandelier_exit: {
      title: 'CHANDELIER EXIT',
      fields: [
        { key: 'atr_period', label: 'ATR Period (22)', type: 'number', optimizable: true },
        { key: 'atr_multiplier', label: 'ATR Multiplier (3.0)', type: 'number', optimizable: true },
        { key: 'use_close', label: 'Use Close Price', type: 'checkbox' },
        { type: 'separator', label: '------- Apply To -------' },
        { key: 'use_for_long', label: 'Use for LONG (trail from High)', type: 'checkbox' },
        { key: 'use_for_short', label: 'Use for SHORT (trail from Low)', type: 'checkbox' }
      ]
    },

    // =============================================
    // DCA CLOSE CONDITIONS
    // =============================================
    rsi_close: {
      title: 'RSI CLOSE CONDITION',
      fields: [
        { key: 'rsi_close_enable', label: 'Enable RSI Close', type: 'checkbox' },
        { key: 'rsi_close_length', label: 'RSI Length', type: 'number', optimizable: true },
        { key: 'rsi_close_timeframe', label: 'TimeFrame', type: 'select', options: ['Chart', '1m', '5m', '15m', '30m', '1h', '4h', '1D'] },
        { type: 'separator', label: '------- Profit Filter -------' },
        { key: 'rsi_close_only_profit', label: 'Close Only With Profit', type: 'checkbox' },
        { key: 'rsi_close_min_profit', label: 'Min Profit %', type: 'number', optimizable: true },
        { type: 'separator', label: '------- Reach Level Mode -------' },
        { key: 'rsi_close_reach_enable', label: 'Use Reach Level', type: 'checkbox' },
        { key: 'rsi_close_reach_long_more', label: 'LONG: Close if RSI >', type: 'number', optimizable: true },
        { key: 'rsi_close_reach_long_less', label: 'LONG: Close if RSI <', type: 'number', optimizable: true },
        { key: 'rsi_close_reach_short_more', label: 'SHORT: Close if RSI >', type: 'number', optimizable: true },
        { key: 'rsi_close_reach_short_less', label: 'SHORT: Close if RSI <', type: 'number', optimizable: true },
        { type: 'separator', label: '------- Cross Level Mode -------' },
        { key: 'rsi_close_cross_enable', label: 'Use Cross Level', type: 'checkbox' },
        { key: 'rsi_close_cross_long_level', label: 'LONG: Close on cross down', type: 'number', optimizable: true },
        { key: 'rsi_close_cross_short_level', label: 'SHORT: Close on cross up', type: 'number', optimizable: true }
      ]
    },
    stoch_close: {
      title: 'STOCHASTIC CLOSE CONDITION',
      fields: [
        { key: 'stoch_close_enable', label: 'Enable Stochastic Close', type: 'checkbox' },
        { key: 'stoch_close_k_length', label: '%K Length', type: 'number', optimizable: true },
        { key: 'stoch_close_k_smooth', label: '%K Smoothing', type: 'number', optimizable: true },
        { key: 'stoch_close_d_smooth', label: '%D Smoothing', type: 'number', optimizable: true },
        { key: 'stoch_close_timeframe', label: 'TimeFrame', type: 'select', options: ['Chart', '1m', '5m', '15m', '30m', '1h', '4h', '1D'] },
        { type: 'separator', label: '------- Profit Filter -------' },
        { key: 'stoch_close_only_profit', label: 'Close Only With Profit', type: 'checkbox' },
        { key: 'stoch_close_min_profit', label: 'Min Profit %', type: 'number', optimizable: true },
        { type: 'separator', label: '------- Reach Level Mode -------' },
        { key: 'stoch_close_reach_enable', label: 'Use Reach Level', type: 'checkbox' },
        { key: 'stoch_close_reach_long_more', label: 'LONG: Close if %K >', type: 'number', optimizable: true },
        { key: 'stoch_close_reach_long_less', label: 'LONG: Close if %K <', type: 'number', optimizable: true },
        { key: 'stoch_close_reach_short_more', label: 'SHORT: Close if %K >', type: 'number', optimizable: true },
        { key: 'stoch_close_reach_short_less', label: 'SHORT: Close if %K <', type: 'number', optimizable: true },
        { type: 'separator', label: '------- Cross Level Mode -------' },
        { key: 'stoch_close_cross_enable', label: 'Use Cross Level', type: 'checkbox' },
        { key: 'stoch_close_cross_long_level', label: 'LONG: Close on cross down', type: 'number', optimizable: true },
        { key: 'stoch_close_cross_short_level', label: 'SHORT: Close on cross up', type: 'number', optimizable: true }
      ]
    },
    channel_close: {
      title: 'CHANNEL CLOSE (KELTNER/BOLLINGER)',
      fields: [
        { key: 'channel_close_enable', label: 'Enable Channel Close', type: 'checkbox' },
        { key: 'channel_close_timeframe', label: 'TimeFrame', type: 'select', options: ['Chart', '1m', '5m', '15m', '30m', '1h', '4h', '1D'] },
        { key: 'channel_close_band', label: 'Band Action', type: 'select', options: ['Breakout', 'Rebound'] },
        { key: 'channel_close_type', label: 'Channel Type', type: 'select', options: ['Keltner', 'Bollinger'] },
        { key: 'channel_close_condition', label: 'Condition', type: 'select', options: ['long_upper_short_lower', 'long_lower_short_upper', 'long_upper_short_upper', 'long_lower_short_lower'] },
        { type: 'separator', label: '------- Keltner Channel -------' },
        { key: 'channel_close_keltner_length', label: 'Keltner Length', type: 'number', optimizable: true },
        { key: 'channel_close_keltner_mult', label: 'Keltner Multiplier', type: 'number', optimizable: true },
        { type: 'separator', label: '------- Bollinger Bands -------' },
        { key: 'channel_close_bb_length', label: 'BB Length', type: 'number', optimizable: true },
        { key: 'channel_close_bb_deviation', label: 'BB Deviation', type: 'number', optimizable: true }
      ]
    },
    ma_close: {
      title: 'TWO MAs CLOSE CONDITION',
      fields: [
        { key: 'ma_close_enable', label: 'Enable MA Close', type: 'checkbox' },
        { key: 'ma_close_show_lines', label: 'Show MA Lines on Chart', type: 'checkbox' },
        { type: 'separator', label: '------- Profit Filter -------' },
        { key: 'ma_close_only_profit', label: 'Close Only With Profit', type: 'checkbox' },
        { key: 'ma_close_min_profit', label: 'Min Profit %', type: 'number', optimizable: true },
        { type: 'separator', label: '------- MA 1 (Fast) -------' },
        { key: 'ma_close_ma1_length', label: 'MA1 Length', type: 'number', optimizable: true },
        { key: 'ma_close_ma1_type', label: 'MA1 Type', type: 'select', options: ['SMA', 'EMA', 'WMA', 'DEMA', 'TEMA', 'HMA'] },
        { type: 'separator', label: '------- MA 2 (Slow) -------' },
        { key: 'ma_close_ma2_length', label: 'MA2 Length', type: 'number', optimizable: true },
        { key: 'ma_close_ma2_type', label: 'MA2 Type', type: 'select', options: ['SMA', 'EMA', 'WMA', 'DEMA', 'TEMA', 'HMA'] }
      ]
    },
    psar_close: {
      title: 'PARABOLIC SAR CLOSE',
      fields: [
        { key: 'psar_close_enable', label: 'Enable PSAR Close', type: 'checkbox' },
        { key: 'psar_close_opposite', label: 'Close on Opposite Signal', type: 'checkbox' },
        { type: 'separator', label: '------- Profit Filter -------' },
        { key: 'psar_close_only_profit', label: 'Close Only With Profit', type: 'checkbox' },
        { key: 'psar_close_min_profit', label: 'Min Profit %', type: 'number', optimizable: true },
        { type: 'separator', label: '------- PSAR Parameters -------' },
        { key: 'psar_close_start', label: 'Start (0.02)', type: 'number', optimizable: true },
        { key: 'psar_close_increment', label: 'Increment (0.02)', type: 'number', optimizable: true },
        { key: 'psar_close_maximum', label: 'Maximum (0.2)', type: 'number', optimizable: true },
        { key: 'psar_close_nth_bar', label: 'Close on Nth Trend Bar (0=any)', type: 'number', optimizable: true }
      ]
    },
    time_bars_close: {
      title: 'TIME/BARS CLOSE',
      fields: [
        { key: 'time_bars_close_enable', label: 'Enable Time/Bars Close', type: 'checkbox' },
        { key: 'close_after_bars', label: 'Close After N Bars', type: 'number', optimizable: true },
        { type: 'separator', label: '------- Profit Filter -------' },
        { key: 'close_only_profit', label: 'Close Only With Profit', type: 'checkbox' },
        { key: 'close_min_profit', label: 'Min Profit %', type: 'number', optimizable: true },
        { key: 'close_max_bars', label: 'Max Bars (force close)', type: 'number', optimizable: true }
      ]
    },

    // =============================================
    // POSITION SIZING
    // =============================================
    fixed_size: {
      title: 'Fixed Position Size',
      fields: [
        { key: 'size', label: 'Size', type: 'number', optimizable: false },
        { key: 'size_type', label: 'Size Type', type: 'select', options: ['base_currency', 'quote_currency', 'contracts'] }
      ]
    },
    percent_balance: {
      title: '% of Balance',
      fields: [
        { key: 'percent', label: 'Balance %', type: 'number', optimizable: true },
        { key: 'use_available', label: 'Use Available Balance', type: 'checkbox' }
      ]
    },
    risk_percent: {
      title: 'Risk % per Trade',
      fields: [
        { key: 'risk_percent', label: 'Risk %', type: 'number', optimizable: true },
        { key: 'stop_distance', label: 'Stop Distance %', type: 'number', optimizable: true }
      ]
    },
    atr_sizing: {
      title: 'ATR-based Sizing',
      fields: [
        { key: 'risk_percent', label: 'Risk %', type: 'number', optimizable: true },
        { key: 'atr_period', label: 'ATR Period', type: 'number', optimizable: true },
        { key: 'atr_multiplier', label: 'ATR Multiplier', type: 'number', optimizable: true }
      ]
    },
    kelly_criterion: {
      title: 'Kelly Criterion',
      fields: [
        { key: 'win_rate', label: 'Win Rate (0-1)', type: 'number', optimizable: false },
        { key: 'reward_risk', label: 'Reward/Risk Ratio', type: 'number', optimizable: false },
        { key: 'fraction', label: 'Kelly Fraction', type: 'number', optimizable: false }
      ]
    },

    // =============================================
    // ENTRY REFINEMENT
    // =============================================
    dca: {
      title: 'DCA (Dollar Cost Averaging)',
      fields: [
        { key: 'orders_count', label: 'Number of Orders', type: 'number', optimizable: true },
        { key: 'price_step', label: 'Price Step %', type: 'number', optimizable: true },
        { key: 'size_multiplier', label: 'Size Multiplier', type: 'number', optimizable: true },
        { key: 'total_size', label: 'Total Size %', type: 'number', optimizable: false }
      ]
    },
    pyramiding: {
      title: 'Pyramiding',
      fields: [
        { key: 'max_adds', label: 'Max Additions', type: 'number', optimizable: true },
        { key: 'add_size_percent', label: 'Add Size %', type: 'number', optimizable: true },
        { key: 'profit_trigger', label: 'Profit Trigger %', type: 'number', optimizable: true }
      ]
    },
    grid_orders: {
      title: 'Grid Orders',
      fields: [
        { key: 'grid_levels', label: 'Grid Levels', type: 'number', optimizable: true },
        { key: 'grid_step', label: 'Grid Step %', type: 'number', optimizable: true },
        { key: 'size_per_level', label: 'Size per Level %', type: 'number', optimizable: false }
      ]
    },
    average_down: {
      title: 'Average Down',
      fields: [
        { key: 'max_adds', label: 'Max Additions', type: 'number', optimizable: true },
        { key: 'loss_trigger', label: 'Loss Trigger %', type: 'number', optimizable: true },
        { key: 'add_size_percent', label: 'Add Size %', type: 'number', optimizable: true }
      ]
    },
    reentry: {
      title: 'Re-entry Logic',
      fields: [
        { key: 'wait_bars', label: 'Wait Bars', type: 'number', optimizable: true },
        { key: 'max_reentries', label: 'Max Re-entries', type: 'number', optimizable: true },
        { key: 'same_direction', label: 'Same Direction Only', type: 'checkbox' }
      ]
    },
    // =============================================
    // MARTINGALE & ANTI-MARTINGALE
    // =============================================
    martingale: {
      title: 'MARTINGALE',
      fields: [
        { key: 'multiplier', label: 'Size Multiplier (2.0)', type: 'number', optimizable: true },
        { key: 'max_steps', label: 'Max Steps', type: 'number', optimizable: true },
        { key: 'reset_on_win', label: 'Reset on Win', type: 'checkbox' },
        { type: 'separator', label: '------- Safety Limits -------' },
        { key: 'max_position_size', label: 'Max Position Size', type: 'number', optimizable: false }
      ]
    },
    anti_martingale: {
      title: 'ANTI-MARTINGALE',
      fields: [
        { key: 'multiplier', label: 'Size Multiplier (1.5)', type: 'number', optimizable: true },
        { key: 'max_steps', label: 'Max Steps', type: 'number', optimizable: true },
        { key: 'reset_on_loss', label: 'Reset on Loss', type: 'checkbox' },
        { type: 'separator', label: '------- Base Size -------' },
        { key: 'base_size_percent', label: 'Base Size %', type: 'number', optimizable: true }
      ]
    },
    // =============================================
    // DCA VARIANTS
    // =============================================
    dca_by_signal: {
      title: 'DCA BY SIGNAL',
      fields: [
        { key: 'max_dca_orders', label: 'Max DCA Orders', type: 'number', optimizable: true },
        { key: 'size_multiplier', label: 'Size Multiplier', type: 'number', optimizable: true },
        { key: 'same_signal_required', label: 'Same Signal Required', type: 'checkbox' },
        { type: 'separator', label: '------- Timing -------' },
        { key: 'min_bars_between', label: 'Min Bars Between Orders', type: 'number', optimizable: true }
      ]
    },
    dca_by_percent: {
      title: 'DCA BY % DROP',
      fields: [
        { key: 'price_drop_percent', label: 'Price Drop % to Trigger', type: 'number', optimizable: true },
        { key: 'max_dca_orders', label: 'Max DCA Orders', type: 'number', optimizable: true },
        { type: 'separator', label: '------- Size Settings -------' },
        { key: 'size_per_order', label: 'Size per Order %', type: 'number', optimizable: true },
        { key: 'use_multiplier', label: 'Use Size Multiplier', type: 'checkbox' },
        { key: 'size_multiplier', label: 'Size Multiplier (1.5)', type: 'number', optimizable: true }
      ]
    },
    scale_in: {
      title: 'SCALE IN',
      fields: [
        { key: 'total_orders', label: 'Total Orders', type: 'number', optimizable: true },
        { key: 'first_order_percent', label: 'First Order % of Total', type: 'number', optimizable: false },
        { type: 'separator', label: '------- Interval Settings -------' },
        { key: 'interval_type', label: 'Interval Type', type: 'select', options: ['bars', 'seconds', 'price_move'] },
        { key: 'interval_value', label: 'Interval Value', type: 'number', optimizable: true },
        { key: 'price_condition', label: 'Price Condition', type: 'select', options: ['any', 'better_price', 'worse_price'] }
      ]
    },

    // =============================================
    // RISK CONTROLS (CIRCUIT BREAKERS)
    // =============================================
    max_daily_loss: {
      title: 'Max Daily Loss',
      fields: [
        { key: 'max_loss_percent', label: 'Max Loss %', type: 'number', optimizable: false },
        { key: 'max_loss_amount', label: 'Max Loss Amount', type: 'number', optimizable: false },
        { key: 'use_percent', label: 'Use Percentage', type: 'checkbox' },
        { key: 'reset_hour', label: 'Reset Hour (UTC)', type: 'number', optimizable: false }
      ]
    },
    max_drawdown: {
      title: 'Max Drawdown',
      fields: [
        { key: 'max_dd_percent', label: 'Max Drawdown %', type: 'number', optimizable: false },
        { key: 'from_peak', label: 'From Equity Peak', type: 'checkbox' },
        { key: 'stop_all_trading', label: 'Stop All Trading', type: 'checkbox' }
      ]
    },
    max_trades_day: {
      title: 'Max Trades per Day',
      fields: [
        { key: 'max_trades', label: 'Max Trades', type: 'number', optimizable: false },
        { key: 'reset_hour', label: 'Reset Hour (UTC)', type: 'number', optimizable: false }
      ]
    },
    consecutive_loss: {
      title: 'Consecutive Loss Limit',
      fields: [
        { key: 'max_consecutive', label: 'Max Consecutive Losses', type: 'number', optimizable: false },
        { key: 'cooloff_hours', label: 'Cool-off Hours', type: 'number', optimizable: false }
      ]
    },
    cooloff_period: {
      title: 'Cool-off Period',
      fields: [
        { key: 'cooloff_hours', label: 'Cool-off Hours', type: 'number', optimizable: false },
        { key: 'trigger_type', label: 'Trigger Type', type: 'select', options: ['loss_count', 'loss_amount', 'drawdown'] },
        { key: 'trigger_value', label: 'Trigger Value', type: 'number', optimizable: false }
      ]
    },

    // =============================================
    // SESSION MANAGEMENT
    // =============================================
    active_hours: {
      title: 'Active Trading Hours',
      fields: [
        { key: 'start_hour', label: 'Start Hour', type: 'number', optimizable: false },
        { key: 'end_hour', label: 'End Hour', type: 'number', optimizable: false },
        { key: 'timezone', label: 'Timezone', type: 'select', options: ['UTC', 'EST', 'GMT', 'CET', 'JST'] }
      ]
    },
    trading_days: {
      title: 'Trading Days',
      fields: [
        { key: 'monday', label: 'Monday', type: 'checkbox' },
        { key: 'tuesday', label: 'Tuesday', type: 'checkbox' },
        { key: 'wednesday', label: 'Wednesday', type: 'checkbox' },
        { key: 'thursday', label: 'Thursday', type: 'checkbox' },
        { key: 'friday', label: 'Friday', type: 'checkbox' },
        { key: 'saturday', label: 'Saturday', type: 'checkbox' },
        { key: 'sunday', label: 'Sunday', type: 'checkbox' }
      ]
    },
    session_filter: {
      title: 'Session Filter',
      fields: [
        { key: 'london', label: 'London Session', type: 'checkbox' },
        { key: 'new_york', label: 'New York Session', type: 'checkbox' },
        { key: 'tokyo', label: 'Tokyo Session', type: 'checkbox' },
        { key: 'sydney', label: 'Sydney Session', type: 'checkbox' },
        { key: 'overlap_only', label: 'Overlap Only', type: 'checkbox' }
      ]
    },
    news_filter: {
      title: 'News Event Filter',
      fields: [
        { key: 'high_impact', label: 'Avoid High Impact', type: 'checkbox' },
        { key: 'medium_impact', label: 'Avoid Medium Impact', type: 'checkbox' },
        { key: 'minutes_before', label: 'Minutes Before', type: 'number', optimizable: false },
        { key: 'minutes_after', label: 'Minutes After', type: 'number', optimizable: false }
      ]
    },
    weekend_close: {
      title: 'Weekend Close',
      fields: [
        { key: 'close_friday_hour', label: 'Close Friday Hour', type: 'number', optimizable: false },
        { key: 'close_all', label: 'Close All Positions', type: 'checkbox' }
      ]
    },

    // =============================================
    // TIME MANAGEMENT
    // =============================================
    time_stop: {
      title: 'Time-based Stop',
      fields: [
        { key: 'hours', label: 'Max Hours', type: 'number', optimizable: true },
        { key: 'close_in_profit', label: 'Close if in Profit', type: 'checkbox' },
        { key: 'close_in_loss', label: 'Close if in Loss', type: 'checkbox' }
      ]
    },
    max_duration: {
      title: 'Max Trade Duration',
      fields: [
        { key: 'max_hours', label: 'Max Hours', type: 'number', optimizable: true },
        { key: 'action', label: 'Action', type: 'select', options: ['close', 'trail', 'break_even'] }
      ]
    },
    session_close: {
      title: 'Session Close',
      fields: [
        { key: 'close_hour', label: 'Close Hour', type: 'number', optimizable: false },
        { key: 'close_minute', label: 'Close Minute', type: 'number', optimizable: false },
        { key: 'timezone', label: 'Timezone', type: 'select', options: ['UTC', 'EST', 'GMT', 'CET'] }
      ]
    },
    intraday_only: {
      title: 'Intraday Only',
      fields: [
        { key: 'close_hour', label: 'Close Hour', type: 'number', optimizable: false },
        { key: 'close_minute', label: 'Close Minute', type: 'number', optimizable: false }
      ]
    },

    // =============================================
    // CORRELATION & MULTI-SYMBOL
    // =============================================
    correlation_filter: {
      title: 'Correlation Filter',
      fields: [
        { key: 'use_correlation', label: 'Enable Filter', type: 'checkbox' },
        { key: 'correlated_symbol', label: 'Correlated Symbol', type: 'text' },
        { key: 'correlation_period', label: 'Period', type: 'number', optimizable: true },
        { key: 'min_correlation', label: 'Min Correlation', type: 'number', optimizable: true },
        { key: 'max_correlation', label: 'Max Correlation', type: 'number', optimizable: false },
        { key: 'correlation_mode', label: 'Mode', type: 'select', options: ['positive', 'negative', 'any'] },
        { key: 'use_for_long', label: 'Use for Long', type: 'checkbox' },
        { key: 'use_for_short', label: 'Use for Short', type: 'checkbox' }
      ]
    },
    btc_dominance: {
      title: 'BTC Dominance Filter',
      fields: [
        { key: 'use_btc_dom', label: 'Enable', type: 'checkbox' },
        { key: 'btc_dom_threshold', label: 'Threshold %', type: 'number', optimizable: true },
        { key: 'condition', label: 'Condition', type: 'select', options: ['above', 'below', 'rising', 'falling'] },
        { key: 'use_trend', label: 'Use Trend', type: 'checkbox' },
        { key: 'trend_period', label: 'Trend Period', type: 'number', optimizable: false }
      ]
    },
    sector_strength: {
      title: 'Sector Strength',
      fields: [
        { key: 'use_sector', label: 'Enable', type: 'checkbox' },
        { key: 'benchmark_symbol', label: 'Benchmark', type: 'text' },
        { key: 'lookback_period', label: 'Lookback', type: 'number', optimizable: true },
        { key: 'min_outperformance', label: 'Min Outperformance %', type: 'number', optimizable: true },
        { key: 'use_for_long', label: 'Use for Long', type: 'checkbox' },
        { key: 'use_for_short', label: 'Use for Short', type: 'checkbox' }
      ]
    },
    relative_strength: {
      title: 'Relative Strength',
      fields: [
        { key: 'use_rs', label: 'Enable', type: 'checkbox' },
        { key: 'benchmark', label: 'Benchmark', type: 'text' },
        { key: 'rs_period', label: 'RS Period', type: 'number', optimizable: true },
        { key: 'rs_threshold', label: 'RS Threshold', type: 'number', optimizable: true },
        { key: 'rs_condition', label: 'Condition', type: 'select', options: ['above', 'below', 'rising', 'falling'] }
      ]
    },

    // =============================================
    // ALERT SYSTEM
    // =============================================
    price_alert: {
      title: 'Price Alert',
      fields: [
        { key: 'enabled', label: 'Enable Alert', type: 'checkbox' },
        { key: 'alert_type', label: 'Alert Type', type: 'select', options: ['crossing', 'above', 'below'] },
        { key: 'price_level', label: 'Price Level', type: 'number', optimizable: false },
        { key: 'send_notification', label: 'Send Notification', type: 'checkbox' },
        { key: 'sound_alert', label: 'Sound Alert', type: 'checkbox' },
        { key: 'webhook_url', label: 'Webhook URL', type: 'text' }
      ]
    },
    indicator_alert: {
      title: 'Indicator Alert',
      fields: [
        { key: 'enabled', label: 'Enable Alert', type: 'checkbox' },
        { key: 'indicator', label: 'Indicator', type: 'select', options: ['rsi', 'macd', 'stochastic', 'cci', 'adx'] },
        { key: 'condition', label: 'Condition', type: 'select', options: ['crosses_above', 'crosses_below', 'above', 'below'] },
        { key: 'threshold', label: 'Threshold', type: 'number', optimizable: false },
        { key: 'send_notification', label: 'Send Notification', type: 'checkbox' },
        { key: 'sound_alert', label: 'Sound Alert', type: 'checkbox' }
      ]
    },
    trade_alert: {
      title: 'Trade Alert',
      fields: [
        { key: 'enabled', label: 'Enable Alert', type: 'checkbox' },
        { key: 'on_entry', label: 'On Entry', type: 'checkbox' },
        { key: 'on_exit', label: 'On Exit', type: 'checkbox' },
        { key: 'on_sl_hit', label: 'On SL Hit', type: 'checkbox' },
        { key: 'on_tp_hit', label: 'On TP Hit', type: 'checkbox' },
        { key: 'send_notification', label: 'Send Notification', type: 'checkbox' },
        { key: 'webhook_url', label: 'Webhook URL', type: 'text' }
      ]
    },
    pnl_alert: {
      title: 'P&L Alert',
      fields: [
        { key: 'enabled', label: 'Enable Alert', type: 'checkbox' },
        { key: 'profit_threshold', label: 'Profit Threshold %', type: 'number', optimizable: false },
        { key: 'loss_threshold', label: 'Loss Threshold %', type: 'number', optimizable: false },
        { key: 'use_percent', label: 'Use Percent', type: 'checkbox' },
        { key: 'send_notification', label: 'Send Notification', type: 'checkbox' }
      ]
    },
    drawdown_alert: {
      title: 'Drawdown Alert',
      fields: [
        { key: 'enabled', label: 'Enable Alert', type: 'checkbox' },
        { key: 'drawdown_threshold', label: 'Drawdown Threshold %', type: 'number', optimizable: false },
        { key: 'send_notification', label: 'Send Notification', type: 'checkbox' },
        { key: 'pause_trading', label: 'Pause Trading', type: 'checkbox' }
      ]
    },

    // =============================================
    // VISUALIZATION
    // =============================================
    show_entries: {
      title: 'Show Entry Markers',
      fields: [
        { key: 'enabled', label: 'Enable', type: 'checkbox' },
        { key: 'long_color', label: 'Long Color', type: 'color' },
        { key: 'short_color', label: 'Short Color', type: 'color' },
        { key: 'marker_size', label: 'Marker Size', type: 'select', options: ['small', 'medium', 'large'] },
        { key: 'show_label', label: 'Show Label', type: 'checkbox' }
      ]
    },
    show_exits: {
      title: 'Show Exit Markers',
      fields: [
        { key: 'enabled', label: 'Enable', type: 'checkbox' },
        { key: 'profit_color', label: 'Profit Color', type: 'color' },
        { key: 'loss_color', label: 'Loss Color', type: 'color' },
        { key: 'marker_size', label: 'Marker Size', type: 'select', options: ['small', 'medium', 'large'] },
        { key: 'show_pnl', label: 'Show P&L', type: 'checkbox' }
      ]
    },
    show_sl_tp: {
      title: 'Show SL/TP Lines',
      fields: [
        { key: 'enabled', label: 'Enable', type: 'checkbox' },
        { key: 'sl_color', label: 'SL Color', type: 'color' },
        { key: 'tp_color', label: 'TP Color', type: 'color' },
        { key: 'line_style', label: 'Line Style', type: 'select', options: ['solid', 'dashed', 'dotted'] },
        { key: 'show_price', label: 'Show Price', type: 'checkbox' }
      ]
    },
    show_indicators: {
      title: 'Show Indicators on Chart',
      fields: [
        { key: 'enabled', label: 'Enable', type: 'checkbox' }
      ]
    },
    show_equity: {
      title: 'Show Equity Curve',
      fields: [
        { key: 'enabled', label: 'Enable', type: 'checkbox' },
        { key: 'show_drawdown', label: 'Show Drawdown', type: 'checkbox' },
        { key: 'show_benchmark', label: 'Show Benchmark', type: 'checkbox' },
        { key: 'benchmark_symbol', label: 'Benchmark Symbol', type: 'text' }
      ]
    },
    show_trades_table: {
      title: 'Show Trades Table',
      fields: [
        { key: 'enabled', label: 'Enable', type: 'checkbox' },
        { key: 'max_rows', label: 'Max Rows', type: 'number', optimizable: false },
        { key: 'highlight_winners', label: 'Highlight Winners', type: 'checkbox' }
      ]
    },

    // =============================================
    // DCA GRID SETTINGS (TradingView Multi DCA)
    // =============================================
    dca_grid_enable: {
      title: 'DCA GRID MODE',
      fields: [
        { key: 'enabled', label: 'Enable DCA Grid', type: 'checkbox' },
        { key: 'direction', label: 'Grid Direction', type: 'select', options: ['long', 'short', 'both'] },
        { key: 'leverage', label: 'Leverage', type: 'number', optimizable: true },
        { type: 'separator', label: '------- Alerts -------' },
        { key: 'first_order_alert_only', label: 'Alert Only on First Order', type: 'checkbox' }
      ]
    },
    dca_grid_settings: {
      title: 'GRID CONFIGURATION',
      fields: [
        { key: 'deposit', label: 'Bot Deposit ($)', type: 'number', optimizable: false },
        { key: 'grid_size_percent', label: 'Grid Size %', type: 'number', optimizable: true },
        { key: 'order_count', label: 'Number of Orders (3-15)', type: 'number', optimizable: true },
        { type: 'separator', label: '------- Order Distribution -------' },
        { key: 'first_order_percent', label: 'First Order % of Deposit', type: 'number', optimizable: true },
        { key: 'step_type', label: 'Step Type', type: 'select', options: ['linear', 'logarithmic', 'custom'] }
      ]
    },
    dca_martingale_config: {
      title: 'MARTINGALE CONFIGURATION',
      fields: [
        { key: 'enabled', label: 'Use Martingale', type: 'checkbox' },
        { key: 'coefficient', label: 'Martingale Coefficient (1.0-1.8)', type: 'number', optimizable: true },
        { key: 'mode', label: 'Mode', type: 'select', options: ['multiply_each', 'multiply_total', 'progressive'] },
        { type: 'separator', label: '------- Safety Limits -------' },
        { key: 'max_order_size', label: 'Max Single Order Size ($)', type: 'number', optimizable: false },
        { key: 'max_total_position', label: 'Max Total Position ($)', type: 'number', optimizable: false }
      ]
    },
    dca_log_steps: {
      title: 'LOGARITHMIC STEPS',
      fields: [
        { key: 'enabled', label: 'Use Log Steps', type: 'checkbox' },
        { key: 'coefficient', label: 'Log Coefficient (0.8-1.4)', type: 'number', optimizable: true },
        { type: 'separator', label: '------- Step Preview -------' },
        { key: 'first_step_percent', label: 'First Step %', type: 'number', optimizable: true },
        { key: 'last_step_percent', label: 'Last Step %', type: 'number', optimizable: true }
      ]
    },
    dca_dynamic_tp: {
      title: 'DYNAMIC TAKE PROFIT',
      fields: [
        { key: 'enabled', label: 'Change TP on Many Orders', type: 'checkbox' },
        { key: 'trigger_orders', label: 'If Orders More Than', type: 'number', optimizable: true },
        { key: 'new_tp_percent', label: 'Set New TP %', type: 'number', optimizable: true },
        { type: 'separator', label: '------- Adjustments -------' },
        { key: 'decrease_per_order', label: 'Decrease TP per Order %', type: 'number', optimizable: true },
        { key: 'min_tp_percent', label: 'Minimum TP %', type: 'number', optimizable: true }
      ]
    },
    dca_safety_close: {
      title: 'SAFETY CLOSE (DRAWDOWN)',
      fields: [
        { key: 'enabled', label: 'Close on Big Drawdown', type: 'checkbox' },
        { key: 'threshold_type', label: 'Threshold Type', type: 'select', options: ['percent', 'amount'] },
        { key: 'drawdown_percent', label: 'Drawdown % to Close', type: 'number', optimizable: true },
        { key: 'drawdown_amount', label: 'Drawdown $ to Close', type: 'number', optimizable: false },
        { type: 'separator', label: '------- Action -------' },
        { key: 'action', label: 'Action', type: 'select', options: ['close_all', 'close_partial', 'pause'] },
        { key: 'partial_close_percent', label: 'Partial Close %', type: 'number', optimizable: false }
      ]
    },

    // =============================================
    // MULTIPLE TAKE PROFITS (TP1-TP4)
    // =============================================
    multi_tp_enable: {
      title: 'MULTIPLE TAKE PROFITS',
      fields: [
        { key: 'enabled', label: 'Use Multi-TP (TP1-TP4)', type: 'checkbox' },
        { key: 'tp_count', label: 'Number of TPs (1-4)', type: 'number', optimizable: false },
        { key: 'close_remaining_at_last', label: 'Close All at Last TP', type: 'checkbox' }
      ]
    },
    tp1_config: {
      title: 'TP1 CONFIGURATION',
      fields: [
        { key: 'enabled', label: 'Enable TP1', type: 'checkbox' },
        { key: 'percent', label: 'TP1 Target %', type: 'number', optimizable: true },
        { key: 'close_percent', label: 'Close % of Position', type: 'number', optimizable: false }
      ]
    },
    tp2_config: {
      title: 'TP2 CONFIGURATION',
      fields: [
        { key: 'enabled', label: 'Enable TP2', type: 'checkbox' },
        { key: 'percent', label: 'TP2 Target %', type: 'number', optimizable: true },
        { key: 'close_percent', label: 'Close % of Position', type: 'number', optimizable: false }
      ]
    },
    tp3_config: {
      title: 'TP3 CONFIGURATION',
      fields: [
        { key: 'enabled', label: 'Enable TP3', type: 'checkbox' },
        { key: 'percent', label: 'TP3 Target %', type: 'number', optimizable: true },
        { key: 'close_percent', label: 'Close % of Position', type: 'number', optimizable: false }
      ]
    },
    tp4_config: {
      title: 'TP4 CONFIGURATION (FINAL)',
      fields: [
        { key: 'enabled', label: 'Enable TP4', type: 'checkbox' },
        { key: 'percent', label: 'TP4 Target %', type: 'number', optimizable: true },
        { key: 'close_percent', label: 'Close Remaining %', type: 'number', optimizable: false }
      ]
    },

    // =============================================
    // ATR-BASED EXIT
    // =============================================
    atr_sl: {
      title: 'ATR STOP LOSS',
      fields: [
        { key: 'enabled', label: 'Use ATR SL', type: 'checkbox' },
        { key: 'atr_period', label: 'ATR Period', type: 'number', optimizable: true },
        { key: 'atr_multiplier', label: 'ATR Multiplier', type: 'number', optimizable: true },
        { key: 'smoothing', label: 'Smoothing', type: 'select', options: ['RMA', 'SMA', 'EMA', 'WMA'] },
        { key: 'use_wicks', label: 'Consider Wicks', type: 'checkbox' }
      ]
    },
    atr_tp: {
      title: 'ATR TAKE PROFIT',
      fields: [
        { key: 'enabled', label: 'Use ATR TP', type: 'checkbox' },
        { key: 'atr_period', label: 'ATR Period', type: 'number', optimizable: true },
        { key: 'atr_multiplier', label: 'ATR Multiplier', type: 'number', optimizable: true },
        { key: 'smoothing', label: 'Smoothing', type: 'select', options: ['RMA', 'SMA', 'EMA', 'WMA'] }
      ]
    },
    atr_wicks_mode: {
      title: 'ATR WICKS MODE',
      fields: [
        { key: 'enabled', label: 'Enable Wicks Mode', type: 'checkbox' },
        { key: 'sl_wicks', label: 'SL Uses Wicks', type: 'checkbox' },
        { key: 'tp_wicks', label: 'TP Uses Wicks', type: 'checkbox' }
      ]
    },

    // =============================================
    // SIGNAL MEMORY
    // =============================================
    signal_memory_enable: {
      title: 'SIGNAL MEMORY',
      fields: [
        { key: 'enabled', label: 'Enable Signal Memory', type: 'checkbox' },
        { key: 'memory_bars', label: 'Remember for N Bars', type: 'number', optimizable: true },
        { key: 'execute_condition', label: 'Execute When', type: 'select', options: ['immediately', 'on_confirmation', 'on_pullback'] },
        { type: 'separator', label: '------- Filter -------' },
        { key: 'require_filter', label: 'Require Filter Pass', type: 'checkbox' },
        { key: 'filter_type', label: 'Filter Type', type: 'select', options: ['trend', 'volatility', 'volume'] }
      ]
    },
    cross_memory: {
      title: 'CROSS MEMORY',
      fields: [
        { key: 'enabled', label: 'Remember Cross Signals', type: 'checkbox' },
        { key: 'memory_bars', label: 'Memory Bars', type: 'number', optimizable: true },
        { key: 'cross_type', label: 'Cross Type', type: 'select', options: ['ma_cross', 'macd_signal', 'rsi_level', 'stoch_kd'] }
      ]
    },
    pattern_memory: {
      title: 'PATTERN MEMORY',
      fields: [
        { key: 'enabled', label: 'Remember Patterns', type: 'checkbox' },
        { key: 'memory_bars', label: 'Memory Bars', type: 'number', optimizable: true },
        { key: 'patterns', label: 'Patterns', type: 'select', options: ['engulfing', 'hammer', 'doji', 'all'] }
      ]
    }
  };

  const layout = customLayouts[block.type];
  if (!layout) return null;

  // Helper to render a complete optimization row (label + checkbox + range inputs)
  const renderOptRow = (key, label, value) => {
    const opt = optParams[key] || { enabled: false, min: value, max: value, step: 1 };
    const disabled = opt.enabled ? '' : 'disabled';
    return `
      <div class="tv-opt-row" data-param-key="${key}">
        <input type="checkbox" 
               class="tv-opt-checkbox"
               data-param-key="${key}"
               ${opt.enabled ? 'checked' : ''}>
        <span class="tv-opt-label">${label}</span>
        <div class="tv-opt-controls">
          <input type="number" class="tv-opt-input" value="${opt.min}" data-opt-field="min" data-param-key="${key}" ${disabled}>
          <span class="tv-opt-arrow">→</span>
          <input type="number" class="tv-opt-input" value="${opt.max}" data-opt-field="max" data-param-key="${key}" ${disabled}>
          <span class="tv-opt-slash">/</span>
          <input type="number" class="tv-opt-input tv-opt-step" value="${opt.step}" data-opt-field="step" data-param-key="${key}" step="any" ${disabled}>
        </div>
      </div>
    `;
  };

  let html = '<div class="tv-params-container">';

  // Header
  if (layout.title && !optimizationMode) {
    html += `<div class="tv-params-header">${layout.title}</div>`;
  }

  // Optimization mode header
  if (optimizationMode) {
    html += `<div class="tv-params-header">Optimization: ${layout.title || block.name}</div>`;
  }

  // Fields
  layout.fields.forEach(field => {
    // Separator - visual divider with label
    if (field.type === 'separator') {
      if (!optimizationMode) {
        html += `
          <div class="tv-param-separator">
            <span class="tv-separator-label">${field.label || ''}</span>
          </div>
        `;
      }
      return;
    }

    if (field.type === 'inline' && !optimizationMode) {
      // Inline row - only in default mode
      html += '<div class="tv-param-row tv-inline-row">';
      field.fields.forEach(f => {
        if (f.type === 'label') {
          html += `<span class="tv-inline-label">${f.label}</span>`;
        } else if (f.type === 'number') {
          const val = params[f.key] ?? '';
          html += `
            ${f.label ? `<span class="tv-inline-label">${f.label}</span>` : ''}
            <input type="number" 
                   class="tv-input tv-input-inline"
                   style="width: ${f.width || '80px'}"
                   value="${val}"
                   data-block-id="${blockId}"
                   data-param-key="${f.key}">
          `;
        }
      });
      html += '</div>';
    } else if (field.type === 'inline' && optimizationMode) {
      // In optimization mode, render inline fields as separate opt rows
      field.fields.forEach(f => {
        if (f.type === 'number' && f.optimizable) {
          const val = params[f.key] ?? 0;
          const label = f.label || formatParamName(f.key);
          html += renderOptRow(f.key, label, val);
        }
      });
    } else if (field.type === 'checkbox' && !optimizationMode) {
      const checked = params[field.key] ? 'checked' : '';
      html += `
        <div class="tv-param-row tv-checkbox-row">
          <label class="tv-checkbox-label">
            <input type="checkbox" 
                   class="tv-checkbox"
                   data-block-id="${blockId}"
                   data-param-key="${field.key}"
                   ${checked}>
            ${field.label}
            ${field.hasTooltip ? '<i class="bi bi-info-circle tv-tooltip-icon"></i>' : ''}
          </label>
        </div>
      `;
    } else if (field.type === 'select' && !optimizationMode) {
      const val = params[field.key] ?? 'chart';
      html += `
        <div class="tv-param-row">
          <label class="tv-label">${field.label}</label>
          <select class="tv-select"
                  data-block-id="${blockId}"
                  data-param-key="${field.key}">
            ${field.options.map(opt => {
        const optVal = opt.toLowerCase();
        return `<option value="${optVal}" ${val === optVal ? 'selected' : ''}>${opt}</option>`;
      }).join('')}
          </select>
        </div>
      `;
    } else if (field.type === 'number') {
      const val = params[field.key] ?? '';

      if (optimizationMode && field.optimizable) {
        // Optimization mode - use complete opt row
        html += renderOptRow(field.key, field.label, val);
      } else if (!optimizationMode) {
        // Default mode - show single input
        html += `
          <div class="tv-param-row">
            <label class="tv-label">${field.label}</label>
            <input type="number" 
                   class="tv-input"
                   value="${val}"
                   data-block-id="${blockId}"
                   data-param-key="${field.key}">
            ${field.hasTooltip ? '<i class="bi bi-info-circle tv-tooltip-icon"></i>' : ''}
          </div>
        `;
      }
    }
  }); html += '</div>';
  return html;
}

// Get port configuration based on block type
function getBlockPorts(blockId, category) {
  const portConfigs = {
    // Indicators - output data
    rsi: {
      inputs: [],
      outputs: [{ id: 'value', label: 'Value', type: 'data' }]
    },
    macd: {
      inputs: [],
      outputs: [
        { id: 'macd', label: 'MACD', type: 'data' },
        { id: 'signal', label: 'Signal', type: 'data' },
        { id: 'hist', label: 'Hist', type: 'data' }
      ]
    },
    ema: {
      inputs: [],
      outputs: [{ id: 'value', label: 'Value', type: 'data' }]
    },
    sma: {
      inputs: [],
      outputs: [{ id: 'value', label: 'Value', type: 'data' }]
    },
    bollinger: {
      inputs: [],
      outputs: [
        { id: 'upper', label: 'Upper', type: 'data' },
        { id: 'middle', label: 'Mid', type: 'data' },
        { id: 'lower', label: 'Lower', type: 'data' }
      ]
    },
    atr: {
      inputs: [],
      outputs: [{ id: 'value', label: 'Value', type: 'data' }]
    },
    stochastic: {
      inputs: [],
      outputs: [
        { id: 'k', label: '%K', type: 'data' },
        { id: 'd', label: '%D', type: 'data' }
      ]
    },
    adx: { inputs: [], outputs: [{ id: 'value', label: 'ADX', type: 'data' }] },

    // Conditions - input data, output bool
    crossover: {
      inputs: [
        { id: 'a', label: 'A', type: 'data' },
        { id: 'b', label: 'B', type: 'data' }
      ],
      outputs: [{ id: 'result', label: '', type: 'condition' }]
    },
    crossunder: {
      inputs: [
        { id: 'a', label: 'A', type: 'data' },
        { id: 'b', label: 'B', type: 'data' }
      ],
      outputs: [{ id: 'result', label: '', type: 'condition' }]
    },
    greater_than: {
      inputs: [
        { id: 'left', label: 'A', type: 'data' },
        { id: 'right', label: 'B', type: 'data' }
      ],
      outputs: [{ id: 'result', label: '', type: 'condition' }]
    },
    less_than: {
      inputs: [
        { id: 'left', label: 'A', type: 'data' },
        { id: 'right', label: 'B', type: 'data' }
      ],
      outputs: [{ id: 'result', label: '', type: 'condition' }]
    },
    equals: {
      inputs: [
        { id: 'a', label: 'A', type: 'data' },
        { id: 'b', label: 'B', type: 'data' }
      ],
      outputs: [{ id: 'result', label: '', type: 'condition' }]
    },
    between: {
      inputs: [
        { id: 'value', label: 'Val', type: 'data' },
        { id: 'min', label: 'Min', type: 'data' },
        { id: 'max', label: 'Max', type: 'data' }
      ],
      outputs: [{ id: 'result', label: '', type: 'condition' }]
    },

    // Actions - input condition, output flow
    buy: {
      inputs: [{ id: 'trigger', label: '', type: 'condition' }],
      outputs: [{ id: 'exec', label: '', type: 'flow' }]
    },
    sell: {
      inputs: [{ id: 'trigger', label: '', type: 'condition' }],
      outputs: [{ id: 'exec', label: '', type: 'flow' }]
    },
    close: {
      inputs: [{ id: 'trigger', label: '', type: 'condition' }],
      outputs: [{ id: 'exec', label: '', type: 'flow' }]
    },
    stop_loss: {
      inputs: [{ id: 'trigger', label: '', type: 'flow' }],
      outputs: []
    },
    take_profit: {
      inputs: [{ id: 'trigger', label: '', type: 'flow' }],
      outputs: []
    },
    trailing_stop: {
      inputs: [{ id: 'trigger', label: '', type: 'flow' }],
      outputs: []
    },

    // Logic - input/output conditions
    and: {
      inputs: [
        { id: 'a', label: 'A', type: 'condition' },
        { id: 'b', label: 'B', type: 'condition' }
      ],
      outputs: [{ id: 'result', label: '', type: 'condition' }]
    },
    or: {
      inputs: [
        { id: 'a', label: 'A', type: 'condition' },
        { id: 'b', label: 'B', type: 'condition' }
      ],
      outputs: [{ id: 'result', label: '', type: 'condition' }]
    },
    not: {
      inputs: [{ id: 'input', label: '', type: 'condition' }],
      outputs: [{ id: 'result', label: '', type: 'condition' }]
    },
    delay: {
      inputs: [{ id: 'input', label: '', type: 'condition' }],
      outputs: [{ id: 'result', label: '', type: 'condition' }]
    },
    filter: {
      inputs: [
        { id: 'signal', label: 'Sig', type: 'condition' },
        { id: 'filter', label: 'Flt', type: 'condition' }
      ],
      outputs: [{ id: 'result', label: '', type: 'condition' }]
    },

    // Inputs - output data
    price: {
      inputs: [],
      outputs: [
        { id: 'open', label: 'O', type: 'data' },
        { id: 'high', label: 'H', type: 'data' },
        { id: 'low', label: 'L', type: 'data' },
        { id: 'close', label: 'C', type: 'data' }
      ]
    },
    volume: {
      inputs: [],
      outputs: [{ id: 'value', label: 'Vol', type: 'data' }]
    },
    constant: {
      inputs: [],
      outputs: [{ id: 'value', label: '', type: 'data' }]
    },
    timeframe: {
      inputs: [],
      outputs: [{ id: 'value', label: '', type: 'data' }]
    },

    // Main Strategy node - receives entry/exit signals
    strategy: {
      inputs: [
        { id: 'entry_long', label: 'Entry Long', type: 'condition' },
        { id: 'exit_long', label: 'Exit Long', type: 'condition' },
        { id: 'entry_short', label: 'Entry Short', type: 'condition' },
        { id: 'exit_short', label: 'Exit Short', type: 'condition' }
      ],
      outputs: []
    }
  };

  return (
    portConfigs[blockId] || {
      inputs: [{ id: 'in', label: '', type: 'data' }],
      outputs: [{ id: 'out', label: '', type: 'data' }]
    }
  );
}

function renderPorts(ports, direction, blockId) {
  if (!ports || ports.length === 0) return '';

  if (ports.length === 1) {
    const port = ports[0];
    const posClass = direction === 'input' ? 'input' : 'output';
    return `<div class="port ${posClass} ${port.type}-port" 
                 data-port-id="${port.id}" 
                 data-port-type="${port.type}"
                 data-block-id="${blockId}"
                 data-direction="${direction}"
                 title="${port.label || port.type}"></div>`;
  }

  // Multiple ports
  return `
    <div class="ports-container ${direction}-ports">
      ${ports
      .map(
        (port) => `
        <div class="port-row ${direction}">
          <div class="port ${port.type}-port" 
               data-port-id="${port.id}" 
               data-port-type="${port.type}"
               data-block-id="${blockId}"
               data-direction="${direction}"
               title="${port.label || port.type}"></div>
          ${port.label ? `<span class="port-label">${port.label}</span>` : ''}
        </div>
      `
      )
      .join('')}
    </div>
  `;
}

function renderBlocks() {
  console.log(`[Strategy Builder] renderBlocks called, blocks count: ${strategyBlocks.length}`);
  const container = document.getElementById('blocksContainer');
  if (!container) {
    console.error('[Strategy Builder] Blocks container not found!');
    return;
  }
  container.innerHTML = strategyBlocks
    .map((block) => {
      const ports = getBlockPorts(block.type, block.category);
      const isMain = block.isMain === true;
      const paramHint = getCompactParamHint(block.params || {});
      const hasOptimization = block.optimizationParams &&
        Object.values(block.optimizationParams).some(p => p.enabled);
      return `
        <div class="strategy-block ${block.category} ${selectedBlockId === block.id ? 'selected' : ''} ${isMain ? 'main-block' : ''} ${hasOptimization ? 'has-optimization' : ''}"
             id="${block.id}"
             style="left: ${block.x}px; top: ${block.y}px"
             data-block-id="${block.id}">
            ${renderPorts(ports.inputs, 'input', block.id)}
            <div class="block-header">
                <div class="block-header-icon">
                    <i class="bi bi-${block.icon}"></i>
                </div>
                <span class="block-header-title">${block.name}</span>
                ${!isMain ? `
                <div class="block-header-actions">
                    <button class="block-action-btn" data-action="duplicate" title="Duplicate"><i class="bi bi-copy"></i></button>
                    <button class="block-action-btn" data-action="delete" title="Delete"><i class="bi bi-trash"></i></button>
                    <button class="block-header-menu" title="Settings"><i class="bi bi-three-dots"></i></button>
                </div>` : ''}
            </div>
            ${paramHint ? `<div class="block-param-hint">${paramHint}</div>` : ''}
            ${renderPorts(ports.outputs, 'output', block.id)}
        </div>
      `;
    })
    .join('');

  // Re-render connections after blocks
  renderConnections();
}

// Generate compact param hint for block (e.g. "14 | 70 | 30")
function getCompactParamHint(params) {
  const entries = Object.entries(params);
  if (entries.length === 0) return '';

  // Show up to 3 key values separated by |
  const values = entries.slice(0, 3).map(([_key, val]) => {
    // Shorten booleans
    if (val === true) return '✓';
    if (val === false) return '✗';
    // Shorten long strings
    if (typeof val === 'string' && val.length > 6) return val.slice(0, 6) + '…';
    return val;
  });

  return values.join(' | ') + (entries.length > 3 ? ' …' : '');
}

// Show block parameters popup
function showBlockParamsPopup(blockId, optimizationMode = false) {
  const block = strategyBlocks.find(b => b.id === blockId);
  if (!block) return;

  // Remove existing popup
  const existingPopup = document.querySelector('.block-params-popup');
  if (existingPopup) existingPopup.remove();

  const blockEl = document.getElementById(blockId);
  if (!blockEl) return;

  const params = block.params || {};
  const optParams = block.optimizationParams || {};

  // Auto-switch to optimization mode if block has optimization enabled
  const hasOptimization = block.optimizationParams &&
    Object.values(block.optimizationParams).some(p => p.enabled);
  if (hasOptimization && !optimizationMode) {
    optimizationMode = true;
  }

  const popup = document.createElement('div');
  popup.className = `block-params-popup ${optimizationMode ? 'optimization-mode' : ''}`;
  popup.dataset.blockId = blockId;
  popup.dataset.optimizationMode = optimizationMode;

  popup.innerHTML = `
    <div class="popup-header">
      <span class="popup-title"><i class="bi bi-${block.icon}"></i> ${block.name}</span>
      <button class="popup-close" data-action="close"><i class="bi bi-x"></i></button>
    </div>
    <div class="popup-body">
      ${renderGroupedParams(block, optimizationMode) || (Object.keys(params).length === 0
      ? '<p class="text-muted">No parameters</p>'
      : Object.entries(params).map(([key, value]) => {
        const opt = optParams[key] || { enabled: false, min: value, max: value, step: 1 };
        return optimizationMode ? `
          <div class="popup-param-row optimization-row">
            <div class="opt-checkbox">
              <input type="checkbox" 
                     id="opt_${blockId}_${key}" 
                     class="opt-enable-checkbox"
                     data-param-key="${key}"
                     ${opt.enabled ? 'checked' : ''}>
            </div>
            <label class="popup-param-label" for="opt_${blockId}_${key}">${formatParamName(key)}</label>
            <div class="opt-range-inputs">
              <input type="number" class="opt-input opt-min" value="${opt.min}" data-param-key="${key}" data-opt-field="min" title="From">
              <span class="opt-separator">→</span>
              <input type="number" class="opt-input opt-max" value="${opt.max}" data-param-key="${key}" data-opt-field="max" title="To">
              <span class="opt-separator">/</span>
              <input type="number" class="opt-input opt-step" value="${opt.step}" data-param-key="${key}" data-opt-field="step" title="Step" step="any">
            </div>
          </div>
          ` : `
          <div class="popup-param-row">
            <label class="popup-param-label">${formatParamName(key)}</label>
            <input type="text" 
                   class="popup-param-input" 
                   value="${value}"
                   data-block-id="${blockId}"
                   data-param-key="${key}">
          </div>
          `;
      }).join(''))}
    </div>
    <div class="popup-footer">
      <button class="btn btn-sm" data-action="default">
        <i class="bi bi-arrow-counterclockwise"></i> Default
      </button>
      <button class="btn btn-sm ${optimizationMode ? 'active' : ''}" data-action="optimization">
        <i class="bi bi-sliders"></i> Optimization
      </button>
    </div>
  `;

  // Add event listeners
  popup.querySelector('.popup-close').addEventListener('click', closeBlockParamsPopup);

  popup.querySelector('[data-action="default"]').addEventListener('click', () => resetBlockToDefaults(blockId));

  popup.querySelector('[data-action="optimization"]').addEventListener('click', (e) => {
    e.stopPropagation();
    // Remove listener before switching to prevent auto-close
    document.removeEventListener('click', closePopupOnOutsideClick);

    // If already in optimization mode - reset all optimization params and switch to normal mode
    if (optimizationMode) {
      // Reset all optimization params
      if (block.optimizationParams) {
        Object.keys(block.optimizationParams).forEach(key => {
          block.optimizationParams[key].enabled = false;
        });
      }
      updateBlockOptimizationIndicator(blockId);
      renderBlocks();
      showBlockParamsPopup(blockId, false);
    } else {
      // Switch to optimization mode
      showBlockParamsPopup(blockId, true);
    }
  });

  if (optimizationMode) {
    // Optimization mode handlers
    popup.querySelectorAll('.opt-enable-checkbox').forEach(checkbox => {
      checkbox.addEventListener('click', (e) => e.stopPropagation());
      checkbox.addEventListener('change', (e) => {
        e.stopPropagation();
        const key = checkbox.dataset.paramKey;
        if (!block.optimizationParams) block.optimizationParams = {};
        if (!block.optimizationParams[key]) {
          block.optimizationParams[key] = { enabled: false, min: params[key], max: params[key], step: 1 };
        }
        block.optimizationParams[key].enabled = checkbox.checked;
        updateBlockOptimizationIndicator(blockId);
      });
    });

    popup.querySelectorAll('.opt-input').forEach(input => {
      input.addEventListener('click', (e) => e.stopPropagation());
      input.addEventListener('change', (e) => {
        e.stopPropagation();
        const key = input.dataset.paramKey;
        const field = input.dataset.optField;
        if (!block.optimizationParams) block.optimizationParams = {};
        if (!block.optimizationParams[key]) {
          block.optimizationParams[key] = { enabled: false, min: params[key], max: params[key], step: 1 };
        }
        block.optimizationParams[key][field] = parseFloat(input.value);
      });
    });
  } else {
    // Normal mode - param value handlers
    popup.querySelectorAll('.popup-param-input').forEach(input => {
      input.addEventListener('click', (e) => e.stopPropagation());
      input.addEventListener('change', (e) => {
        e.stopPropagation();
        const key = input.dataset.paramKey;
        const value = input.value;
        updateBlockParam(blockId, key, value);
      });
    });
  }

  // Handle group toggles (for grouped params like RSI Filter)
  popup.querySelectorAll('.group-toggle').forEach(toggle => {
    toggle.addEventListener('click', (e) => e.stopPropagation());
    toggle.addEventListener('change', (e) => {
      e.stopPropagation();
      const key = toggle.dataset.paramKey;
      const enabled = toggle.checked;
      updateBlockParam(blockId, key, enabled);

      // Show/hide group body
      const group = toggle.closest('.param-group');
      if (group) {
        const body = group.querySelector('.param-group-body');
        if (body) body.style.display = enabled ? '' : 'none';
        group.classList.toggle('collapsed', !enabled);
      }
    });
  });

  // Handle select dropdowns (legacy)
  popup.querySelectorAll('.popup-param-select').forEach(select => {
    select.addEventListener('click', (e) => e.stopPropagation());
    select.addEventListener('change', (e) => {
      e.stopPropagation();
      const key = select.dataset.paramKey;
      updateBlockParam(blockId, key, select.value);
    });
  });

  // Handle checkbox params (legacy)
  popup.querySelectorAll('.popup-param-checkbox').forEach(checkbox => {
    checkbox.addEventListener('click', (e) => e.stopPropagation());
    checkbox.addEventListener('change', (e) => {
      e.stopPropagation();
      const key = checkbox.dataset.paramKey;
      updateBlockParam(blockId, key, checkbox.checked);
    });
  });

  // ========== TradingView-style handlers ==========

  // TV inputs
  popup.querySelectorAll('.tv-input').forEach(input => {
    input.addEventListener('click', (e) => e.stopPropagation());
    input.addEventListener('change', (e) => {
      e.stopPropagation();
      const key = input.dataset.paramKey;
      const val = parseFloat(input.value) || 0;
      updateBlockParam(blockId, key, val);
    });
  });

  // TV selects
  popup.querySelectorAll('.tv-select').forEach(select => {
    select.addEventListener('click', (e) => e.stopPropagation());
    select.addEventListener('change', (e) => {
      e.stopPropagation();
      const key = select.dataset.paramKey;
      updateBlockParam(blockId, key, select.value);
    });
  });

  // TV checkboxes
  popup.querySelectorAll('.tv-checkbox').forEach(checkbox => {
    checkbox.addEventListener('click', (e) => e.stopPropagation());
    checkbox.addEventListener('change', (e) => {
      e.stopPropagation();
      const key = checkbox.dataset.paramKey;
      updateBlockParam(blockId, key, checkbox.checked);
    });
  });

  // ========== TV-style Optimization handlers ==========

  // TV optimization checkboxes
  popup.querySelectorAll('.tv-opt-checkbox').forEach(checkbox => {
    checkbox.addEventListener('click', (e) => e.stopPropagation());
    checkbox.addEventListener('change', (e) => {
      e.stopPropagation();
      const key = checkbox.dataset.paramKey;
      if (!block.optimizationParams) block.optimizationParams = {};
      if (!block.optimizationParams[key]) {
        block.optimizationParams[key] = { enabled: false, min: params[key], max: params[key], step: 1 };
      }
      block.optimizationParams[key].enabled = checkbox.checked;

      // Enable/disable associated inputs
      const row = checkbox.closest('.tv-opt-row');
      if (row) {
        row.querySelectorAll('.tv-opt-input').forEach(inp => {
          inp.disabled = !checkbox.checked;
        });
      }
      updateBlockOptimizationIndicator(blockId);
    });
  });

  // TV optimization inputs
  popup.querySelectorAll('.tv-opt-input').forEach(input => {
    input.addEventListener('click', (e) => e.stopPropagation());
    input.addEventListener('change', (e) => {
      e.stopPropagation();
      const key = input.dataset.paramKey;
      const field = input.dataset.optField;
      if (!block.optimizationParams) block.optimizationParams = {};
      if (!block.optimizationParams[key]) {
        block.optimizationParams[key] = { enabled: false, min: params[key], max: params[key], step: 1 };
      }
      block.optimizationParams[key][field] = parseFloat(input.value);
    });
  });

  // Append popup inside the block element
  blockEl.appendChild(popup);

  // CRITICAL: Stop all clicks inside popup from bubbling to document
  popup.addEventListener('click', (e) => {
    e.stopPropagation();
  });

  // Position popup to the right of the block
  const blockWidth = blockEl.offsetWidth;
  popup.style.left = `${blockWidth + 10}px`;
  popup.style.top = '0px';

  // Close on outside click
  setTimeout(() => {
    document.addEventListener('click', closePopupOnOutsideClick);
  }, 10);
}

// Update block visual indicator for optimization
function updateBlockOptimizationIndicator(blockId) {
  const block = strategyBlocks.find(b => b.id === blockId);
  if (!block) return;

  const blockEl = document.getElementById(blockId);
  if (!blockEl) return;

  const hasOptimization = block.optimizationParams &&
    Object.values(block.optimizationParams).some(p => p.enabled);

  blockEl.classList.toggle('has-optimization', hasOptimization);
}

function closePopupOnOutsideClick(e) {
  const popup = document.querySelector('.block-params-popup');
  if (popup && !popup.contains(e.target) && !e.target.closest('.block-header-menu')) {
    closeBlockParamsPopup();
  }
}

function closeBlockParamsPopup() {
  const popup = document.querySelector('.block-params-popup');
  if (popup) popup.remove();
  document.removeEventListener('click', closePopupOnOutsideClick);
}

function updateBlockParamFromPopup(input) {
  const blockId = input.dataset.blockId;
  const key = input.dataset.paramKey;
  const value = input.value;
  updateBlockParam(blockId, key, value);
}

function resetBlockToDefaults(blockId) {
  const block = strategyBlocks.find(b => b.id === blockId);
  if (!block) return;

  // Get default params from getDefaultParams function
  const defaultParams = getDefaultParams(block.type);

  if (Object.keys(defaultParams).length > 0) {
    block.params = { ...defaultParams };
    renderBlocks();
    // Refresh popup if open
    closeBlockParamsPopup();
    showBlockParamsPopup(blockId);
    console.log('[Strategy Builder] Reset to defaults:', block.type, defaultParams);
  } else {
    console.log('[Strategy Builder] No default params for:', block.type);
  }
}

function duplicateBlock(blockId) {
  const block = strategyBlocks.find(b => b.id === blockId);
  if (!block || block.isMain) return;

  const newBlock = {
    ...block,
    id: `block_${Date.now()}`,
    x: block.x + 30,
    y: block.y + 30,
    params: { ...block.params }
  };

  strategyBlocks.push(newBlock);
  renderBlocks();
  selectBlock(newBlock.id);
}

function deleteBlock(blockId) {
  const block = strategyBlocks.find(b => b.id === blockId);
  if (!block || block.isMain) {
    console.log('[Strategy Builder] Cannot delete main Strategy node');
    return;
  }

  // Remove connections involving this block
  for (let i = connections.length - 1; i >= 0; i--) {
    const c = connections[i];
    if (c.source.blockId === blockId || c.target.blockId === blockId) {
      connections.splice(i, 1);
    }
  }

  // Remove block
  const idx = strategyBlocks.findIndex(b => b.id === blockId);
  if (idx !== -1) {
    strategyBlocks.splice(idx, 1);
  }

  if (selectedBlockId === blockId) {
    selectedBlockId = null;
  }

  renderBlocks();
  renderBlockProperties();

  // Notify optimization panels about block changes
  dispatchBlocksChanged();
}

function renderBlockParams(block) {
  const params = block.params;
  if (Object.keys(params).length === 0) {
    return '<span class="text-secondary" style="font-size: 11px">No parameters</span>';
  }

  return Object.entries(params)
    .map(
      ([key, value]) => `
                <div class="block-param">
                    <span class="block-param-label">${formatParamName(key)}</span>
                    <input type="text" 
                           class="block-param-input" 
                           value="${value}"
                           onchange="updateBlockParam('${block.id}', '${key}', this.value)"
                           onclick="event.stopPropagation()">
                </div>
            `
    )
    .join('');
}

function formatParamName(name) {
  return name.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
}

function selectBlock(blockId) {
  // Clear multi-selection when selecting single block
  clearMultiSelection();
  selectedBlockId = blockId;
  renderBlocks();
  renderBlockProperties();
}

function renderBlockProperties() {
  const container = document.getElementById('blockProperties');
  const block = strategyBlocks.find((b) => b.id === selectedBlockId);

  if (!block) {
    container.innerHTML =
      '<p class="text-secondary" style="font-size: 13px; text-align: center; padding: 20px 0">Select a block to view its properties</p>';
    return;
  }

  container.innerHTML = `
                <div class="property-row">
                    <span class="property-label">Name</span>
                    <span class="property-value">${block.name}</span>
                </div>
                <div class="property-row">
                    <span class="property-label">Type</span>
                    <span class="property-value">${block.type}</span>
                </div>
                <div class="property-row">
                    <span class="property-label">Category</span>
                    <span class="property-value">${block.category}</span>
                </div>
                <hr style="border-color: var(--border-color); margin: 12px 0">
                ${Object.entries(block.params)
      .map(
        ([key, value]) => `
                    <div class="property-row">
                        <span class="property-label">${formatParamName(key)}</span>
                        <input type="text" class="property-input" value="${value}" 
                               onchange="updateBlockParam('${block.id}', '${key}', this.value)">
                    </div>
                `
      )
      .join('')}
            `;
}

// =============================================================================
// BLOCK PARAMETER VALIDATION
// =============================================================================

/**
 * Validation rules for block parameters.
 * Each rule specifies: min, max, type, required, allowedValues
 */
const blockValidationRules = {
  // Momentum Indicators
  rsi: {
    period: { min: 1, max: 500, type: 'number', required: true },
    overbought: { min: 0, max: 100, type: 'number' },
    oversold: { min: 0, max: 100, type: 'number' }
  },
  stochastic: {
    k_period: { min: 1, max: 500, type: 'number', required: true },
    d_period: { min: 1, max: 100, type: 'number', required: true },
    smooth_k: { min: 1, max: 100, type: 'number' },
    overbought: { min: 0, max: 100, type: 'number' },
    oversold: { min: 0, max: 100, type: 'number' }
  },
  stoch_rsi: {
    rsi_period: { min: 1, max: 500, type: 'number', required: true },
    stoch_period: { min: 1, max: 500, type: 'number', required: true },
    k_period: { min: 1, max: 100, type: 'number' },
    d_period: { min: 1, max: 100, type: 'number' },
    overbought: { min: 0, max: 100, type: 'number' },
    oversold: { min: 0, max: 100, type: 'number' }
  },
  williams_r: {
    period: { min: 1, max: 500, type: 'number', required: true },
    overbought: { min: -100, max: 0, type: 'number' },
    oversold: { min: -100, max: 0, type: 'number' }
  },
  mfi: {
    period: { min: 1, max: 500, type: 'number', required: true },
    overbought: { min: 0, max: 100, type: 'number' },
    oversold: { min: 0, max: 100, type: 'number' }
  },
  cci: {
    period: { min: 1, max: 500, type: 'number', required: true },
    overbought: { min: -500, max: 500, type: 'number' },
    oversold: { min: -500, max: 500, type: 'number' }
  },
  cmo: {
    period: { min: 1, max: 500, type: 'number', required: true },
    overbought: { min: -100, max: 100, type: 'number' },
    oversold: { min: -100, max: 100, type: 'number' }
  },
  roc: {
    period: { min: 1, max: 500, type: 'number', required: true }
  },

  // Trend Indicators
  sma: { period: { min: 1, max: 500, type: 'number', required: true } },
  ema: { period: { min: 1, max: 500, type: 'number', required: true } },
  wma: { period: { min: 1, max: 500, type: 'number', required: true } },
  dema: { period: { min: 1, max: 500, type: 'number', required: true } },
  tema: { period: { min: 1, max: 500, type: 'number', required: true } },
  hull_ma: { period: { min: 1, max: 500, type: 'number', required: true } },
  macd: {
    fast_period: { min: 1, max: 500, type: 'number', required: true },
    slow_period: { min: 1, max: 500, type: 'number', required: true },
    signal_period: { min: 1, max: 100, type: 'number', required: true }
  },
  adx: {
    period: { min: 1, max: 500, type: 'number', required: true },
    threshold: { min: 0, max: 100, type: 'number' }
  },
  supertrend: {
    period: { min: 1, max: 500, type: 'number', required: true },
    multiplier: { min: 0.1, max: 10, type: 'number', required: true }
  },
  ichimoku: {
    tenkan_period: { min: 1, max: 500, type: 'number', required: true },
    kijun_period: { min: 1, max: 500, type: 'number', required: true },
    senkou_b_period: { min: 1, max: 500, type: 'number', required: true },
    displacement: { min: 1, max: 100, type: 'number' }
  },
  parabolic_sar: {
    start: { min: 0.001, max: 1, type: 'number', required: true },
    increment: { min: 0.001, max: 1, type: 'number', required: true },
    max_value: { min: 0.01, max: 2, type: 'number', required: true }
  },
  aroon: {
    period: { min: 1, max: 500, type: 'number', required: true },
    threshold: { min: 0, max: 100, type: 'number' }
  },
  qqe: {
    rsi_period: { min: 1, max: 500, type: 'number', required: true },
    qqe_factor: { min: 0.1, max: 20, type: 'number', required: true },
    smoothing_period: { min: 1, max: 100, type: 'number', required: true }
  },

  // Volatility Indicators
  atr: { period: { min: 1, max: 500, type: 'number', required: true } },
  atrp: { period: { min: 1, max: 500, type: 'number', required: true } },
  bollinger: {
    period: { min: 1, max: 500, type: 'number', required: true },
    std_dev: { min: 0.1, max: 10, type: 'number', required: true }
  },
  keltner: {
    ema_period: { min: 1, max: 500, type: 'number', required: true },
    atr_period: { min: 1, max: 500, type: 'number', required: true },
    multiplier: { min: 0.1, max: 10, type: 'number', required: true }
  },
  donchian: { period: { min: 1, max: 500, type: 'number', required: true } },
  stddev: { period: { min: 1, max: 500, type: 'number', required: true } },

  // Volume Indicators
  cmf: { period: { min: 1, max: 500, type: 'number', required: true } },

  // Action Blocks
  stop_loss: {
    percent: { min: 0.001, max: 100, type: 'number', required: true }
  },
  take_profit: {
    percent: { min: 0.001, max: 1000, type: 'number', required: true }
  },
  trailing_stop: {
    percent: { min: 0.001, max: 100, type: 'number', required: true },
    activation: { min: 0, max: 100, type: 'number' }
  },
  atr_stop: {
    period: { min: 1, max: 500, type: 'number', required: true },
    multiplier: { min: 0.1, max: 20, type: 'number', required: true }
  },
  chandelier_stop: {
    period: { min: 1, max: 500, type: 'number', required: true },
    multiplier: { min: 0.1, max: 20, type: 'number', required: true }
  },
  break_even: {
    trigger: { min: 0.001, max: 100, type: 'number', required: true },
    offset: { min: -10, max: 10, type: 'number' }
  },
  profit_lock: {
    trigger: { min: 0.001, max: 100, type: 'number', required: true },
    lock_percent: { min: 0, max: 100, type: 'number', required: true }
  },
  scale_out: {
    target: { min: 0.001, max: 100, type: 'number', required: true },
    percent: { min: 1, max: 100, type: 'number', required: true }
  },
  multi_tp: {
    tp1: { min: 0.001, max: 1000, type: 'number' },
    tp2: { min: 0.001, max: 1000, type: 'number' },
    tp3: { min: 0.001, max: 1000, type: 'number' }
  },
  limit_entry: {
    offset_percent: { min: -50, max: 50, type: 'number', required: true }
  },
  stop_entry: {
    offset_percent: { min: -50, max: 50, type: 'number', required: true }
  },

  // Exit Blocks
  atr_exit: {
    period: { min: 1, max: 500, type: 'number', required: true },
    tp_mult: { min: 0.1, max: 50, type: 'number', required: true },
    sl_mult: { min: 0.1, max: 50, type: 'number', required: true }
  },
  session_exit: {
    hour: { min: 0, max: 23, type: 'number', required: true },
    minute: { min: 0, max: 59, type: 'number' }
  },
  indicator_exit: {
    threshold: { min: -1000, max: 1000, type: 'number', required: true }
  },
  partial_close: {
    target: { min: 0.001, max: 100, type: 'number', required: true },
    percent: { min: 1, max: 100, type: 'number', required: true }
  },
  multi_tp_exit: {
    tp1: { min: 0.001, max: 1000, type: 'number' },
    tp2: { min: 0.001, max: 1000, type: 'number' },
    tp3: { min: 0.001, max: 1000, type: 'number' },
    alloc1: { min: 1, max: 100, type: 'number' },
    alloc2: { min: 1, max: 100, type: 'number' },
    alloc3: { min: 1, max: 100, type: 'number' }
  },
  // DCA Close Conditions validation
  rsi_close: {
    rsi_close_length: { min: 2, max: 200, type: 'number' },
    rsi_close_min_profit: { min: 0, max: 100, type: 'number' },
    rsi_close_reach_long_more: { min: 0, max: 100, type: 'number' },
    rsi_close_reach_long_less: { min: 0, max: 100, type: 'number' },
    rsi_close_reach_short_more: { min: 0, max: 100, type: 'number' },
    rsi_close_reach_short_less: { min: 0, max: 100, type: 'number' },
    rsi_close_cross_long_level: { min: 0, max: 100, type: 'number' },
    rsi_close_cross_short_level: { min: 0, max: 100, type: 'number' }
  },
  stoch_close: {
    stoch_close_k_length: { min: 1, max: 200, type: 'number' },
    stoch_close_k_smooth: { min: 1, max: 50, type: 'number' },
    stoch_close_d_smooth: { min: 1, max: 50, type: 'number' },
    stoch_close_min_profit: { min: 0, max: 100, type: 'number' },
    stoch_close_reach_long_more: { min: 0, max: 100, type: 'number' },
    stoch_close_reach_long_less: { min: 0, max: 100, type: 'number' },
    stoch_close_reach_short_more: { min: 0, max: 100, type: 'number' },
    stoch_close_reach_short_less: { min: 0, max: 100, type: 'number' }
  },
  channel_close: {
    channel_close_keltner_length: { min: 1, max: 200, type: 'number' },
    channel_close_keltner_mult: { min: 0.1, max: 10, type: 'number' },
    channel_close_bb_length: { min: 1, max: 200, type: 'number' },
    channel_close_bb_deviation: { min: 0.1, max: 10, type: 'number' }
  },
  ma_close: {
    ma_close_min_profit: { min: 0, max: 100, type: 'number' },
    ma_close_ma1_length: { min: 1, max: 500, type: 'number' },
    ma_close_ma2_length: { min: 1, max: 500, type: 'number' }
  },
  psar_close: {
    psar_close_min_profit: { min: 0, max: 100, type: 'number' },
    psar_close_start: { min: 0.001, max: 1, type: 'number' },
    psar_close_increment: { min: 0.001, max: 1, type: 'number' },
    psar_close_maximum: { min: 0.01, max: 1, type: 'number' },
    psar_close_nth_bar: { min: 0, max: 100, type: 'number' }
  },
  time_bars_close: {
    close_after_bars: { min: 1, max: 1000, type: 'number' },
    close_min_profit: { min: 0, max: 100, type: 'number' },
    close_max_bars: { min: 1, max: 10000, type: 'number' }
  },
  break_even_exit: {
    trigger: { min: 0.001, max: 100, type: 'number', required: true },
    offset: { min: -10, max: 10, type: 'number' }
  },

  // Conditions
  crossover: {},
  crossunder: {},
  greater_than: { value: { type: 'number' } },
  less_than: { value: { type: 'number' } },
  equals: { value: { type: 'number' } },
  between: {
    min_value: { type: 'number', required: true },
    max_value: { type: 'number', required: true }
  },

  // Price Action Patterns (no numeric validation needed)
  engulfing: {},
  hammer: { min_wick_ratio: { min: 0.1, max: 10, type: 'number' } },
  doji: { body_threshold: { min: 0.01, max: 1, type: 'number' } },
  pin_bar: { min_wick_ratio: { min: 0.1, max: 10, type: 'number' } },
  inside_bar: {},
  outside_bar: {},
  three_white_soldiers: {},
  morning_star: {},
  hammer_hangman: { min_wick_ratio: { min: 0.1, max: 10, type: 'number' } },
  doji_patterns: { body_threshold: { min: 0.01, max: 1, type: 'number' } },
  shooting_star: { min_wick_ratio: { min: 0.1, max: 10, type: 'number' } },
  marubozu: { max_wick_ratio: { min: 0.01, max: 1, type: 'number' } },
  tweezer: { tolerance: { min: 0.0001, max: 0.1, type: 'number' } },
  three_methods: {},
  piercing_darkcloud: {},
  harami: {},

  // Divergence
  rsi_divergence: {
    period: { min: 1, max: 500, type: 'number', required: true },
    lookback: { min: 5, max: 200, type: 'number' }
  },
  macd_divergence: {
    fast_period: { min: 1, max: 500, type: 'number', required: true },
    slow_period: { min: 1, max: 500, type: 'number', required: true },
    signal_period: { min: 1, max: 100, type: 'number' }
  },
  stoch_divergence: {
    k_period: { min: 1, max: 500, type: 'number', required: true },
    d_period: { min: 1, max: 100, type: 'number' }
  },
  obv_divergence: {
    lookback: { min: 5, max: 200, type: 'number' }
  },
  mfi_divergence: {
    period: { min: 1, max: 500, type: 'number', required: true },
    lookback: { min: 5, max: 200, type: 'number' }
  }
};

/**
 * Validate a single parameter value against rules.
 * @param {*} value - The parameter value
 * @param {Object} rule - The validation rule
 * @param {string} paramName - Parameter name for error message
 * @returns {{valid: boolean, error: string|null}}
 */
function validateParamValue(value, rule, paramName) {
  if (!rule) return { valid: true, error: null };

  // Check required
  if (rule.required && (value === undefined || value === null || value === '')) {
    return { valid: false, error: `${formatParamName(paramName)} is required` };
  }

  // Skip validation if empty and not required
  if (value === undefined || value === null || value === '') {
    return { valid: true, error: null };
  }

  // Type validation
  if (rule.type === 'number') {
    const numValue = parseFloat(value);
    if (isNaN(numValue)) {
      return { valid: false, error: `${formatParamName(paramName)} must be a number` };
    }

    // Range validation
    if (rule.min !== undefined && numValue < rule.min) {
      return { valid: false, error: `${formatParamName(paramName)} must be >= ${rule.min}` };
    }
    if (rule.max !== undefined && numValue > rule.max) {
      return { valid: false, error: `${formatParamName(paramName)} must be <= ${rule.max}` };
    }
  }

  // Allowed values validation
  if (rule.allowedValues && !rule.allowedValues.includes(value)) {
    return { valid: false, error: `${formatParamName(paramName)} must be one of: ${rule.allowedValues.join(', ')}` };
  }

  return { valid: true, error: null };
}

/**
 * Validate all parameters of a block.
 * @param {Object} block - The block to validate
 * @returns {{valid: boolean, errors: string[]}}
 */
function validateBlockParams(block) {
  const rules = blockValidationRules[block.type];
  if (!rules) return { valid: true, errors: [] };

  const errors = [];

  for (const [paramName, rule] of Object.entries(rules)) {
    const value = block.params[paramName];
    const result = validateParamValue(value, rule, paramName);
    if (!result.valid) {
      errors.push(result.error);
    }
  }

  // Additional cross-parameter validations
  if (block.type === 'macd') {
    const fast = parseFloat(block.params.fast_period);
    const slow = parseFloat(block.params.slow_period);
    if (!isNaN(fast) && !isNaN(slow) && fast >= slow) {
      errors.push('Fast period must be less than slow period');
    }
  }

  if (block.type === 'between') {
    const min = parseFloat(block.params.min_value);
    const max = parseFloat(block.params.max_value);
    if (!isNaN(min) && !isNaN(max) && min >= max) {
      errors.push('Min value must be less than max value');
    }
  }

  if (block.type === 'multi_tp' || block.type === 'multi_tp_exit') {
    const tp1 = parseFloat(block.params.tp1 || 0);
    const tp2 = parseFloat(block.params.tp2 || 0);
    const tp3 = parseFloat(block.params.tp3 || 0);
    if (tp1 > 0 && tp2 > 0 && tp1 >= tp2) {
      errors.push('TP1 must be less than TP2');
    }
    if (tp2 > 0 && tp3 > 0 && tp2 >= tp3) {
      errors.push('TP2 must be less than TP3');
    }
  }

  return { valid: errors.length === 0, errors };
}

/**
 * Update visual validation state on a block element.
 * @param {string} blockId - Block ID
 * @param {{valid: boolean, errors: string[]}} validationResult
 */
function updateBlockValidationState(blockId, validationResult) {
  const blockEl = document.getElementById(blockId);
  if (!blockEl) return;

  // Remove existing validation classes
  blockEl.classList.remove('block-valid', 'block-invalid');

  if (validationResult.valid) {
    blockEl.classList.add('block-valid');
    blockEl.title = '';
  } else {
    blockEl.classList.add('block-invalid');
    blockEl.title = validationResult.errors.join('\n');
  }
}

/**
 * Real-time validation for parameter input.
 * @param {HTMLInputElement} input - The input element
 */
function validateParamInput(input) {
  const blockId = input.dataset.blockId;
  const paramKey = input.dataset.paramKey;
  const block = strategyBlocks.find(b => b.id === blockId);

  if (!block) return;

  const rules = blockValidationRules[block.type];
  const rule = rules ? rules[paramKey] : null;

  const result = validateParamValue(input.value, rule, paramKey);

  // Update input visual state
  input.classList.remove('param-valid', 'param-invalid');
  if (!result.valid) {
    input.classList.add('param-invalid');
    input.title = result.error;
  } else {
    input.classList.add('param-valid');
    input.title = '';
  }

  // Also update the block's overall validation state
  const fullValidation = validateBlockParams(block);
  updateBlockValidationState(blockId, fullValidation);
}

function updateBlockParam(blockId, param, value) {
  const block = strategyBlocks.find((b) => b.id === blockId);
  if (block) {
    // Store the value
    const parsedValue = isNaN(value) ? value : parseFloat(value);
    block.params[param] = parsedValue;

    // Update hint on the block without full re-render
    const blockEl = document.getElementById(blockId);
    if (blockEl) {
      const hintEl = blockEl.querySelector('.block-param-hint');
      if (hintEl) {
        hintEl.textContent = getCompactParamHint(block.params);
      }
    }

    // Local validation (immediate feedback)
    const validationResult = validateBlockParams(block);
    updateBlockValidationState(blockId, validationResult);

    // Log validation errors if any
    if (!validationResult.valid) {
      console.warn(`[Strategy Builder] Block ${blockId} validation errors:`, validationResult.errors);
    }

    // WebSocket validation (server-side, debounced)
    if (wsValidation && wsValidation.isConnected()) {
      wsValidation.validateParam(blockId, block.type, param, parsedValue, (result) => {
        if (!result.fallback && !result.valid) {
          // Server found additional errors - update UI
          const serverErrors = result.messages
            .filter(m => m.severity === 'error')
            .map(m => m.message);
          if (serverErrors.length > 0) {
            const combined = [...validationResult.errors, ...serverErrors];
            updateBlockValidationState(blockId, { valid: false, errors: combined });
          }
        }
      });
    }
  }
}

function startDragBlock(event, blockId) {
  if (event.target.closest('.block-param-input')) return;

  isDragging = true;
  const block = document.getElementById(blockId);
  const rect = block.getBoundingClientRect();
  dragOffset = {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top
  };

  const onMouseMove = (e) => {
    if (!isDragging) return;
    const container = document
      .getElementById('canvasContainer')
      .getBoundingClientRect();
    const x = e.clientX - container.left - dragOffset.x;
    const y = e.clientY - container.top - dragOffset.y;

    block.style.left = `${Math.max(0, x)}px`;
    block.style.top = `${Math.max(0, y)}px`;

    // Update state
    const blockData = strategyBlocks.find((b) => b.id === blockId);
    if (blockData) {
      blockData.x = Math.max(0, x);
      blockData.y = Math.max(0, y);
    }

    // Update connections in real-time
    renderConnections();
  };

  const onMouseUp = () => {
    isDragging = false;
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
    renderConnections(); // Update connections when block moved
  };

  document.addEventListener('mousemove', onMouseMove);
  document.addEventListener('mouseup', onMouseUp);
}

// ============================================
// MARQUEE SELECTION (Rectangle Select)
// ============================================

function startMarqueeSelection(event) {
  // Clear previous selection if not holding Shift
  if (!event.shiftKey) {
    selectedBlockIds = [];
    clearMultiSelection();
  }

  isMarqueeSelecting = true;
  const container = document.getElementById('canvasContainer');
  const blocksContainer = document.getElementById('blocksContainer');
  const rect = container.getBoundingClientRect();

  marqueeStart = {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top
  };

  // Create marquee element in blocksContainer (same coordinate system as blocks)
  marqueeElement = document.createElement('div');
  marqueeElement.className = 'marquee-selection';
  marqueeElement.style.cssText = `
    position: absolute;
    border: 2px dashed #58a6ff;
    background: rgba(88, 166, 255, 0.15);
    pointer-events: none;
    z-index: 9999;
    border-radius: 4px;
  `;
  blocksContainer.appendChild(marqueeElement);

  const onMouseMove = (e) => {
    if (!isMarqueeSelecting) return;

    const currentX = e.clientX - rect.left;
    const currentY = e.clientY - rect.top;

    const left = Math.min(marqueeStart.x, currentX);
    const top = Math.min(marqueeStart.y, currentY);
    const width = Math.abs(currentX - marqueeStart.x);
    const height = Math.abs(currentY - marqueeStart.y);

    marqueeElement.style.left = `${left}px`;
    marqueeElement.style.top = `${top}px`;
    marqueeElement.style.width = `${width}px`;
    marqueeElement.style.height = `${height}px`;

    // Highlight blocks inside marquee
    highlightBlocksInMarquee(left, top, width, height);
  };

  const onMouseUp = () => {
    isMarqueeSelecting = false;

    // Get final selection
    if (marqueeElement) {
      const marqueeBounds = {
        left: parseInt(marqueeElement.style.left),
        top: parseInt(marqueeElement.style.top),
        width: parseInt(marqueeElement.style.width),
        height: parseInt(marqueeElement.style.height)
      };
      selectBlocksInMarquee(marqueeBounds);
      marqueeElement.remove();
      marqueeElement = null;
    }

    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
  };

  document.addEventListener('mousemove', onMouseMove);
  document.addEventListener('mouseup', onMouseUp);
}

function highlightBlocksInMarquee(left, top, width, height) {
  const marqueeBounds = { left, top, right: left + width, bottom: top + height };

  strategyBlocks.forEach(block => {
    const blockEl = document.getElementById(block.id);
    if (!blockEl) return;

    const blockBounds = {
      left: block.x,
      top: block.y,
      right: block.x + blockEl.offsetWidth,
      bottom: block.y + blockEl.offsetHeight
    };

    // Check intersection
    const intersects = !(
      blockBounds.right < marqueeBounds.left ||
      blockBounds.left > marqueeBounds.right ||
      blockBounds.bottom < marqueeBounds.top ||
      blockBounds.top > marqueeBounds.bottom
    );

    blockEl.classList.toggle('marquee-hover', intersects);
  });
}

function selectBlocksInMarquee(bounds) {
  strategyBlocks.forEach(block => {
    const blockEl = document.getElementById(block.id);
    if (!blockEl) return;

    blockEl.classList.remove('marquee-hover');

    const blockBounds = {
      left: block.x,
      top: block.y,
      right: block.x + blockEl.offsetWidth,
      bottom: block.y + blockEl.offsetHeight
    };

    // Check intersection
    const intersects = !(
      blockBounds.right < bounds.left ||
      blockBounds.left > bounds.left + bounds.width ||
      blockBounds.bottom < bounds.top ||
      blockBounds.top > bounds.top + bounds.height
    );

    if (intersects && !selectedBlockIds.includes(block.id)) {
      selectedBlockIds.push(block.id);
      blockEl.classList.add('multi-selected');
    }
  });

  console.log('[Strategy Builder] Selected blocks:', selectedBlockIds.length);
}

function clearMultiSelection() {
  document.querySelectorAll('.strategy-block.multi-selected').forEach(el => {
    el.classList.remove('multi-selected');
  });
  selectedBlockIds = [];
}

// ============================================
// GROUP DRAG
// ============================================

function startGroupDrag(event) {
  isGroupDragging = true;

  const container = document.getElementById('canvasContainer');
  const rect = container.getBoundingClientRect();
  const mouseX = event.clientX - rect.left;
  const mouseY = event.clientY - rect.top;

  // Calculate offset from mouse for each selected block
  groupDragOffsets = {};
  selectedBlockIds.forEach(blockId => {
    const block = strategyBlocks.find(b => b.id === blockId);
    if (block) {
      groupDragOffsets[blockId] = {
        x: block.x - mouseX,
        y: block.y - mouseY
      };
    }
  });

  const onMouseMove = (e) => {
    if (!isGroupDragging) return;

    const currentX = e.clientX - rect.left;
    const currentY = e.clientY - rect.top;

    // Move all selected blocks
    selectedBlockIds.forEach(blockId => {
      const block = strategyBlocks.find(b => b.id === blockId);
      const blockEl = document.getElementById(blockId);
      const offset = groupDragOffsets[blockId];

      if (block && blockEl && offset) {
        const newX = Math.max(0, currentX + offset.x);
        const newY = Math.max(0, currentY + offset.y);

        block.x = newX;
        block.y = newY;
        blockEl.style.left = `${newX}px`;
        blockEl.style.top = `${newY}px`;
      }
    });

    renderConnections();
  };

  const onMouseUp = () => {
    isGroupDragging = false;
    groupDragOffsets = {};
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
    renderConnections();
  };

  document.addEventListener('mousemove', onMouseMove);
  document.addEventListener('mouseup', onMouseUp);
}

// ============================================

let isConnecting = false;
let connectionStart = null;
let tempLine = null;

function initConnectionSystem() {
  const canvas = document.getElementById('connectionsCanvas');
  const container = document.getElementById('canvasContainer');

  // Listen for port clicks
  container.addEventListener('mousedown', (e) => {
    const port = e.target.closest('.port');
    if (port) {
      e.stopPropagation();
      startConnection(port, e);
    }
  });

  // Listen for mouse move during connection
  container.addEventListener('mousemove', (e) => {
    if (isConnecting) {
      updateTempConnection(e);
    }
  });

  // Listen for mouse up to complete connection
  container.addEventListener('mouseup', (e) => {
    if (isConnecting) {
      const port = e.target.closest('.port');
      if (port && port !== connectionStart.element) {
        completeConnection(port);
      } else {
        cancelConnection();
      }
    }
  });
}

function startConnection(portElement, event) {
  isConnecting = true;
  const rect = portElement.getBoundingClientRect();
  const containerRect = document
    .getElementById('canvasContainer')
    .getBoundingClientRect();

  connectionStart = {
    element: portElement,
    blockId: portElement.dataset.blockId,
    portId: portElement.dataset.portId,
    portType: portElement.dataset.portType,
    direction: portElement.dataset.direction,
    x: rect.left + rect.width / 2 - containerRect.left,
    y: rect.top + rect.height / 2 - containerRect.top
  };

  // Create temp line
  const svg = document.getElementById('connectionsCanvas');
  tempLine = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  tempLine.classList.add('connection-line', 'temp');
  svg.appendChild(tempLine);

  portElement.classList.add('connecting');
}

function updateTempConnection(event) {
  if (!tempLine || !connectionStart) return;

  const containerRect = document
    .getElementById('canvasContainer')
    .getBoundingClientRect();
  const endX = event.clientX - containerRect.left;
  const endY = event.clientY - containerRect.top;

  const path = createBezierPath(
    connectionStart.x,
    connectionStart.y,
    endX,
    endY,
    connectionStart.direction === 'output'
  );
  tempLine.setAttribute('d', path);
}

function completeConnection(endPortElement) {
  const endDirection = endPortElement.dataset.direction;

  // Validate: can't connect same direction
  if (connectionStart.direction === endDirection) {
    cancelConnection();
    return;
  }

  // Validate: can't connect same block
  if (connectionStart.blockId === endPortElement.dataset.blockId) {
    cancelConnection();
    return;
  }

  // Validate: port types should be compatible
  const startType = connectionStart.portType;
  const endType = endPortElement.dataset.portType;
  if (startType !== endType) {
    // Allow data->data, condition->condition, flow->flow
    cancelConnection();
    showNotification('Несовместимые типы портов', 'error');
    return;
  }

  // Determine source and target
  let source, target;
  if (connectionStart.direction === 'output') {
    source = {
      blockId: connectionStart.blockId,
      portId: connectionStart.portId
    };
    target = {
      blockId: endPortElement.dataset.blockId,
      portId: endPortElement.dataset.portId
    };
  } else {
    source = {
      blockId: endPortElement.dataset.blockId,
      portId: endPortElement.dataset.portId
    };
    target = {
      blockId: connectionStart.blockId,
      portId: connectionStart.portId
    };
  }

  // Check if connection already exists
  const exists = connections.some(
    (c) =>
      c.source.blockId === source.blockId &&
      c.source.portId === source.portId &&
      c.target.blockId === target.blockId &&
      c.target.portId === target.portId
  );

  if (!exists) {
    connections.push({
      id: `conn_${Date.now()}`,
      source,
      target,
      type: startType
    });
  }

  cancelConnection();
  renderConnections();
}

function cancelConnection() {
  isConnecting = false;
  if (tempLine) {
    tempLine.remove();
    tempLine = null;
  }
  if (connectionStart?.element) {
    connectionStart.element.classList.remove('connecting');
  }
  connectionStart = null;
}

function renderConnections() {
  const svg = document.getElementById('connectionsCanvas');
  // Clear existing connections (except temp)
  svg
    .querySelectorAll('.connection-line:not(.temp)')
    .forEach((el) => el.remove());

  connections.forEach((conn) => {
    const sourceBlock = document.getElementById(conn.source.blockId);
    const targetBlock = document.getElementById(conn.target.blockId);

    if (!sourceBlock || !targetBlock) return;

    // Find ports
    const sourcePort = sourceBlock.querySelector(
      `[data-port-id="${conn.source.portId}"][data-direction="output"]`
    );
    const targetPort = targetBlock.querySelector(
      `[data-port-id="${conn.target.portId}"][data-direction="input"]`
    );

    if (!sourcePort || !targetPort) return;

    const containerRect = document
      .getElementById('canvasContainer')
      .getBoundingClientRect();
    const sourceRect = sourcePort.getBoundingClientRect();
    const targetRect = targetPort.getBoundingClientRect();

    const startX = sourceRect.left + sourceRect.width / 2 - containerRect.left;
    const startY = sourceRect.top + sourceRect.height / 2 - containerRect.top;
    const endX = targetRect.left + targetRect.width / 2 - containerRect.left;
    const endY = targetRect.top + targetRect.height / 2 - containerRect.top;

    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.classList.add('connection-line', conn.type);
    path.setAttribute('d', createBezierPath(startX, startY, endX, endY, true));
    path.dataset.connectionId = conn.id;

    // Delete on click
    path.addEventListener('click', () => {
      deleteConnection(conn.id);
    });

    svg.appendChild(path);

    // Mark ports as connected
    sourcePort.classList.add('connected');
    targetPort.classList.add('connected');
  });
}

function createBezierPath(x1, y1, x2, y2, fromOutput) {
  const dx = Math.abs(x2 - x1);
  const controlOffset = Math.max(50, dx * 0.5);

  if (fromOutput) {
    return `M ${x1} ${y1} C ${x1 + controlOffset} ${y1}, ${x2 - controlOffset} ${y2}, ${x2} ${y2}`;
  } else {
    return `M ${x1} ${y1} C ${x1 - controlOffset} ${y1}, ${x2 + controlOffset} ${y2}, ${x2} ${y2}`;
  }
}

function deleteConnection(connectionId) {
  const index = connections.findIndex((c) => c.id === connectionId);
  if (index !== -1) {
    connections.splice(index, 1);
    renderConnections();
    renderBlocks(); // Update port states
  }
}

// Modal functions
function openTemplatesModal() {
  console.log('[Strategy Builder] Opening templates modal');
  const modal = document.getElementById('templatesModal');
  if (!modal) {
    console.error('[Strategy Builder] Templates modal not found!');
    return;
  }

  // Prevent any other handlers from closing it immediately
  const wasOpen = modal.classList.contains('active');
  if (wasOpen) {
    console.log('[Strategy Builder] Modal already open, skipping');
    return;
  }

  // Ensure templates are rendered before opening
  renderTemplates();

  // Update open time before opening (for overlay handler to check)
  if (window._updateTemplatesModalOpenTime) {
    window._updateTemplatesModalOpenTime();
  }

  // Open modal
  modal.classList.add('active');
  console.log('[Strategy Builder] Templates modal opened');
  console.log('[Strategy Builder] Modal classes:', modal.className);
  console.log('[Strategy Builder] Modal display:', window.getComputedStyle(modal).display);
  console.log('[Strategy Builder] Modal z-index:', window.getComputedStyle(modal).zIndex);
  console.log('[Strategy Builder] Modal visibility:', window.getComputedStyle(modal).visibility);

  // Check modal content visibility
  const modalContent = modal.querySelector('.modal');
  if (modalContent) {
    const contentStyle = window.getComputedStyle(modalContent);
    console.log('[Strategy Builder] Modal content (.modal) found');
    console.log('  - Display:', contentStyle.display);
    console.log('  - Opacity:', contentStyle.opacity);
    console.log('  - Visibility:', contentStyle.visibility);
    console.log('  - Z-index:', contentStyle.zIndex);
    console.log('  - Width:', contentStyle.width);
    console.log('  - Height:', contentStyle.height);
    console.log('  - Background:', contentStyle.backgroundColor);

    // Force visibility if needed
    if (contentStyle.display === 'none' || contentStyle.opacity === '0' || contentStyle.visibility === 'hidden') {
      console.warn('[Strategy Builder] Modal content not visible, forcing display');
      modalContent.style.display = 'flex';
      modalContent.style.flexDirection = 'column';
      modalContent.style.opacity = '1';
      modalContent.style.visibility = 'visible';
    }
  } else {
    console.error('[Strategy Builder] Modal content (.modal) NOT FOUND!');
  }

  // Verify it's still open after a moment
  setTimeout(() => {
    const stillOpen = modal.classList.contains('active');
    if (!stillOpen) {
      console.error('[Strategy Builder] Modal was closed unexpectedly! Reopening...');
      modal.classList.add('active');
    } else {
      console.log('[Strategy Builder] Modal confirmed open');
    }
  }, 100);
}

function closeTemplatesModal() {
  console.log('[Strategy Builder] Closing templates modal');
  const modal = document.getElementById('templatesModal');
  if (modal) {
    modal.classList.remove('active');
    console.log('[Strategy Builder] Templates modal closed');
  }
}

function selectTemplate(templateId) {
  console.log(`[Strategy Builder] Template selected: ${templateId}`);
  selectedTemplate = templateId;
  renderTemplates();

  // Visual feedback
  const cards = document.querySelectorAll('.template-card');
  cards.forEach(card => {
    if (card.dataset.templateId === templateId) {
      card.classList.add('selected');
      console.log(`[Strategy Builder] Template card selected: ${templateId}`);
    } else {
      card.classList.remove('selected');
    }
  });
}

function loadSelectedTemplate() {
  if (!selectedTemplate) {
    console.warn('[Strategy Builder] No template selected');
    showNotification('Выберите шаблон', 'warning');
    return;
  }

  console.log(`[Strategy Builder] Loading template: ${selectedTemplate}`);
  const template = templates.find((t) => t.id === selectedTemplate);
  if (template) {
    console.log('[Strategy Builder] Template found:', template);

    // Update strategy name
    const nameInput = document.getElementById('strategyName');
    if (nameInput) {
      nameInput.value = template.name;
    }

    // Load template blocks and connections
    loadTemplateData(selectedTemplate);

    // Close modal after a short delay to ensure template is loaded
    setTimeout(() => {
      closeTemplatesModal();
      showNotification(`Шаблон "${template.name}" загружен`, 'success');
    }, 100);
  } else {
    console.error(`[Strategy Builder] Template not found: ${selectedTemplate}`);
    showNotification(`Шаблон "${selectedTemplate}" не найден`, 'error');
  }
}

// Template data with actual blocks and connections
const templateData = {
  rsi_oversold: {
    blocks: [
      {
        id: 'rsi_1',
        type: 'rsi',
        category: 'indicator',
        name: 'RSI',
        icon: 'graph-up',
        x: 100,
        y: 150,
        params: { period: 14, overbought: 70, oversold: 30 }
      },
      {
        id: 'const_30',
        type: 'constant',
        category: 'input',
        name: 'Constant',
        icon: 'hash',
        x: 100,
        y: 300,
        params: { value: 30 }
      },
      {
        id: 'const_70',
        type: 'constant',
        category: 'input',
        name: 'Constant',
        icon: 'hash',
        x: 100,
        y: 400,
        params: { value: 70 }
      },
      {
        id: 'less_than_1',
        type: 'less_than',
        category: 'condition',
        name: 'Less Than',
        icon: 'chevron-double-down',
        x: 350,
        y: 200,
        params: {}
      },
      {
        id: 'greater_than_1',
        type: 'greater_than',
        category: 'condition',
        name: 'Greater Than',
        icon: 'chevron-double-up',
        x: 350,
        y: 350,
        params: {}
      }
    ],
    connections: [
      {
        id: 'conn_1',
        source: { blockId: 'rsi_1', portId: 'value' },
        target: { blockId: 'less_than_1', portId: 'left' },
        type: 'data'
      },
      {
        id: 'conn_2',
        source: { blockId: 'const_30', portId: 'value' },
        target: { blockId: 'less_than_1', portId: 'right' },
        type: 'data'
      },
      {
        id: 'conn_3',
        source: { blockId: 'rsi_1', portId: 'value' },
        target: { blockId: 'greater_than_1', portId: 'left' },
        type: 'data'
      },
      {
        id: 'conn_4',
        source: { blockId: 'const_70', portId: 'value' },
        target: { blockId: 'greater_than_1', portId: 'right' },
        type: 'data'
      },
      {
        id: 'conn_5',
        source: { blockId: 'less_than_1', portId: 'result' },
        target: { blockId: 'main_strategy', portId: 'entry_long' },
        type: 'condition'
      },
      {
        id: 'conn_6',
        source: { blockId: 'greater_than_1', portId: 'result' },
        target: { blockId: 'main_strategy', portId: 'exit_long' },
        type: 'condition'
      },
      {
        id: 'conn_7',
        source: { blockId: 'greater_than_1', portId: 'result' },
        target: { blockId: 'main_strategy', portId: 'entry_short' },
        type: 'condition'
      },
      {
        id: 'conn_8',
        source: { blockId: 'less_than_1', portId: 'result' },
        target: { blockId: 'main_strategy', portId: 'exit_short' },
        type: 'condition'
      }
    ]
  },
  macd_crossover: {
    blocks: [
      {
        id: 'macd_1',
        type: 'macd',
        category: 'indicator',
        name: 'MACD',
        icon: 'bar-chart',
        x: 100,
        y: 200,
        params: { fast: 12, slow: 26, signal: 9 }
      },
      {
        id: 'crossover_1',
        type: 'crossover',
        category: 'condition',
        name: 'Crossover',
        icon: 'intersect',
        x: 350,
        y: 150,
        params: {}
      },
      {
        id: 'crossunder_1',
        type: 'crossunder',
        category: 'condition',
        name: 'Crossunder',
        icon: 'intersect',
        x: 350,
        y: 350,
        params: {}
      }
    ],
    connections: [
      {
        id: 'conn_1',
        source: { blockId: 'macd_1', portId: 'macd' },
        target: { blockId: 'crossover_1', portId: 'a' },
        type: 'data'
      },
      {
        id: 'conn_2',
        source: { blockId: 'macd_1', portId: 'signal' },
        target: { blockId: 'crossover_1', portId: 'b' },
        type: 'data'
      },
      {
        id: 'conn_3',
        source: { blockId: 'macd_1', portId: 'macd' },
        target: { blockId: 'crossunder_1', portId: 'a' },
        type: 'data'
      },
      {
        id: 'conn_4',
        source: { blockId: 'macd_1', portId: 'signal' },
        target: { blockId: 'crossunder_1', portId: 'b' },
        type: 'data'
      },
      {
        id: 'conn_5',
        source: { blockId: 'crossover_1', portId: 'result' },
        target: { blockId: 'main_strategy', portId: 'entry_long' },
        type: 'condition'
      },
      {
        id: 'conn_6',
        source: { blockId: 'crossunder_1', portId: 'result' },
        target: { blockId: 'main_strategy', portId: 'exit_long' },
        type: 'condition'
      },
      {
        id: 'conn_7',
        source: { blockId: 'crossunder_1', portId: 'result' },
        target: { blockId: 'main_strategy', portId: 'entry_short' },
        type: 'condition'
      },
      {
        id: 'conn_8',
        source: { blockId: 'crossover_1', portId: 'result' },
        target: { blockId: 'main_strategy', portId: 'exit_short' },
        type: 'condition'
      }
    ]
  },
  ema_crossover: {
    blocks: [
      {
        id: 'ema_fast',
        type: 'ema',
        category: 'indicator',
        name: 'EMA Fast',
        icon: 'graph-up-arrow',
        x: 100,
        y: 150,
        params: { period: 9 }
      },
      {
        id: 'ema_slow',
        type: 'ema',
        category: 'indicator',
        name: 'EMA Slow',
        icon: 'graph-up-arrow',
        x: 100,
        y: 300,
        params: { period: 21 }
      },
      {
        id: 'crossover_1',
        type: 'crossover',
        category: 'condition',
        name: 'Crossover',
        icon: 'intersect',
        x: 350,
        y: 150,
        params: {}
      },
      {
        id: 'crossunder_1',
        type: 'crossunder',
        category: 'condition',
        name: 'Crossunder',
        icon: 'intersect',
        x: 350,
        y: 350,
        params: {}
      }
    ],
    connections: [
      {
        id: 'conn_1',
        source: { blockId: 'ema_fast', portId: 'value' },
        target: { blockId: 'crossover_1', portId: 'a' },
        type: 'data'
      },
      {
        id: 'conn_2',
        source: { blockId: 'ema_slow', portId: 'value' },
        target: { blockId: 'crossover_1', portId: 'b' },
        type: 'data'
      },
      {
        id: 'conn_3',
        source: { blockId: 'ema_fast', portId: 'value' },
        target: { blockId: 'crossunder_1', portId: 'a' },
        type: 'data'
      },
      {
        id: 'conn_4',
        source: { blockId: 'ema_slow', portId: 'value' },
        target: { blockId: 'crossunder_1', portId: 'b' },
        type: 'data'
      },
      {
        id: 'conn_5',
        source: { blockId: 'crossover_1', portId: 'result' },
        target: { blockId: 'main_strategy', portId: 'entry_long' },
        type: 'condition'
      },
      {
        id: 'conn_6',
        source: { blockId: 'crossunder_1', portId: 'result' },
        target: { blockId: 'main_strategy', portId: 'exit_long' },
        type: 'condition'
      },
      {
        id: 'conn_7',
        source: { blockId: 'crossunder_1', portId: 'result' },
        target: { blockId: 'main_strategy', portId: 'entry_short' },
        type: 'condition'
      },
      {
        id: 'conn_8',
        source: { blockId: 'crossover_1', portId: 'result' },
        target: { blockId: 'main_strategy', portId: 'exit_short' },
        type: 'condition'
      }
    ]
  },
  bollinger_bounce: {
    blocks: [
      {
        id: 'price_1',
        type: 'price',
        category: 'input',
        name: 'Price',
        icon: 'currency-dollar',
        x: 50,
        y: 150,
        params: {}
      },
      {
        id: 'bb_1',
        type: 'bollinger',
        category: 'indicator',
        name: 'Bollinger Bands',
        icon: 'distribute-vertical',
        x: 50,
        y: 300,
        params: { period: 20, stdDev: 2 }
      },
      {
        id: 'less_than_1',
        type: 'less_than',
        category: 'condition',
        name: 'Less Than',
        icon: 'chevron-double-down',
        x: 300,
        y: 150,
        params: {}
      },
      {
        id: 'greater_than_1',
        type: 'greater_than',
        category: 'condition',
        name: 'Greater Than',
        icon: 'chevron-double-up',
        x: 300,
        y: 350,
        params: {}
      }
    ],
    connections: [
      {
        id: 'conn_1',
        source: { blockId: 'price_1', portId: 'close' },
        target: { blockId: 'less_than_1', portId: 'left' },
        type: 'data'
      },
      {
        id: 'conn_2',
        source: { blockId: 'bb_1', portId: 'lower' },
        target: { blockId: 'less_than_1', portId: 'right' },
        type: 'data'
      },
      {
        id: 'conn_3',
        source: { blockId: 'price_1', portId: 'close' },
        target: { blockId: 'greater_than_1', portId: 'left' },
        type: 'data'
      },
      {
        id: 'conn_4',
        source: { blockId: 'bb_1', portId: 'upper' },
        target: { blockId: 'greater_than_1', portId: 'right' },
        type: 'data'
      },
      {
        id: 'conn_5',
        source: { blockId: 'less_than_1', portId: 'result' },
        target: { blockId: 'main_strategy', portId: 'entry_long' },
        type: 'condition'
      },
      {
        id: 'conn_6',
        source: { blockId: 'greater_than_1', portId: 'result' },
        target: { blockId: 'main_strategy', portId: 'exit_long' },
        type: 'condition'
      }
    ]
  },
  rsi_long_short: {
    blocks: [
      {
        id: 'rsi_1',
        type: 'rsi',
        category: 'indicator',
        name: 'RSI',
        icon: 'graph-up',
        x: 150,
        y: 150,
        params: { period: 14, overbought: 70, oversold: 30 }
      },
      {
        id: 'const_30',
        type: 'constant',
        category: 'input',
        name: 'Constant',
        icon: 'hash',
        x: 150,
        y: 300,
        params: { value: 30 }
      },
      {
        id: 'const_70',
        type: 'constant',
        category: 'input',
        name: 'Constant',
        icon: 'hash',
        x: 150,
        y: 450,
        params: { value: 70 }
      },
      {
        id: 'less_than_oversold',
        type: 'less_than',
        category: 'condition',
        name: 'Less Than',
        icon: 'chevron-double-down',
        x: 400,
        y: 200,
        params: {}
      },
      {
        id: 'greater_than_overbought',
        type: 'greater_than',
        category: 'condition',
        name: 'Greater Than',
        icon: 'chevron-double-up',
        x: 400,
        y: 400,
        params: {}
      }
    ],
    connections: [
      // RSI -> Less Than (left) - для проверки RSI < 30
      {
        id: 'conn_1',
        source: { blockId: 'rsi_1', portId: 'value' },
        target: { blockId: 'less_than_oversold', portId: 'left' },
        type: 'data'
      },
      // Constant 30 -> Less Than (right) - порог oversold
      {
        id: 'conn_2',
        source: { blockId: 'const_30', portId: 'value' },
        target: { blockId: 'less_than_oversold', portId: 'right' },
        type: 'data'
      },
      // RSI -> Greater Than (left) - для проверки RSI > 70
      {
        id: 'conn_3',
        source: { blockId: 'rsi_1', portId: 'value' },
        target: { blockId: 'greater_than_overbought', portId: 'left' },
        type: 'data'
      },
      // Constant 70 -> Greater Than (right) - порог overbought
      {
        id: 'conn_4',
        source: { blockId: 'const_70', portId: 'value' },
        target: { blockId: 'greater_than_overbought', portId: 'right' },
        type: 'data'
      },
      // Less Than (oversold) -> Entry Long (RSI < 30 = вход в Long)
      {
        id: 'conn_5',
        source: { blockId: 'less_than_oversold', portId: 'result' },
        target: { blockId: 'main_strategy', portId: 'entry_long' },
        type: 'condition'
      },
      // Greater Than (overbought) -> Exit Long (RSI > 70 = выход из Long)
      {
        id: 'conn_6',
        source: { blockId: 'greater_than_overbought', portId: 'result' },
        target: { blockId: 'main_strategy', portId: 'exit_long' },
        type: 'condition'
      },
      // Greater Than (overbought) -> Entry Short (RSI > 70 = вход в Short)
      {
        id: 'conn_7',
        source: { blockId: 'greater_than_overbought', portId: 'result' },
        target: { blockId: 'main_strategy', portId: 'entry_short' },
        type: 'condition'
      },
      // Less Than (oversold) -> Exit Short (RSI < 30 = выход из Short)
      {
        id: 'conn_8',
        source: { blockId: 'less_than_oversold', portId: 'result' },
        target: { blockId: 'main_strategy', portId: 'exit_short' },
        type: 'condition'
      }
    ]
  }
};

function loadTemplateData(templateId) {
  console.log(`[Strategy Builder] Loading template: ${templateId}`);
  const data = templateData[templateId];
  if (!data) {
    console.error(`[Strategy Builder] Template data not found for: ${templateId}`);
    showNotification(`Шаблон "${templateId}" не найден`, 'error');
    return;
  }

  console.log('[Strategy Builder] Template data found:', data);
  console.log(`[Strategy Builder] Blocks: ${data.blocks.length}, Connections: ${data.connections.length}`);

  // Keep main strategy node, clear others
  const mainNode = strategyBlocks.find((b) => b.isMain);
  strategyBlocks = mainNode ? [mainNode] : [];

  // Position main strategy node on the right side
  if (mainNode) {
    mainNode.x = 600;
    mainNode.y = 250;
  }

  // Clear connections
  connections.length = 0;

  // Add template blocks
  data.blocks.forEach((block) => {
    const newBlock = { ...block };
    // Don't modify IDs - they are used in connections
    // Only ensure main_strategy is not duplicated
    if (newBlock.id === 'main_strategy' || newBlock.isMain) {
      console.log('[Strategy Builder] Skipping main_strategy block - already exists');
      return; // Skip main strategy node - it already exists
    }
    strategyBlocks.push(newBlock);
    console.log(`[Strategy Builder] Added block: ${newBlock.id} (${newBlock.type})`);
  });

  console.log(`[Strategy Builder] Added ${data.blocks.length} blocks`);

  // Add template connections
  data.connections.forEach((conn) => {
    // Map template block IDs to actual block IDs
    const sourceBlock = strategyBlocks.find((b) =>
      b.id.startsWith(conn.source.blockId) || b.id === conn.source.blockId
    );

    // Special handling for main_strategy node
    let targetBlock;
    if (conn.target.blockId === 'main_strategy') {
      targetBlock = strategyBlocks.find((b) => b.isMain);
    } else {
      targetBlock = strategyBlocks.find((b) =>
        b.id.startsWith(conn.target.blockId) || b.id === conn.target.blockId
      );
    }

    if (sourceBlock && targetBlock) {
      const newConn = {
        id: `conn_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        source: {
          blockId: sourceBlock.id,
          portId: conn.source.portId
        },
        target: {
          blockId: targetBlock.id,
          portId: conn.target.portId
        },
        type: conn.type
      };
      connections.push(newConn);
      console.log(`[Strategy Builder] Connection added: ${sourceBlock.id}.${conn.source.portId} -> ${targetBlock.id}.${conn.target.portId}`);
    } else {
      console.warn('[Strategy Builder] Connection skipped - blocks not found:', {
        source: conn.source.blockId,
        target: conn.target.blockId,
        sourceFound: !!sourceBlock,
        targetFound: !!targetBlock,
        allBlocks: strategyBlocks.map(b => ({ id: b.id, isMain: b.isMain }))
      });
    }
  });

  console.log(`[Strategy Builder] Added ${connections.length} connections`);

  // Re-render
  renderBlocks();
  renderConnections();
  selectedBlockId = null;
  renderBlockProperties();

  console.log(`[Strategy Builder] Template "${templateId}" loaded successfully`);
  showNotification(`Шаблон "${templateId}" загружен`, 'success');
}

// Toolbar functions
function undo() {
  console.log('Undo');
}

function redo() {
  console.log('Redo');
}

function deleteSelected() {
  if (selectedBlockId) {
    // Don't delete main strategy node
    const block = strategyBlocks.find((b) => b.id === selectedBlockId);
    if (block && block.isMain) {
      console.log('Cannot delete main Strategy node');
      return;
    }

    // Remove connections involving this block
    const connectionsToRemove = connections.filter(
      (c) =>
        c.source.blockId === selectedBlockId ||
        c.target.blockId === selectedBlockId
    );
    connectionsToRemove.forEach((c) => {
      const idx = connections.indexOf(c);
      if (idx !== -1) connections.splice(idx, 1);
    });

    strategyBlocks = strategyBlocks.filter((b) => b.id !== selectedBlockId);
    selectedBlockId = null;
    renderBlocks();
    renderBlockProperties();
  }
}

function duplicateSelected() {
  if (selectedBlockId) {
    const block = strategyBlocks.find((b) => b.id === selectedBlockId);
    // Don't duplicate main node
    if (block && !block.isMain) {
      const newBlock = {
        ...block,
        id: `block_${Date.now()}`,
        x: block.x + 30,
        y: block.y + 30,
        isMain: false,
        params: { ...block.params }
      };
      strategyBlocks.push(newBlock);
      renderBlocks();
      selectBlock(newBlock.id);
    }
  }
}

function alignBlocks(direction) {
  console.log(`Align ${direction}`);
}

function autoLayout() {
  console.log('Auto layout');
}

function fitToScreen() {
  resetZoom();
}

function zoomIn() {
  zoom = Math.min(zoom + 0.1, 2);
  updateZoom();
}

function zoomOut() {
  zoom = Math.max(zoom - 0.1, 0.5);
  updateZoom();
}

function resetZoom() {
  zoom = 1;
  updateZoom();
}

function updateZoom() {
  document.getElementById('zoomLevel').textContent =
    `${Math.round(zoom * 100)}%`;
  document.getElementById('blocksContainer').style.transform = `scale(${zoom})`;
  document.getElementById('blocksContainer').style.transformOrigin = '0 0';
}

// Strategy actions
async function validateStrategy() {
  try {
    console.log('[Strategy Builder] validateStrategy called');
    console.log('[Strategy Builder] Current blocks:', strategyBlocks.length);
    console.log('[Strategy Builder] Current connections:', connections.length);

    showNotification('Валидация стратегии...', 'info');

    const result = {
      valid: true,
      errors: [],
      warnings: []
    };

    // Check for blocks
    if (strategyBlocks.length === 0) {
      result.valid = false;
      result.errors.push('Strategy has no blocks');
    }

    // Check for main strategy node
    const mainNode = strategyBlocks.find((b) => b.isMain);
    if (!mainNode) {
      result.valid = false;
      result.errors.push('Main strategy node is missing');
    } else {
      // Check for connections to main strategy node
      const hasConnections = connections.some((c) =>
        c.target.blockId === mainNode.id || c.source.blockId === mainNode.id
      );
      if (!hasConnections) {
        result.warnings.push('Strategy node has no connections');
      }

      // Check for entry signals (connected to main strategy)
      const entryConnections = connections.filter((c) => c.target.blockId === mainNode.id);
      if (entryConnections.length === 0) {
        result.warnings.push('No signals connected to strategy node');
      } else {
        // Check if at least one connection comes from a condition block
        const hasConditionSignals = entryConnections.some((c) => {
          const sourceBlock = strategyBlocks.find((b) => b.id === c.source.blockId);
          return sourceBlock && (
            sourceBlock.type === 'less_than' ||
            sourceBlock.type === 'greater_than' ||
            sourceBlock.type === 'crossover' ||
            sourceBlock.type === 'and' ||
            sourceBlock.type === 'or'
          );
        });
        if (!hasConditionSignals) {
          result.warnings.push('No condition blocks connected to strategy node');
        }
      }
    }

    // Check for disconnected blocks (blocks without connections)
    const connectedBlockIds = new Set();
    connections.forEach((c) => {
      connectedBlockIds.add(c.source.blockId);
      connectedBlockIds.add(c.target.blockId);
    });
    const disconnectedBlocks = strategyBlocks.filter((b) => !b.isMain && !connectedBlockIds.has(b.id));
    if (disconnectedBlocks.length > 0) {
      result.warnings.push(`${disconnectedBlocks.length} block(s) are not connected`);
    }

    // NEW: Validate block parameters
    let blocksWithInvalidParams = 0;
    strategyBlocks.forEach((block) => {
      if (block.isMain) return; // Skip main strategy node

      const paramValidation = validateBlockParams(block);
      updateBlockValidationState(block.id, paramValidation);

      if (!paramValidation.valid) {
        blocksWithInvalidParams++;
        // Add first error as detailed message
        if (paramValidation.errors.length > 0) {
          result.errors.push(`Block "${block.name}": ${paramValidation.errors[0]}`);
        }
      }
    });

    if (blocksWithInvalidParams > 0) {
      result.valid = false;
      if (blocksWithInvalidParams > 1) {
        result.warnings.push(`${blocksWithInvalidParams} blocks have invalid parameters (hover for details)`);
      }
    }

    console.log('[Strategy Builder] Validation result:', result);
    updateValidationPanel(result);

  } catch (error) {
    console.error('[Strategy Builder] Validation error:', error);
    showNotification(`Ошибка валидации: ${error.message}`, 'error');
    updateValidationPanel({
      valid: false,
      errors: [`Validation failed: ${error.message}`],
      warnings: []
    });
  }
}

function updateValidationPanel(result) {
  console.log('[Strategy Builder] updateValidationPanel called');
  const status = document.getElementById('validationStatus');
  const list = document.getElementById('validationList');

  if (!status || !list) {
    console.warn('[Strategy Builder] Validation panel elements not found');
    // Fallback: show in console and toast notification
    const messages = [...result.errors, ...result.warnings];
    if (messages.length > 0) {
      showNotification(`Валидация:\n${messages.join('\n')}`, 'warning');
    } else {
      showNotification('Стратегия валидна!', 'success');
    }
    return;
  }

  // Note: Sidebar-right opening is handled separately by the Validate button
  // Validation panel visibility is controlled by CSS classes, not inline styles

  // Update status
  if (result.valid && result.errors.length === 0) {
    status.className = 'validation-status valid';
    status.innerHTML = '<i class="bi bi-check-circle-fill"></i> Valid';
    status.style.color = '#28a745';
  } else {
    status.className = 'validation-status invalid';
    status.innerHTML = '<i class="bi bi-x-circle-fill"></i> Invalid';
    status.style.color = '#dc3545';
  }

  // Build messages HTML
  let html = '';
  result.errors.forEach((err) => {
    html += `<div class="validation-item error"><i class="bi bi-x-circle"></i><span>${err}</span></div>`;
  });
  result.warnings.forEach((warn) => {
    html += `<div class="validation-item warning"><i class="bi bi-exclamation-triangle"></i><span>${warn}</span></div>`;
  });

  if (html === '') {
    html =
      '<div class="validation-item info"><i class="bi bi-info-circle"></i><span>Strategy is ready for backtesting</span></div>';
  }

  list.innerHTML = html;
  list.style.display = 'block';
  list.style.visibility = 'visible';

  console.log('[Strategy Builder] Validation panel updated', {
    valid: result.valid,
    errors: result.errors.length,
    warnings: result.warnings.length,
    statusVisible: status.offsetParent !== null,
    listVisible: list.offsetParent !== null
  });

  // Also show notification
  if (result.errors.length > 0) {
    showNotification(`Валидация не пройдена: ${result.errors[0]}`, 'error');
  } else if (result.warnings.length > 0) {
    showNotification(`Предупреждения: ${result.warnings[0]}`, 'warning');
  } else {
    showNotification('Стратегия валидна!', 'success');
  }
}

async function generateCode() {
  console.log('[Strategy Builder] generateCode called');
  const strategyId = getStrategyIdFromURL();
  console.log('[Strategy Builder] Strategy ID from URL:', strategyId);

  if (!strategyId) {
    showNotification('Сохраните стратегию перед генерацией кода', 'warning');
    if (confirm('Strategy not saved. Save now?')) {
      await saveStrategy();
      // Re-check after save
      const newId = getStrategyIdFromURL();
      if (!newId) {
        showNotification('Не удалось получить ID стратегии после сохранения', 'error');
        return;
      }
    } else {
      return;
    }
  }

  const finalId = getStrategyIdFromURL();
  if (!finalId) {
    showNotification('ID стратегии отсутствует. Невозможно сгенерировать код.', 'error');
    return;
  }

  try {
    showNotification('Генерация Python кода...', 'info');

    const url = `/api/v1/strategy-builder/strategies/${finalId}/generate-code`;
    console.log(`[Strategy Builder] Generate code request: POST ${url}`);

    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        template: 'backtest',
        include_comments: true,
        include_logging: true,
        async_mode: false
      })
    });

    console.log(`[Strategy Builder] Generate code response: status=${response.status}, ok=${response.ok}`);

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`[Strategy Builder] Generate code error: status=${response.status}, body=${errorText}`);
      let errorDetail = 'Unknown error';
      try {
        const errorJson = JSON.parse(errorText);
        errorDetail = errorJson.detail || errorJson.message || errorText;
      } catch {
        errorDetail = errorText || `HTTP ${response.status}`;
      }
      showNotification(`Генерация кода не удалась: ${errorDetail}`, 'error');
      return;
    }

    const data = await response.json();
    console.log('[Strategy Builder] Generate code success:', { success: data.success, code_length: data.code?.length || 0 });

    if (!data.success) {
      const errors = data.errors || data.detail || 'Unknown error';
      showNotification(`Генерация кода не удалась: ${JSON.stringify(errors)}`, 'error');
      return;
    }

    const code = data.code || '';
    if (!code) {
      showNotification('Генерация кода вернула пустой результат', 'warning');
      return;
    }

    // Open code in a new window for now
    const win = window.open('', '_blank');
    if (win) {
      const escaped = code
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
      win.document.write(
        `<html><head><title>Сгенерированный код стратегии</title></head><body><pre style="white-space:pre; font-family:monospace; font-size:12px; padding:16px;">${escaped}</pre></body></html>`
      );
      win.document.close();
    } else {
      // Fallback: log to console
      console.log('Generated code:', code);
      showNotification('Всплывающее окно заблокировано. Код в консоли.', 'warning');
    }

    showNotification('Код успешно сгенерирован', 'success');
  } catch (err) {
    showNotification(`Ошибка генерации кода: ${err.message}`, 'error');
  }
}

// Helper function to get strategy ID from URL
function getStrategyIdFromURL() {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get('id');
}

// Helper function to update "Last saved" timestamp
function updateLastSaved(timestamp = null) {
  const lastSavedEl = document.querySelector('.text-secondary.text-sm');
  if (lastSavedEl) {
    if (timestamp) {
      const date = new Date(timestamp);
      lastSavedEl.innerHTML = `<i class="bi bi-clock"></i> Last saved: ${date.toLocaleString()}`;
    } else {
      lastSavedEl.innerHTML = `<i class="bi bi-clock"></i> Last saved: ${new Date().toLocaleString()}`;
    }
  }
}

/**
 * Dispatch event when strategy blocks change
 * This notifies optimization_panels.js to sync parameter ranges
 */
function dispatchBlocksChanged() {
  const event = new CustomEvent('strategyBlocksChanged', {
    detail: { blocks: strategyBlocks }
  });
  document.dispatchEvent(event);
  console.log('[Strategy Builder] Dispatched strategyBlocksChanged event with', strategyBlocks.length, 'blocks');
}

// Helper function to show notifications
function showNotification(message, type = 'info') {
  console.log(`[${type.toUpperCase()}] ${message}`);

  // Try to find or create notification container
  let notificationContainer = document.getElementById('notificationContainer');
  if (!notificationContainer) {
    notificationContainer = document.createElement('div');
    notificationContainer.id = 'notificationContainer';
    document.body.appendChild(notificationContainer);
  }
  // Always update styles to ensure bottom position
  notificationContainer.style.cssText = `
    position: fixed;
    bottom: 20px;
    right: 20px;
    z-index: 10000;
    display: flex;
    flex-direction: column-reverse;
    gap: 10px;
  `;

  // Create notification element
  const notification = document.createElement('div');
  const colors = {
    success: { bg: '#28a745', text: '#fff' },
    error: { bg: '#dc3545', text: '#fff' },
    warning: { bg: '#ffc107', text: '#000' },
    info: { bg: '#17a2b8', text: '#fff' }
  };

  const color = colors[type] || colors.info;
  notification.style.cssText = `
    background: ${color.bg};
    color: ${color.text};
    padding: 12px 20px;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    min-width: 250px;
    max-width: 400px;
    animation: slideInBottom 0.3s ease;
  `;
  notification.textContent = message;

  // Add animation
  const style = document.createElement('style');
  style.textContent = `
    @keyframes slideInBottom {
      from { transform: translateY(100px); opacity: 0; }
      to { transform: translateY(0); opacity: 1; }
    }
  `;
  if (!document.getElementById('notificationStyles')) {
    style.id = 'notificationStyles';
    document.head.appendChild(style);
  }

  notificationContainer.appendChild(notification);

  // Auto-remove after delay
  const delay = type === 'error' ? 5000 : type === 'warning' ? 4000 : 3000;
  setTimeout(() => {
    notification.style.animation = 'slideInBottom 0.3s ease reverse';
    setTimeout(() => {
      if (notification.parentNode) {
        notification.parentNode.removeChild(notification);
      }
    }, 300);
  }, delay);

  // Fallback to console if critical
  if (type === 'error') {
    console.error(message);
  }
}

async function saveStrategy() {
  console.log('[Strategy Builder] saveStrategy called');
  const strategy = buildStrategyPayload();
  console.log('[Strategy Builder] Strategy payload:', strategy);

  // Валидация
  if (!strategy.name || strategy.name.trim() === '') {
    showNotification('Название стратегии обязательно', 'error');
    return;
  }

  if (!strategy.blocks || strategy.blocks.length === 0) {
    showNotification('Стратегия должна иметь хотя бы один блок', 'warning');
  }

  // WebSocket server-side validation before save
  if (wsValidation && wsValidation.isConnected()) {
    console.log('[Strategy Builder] Running server-side validation before save...');
    const wsValidationResult = await new Promise((resolve) => {
      wsValidation.validateStrategy(strategy.blocks, strategy.connections, (result) => {
        resolve(result);
      });
      // Timeout fallback
      setTimeout(() => resolve({ valid: true, fallback: true }), 3000);
    });

    if (!wsValidationResult.fallback && !wsValidationResult.valid) {
      const errorCount = wsValidationResult.messages?.filter(m => m.severity === 'error').length || 0;
      const warningCount = wsValidationResult.messages?.filter(m => m.severity === 'warning').length || 0;

      console.warn('[Strategy Builder] Server validation failed:', wsValidationResult.messages);

      if (errorCount > 0) {
        const errorMsgs = wsValidationResult.messages
          .filter(m => m.severity === 'error')
          .map(m => m.message)
          .slice(0, 3)
          .join('\n• ');
        showNotification(`Валидация не пройдена (${errorCount} ошибок):\n• ${errorMsgs}`, 'error');
        return;
      } else if (warningCount > 0) {
        // Warnings - ask user to continue
        const warningMsgs = wsValidationResult.messages
          .filter(m => m.severity === 'warning')
          .map(m => m.message)
          .slice(0, 3)
          .join('\n• ');
        if (!confirm(`Обнаружены предупреждения (${warningCount}):\n• ${warningMsgs}\n\nСохранить всё равно?`)) {
          return;
        }
      }
    }
    console.log('[Strategy Builder] Server validation passed');
  }

  try {
    const strategyId = getStrategyIdFromURL();

    // Если стратегия есть в URL, но она не Strategy Builder стратегия, создаем новую
    // Для этого сначала проверяем, существует ли она как Strategy Builder стратегия
    let finalStrategyId = strategyId;
    if (strategyId) {
      try {
        const checkResponse = await fetch(`/api/v1/strategy-builder/strategies/${strategyId}`);
        if (!checkResponse.ok) {
          console.warn(`[Strategy Builder] Strategy ${strategyId} not found as Strategy Builder strategy, will create new`);
          finalStrategyId = null; // Создадим новую стратегию
        }
      } catch (checkErr) {
        console.warn(`[Strategy Builder] Error checking strategy: ${checkErr}, will create new`);
        finalStrategyId = null;
      }
    }

    const method = finalStrategyId ? 'PUT' : 'POST';
    const url = finalStrategyId
      ? `/api/v1/strategy-builder/strategies/${finalStrategyId}`
      : '/api/v1/strategy-builder/strategies';

    console.log(`[Strategy Builder] Saving strategy: method=${method}, url=${url}, id=${finalStrategyId || 'new'}`);
    console.log(`[Strategy Builder] Payload blocks: ${strategy.blocks.length}, connections: ${strategy.connections.length}`);

    const response = await fetch(url, {
      method: method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(strategy)
    });

    console.log(`[Strategy Builder] Save response: status=${response.status}, ok=${response.ok}`);

    if (response.ok) {
      const data = await response.json();
      console.log('[Strategy Builder] Save success:', data);
      updateLastSaved(data.updated_at || new Date().toISOString());
      showNotification('Стратегия успешно сохранена!', 'success');

      // Обновить URL если новая стратегия
      if (!finalStrategyId && data.id) {
        console.log(`[Strategy Builder] Updating URL with new strategy ID: ${data.id}`);
        window.history.pushState({}, '', `?id=${data.id}`);
      }
    } else {
      const errorText = await response.text();
      console.error(`[Strategy Builder] Save error: status=${response.status}, body=${errorText}`);
      let errorDetail = 'Unknown error';
      try {
        const errorJson = JSON.parse(errorText);
        errorDetail = errorJson.detail || errorJson.message || errorText;
      } catch {
        errorDetail = errorText || `HTTP ${response.status}`;
      }
      showNotification(`Ошибка сохранения стратегии: ${errorDetail}`, 'error');
    }
  } catch (err) {
    console.error('[Strategy Builder] Save exception:', err);
    showNotification(`Не удалось сохранить стратегию: ${err.message}`, 'error');
  }
}

function buildStrategyPayload() {
  console.log('[Strategy Builder] buildStrategyPayload called');

  const nameEl = document.getElementById('strategyName');
  const timeframeEl = document.getElementById('strategyTimeframe');
  const symbolEl = document.getElementById('strategySymbol');
  const marketTypeEl = document.getElementById('builderMarketType');
  const directionEl = document.getElementById('builderDirection');
  const initialCapitalEl = document.getElementById('initialCapital');

  console.log('[Strategy Builder] Form elements:', {
    name: nameEl?.value,
    timeframe: timeframeEl?.value,
    symbol: symbolEl?.value,
    market_type: marketTypeEl?.value,
    direction: directionEl?.value,
    initial_capital: initialCapitalEl?.value
  });

  const payload = {
    name: nameEl?.value || 'New Strategy',
    description: '', // TODO: добавить поле описания в UI
    timeframe: timeframeEl?.value || '1h',
    symbol: symbolEl?.value || 'BTCUSDT',
    market_type: marketTypeEl?.value || 'linear',
    direction: directionEl?.value || 'both',
    initial_capital: parseFloat(initialCapitalEl?.value || 10000),
    blocks: strategyBlocks.filter((b) => !b.isMain),
    connections: connections
  };

  console.log('[Strategy Builder] Payload built:', {
    ...payload,
    blocks_count: payload.blocks.length,
    connections_count: payload.connections.length
  });

  return payload;
}

async function autoSaveStrategy() {
  try {
    const strategyId = getStrategyIdFromURL() || 'draft';
    const payload = buildStrategyPayload();

    // Не автосохраняем пустые стратегии
    if (!payload.blocks.length && !connections.length) {
      return;
    }

    const serialized = JSON.stringify(payload);
    if (serialized === lastAutoSavePayload) {
      return; // нет изменений
    }
    lastAutoSavePayload = serialized;

    // 1) LocalStorage draft
    try {
      const key = `strategy_builder_draft_${strategyId}`;
      window.localStorage.setItem(key, serialized);
    } catch (e) {
      console.warn('LocalStorage autosave failed:', e);
    }

    // 2) Remote autosave only если есть реальный ID (стратегия уже сохранена)
    if (strategyId !== 'draft') {
      const url = `/api/v1/strategy-builder/strategies/${strategyId}`;
      const response = await fetch(url, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: serialized
      });

      if (response.ok) {
        const data = await response.json();
        updateLastSaved(data.updated_at || new Date().toISOString());
      } else {
        // Тихая ошибка, без алерта — не мешать пользователю
        console.warn('Autosave PUT failed', await response.text());
      }
    }
  } catch (err) {
    console.warn('Autosave failed:', err);
  }
}

async function loadStrategy(strategyId) {
  try {
    const url = `/api/v1/strategy-builder/strategies/${strategyId}`;
    console.log(`[Strategy Builder] Loading strategy: GET ${url}`);

    const response = await fetch(url);
    console.log(`[Strategy Builder] Load response: status=${response.status}, ok=${response.ok}`);

    if (!response.ok) {
      if (response.status === 404) {
        const errorText = await response.text();
        console.error(`[Strategy Builder] Strategy not found: ${errorText}`);
        showNotification('Стратегия не найдена. Возможно, это не Strategy Builder стратегия.', 'error');
        return;
      }
      const errorText = await response.text();
      console.error(`[Strategy Builder] Load error: status=${response.status}, body=${errorText}`);
      throw new Error(`HTTP ${response.status}: ${errorText}`);
    }

    const strategy = await response.json();
    console.log('[Strategy Builder] Strategy loaded:', {
      id: strategy.id,
      name: strategy.name,
      is_builder_strategy: strategy.is_builder_strategy,
      blocks_count: strategy.blocks?.length || 0,
      connections_count: strategy.connections?.length || 0
    });

    // Обновить UI поля
    document.getElementById('strategyName').value = strategy.name || 'New Strategy';
    if (document.getElementById('strategyTimeframe')) {
      document.getElementById('strategyTimeframe').value = strategy.timeframe || '1h';
    }
    if (document.getElementById('strategySymbol')) {
      document.getElementById('strategySymbol').value = strategy.symbol || 'BTCUSDT';
    }
    if (document.getElementById('builderMarketType')) {
      document.getElementById('builderMarketType').value = strategy.market_type || 'linear';
    }
    if (document.getElementById('builderDirection')) {
      document.getElementById('builderDirection').value = strategy.direction || 'both';
    }
    if (document.getElementById('initialCapital')) {
      document.getElementById('initialCapital').value = strategy.initial_capital || 10000;
    }

    // Восстановить блоки и соединения
    // Сохранить main_strategy node если он есть
    const mainNode = strategyBlocks.find((b) => b.isMain);
    strategyBlocks = mainNode ? [mainNode] : [];

    // Добавить загруженные блоки
    if (strategy.blocks && Array.isArray(strategy.blocks)) {
      strategyBlocks.push(...strategy.blocks);
    }

    // Восстановить соединения
    connections.length = 0;
    if (strategy.connections && Array.isArray(strategy.connections)) {
      connections.push(...strategy.connections);
    }

    // Перерисовать canvas
    renderBlocks();
    renderConnections();

    updateLastSaved(strategy.updated_at);
    showNotification('Стратегия успешно загружена!', 'success');
  } catch (err) {
    showNotification(`Ошибка загрузки стратегии: ${err.message}`, 'error');
  }
}

// =============================================
// BACKEND INTEGRATION: Map Strategy Blocks to API
// =============================================

/**
 * Convert strategy blocks to backend API format
 * Maps visual blocks to strategy_type and strategy_params
 */
function mapBlocksToBackendParams() {
  const result = {
    strategy_type: 'custom',
    strategy_params: {},
    filters: [],
    exits: [],
    position_sizing: null,
    risk_controls: []
  };

  // Find entry indicators (RSI, MACD, etc.)
  const indicatorBlocks = strategyBlocks.filter(b =>
    blockLibrary.indicators.some(ind => ind.id === b.type)
  );

  // Find filters
  const filterBlocks = strategyBlocks.filter(b =>
    blockLibrary.filters.some(f => f.id === b.type)
  );

  // Find exit conditions
  const exitBlocks = strategyBlocks.filter(b =>
    blockLibrary.exits && blockLibrary.exits.some(e => e.id === b.type)
  );

  // Find position sizing
  const sizingBlocks = strategyBlocks.filter(b =>
    blockLibrary.position_sizing && blockLibrary.position_sizing.some(s => s.id === b.type)
  );

  // Find risk controls
  const riskBlocks = strategyBlocks.filter(b =>
    blockLibrary.risk_controls && blockLibrary.risk_controls.some(r => r.id === b.type)
  );

  // Map primary indicator to strategy_type
  if (indicatorBlocks.length > 0) {
    const primaryIndicator = indicatorBlocks[0];
    result.strategy_type = mapIndicatorToStrategyType(primaryIndicator.type);
    result.strategy_params = mapIndicatorParams(primaryIndicator);
  }

  // Map filters
  filterBlocks.forEach(block => {
    result.filters.push({
      type: block.type,
      params: block.params || getDefaultParams(block.type),
      enabled: block.params?.enabled !== false
    });
  });

  // Map exits
  exitBlocks.forEach(block => {
    result.exits.push({
      type: block.type,
      params: block.params || getDefaultParams(block.type)
    });
  });

  // Map position sizing (use first one)
  if (sizingBlocks.length > 0) {
    result.position_sizing = {
      type: sizingBlocks[0].type,
      params: sizingBlocks[0].params || getDefaultParams(sizingBlocks[0].type)
    };
  }

  // Map risk controls
  riskBlocks.forEach(block => {
    result.risk_controls.push({
      type: block.type,
      params: block.params || getDefaultParams(block.type)
    });
  });

  return result;
}

/**
 * Map indicator block type to backend strategy_type
 */
function mapIndicatorToStrategyType(blockType) {
  const mapping = {
    'rsi': 'rsi',
    'macd': 'macd',
    'ema': 'ema_cross',
    'sma': 'sma_cross',
    'bollinger': 'bollinger_bands',
    'supertrend': 'supertrend',
    'stochastic': 'stochastic',
    'cci': 'cci',
    'atr': 'atr',
    'adx': 'adx',
    'ichimoku': 'ichimoku',
    'vwap': 'vwap',
    'obv': 'obv',
    'mfi': 'mfi',
    'williams_r': 'williams_r',
    'roc': 'roc',
    'momentum': 'momentum',
    'trix': 'trix',
    'keltner': 'keltner',
    'donchian': 'donchian',
    'parabolic_sar': 'parabolic_sar',
    'pivot_points': 'pivot_points',
    'fibonacci': 'fibonacci',
    'heikin_ashi': 'heikin_ashi',
    'renko': 'renko',
    'volume_profile': 'volume_profile',
    'vwma': 'vwma',
    'tema': 'tema',
    'dema': 'dema',
    'wma': 'wma',
    'hull_ma': 'hull_ma',
    'zlema': 'zlema',
    'kama': 'kama',
    'linear_regression': 'linear_regression',
    'mtf': 'mtf'
  };
  return mapping[blockType] || 'custom';
}

/**
 * Map indicator block params to backend strategy_params format
 */
function mapIndicatorParams(block) {
  const params = block.params || getDefaultParams(block.type);

  // Common mappings
  const mapped = {};

  switch (block.type) {
    case 'rsi':
      mapped.period = params.period || 14;
      mapped.overbought = params.overbought || 70;
      mapped.oversold = params.oversold || 30;
      mapped.source = params.source || 'close';
      break;

    case 'macd':
      mapped.fast_period = params.fast_period || 12;
      mapped.slow_period = params.slow_period || 26;
      mapped.signal_period = params.signal_period || 9;
      mapped.source = params.source || 'close';
      break;

    case 'ema':
    case 'sma':
      mapped.fast_period = params.fast_period || 9;
      mapped.slow_period = params.slow_period || 21;
      mapped.source = params.source || 'close';
      break;

    case 'bollinger':
      mapped.period = params.period || 20;
      mapped.std_dev = params.std_dev || 2.0;
      mapped.source = params.source || 'close';
      break;

    case 'supertrend':
      mapped.period = params.period || 10;
      mapped.multiplier = params.multiplier || 3.0;
      break;

    case 'stochastic':
      mapped.k_period = params.k_period || 14;
      mapped.d_period = params.d_period || 3;
      mapped.smooth_k = params.smooth_k || 3;
      mapped.overbought = params.overbought || 80;
      mapped.oversold = params.oversold || 20;
      break;

    default:
      // Pass through all params for unknown types
      Object.assign(mapped, params);
  }

  return mapped;
}

/**
 * Build full backtest request from UI state
 */
function buildBacktestRequest() {
  const strategyMapping = mapBlocksToBackendParams();

  // Get UI values for backtest params
  const intervalRaw = document.getElementById('backtestInterval')?.value || '15';
  const interval = convertIntervalToAPIFormat(intervalRaw);

  const backtestConfig = {
    // Basic params
    symbol: document.getElementById('backtestSymbol')?.value || 'BTCUSDT',
    interval: interval,
    start_date: document.getElementById('backtestStartDate')?.value || '2024-01-01',
    end_date: document.getElementById('backtestEndDate')?.value || '2024-12-31',

    // Capital & Risk
    initial_capital: parseFloat(document.getElementById('backtestCapital')?.value) || 10000,
    leverage: parseInt(document.getElementById('backtestLeverage')?.value) || 10,
    direction: document.getElementById('backtestDirection')?.value || 'both',

    // Commission for TradingView parity
    commission: 0.0007,  // 0.07%
    slippage: 0.0005,    // 0.05%

    // Strategy from blocks
    strategy_type: strategyMapping.strategy_type,
    strategy_params: strategyMapping.strategy_params,

    // Advanced: filters, exits, sizing
    filters: strategyMapping.filters,
    exit_rules: strategyMapping.exits,
    position_sizing: strategyMapping.position_sizing,
    risk_controls: strategyMapping.risk_controls
  };

  return backtestConfig;
}

/**
 * Convert interval value to API format
 */
function convertIntervalToAPIFormat(value) {
  const mapping = {
    '1': '1m',
    '5': '5m',
    '15': '15m',
    '30': '30m',
    '60': '1h',
    '240': '4h',
    'D': '1D',
    'W': '1W',
    // Already formatted
    '1m': '1m',
    '5m': '5m',
    '15m': '15m',
    '30m': '30m',
    '1h': '1h',
    '4h': '4h',
    '1D': '1D',
    '1W': '1W'
  };
  return mapping[value] || '15m';
}

async function runBacktest() {
  console.log('[Strategy Builder] runBacktest called');
  const strategyId = getStrategyIdFromURL();
  console.log('[Strategy Builder] Strategy ID from URL:', strategyId);

  if (!strategyId) {
    showNotification('Сохраните стратегию перед запуском бэктеста', 'warning');
    // Предложить сохранить
    if (confirm('Strategy not saved. Save now?')) {
      await saveStrategy();
      // После сохранения попробовать снова
      const newId = getStrategyIdFromURL();
      if (newId) {
        console.log('[Strategy Builder] Retrying backtest with new ID:', newId);
        await runBacktest();
      } else {
        showNotification('Не удалось получить ID стратегии после сохранения', 'error');
      }
    }
    return;
  }

  if (strategyBlocks.length === 0) {
    showNotification('Добавьте блоки в стратегию перед бэктестом', 'warning');
    return;
  }

  // Собрать параметры бэктеста используя маппинг блоков
  const backtestParams = buildBacktestRequest();

  // Override with strategy ID
  backtestParams.strategy_id = strategyId;

  console.log('[Strategy Builder] Built backtest params from blocks:', backtestParams);

  try {
    showNotification('Запуск бэктеста...', 'info');

    const url = `/api/v1/strategy-builder/strategies/${strategyId}/backtest`;
    console.log(`[Strategy Builder] Backtest request: POST ${url}`);
    console.log('[Strategy Builder] Backtest params:', backtestParams);

    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(backtestParams)
    });

    console.log(`[Strategy Builder] Backtest response: status=${response.status}, ok=${response.ok}`);

    if (response.ok) {
      const data = await response.json();
      console.log('[Strategy Builder] Backtest success:', data);

      // Check if results are returned directly (for quick preview)
      if (data.metrics || data.trades || data.equity_curve) {
        // Show results in modal for quick preview
        showNotification('Бэктест завершён!', 'success');
        displayBacktestResults(data);
      } else if (data.backtest_id) {
        // Offer choice: view in modal or full page
        showNotification('Бэктест завершён!', 'success');
        // Try to fetch full results for modal display
        try {
          const resultsResponse = await fetch(`/api/v1/backtests/${data.backtest_id}`);
          if (resultsResponse.ok) {
            const resultsData = await resultsResponse.json();
            resultsData.backtest_id = data.backtest_id;
            displayBacktestResults(resultsData);
          } else {
            // Fallback to redirect
            window.location.href = `/frontend/backtest-results.html?backtest_id=${data.backtest_id}`;
          }
        } catch {
          // Fallback to redirect
          window.location.href = `/frontend/backtest-results.html?backtest_id=${data.backtest_id}`;
        }
      } else if (data.redirect_url) {
        console.log(`[Strategy Builder] Redirecting to: ${data.redirect_url}`);
        window.location.href = data.redirect_url;
      } else {
        showNotification('Бэктест запущен. Проверьте результаты позже.', 'info');
      }
    } else {
      const errorText = await response.text();
      console.error(`[Strategy Builder] Backtest error: status=${response.status}, body=${errorText}`);
      let errorDetail = 'Unknown error';
      try {
        const errorJson = JSON.parse(errorText);
        errorDetail = errorJson.detail || errorJson.message || errorText;
      } catch {
        errorDetail = errorText || `HTTP ${response.status}`;
      }
      showNotification(`Ошибка бэктеста: ${errorDetail}`, 'error');
    }
  } catch (err) {
    console.error('[Strategy Builder] Backtest exception:', err);
    showNotification(`Не удалось запустить бэктест: ${err.message}`, 'error');
  }
}

// ============================================
// BACKTEST RESULTS DISPLAY
// ============================================

// Store current backtest results for export
let currentBacktestResults = null;

/**
 * Display backtest results in a beautiful modal
 * @param {Object} results - Backtest results from API
 */
function displayBacktestResults(results) {
  console.log('[Strategy Builder] Displaying backtest results:', results);
  currentBacktestResults = results;

  const modal = document.getElementById('backtestResultsModal');
  if (!modal) {
    console.error('[Strategy Builder] Results modal not found');
    return;
  }

  // Render summary cards
  renderResultsSummaryCards(results);

  // Render overview metrics
  renderOverviewMetrics(results);

  // Render trades table
  renderTradesTable(results.trades || []);

  // Render all metrics
  renderAllMetrics(results);

  // Show modal
  modal.classList.add('active');
  document.body.style.overflow = 'hidden';

  // Initialize equity chart if data available
  if (results.equity_curve && results.equity_curve.length > 0) {
    setTimeout(() => renderEquityChart(results.equity_curve), 100);
  }
}

/**
 * Render summary cards at top of results
 */
function renderResultsSummaryCards(results) {
  const container = document.getElementById('resultsSummaryCards');
  if (!container) return;

  const metrics = results.metrics || results;
  const totalReturn = metrics.total_return_pct || metrics.net_profit_pct || 0;
  const winRate = metrics.win_rate || 0;
  const maxDrawdown = metrics.max_drawdown_pct || 0;
  const totalTrades = metrics.total_trades || 0;
  const profitFactor = metrics.profit_factor || 0;
  const sharpeRatio = metrics.sharpe_ratio || 0;

  const cards = [
    {
      icon: 'bi-cash-stack',
      value: `${totalReturn >= 0 ? '+' : ''}${totalReturn.toFixed(2)}%`,
      label: 'Total Return',
      class: totalReturn >= 0 ? 'positive' : 'negative'
    },
    {
      icon: 'bi-trophy',
      value: `${winRate.toFixed(1)}%`,
      label: 'Win Rate',
      class: winRate >= 50 ? 'positive' : 'warning'
    },
    {
      icon: 'bi-graph-down-arrow',
      value: `${maxDrawdown.toFixed(2)}%`,
      label: 'Max Drawdown',
      class: maxDrawdown > 20 ? 'negative' : 'warning'
    },
    {
      icon: 'bi-arrow-left-right',
      value: totalTrades.toString(),
      label: 'Total Trades',
      class: 'neutral'
    },
    {
      icon: 'bi-bar-chart-line',
      value: profitFactor.toFixed(2),
      label: 'Profit Factor',
      class: profitFactor >= 1.5 ? 'positive' : profitFactor >= 1 ? 'warning' : 'negative'
    },
    {
      icon: 'bi-lightning',
      value: sharpeRatio.toFixed(2),
      label: 'Sharpe Ratio',
      class: sharpeRatio >= 1 ? 'positive' : sharpeRatio >= 0 ? 'warning' : 'negative'
    }
  ];

  container.innerHTML = cards.map(card => `
    <div class="summary-card ${card.class}">
      <i class="summary-card-icon bi ${card.icon}"></i>
      <span class="summary-card-value">${card.value}</span>
      <span class="summary-card-label">${card.label}</span>
    </div>
  `).join('');
}

/**
 * Render overview metrics grid
 */
function renderOverviewMetrics(results) {
  const container = document.getElementById('metricsOverview');
  if (!container) return;

  const metrics = results.metrics || results;

  const overviewCards = [
    { title: 'Net Profit', value: formatCurrency(metrics.net_profit || 0), icon: 'bi-currency-dollar', positive: (metrics.net_profit || 0) >= 0 },
    { title: 'Gross Profit', value: formatCurrency(metrics.gross_profit || 0), icon: 'bi-plus-circle', positive: true },
    { title: 'Gross Loss', value: formatCurrency(metrics.gross_loss || 0), icon: 'bi-dash-circle', positive: false },
    { title: 'Winning Trades', value: `${metrics.winning_trades || 0} / ${metrics.total_trades || 0}`, icon: 'bi-check-circle', positive: true },
    { title: 'Losing Trades', value: `${metrics.losing_trades || 0} / ${metrics.total_trades || 0}`, icon: 'bi-x-circle', positive: false },
    { title: 'Avg Win', value: formatCurrency(metrics.avg_win || 0), icon: 'bi-arrow-up', positive: true },
    { title: 'Avg Loss', value: formatCurrency(metrics.avg_loss || 0), icon: 'bi-arrow-down', positive: false },
    { title: 'Largest Win', value: formatCurrency(metrics.largest_win || 0), icon: 'bi-star', positive: true },
    { title: 'Largest Loss', value: formatCurrency(metrics.largest_loss || 0), icon: 'bi-exclamation-triangle', positive: false },
    { title: 'Avg Trade Duration', value: formatDuration(metrics.avg_trade_duration || 0), icon: 'bi-clock', positive: null },
    { title: 'Max Consecutive Wins', value: metrics.max_consecutive_wins || 0, icon: 'bi-graph-up', positive: true },
    { title: 'Max Consecutive Losses', value: metrics.max_consecutive_losses || 0, icon: 'bi-graph-down', positive: false }
  ];

  container.innerHTML = overviewCards.map(card => `
    <div class="metric-card ${card.positive === true ? 'positive' : card.positive === false ? 'negative' : ''}">
      <div class="metric-card-header">
        <span class="metric-card-title">${card.title}</span>
        <i class="metric-card-icon bi ${card.icon}"></i>
      </div>
      <div class="metric-card-value">${card.value}</div>
    </div>
  `).join('');
}

/**
 * Render trades table
 */
function renderTradesTable(trades) {
  const tbody = document.getElementById('tradesTableBody');
  if (!tbody) return;

  if (!trades || trades.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="11" class="text-center py-3">No trades to display</td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = trades.map((trade, idx) => {
    const isLong = trade.side === 'long' || trade.direction === 'long';
    const pnl = trade.pnl || trade.profit || 0;
    const pnlPct = trade.pnl_pct || trade.profit_pct || 0;
    const mfe = trade.mfe || 0;
    const mae = trade.mae || 0;

    return `
      <tr>
        <td>${idx + 1}</td>
        <td>${formatDateTime(trade.entry_time || trade.open_time)}</td>
        <td>${formatDateTime(trade.exit_time || trade.close_time)}</td>
        <td class="${isLong ? 'trade-side-long' : 'trade-side-short'}">${isLong ? 'LONG' : 'SHORT'}</td>
        <td>${formatPrice(trade.entry_price || trade.open_price)}</td>
        <td>${formatPrice(trade.exit_price || trade.close_price)}</td>
        <td>${(trade.quantity || trade.qty || 0).toFixed(4)}</td>
        <td class="${pnl >= 0 ? 'trade-pnl-positive' : 'trade-pnl-negative'}">${formatCurrency(pnl)}</td>
        <td class="${pnlPct >= 0 ? 'trade-pnl-positive' : 'trade-pnl-negative'}">${pnlPct.toFixed(2)}%</td>
        <td>${mfe.toFixed(2)}%</td>
        <td>${mae.toFixed(2)}%</td>
      </tr>
    `;
  }).join('');
}

/**
 * Render all metrics organized by category
 */
function renderAllMetrics(results) {
  const container = document.getElementById('allMetricsGrid');
  if (!container) return;

  const metrics = results.metrics || results;

  const categories = [
    {
      title: 'Performance',
      icon: 'bi-speedometer2',
      items: [
        { label: 'Total Return', value: formatPercent(metrics.total_return_pct) },
        { label: 'Net Profit', value: formatCurrency(metrics.net_profit) },
        { label: 'Gross Profit', value: formatCurrency(metrics.gross_profit) },
        { label: 'Gross Loss', value: formatCurrency(metrics.gross_loss) },
        { label: 'Profit Factor', value: (metrics.profit_factor || 0).toFixed(2) }
      ]
    },
    {
      title: 'Risk Metrics',
      icon: 'bi-shield-exclamation',
      items: [
        { label: 'Max Drawdown', value: formatPercent(metrics.max_drawdown_pct) },
        { label: 'Max Drawdown $', value: formatCurrency(metrics.max_drawdown) },
        { label: 'Sharpe Ratio', value: (metrics.sharpe_ratio || 0).toFixed(2) },
        { label: 'Sortino Ratio', value: (metrics.sortino_ratio || 0).toFixed(2) },
        { label: 'Calmar Ratio', value: (metrics.calmar_ratio || 0).toFixed(2) }
      ]
    },
    {
      title: 'Trade Statistics',
      icon: 'bi-bar-chart',
      items: [
        { label: 'Total Trades', value: metrics.total_trades || 0 },
        { label: 'Winning Trades', value: metrics.winning_trades || 0 },
        { label: 'Losing Trades', value: metrics.losing_trades || 0 },
        { label: 'Win Rate', value: formatPercent(metrics.win_rate) },
        { label: 'Avg Win/Loss Ratio', value: (metrics.avg_win_loss_ratio || 0).toFixed(2) }
      ]
    },
    {
      title: 'Average Values',
      icon: 'bi-calculator',
      items: [
        { label: 'Avg Trade', value: formatCurrency(metrics.avg_trade) },
        { label: 'Avg Win', value: formatCurrency(metrics.avg_win) },
        { label: 'Avg Loss', value: formatCurrency(metrics.avg_loss) },
        { label: 'Largest Win', value: formatCurrency(metrics.largest_win) },
        { label: 'Largest Loss', value: formatCurrency(metrics.largest_loss) }
      ]
    },
    {
      title: 'Time Analysis',
      icon: 'bi-clock-history',
      items: [
        { label: 'Total Duration', value: formatDuration(metrics.total_duration) },
        { label: 'Avg Trade Duration', value: formatDuration(metrics.avg_trade_duration) },
        { label: 'Avg Win Duration', value: formatDuration(metrics.avg_win_duration) },
        { label: 'Avg Loss Duration', value: formatDuration(metrics.avg_loss_duration) },
        { label: 'Max Trade Duration', value: formatDuration(metrics.max_trade_duration) }
      ]
    },
    {
      title: 'Streaks',
      icon: 'bi-lightning-charge',
      items: [
        { label: 'Max Consecutive Wins', value: metrics.max_consecutive_wins || 0 },
        { label: 'Max Consecutive Losses', value: metrics.max_consecutive_losses || 0 },
        { label: 'Current Streak', value: metrics.current_streak || 0 },
        { label: 'Recovery Factor', value: (metrics.recovery_factor || 0).toFixed(2) },
        { label: 'Expectancy', value: formatCurrency(metrics.expectancy) }
      ]
    }
  ];

  container.innerHTML = categories.map(cat => `
    <div class="metrics-category">
      <h4 class="metrics-category-title">
        <i class="metrics-category-icon bi ${cat.icon}"></i>
        ${cat.title}
      </h4>
      <div class="metrics-list">
        ${cat.items.map(item => `
          <div class="metric-item">
            <span class="metric-item-label">${item.label}</span>
            <span class="metric-item-value">${item.value}</span>
          </div>
        `).join('')}
      </div>
    </div>
  `).join('');
}

/**
 * Render equity curve chart
 */
function renderEquityChart(equityCurve) {
  const canvas = document.getElementById('equityChart');
  if (!canvas || !equityCurve || equityCurve.length === 0) return;

  // Simple canvas rendering (no external chart library needed)
  const ctx = canvas.getContext('2d');
  const container = canvas.parentElement;
  canvas.width = container.clientWidth;
  canvas.height = container.clientHeight;

  const padding = 40;
  const width = canvas.width - padding * 2;
  const height = canvas.height - padding * 2;

  // Extract values
  const values = equityCurve.map(p => p.equity || p.value || p);
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const range = maxVal - minVal || 1;

  // Clear canvas
  ctx.fillStyle = '#161b22';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // Draw grid
  ctx.strokeStyle = '#30363d';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = padding + (height * i) / 4;
    ctx.beginPath();
    ctx.moveTo(padding, y);
    ctx.lineTo(canvas.width - padding, y);
    ctx.stroke();
  }

  // Draw equity line
  ctx.strokeStyle = '#58a6ff';
  ctx.lineWidth = 2;
  ctx.beginPath();

  values.forEach((val, idx) => {
    const x = padding + (idx / (values.length - 1)) * width;
    const y = padding + height - ((val - minVal) / range) * height;

    if (idx === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });

  ctx.stroke();

  // Fill area under curve
  ctx.lineTo(padding + width, padding + height);
  ctx.lineTo(padding, padding + height);
  ctx.closePath();
  ctx.fillStyle = 'rgba(88, 166, 255, 0.1)';
  ctx.fill();

  // Draw labels
  ctx.fillStyle = '#8b949e';
  ctx.font = '11px sans-serif';
  ctx.textAlign = 'right';
  ctx.fillText(formatCurrency(maxVal), padding - 5, padding + 5);
  ctx.fillText(formatCurrency(minVal), padding - 5, padding + height);
}

/**
 * Switch between result tabs
 */
function switchResultsTab(tabId) {
  // Update tab buttons
  document.querySelectorAll('.results-tab').forEach(tab => {
    tab.classList.toggle('active', tab.dataset.tab === tabId);
  });

  // Update tab contents
  document.querySelectorAll('.results-tab-content').forEach(content => {
    content.classList.toggle('active', content.id === `tab-${tabId}`);
  });

  // Re-render chart if equity tab
  if (tabId === 'equity' && currentBacktestResults) {
    setTimeout(() => renderEquityChart(currentBacktestResults.equity_curve), 100);
  }
}

/**
 * Close backtest results modal
 */
function closeBacktestResultsModal() {
  const modal = document.getElementById('backtestResultsModal');
  if (modal) {
    modal.classList.remove('active');
    document.body.style.overflow = '';
  }
}

/**
 * Export backtest results
 */
function exportBacktestResults() {
  if (!currentBacktestResults) {
    showNotification('No results to export', 'warning');
    return;
  }

  const dataStr = JSON.stringify(currentBacktestResults, null, 2);
  const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);
  const filename = `backtest_results_${new Date().toISOString().slice(0, 10)}.json`;

  const link = document.createElement('a');
  link.href = dataUri;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  showNotification('Results exported successfully', 'success');
}

/**
 * View full results page
 */
function viewFullResults() {
  if (currentBacktestResults && currentBacktestResults.backtest_id) {
    window.location.href = `/frontend/backtest-results.html?backtest_id=${currentBacktestResults.backtest_id}`;
  } else {
    showNotification('No backtest ID available', 'warning');
  }
}

// Format helper functions for backtest results
// Note: formatCurrency is imported from utils.js

function formatPercent(value) {
  if (value === undefined || value === null) return '0.00%';
  return Number(value).toFixed(2) + '%';
}

function formatPrice(value) {
  if (value === undefined || value === null) return '0.00';
  return Number(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 8 });
}

function formatDateTime(value) {
  if (!value) return '-';
  const date = new Date(value);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

function formatDuration(seconds) {
  if (!seconds || seconds === 0) return '-';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours > 24) {
    const days = Math.floor(hours / 24);
    return `${days}d ${hours % 24}h`;
  }
  return `${hours}h ${minutes}m`;
}

function showBlockMenu(blockId) {
  // Would show context menu
  console.log('Show menu for', blockId);
}

// Toggle right sidebar collapse/expand
function toggleRightSidebar() {
  const sidebar = document.getElementById('sidebarRight');
  const btn = document.getElementById('toggleRightSidebarBtn');
  const icon = btn.querySelector('i');

  sidebar.classList.toggle('collapsed');

  if (sidebar.classList.contains('collapsed')) {
    icon.classList.remove('bi-chevron-right');
    icon.classList.add('bi-chevron-left');
  } else {
    icon.classList.remove('bi-chevron-left');
    icon.classList.add('bi-chevron-right');
  }
}

// Make toggleRightSidebar available globally
window.toggleRightSidebar = toggleRightSidebar;

// ============================================
// EXPORTS - Make functions available globally
// ============================================

// Strategy CRUD functions
window.saveStrategy = saveStrategy;
window.loadStrategy = loadStrategy;
window.runBacktest = runBacktest;
window.getStrategyIdFromURL = getStrategyIdFromURL;
window.updateLastSaved = updateLastSaved;
window.showNotification = showNotification;

// Block functions
window.addBlockToCanvas = addBlockToCanvas;
window.selectBlock = selectBlock;
window.startDragBlock = startDragBlock;
window.showBlockMenu = showBlockMenu;
window.updateBlockParam = updateBlockParam;
window.onBlockDragStart = onBlockDragStart;
window.onCanvasDrop = onCanvasDrop;
window.showBlockParamsPopup = showBlockParamsPopup;
window.closeBlockParamsPopup = closeBlockParamsPopup;
window.updateBlockParamFromPopup = updateBlockParamFromPopup;
window.duplicateBlock = duplicateBlock;
window.deleteBlock = deleteBlock;
window.resetBlockToDefaults = resetBlockToDefaults;

// Block validation functions
window.validateBlockParams = validateBlockParams;
window.validateParamInput = validateParamInput;
window.updateBlockValidationState = updateBlockValidationState;
window.blockValidationRules = blockValidationRules;

// Connection functions
window.renderConnections = renderConnections;
window.deleteConnection = deleteConnection;

// Canvas functions
window.zoomIn = zoomIn;
window.zoomOut = zoomOut;
window.resetZoom = resetZoom;
window.fitToScreen = fitToScreen;
window.undo = undo;
window.redo = redo;
window.deleteSelected = deleteSelected;

// Modal functions
window.openTemplatesModal = openTemplatesModal;
window.closeTemplatesModal = closeTemplatesModal;
window.selectTemplate = selectTemplate;
window.loadSelectedTemplate = loadSelectedTemplate;
window.renderTemplates = renderTemplates;
window.loadTemplateData = loadTemplateData;

// Backtest Results Display functions
window.displayBacktestResults = displayBacktestResults;
window.closeBacktestResultsModal = closeBacktestResultsModal;
window.switchResultsTab = switchResultsTab;
window.exportBacktestResults = exportBacktestResults;
window.viewFullResults = viewFullResults;

// ============================================
// WEBSOCKET VALIDATION INTEGRATION
// ============================================

/**
 * Initialize WebSocket validation event listeners
 */
function initWsValidationListeners() {
  // Listen for validation results from WebSocket
  window.addEventListener('ws-validation-result', (event) => {
    const { type, block_id, param_name, valid, messages } = event.detail;

    if (type === 'validate_param' && block_id) {
      // Update specific parameter validation state
      const inputEl = document.querySelector(
        `[data-block-id="${block_id}"][data-param-key="${param_name}"]`
      );
      if (inputEl) {
        inputEl.classList.toggle('is-invalid', !valid);
        inputEl.classList.toggle('is-valid', valid);
      }
    } else if (type === 'validate_block' && block_id) {
      // Update block validation state
      const errors = messages?.filter(m => m.severity === 'error').map(m => m.message) || [];
      updateBlockValidationState(block_id, { valid, errors });
    }
  });

  // Listen for connection status changes
  window.addEventListener('ws-validation-connected', () => {
    console.log('[Strategy Builder] WebSocket validation connected');
    updateWsStatusIndicator(true);
  });

  window.addEventListener('ws-validation-disconnected', () => {
    console.log('[Strategy Builder] WebSocket validation disconnected');
    updateWsStatusIndicator(false);
  });
}

/**
 * Update WebSocket status indicator in UI
 */
function updateWsStatusIndicator(connected) {
  let statusEl = document.getElementById('ws-validation-status');

  // Create indicator if it doesn't exist
  if (!statusEl) {
    const toolbar = document.querySelector('.canvas-toolbar') || document.querySelector('.toolbar');
    if (toolbar) {
      statusEl = document.createElement('span');
      statusEl.id = 'ws-validation-status';
      statusEl.className = 'ws-status-indicator ms-2';
      statusEl.innerHTML = '<i class="bi bi-broadcast"></i>';
      toolbar.appendChild(statusEl);
    }
  }

  if (statusEl) {
    statusEl.classList.toggle('connected', connected);
    statusEl.classList.toggle('disconnected', !connected);
    statusEl.title = connected
      ? 'Real-time validation: Active'
      : 'Real-time validation: Disconnected (using local validation)';
    statusEl.innerHTML = connected
      ? '<i class="bi bi-broadcast"></i>'
      : '<i class="bi bi-broadcast-pin"></i>';
  }
}

// Initialize WS listeners when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initWsValidationListeners);
} else {
  initWsValidationListeners();
}

// Export WS functions
window.wsValidation = wsValidation;
window.initWsValidationListeners = initWsValidationListeners;
window.updateWsStatusIndicator = updateWsStatusIndicator;

// Attach to window for backwards compatibility
if (typeof window !== 'undefined') {
  window.strategybuilderPage = {
    // Add public methods here
    wsValidation: wsValidation
  };
}
