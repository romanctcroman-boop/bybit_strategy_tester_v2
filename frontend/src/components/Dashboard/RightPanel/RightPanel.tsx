import React, { useState } from 'react';
import './RightPanel.css';

interface StrategyParams {
  lookback_bars: number;
  level_tolerance_pct: number;
  entry_tolerance_pct: number;
  stop_loss_pct: number;
  max_holding_bars: number;
}

const StrategyParamsForm: React.FC = () => {
  const [params, setParams] = useState<StrategyParams>({
    lookback_bars: 100,
    level_tolerance_pct: 0.5,
    entry_tolerance_pct: 0.15,
    stop_loss_pct: 1.5,
    max_holding_bars: 240,
  });

  return (
    <div className="form-section">
      <h3>Strategy Parameters</h3>

      <div className="form-group">
        <label htmlFor="lookback">Lookback Bars</label>
        <input
          type="number"
          id="lookback"
          value={params.lookback_bars}
          onChange={(e) => setParams({ ...params, lookback_bars: Number(e.target.value) })}
        />
        <span className="input-hint">50-200 bars</span>
      </div>

      <div className="form-group">
        <label htmlFor="level-tolerance">Level Tolerance %</label>
        <input
          type="number"
          id="level-tolerance"
          step="0.1"
          value={params.level_tolerance_pct}
          onChange={(e) => setParams({ ...params, level_tolerance_pct: Number(e.target.value) })}
        />
        <span className="input-hint">0.3-1.0%</span>
      </div>

      <div className="form-group">
        <label htmlFor="entry-tolerance">Entry Tolerance %</label>
        <input
          type="number"
          id="entry-tolerance"
          step="0.05"
          value={params.entry_tolerance_pct}
          onChange={(e) => setParams({ ...params, entry_tolerance_pct: Number(e.target.value) })}
        />
        <span className="input-hint">0.1-0.3%</span>
      </div>

      <div className="form-group">
        <label htmlFor="stop-loss">Stop Loss %</label>
        <input
          type="number"
          id="stop-loss"
          step="0.1"
          value={params.stop_loss_pct}
          onChange={(e) => setParams({ ...params, stop_loss_pct: Number(e.target.value) })}
        />
        <span className="input-hint">1.0-3.0%</span>
      </div>

      <div className="form-group">
        <label htmlFor="max-holding">Max Holding Bars</label>
        <input
          type="number"
          id="max-holding"
          value={params.max_holding_bars}
          onChange={(e) => setParams({ ...params, max_holding_bars: Number(e.target.value) })}
        />
        <span className="input-hint">120-480 bars</span>
      </div>

      <div className="form-actions">
        <button className="btn-reset">Reset Defaults</button>
        <button className="btn-apply">Apply & Retest</button>
      </div>
    </div>
  );
};

const SignalFiltersForm: React.FC = () => {
  const [filters, setFilters] = useState({
    enable_rsi: true,
    use_bollinger: false,
    volume_filter: false,
    rsi_oversold: 30,
    rsi_overbought: 70,
  });

  return (
    <div className="form-section">
      <h3>Signal Filters</h3>

      <div className="checkbox-group">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={filters.enable_rsi}
            onChange={(e) => setFilters({ ...filters, enable_rsi: e.target.checked })}
          />
          <span>Enable RSI Filter</span>
        </label>
      </div>

      {filters.enable_rsi && (
        <div className="conditional-inputs">
          <div className="form-group">
            <label htmlFor="rsi-oversold">RSI Oversold</label>
            <input
              type="number"
              id="rsi-oversold"
              value={filters.rsi_oversold}
              onChange={(e) => setFilters({ ...filters, rsi_oversold: Number(e.target.value) })}
            />
          </div>
          <div className="form-group">
            <label htmlFor="rsi-overbought">RSI Overbought</label>
            <input
              type="number"
              id="rsi-overbought"
              value={filters.rsi_overbought}
              onChange={(e) => setFilters({ ...filters, rsi_overbought: Number(e.target.value) })}
            />
          </div>
        </div>
      )}

      <div className="checkbox-group">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={filters.use_bollinger}
            onChange={(e) => setFilters({ ...filters, use_bollinger: e.target.checked })}
          />
          <span>Use Bollinger Bands</span>
        </label>
      </div>

      <div className="checkbox-group">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={filters.volume_filter}
            onChange={(e) => setFilters({ ...filters, volume_filter: e.target.checked })}
          />
          <span>Volume Filter (Above Average)</span>
        </label>
      </div>
    </div>
  );
};

const PatternSettingsForm: React.FC = () => {
  const [settings, setSettings] = useState({
    sr_min_touches: 2,
    bb_period: 20,
    bb_std_dev: 2.0,
    ema_fast: 10,
    ema_slow: 50,
  });

  return (
    <div className="form-section">
      <h3>Pattern Settings</h3>

      <div className="form-group">
        <label htmlFor="sr-touches">S/R Min Touches</label>
        <input
          type="number"
          id="sr-touches"
          value={settings.sr_min_touches}
          onChange={(e) => setSettings({ ...settings, sr_min_touches: Number(e.target.value) })}
        />
        <span className="input-hint">2-5 touches</span>
      </div>

      <div className="form-group">
        <label htmlFor="bb-period">BB Period</label>
        <input
          type="number"
          id="bb-period"
          value={settings.bb_period}
          onChange={(e) => setSettings({ ...settings, bb_period: Number(e.target.value) })}
        />
        <span className="input-hint">14-30 bars</span>
      </div>

      <div className="form-group">
        <label htmlFor="bb-std">BB Std Dev</label>
        <input
          type="number"
          id="bb-std"
          step="0.1"
          value={settings.bb_std_dev}
          onChange={(e) => setSettings({ ...settings, bb_std_dev: Number(e.target.value) })}
        />
        <span className="input-hint">1.5-3.0</span>
      </div>

      <div className="form-group">
        <label htmlFor="ema-fast">EMA Fast Period</label>
        <input
          type="number"
          id="ema-fast"
          value={settings.ema_fast}
          onChange={(e) => setSettings({ ...settings, ema_fast: Number(e.target.value) })}
        />
        <span className="input-hint">5-20 bars</span>
      </div>

      <div className="form-group">
        <label htmlFor="ema-slow">EMA Slow Period</label>
        <input
          type="number"
          id="ema-slow"
          value={settings.ema_slow}
          onChange={(e) => setSettings({ ...settings, ema_slow: Number(e.target.value) })}
        />
        <span className="input-hint">30-100 bars</span>
      </div>
    </div>
  );
};

const EntryExitConditionsForm: React.FC = () => {
  const [conditions, setConditions] = useState({
    entry_price_near_sr: true,
    entry_rsi_extreme: false,
    entry_bb_touch: false,
    exit_take_profit: true,
    exit_stop_loss: true,
    exit_max_holding: true,
  });

  return (
    <div className="form-section">
      <h3>Entry/Exit Conditions</h3>

      <div className="conditions-grid">
        <div className="condition-category">
          <h4>Entry Rules</h4>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={conditions.entry_price_near_sr}
              onChange={(e) =>
                setConditions({ ...conditions, entry_price_near_sr: e.target.checked })
              }
            />
            <span>Price Near S/R Level</span>
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={conditions.entry_rsi_extreme}
              onChange={(e) =>
                setConditions({ ...conditions, entry_rsi_extreme: e.target.checked })
              }
            />
            <span>RSI at Extreme</span>
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={conditions.entry_bb_touch}
              onChange={(e) => setConditions({ ...conditions, entry_bb_touch: e.target.checked })}
            />
            <span>BB Band Touch</span>
          </label>
        </div>

        <div className="condition-category">
          <h4>Exit Rules</h4>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={conditions.exit_take_profit}
              onChange={(e) => setConditions({ ...conditions, exit_take_profit: e.target.checked })}
            />
            <span>Take Profit Target</span>
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={conditions.exit_stop_loss}
              onChange={(e) => setConditions({ ...conditions, exit_stop_loss: e.target.checked })}
            />
            <span>Stop Loss Trigger</span>
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={conditions.exit_max_holding}
              onChange={(e) => setConditions({ ...conditions, exit_max_holding: e.target.checked })}
            />
            <span>Max Holding Period</span>
          </label>
        </div>
      </div>
    </div>
  );
};

const RightPanel: React.FC = () => {
  return (
    <div className="right-panel">
      <div className="panel-header">
        <h2>Strategy Configuration</h2>
        <button className="btn-save-preset">💾 Save Preset</button>
      </div>

      <StrategyParamsForm />
      <SignalFiltersForm />
      <PatternSettingsForm />
      <EntryExitConditionsForm />
    </div>
  );
};

export default RightPanel;
