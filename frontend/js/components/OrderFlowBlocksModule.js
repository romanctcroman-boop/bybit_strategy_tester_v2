/**
 * Order Flow Blocks Module — Order Flow Analysis блоки
 * 
 * Order Flow Imbalance, Cumulative Delta, Volume Profile
 */

export function createOrderFlowBlocksModule() {
  const orderFlowBlocks = [
    {
      id: 'order_flow_imbalance',
      type: 'order_flow',
      name: 'Order Flow Imbalance',
      description: 'Analyze buy/sell pressure',
      icon: '📈',
      category: 'Order Flow',
      parameters: {
        lookback: { type: 'number', default: 20, min: 5, max: 100 },
        threshold: { type: 'number', default: 0.3, min: 0, max: 1 }
      },
      inputs: ['ohlcv_data'],
      outputs: ['imbalance', 'signal', 'strength']
    },
    {
      id: 'cumulative_delta',
      type: 'order_flow',
      name: 'Cumulative Delta',
      description: 'Cumulative buy/sell delta',
      icon: '📉',
      category: 'Order Flow',
      parameters: {
        window: { type: 'number', default: 10, min: 5, max: 50 }
      },
      inputs: ['ohlcv_data'],
      outputs: ['delta', 'cumulative_delta', 'divergence']
    },
    {
      id: 'volume_profile',
      type: 'order_flow',
      name: 'Volume Profile',
      description: 'Volume by price level',
      icon: '📊',
      category: 'Order Flow',
      parameters: {
        n_bins: { type: 'number', default: 50, min: 10, max: 100 },
        value_area_pct: { type: 'number', default: 0.70, min: 0.5, max: 0.95 }
      },
      inputs: ['ohlcv_data'],
      outputs: ['poc', 'value_area_high', 'value_area_low', 'profile_type']
    },
    {
      id: 'volume_imbalance',
      type: 'order_flow',
      name: 'Volume Imbalance',
      description: 'Volume vs average',
      icon: '⚖️',
      category: 'Order Flow',
      parameters: {
        lookback: { type: 'number', default: 20, min: 5, max: 100 }
      },
      inputs: ['ohlcv_data'],
      outputs: ['imbalance', 'classification']
    }
  ];
  
  function getBlocks() {
    return [...orderFlowBlocks];
  }
  
  function getBlock(blockId) {
    return orderFlowBlocks.find(b => b.id === blockId);
  }
  
  return {
    getBlocks,
    getBlock
  };
}
