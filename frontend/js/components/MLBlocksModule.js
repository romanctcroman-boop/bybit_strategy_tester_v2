/**
 * ML Blocks Module — Machine Learning блоки
 * 
 * LSTM Predictor, ML Signal, Feature Engineering
 */

export function createMLBlocksModule() {
  const mlBlocks = [
    {
      id: 'lstm_predictor',
      type: 'ml',
      name: 'LSTM Predictor',
      description: 'LSTM-based price prediction',
      icon: '🧠',
      category: 'Machine Learning',
      parameters: {
        lookback: { type: 'number', default: 60, min: 10, max: 200 },
        prediction_horizon: { type: 'number', default: 5, min: 1, max: 50 },
        threshold: { type: 'number', default: 0.5, min: 0, max: 1 }
      },
      inputs: ['ohlcv_data'],
      outputs: ['signal', 'confidence', 'prediction']
    },
    {
      id: 'ml_signal',
      type: 'ml',
      name: 'ML Signal',
      description: 'Random Forest / XGBoost signal',
      icon: '🤖',
      category: 'Machine Learning',
      parameters: {
        model_type: { type: 'select', options: ['rf', 'xgb', 'lightgbm'], default: 'rf' },
        n_estimators: { type: 'number', default: 100, min: 10, max: 500 },
        max_depth: { type: 'number', default: 5, min: 1, max: 20 }
      },
      inputs: ['ohlcv_data', 'features'],
      outputs: ['signal', 'confidence', 'feature_importance']
    },
    {
      id: 'feature_engineering',
      type: 'ml',
      name: 'Feature Engineering',
      description: 'Create ML features',
      icon: '⚙️',
      category: 'Machine Learning',
      parameters: {
        features: { 
          type: 'multiselect', 
          options: ['returns', 'volatility', 'rsi', 'macd', 'bollinger', 'volume_change'],
          default: ['returns', 'volatility', 'rsi']
        }
      },
      inputs: ['ohlcv_data'],
      outputs: ['features']
    }
  ];
  
  function getBlocks() {
    return [...mlBlocks];
  }
  
  function getBlock(blockId) {
    return mlBlocks.find(b => b.id === blockId);
  }
  
  return {
    getBlocks,
    getBlock
  };
}
