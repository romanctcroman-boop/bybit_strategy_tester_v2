/**
 * Sentiment Blocks Module — Sentiment Analysis блоки
 * 
 * Twitter Sentiment, News Sentiment, Composite Sentiment
 */

export function createSentimentBlocksModule() {
  const sentimentBlocks = [
    {
      id: 'twitter_sentiment',
      type: 'sentiment',
      name: 'Twitter Sentiment',
      description: 'Analyze Twitter sentiment',
      icon: '🐦',
      category: 'Sentiment Analysis',
      parameters: {
        keywords: { type: 'array', default: ['crypto', 'bitcoin'] },
        min_retweets: { type: 'number', default: 10, min: 0, max: 1000 },
        language: { type: 'select', options: ['en', 'ru', 'es', 'zh'], default: 'en' }
      },
      inputs: ['symbol'],
      outputs: ['sentiment', 'confidence', 'polarity']
    },
    {
      id: 'news_sentiment',
      type: 'sentiment',
      name: 'News Sentiment',
      description: 'Analyze news sentiment',
      icon: '📰',
      category: 'Sentiment Analysis',
      parameters: {
        sources: { 
          type: 'multiselect', 
          options: ['coindesk', 'cointelegraph', 'bloomberg', 'reuters'],
          default: ['coindesk', 'cointelegraph']
        },
        lookback_hours: { type: 'number', default: 24, min: 1, max: 168 }
      },
      inputs: ['symbol'],
      outputs: ['sentiment', 'confidence', 'impact_score']
    },
    {
      id: 'composite_sentiment',
      type: 'sentiment',
      name: 'Composite Sentiment',
      description: 'Combined sentiment score',
      icon: '📊',
      category: 'Sentiment Analysis',
      parameters: {
        twitter_weight: { type: 'number', default: 0.4, min: 0, max: 1 },
        news_weight: { type: 'number', default: 0.4, min: 0, max: 1 },
        reddit_weight: { type: 'number', default: 0.2, min: 0, max: 1 }
      },
      inputs: ['twitter_sentiment', 'news_sentiment', 'reddit_sentiment'],
      outputs: ['composite_sentiment', 'confidence']
    }
  ];
  
  function getBlocks() {
    return [...sentimentBlocks];
  }
  
  function getBlock(blockId) {
    return sentimentBlocks.find(b => b.id === blockId);
  }
  
  return {
    getBlocks,
    getBlock
  };
}
