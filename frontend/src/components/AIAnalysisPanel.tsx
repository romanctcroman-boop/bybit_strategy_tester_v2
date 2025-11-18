/**
 * AIAnalysisPanel - AI-powered backtest analysis using MCP Server + Perplexity AI
 *
 * Features:
 * - Automatic analysis of backtest results
 * - Perplexity AI insights via MCP Bridge
 * - Recommendations for strategy improvements
 * - Risk assessment and optimization suggestions
 */

import React, { useState, useCallback, useEffect } from 'react';
import {
  Paper,
  Typography,
  Button,
  Stack,
  Box,
  CircularProgress,
  Alert,
  Chip,
  Divider,
  Card,
  CardContent,
  LinearProgress,
} from '@mui/material';
import {
  AutoAwesome as AIIcon,
  TrendingUp as TrendingUpIcon,
  Warning as WarningIcon,
  CheckCircle as CheckIcon,
  Lightbulb as LightbulbIcon,
} from '@mui/icons-material';
import type { Backtest } from '../types/api';

interface AIAnalysisPanelProps {
  backtest: Backtest | null;
  results: any; // BacktestResults type
}

interface AIInsight {
  type: 'success' | 'warning' | 'info' | 'error';
  title: string;
  content: string;
  icon?: React.ReactNode;
}

const AIAnalysisPanel: React.FC<AIAnalysisPanelProps> = ({ backtest, results }) => {
  const [analyzing, setAnalyzing] = useState(false);
  const [insights, setInsights] = useState<AIInsight[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [aiResponse, setAiResponse] = useState<string | null>(null);

  const analyzeBacktest = useCallback(async () => {
    if (!backtest || !results) {
      setError('Нет данных для анализа');
      return;
    }

    setAnalyzing(true);
    setError(null);
    setInsights([]);
    setAiResponse(null);

    try {
      // Prepare analysis context for Perplexity AI
      const analysisContext = {
        backtest_id: backtest.id,
        strategy: backtest.strategy_id,
        symbol: backtest.symbol,
        timeframe: backtest.timeframe,
        period: `${backtest.start_date} → ${backtest.end_date}`,
        initial_capital: backtest.initial_capital,
        metrics: {
          net_pnl: results.overview?.net_pnl,
          net_pnl_pct: results.overview?.net_pct,
          total_trades: results.overview?.total_trades,
          win_rate: results.by_side?.all?.win_rate,
          profit_factor: results.overview?.profit_factor,
          max_drawdown: results.overview?.max_drawdown_pct,
          sharpe_ratio: results.risk?.sharpe,
          sortino_ratio: results.risk?.sortino,
        },
      };

      // Call MCP Server endpoint (via backend proxy to avoid CORS)
      const response = await fetch('http://127.0.0.1:8000/api/v1/ai/analyze-backtest', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          context: analysisContext,
          query: `Проанализируй результаты бэктеста торговой стратегии:
          
Стратегия: ${backtest.strategy_id}
Символ: ${backtest.symbol}
Таймфрейм: ${backtest.timeframe}
Период: ${backtest.start_date} - ${backtest.end_date}

Результаты:
- Чистый PnL: ${analysisContext.metrics.net_pnl} USDT (${analysisContext.metrics.net_pnl_pct}%)
- Всего сделок: ${analysisContext.metrics.total_trades}
- Win Rate: ${analysisContext.metrics.win_rate}%
- Profit Factor: ${analysisContext.metrics.profit_factor}
- Макс. просадка: ${analysisContext.metrics.max_drawdown}%
- Sharpe Ratio: ${analysisContext.metrics.sharpe_ratio}
- Sortino Ratio: ${analysisContext.metrics.sortino_ratio}

Дай подробный анализ:
1. Оценка эффективности стратегии (отлично/хорошо/удовлетворительно/плохо)
2. Ключевые сильные стороны
3. Основные риски и слабости
4. Рекомендации по оптимизации
5. Сравнение с типичными результатами для этого таймфрейма и символа`,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      setAiResponse(data.analysis || data.result || JSON.stringify(data));

      // Parse AI response into structured insights
      const parsedInsights = parseAIResponse(data.analysis || data.result || '');
      setInsights(parsedInsights);
    } catch (err: any) {
      console.error('AI Analysis error:', err);
      setError(err.message || 'Не удалось получить AI-анализ');

      // Fallback: Generate basic insights from metrics
      const fallbackInsights = generateFallbackInsights(results);
      setInsights(fallbackInsights);
    } finally {
      setAnalyzing(false);
    }
  }, [backtest, results]);

  // Generate insights when backtest data is available
  useEffect(() => {
    if (backtest && results && insights.length === 0) {
      // Auto-generate basic insights immediately
      const basicInsights = generateFallbackInsights(results);
      setInsights(basicInsights);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backtest, results]);

  const parseAIResponse = (response: string): AIInsight[] => {
    const insights: AIInsight[] = [];

    // Simple parsing logic - можно улучшить с помощью ML
    if (response.includes('отлично') || response.includes('excellent')) {
      insights.push({
        type: 'success',
        title: 'Отличная производительность',
        content: 'Стратегия показывает выдающиеся результаты',
        icon: <CheckIcon />,
      });
    }

    if (response.includes('риск') || response.includes('risk')) {
      insights.push({
        type: 'warning',
        title: 'Выявлены риски',
        content: 'Обратите внимание на управление рисками',
        icon: <WarningIcon />,
      });
    }

    if (response.includes('оптимиз') || response.includes('improve')) {
      insights.push({
        type: 'info',
        title: 'Возможности оптимизации',
        content: 'Есть потенциал для улучшения параметров',
        icon: <LightbulbIcon />,
      });
    }

    return insights.length > 0
      ? insights
      : [
          {
            type: 'info',
            title: 'AI-анализ получен',
            content: response.substring(0, 200) + '...',
            icon: <AIIcon />,
          },
        ];
  };

  const generateFallbackInsights = (results: any): AIInsight[] => {
    const insights: AIInsight[] = [];
    const overview = results.overview || {};
    const winRate = results.by_side?.all?.win_rate;
    const profitFactor = overview.profit_factor;
    const sharpe = results.risk?.sharpe;

    // Win Rate analysis
    if (winRate != null) {
      if (winRate >= 60) {
        insights.push({
          type: 'success',
          title: 'Высокий Win Rate',
          content: `Win Rate ${winRate.toFixed(2)}% указывает на эффективную стратегию входа`,
          icon: <CheckIcon />,
        });
      } else if (winRate < 40) {
        insights.push({
          type: 'warning',
          title: 'Низкий Win Rate',
          content: `Win Rate ${winRate.toFixed(2)}% требует внимания. Рассмотрите улучшение условий входа`,
          icon: <WarningIcon />,
        });
      }
    }

    // Profit Factor analysis
    if (profitFactor != null) {
      if (profitFactor >= 2.0) {
        insights.push({
          type: 'success',
          title: 'Отличный Profit Factor',
          content: `Profit Factor ${profitFactor.toFixed(2)} показывает сильное преимущество`,
          icon: <TrendingUpIcon />,
        });
      } else if (profitFactor < 1.5) {
        insights.push({
          type: 'warning',
          title: 'Profit Factor требует улучшения',
          content: `Profit Factor ${profitFactor.toFixed(2)} ниже рекомендуемого уровня 1.5`,
          icon: <WarningIcon />,
        });
      }
    }

    // Sharpe Ratio analysis
    if (sharpe != null) {
      if (sharpe >= 1.5) {
        insights.push({
          type: 'success',
          title: 'Хороший риск-профиль',
          content: `Sharpe Ratio ${sharpe.toFixed(2)} указывает на благоприятное соотношение риск/доходность`,
          icon: <CheckIcon />,
        });
      } else if (sharpe < 1.0) {
        insights.push({
          type: 'info',
          title: 'Рекомендация по оптимизации',
          content: 'Рассмотрите ML-оптимизацию параметров для улучшения Sharpe Ratio',
          icon: <LightbulbIcon />,
        });
      }
    }

    return insights;
  };

  const getInsightColor = (type: string) => {
    switch (type) {
      case 'success':
        return 'success';
      case 'warning':
        return 'warning';
      case 'error':
        return 'error';
      default:
        return 'info';
    }
  };

  return (
    <Paper sx={{ p: 3, mt: 3, borderRadius: 2 }}>
      <Stack spacing={3}>
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Stack direction="row" spacing={1.5} alignItems="center">
            <AIIcon color="primary" sx={{ fontSize: 32 }} />
            <Box>
              <Typography variant="h6">AI-анализ результатов</Typography>
              <Typography variant="caption" color="text.secondary">
                Powered by Perplexity AI via MCP Bridge
              </Typography>
            </Box>
          </Stack>
          <Button
            variant="contained"
            onClick={analyzeBacktest}
            disabled={analyzing || !backtest}
            startIcon={analyzing ? <CircularProgress size={18} /> : <AIIcon />}
          >
            {analyzing ? 'Анализируем...' : 'Запустить AI-анализ'}
          </Button>
        </Stack>

        {analyzing && <LinearProgress />}

        {error && (
          <Alert severity="error" onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {insights.length > 0 && (
          <Box>
            <Typography variant="subtitle2" sx={{ mb: 2 }}>
              Ключевые инсайты ({insights.length})
            </Typography>
            <Stack spacing={2}>
              {insights.map((insight, index) => (
                <Card
                  key={index}
                  variant="outlined"
                  sx={{
                    borderLeft: 4,
                    borderColor: `${getInsightColor(insight.type)}.main`,
                  }}
                >
                  <CardContent>
                    <Stack direction="row" spacing={2} alignItems="flex-start">
                      <Box sx={{ color: `${getInsightColor(insight.type)}.main`, pt: 0.5 }}>
                        {insight.icon}
                      </Box>
                      <Box flexGrow={1}>
                        <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 0.5 }}>
                          <Typography variant="subtitle1" fontWeight={600}>
                            {insight.title}
                          </Typography>
                          <Chip
                            label={insight.type.toUpperCase()}
                            size="small"
                            color={getInsightColor(insight.type) as any}
                            sx={{ height: 20, fontSize: '0.7rem' }}
                          />
                        </Stack>
                        <Typography variant="body2" color="text.secondary">
                          {insight.content}
                        </Typography>
                      </Box>
                    </Stack>
                  </CardContent>
                </Card>
              ))}
            </Stack>
          </Box>
        )}

        {aiResponse && (
          <>
            <Divider />
            <Box>
              <Typography variant="subtitle2" sx={{ mb: 1.5 }}>
                Полный AI-отчёт
              </Typography>
              <Paper
                variant="outlined"
                sx={{
                  p: 2,
                  backgroundColor: 'action.hover',
                  maxHeight: 400,
                  overflow: 'auto',
                }}
              >
                <Typography
                  variant="body2"
                  component="pre"
                  sx={{
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    fontFamily: 'monospace',
                    fontSize: '0.875rem',
                  }}
                >
                  {aiResponse}
                </Typography>
              </Paper>
            </Box>
          </>
        )}

        {!analyzing && insights.length === 0 && !error && (
          <Alert severity="info">
            Нажмите &quot;Запустить AI-анализ&quot; для получения детальных рекомендаций от
            Perplexity AI
          </Alert>
        )}
      </Stack>
    </Paper>
  );
};

export default AIAnalysisPanel;
