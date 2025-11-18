/**
 * Create Backtest Form Component
 *
 * Форма для запуска нового бэктеста с выбором:
 * - Symbol (торговая пара)
 * - Strategy (торговая стратегия)
 * - Timeframe (таймфрейм)
 * - Date range (период данных)
 * - Parameters (параметры стратегии)
 *
 * @version 2.0 - Fixed type safety, validation, sanitization, rate limiting
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
  Alert,
  CircularProgress,
  Chip,
  Stack,
  Divider,
  LinearProgress,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import { DatePicker } from '@mui/x-date-pickers';
import { useNotify } from './NotificationsProvider';
import { BacktestsApi } from '../services/api';

// Import types and constants
import type { Strategy, BacktestConfig } from '../types/backtest';
import { SYMBOLS, TIMEFRAMES, DEFAULT_STRATEGIES } from '../constants/backtest';

// Import utilities
import {
  validateBacktestForm,
  sanitizeStrategyParams,
  getErrorMessage,
  formatDateForBackend,
} from '../utils/backtestValidation';
import { useRateLimitedSubmit } from '../hooks/useRateLimitedSubmit';

interface CreateBacktestFormProps {
  onSuccess?: (backtestId: number) => void;
}

const CreateBacktestForm: React.FC<CreateBacktestFormProps> = ({ onSuccess }) => {
  const notify = useNotify();

  // Form state
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [strategy, setStrategy] = useState<Strategy>(DEFAULT_STRATEGIES[0]);
  const [timeframe, setTimeframe] = useState('1h');
  const [startDate, setStartDate] = useState<Date | null>(
    new Date(Date.now() - 90 * 24 * 60 * 60 * 1000) // 90 days ago
  );
  const [endDate, setEndDate] = useState<Date | null>(new Date());
  const [initialCapital, setInitialCapital] = useState(10000);
  const [commission, setCommission] = useState(0.06);
  const [leverage, setLeverage] = useState(1);

  // Strategy parameters (dynamic based on strategy)
  const [strategyParams, setStrategyParams] = useState<Record<string, any>>(
    DEFAULT_STRATEGIES[0].default_params || {}
  );

  // Loading & error state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Update strategy params when strategy changes
  useEffect(() => {
    if (strategy?.default_params) {
      setStrategyParams(strategy.default_params);
    }
  }, [strategy]);

  // Handle strategy change with validation
  const handleStrategyChange = useCallback((strategyId: number) => {
    const selectedStrategy = DEFAULT_STRATEGIES.find((s) => s.id === strategyId);

    if (!selectedStrategy) {
      setError('Стратегия не найдена');
      return;
    }

    setStrategy(selectedStrategy);
    setStrategyParams(selectedStrategy.default_params || {});
  }, []);

  const handleParamChange = useCallback((paramName: string, value: any) => {
    setStrategyParams((prev) => ({
      ...prev,
      [paramName]: value,
    }));
  }, []);

  // Main submit handler
  const handleSubmitInternal = async (e: React.FormEvent) => {
    e.preventDefault();

    // Comprehensive validation
    const validationError = validateBacktestForm({
      strategy,
      startDate,
      endDate,
      initialCapital,
      commission,
      leverage,
      strategyParams,
    });

    if (validationError) {
      setError(validationError);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Sanitize strategy params
      const sanitizedParams = sanitizeStrategyParams(strategyParams);

      // Prepare backtest config
      const backtestConfig: BacktestConfig = {
        symbol,
        timeframe,
        start_date: formatDateForBackend(startDate!),
        end_date: formatDateForBackend(endDate!),
        initial_capital: initialCapital,
        commission: commission / 100, // Convert to decimal
        leverage,
        strategy_config: {
          type: strategy.type,
          ...sanitizedParams,
        },
      };

      // Submit backtest
      const response = await BacktestsApi.run(backtestConfig);

      notify({ message: `Бэктест #${response.id} успешно запущен!`, severity: 'success' });

      if (onSuccess) {
        onSuccess(response.id);
      }
    } catch (err: any) {
      const errorMessage = getErrorMessage(err);
      setError(errorMessage);
      notify({ message: `Ошибка запуска бэктеста: ${errorMessage}`, severity: 'error' });
    } finally {
      setLoading(false);
    }
  };

  // Rate-limited submit handler
  const handleSubmit = useRateLimitedSubmit(handleSubmitInternal, {
    cooldownMs: 2000,
    onRateLimitExceeded: () => {
      setError('Пожалуйста, подождите 2 секунды перед следующей отправкой');
    },
  });

  return (
    <Card>
      <CardHeader
        title="Создать новый бэктест"
        subheader="Заполните параметры для запуска бэктестирования стратегии"
      />
      <CardContent>
        <form onSubmit={handleSubmit}>
          <Grid container spacing={3}>
            {/* Symbol Selection */}
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Торговая пара</InputLabel>
                <Select
                  value={symbol}
                  label="Торговая пара"
                  onChange={(e) => setSymbol(e.target.value)}
                >
                  {SYMBOLS.map((sym) => (
                    <MenuItem key={sym} value={sym}>
                      {sym}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            {/* Timeframe Selection */}
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Таймфрейм</InputLabel>
                <Select
                  value={timeframe}
                  label="Таймфрейм"
                  onChange={(e) => setTimeframe(e.target.value)}
                >
                  {TIMEFRAMES.map((tf) => (
                    <MenuItem key={tf.value} value={tf.value}>
                      {tf.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            {/* Strategy Selection */}
            <Grid item xs={12}>
              <FormControl fullWidth>
                <InputLabel>Стратегия</InputLabel>
                <Select
                  value={strategy?.id || ''}
                  label="Стратегия"
                  onChange={(e) => handleStrategyChange(Number(e.target.value))}
                >
                  {DEFAULT_STRATEGIES.map((strat) => (
                    <MenuItem key={strat.id} value={strat.id}>
                      <Box>
                        <Typography variant="body1">{strat.name}</Typography>
                        <Typography variant="caption" color="text.secondary">
                          {strat.description}
                        </Typography>
                      </Box>
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            {/* Date Range */}
            <Grid item xs={12} sm={6}>
              <DatePicker
                label="Дата начала"
                value={startDate}
                onChange={setStartDate}
                slotProps={{ textField: { fullWidth: true } }}
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <DatePicker
                label="Дата окончания"
                value={endDate}
                onChange={setEndDate}
                slotProps={{ textField: { fullWidth: true } }}
              />
            </Grid>

            <Grid item xs={12}>
              <Divider>
                <Chip label="Параметры бэктеста" />
              </Divider>
            </Grid>

            {/* Backtest Parameters */}
            <Grid item xs={12} sm={4}>
              <TextField
                fullWidth
                label="Начальный капитал (USDT)"
                type="number"
                value={initialCapital}
                onChange={(e) => setInitialCapital(Number(e.target.value))}
                inputProps={{ min: 100, step: 100 }}
              />
            </Grid>

            <Grid item xs={12} sm={4}>
              <TextField
                fullWidth
                label="Комиссия (%)"
                type="number"
                value={commission}
                onChange={(e) => setCommission(Number(e.target.value))}
                inputProps={{ min: 0, max: 1, step: 0.01 }}
              />
            </Grid>

            <Grid item xs={12} sm={4}>
              <TextField
                fullWidth
                label="Плечо"
                type="number"
                value={leverage}
                onChange={(e) => setLeverage(Number(e.target.value))}
                inputProps={{ min: 1, max: 100 }}
              />
            </Grid>

            {/* Strategy Parameters */}
            {strategy && Object.keys(strategyParams).length > 0 && (
              <>
                <Grid item xs={12}>
                  <Divider>
                    <Chip label="Параметры стратегии" />
                  </Divider>
                </Grid>

                {Object.entries(strategyParams).map(([key, value]) => (
                  <Grid item xs={12} sm={6} md={4} key={key}>
                    <TextField
                      fullWidth
                      label={key.replace(/_/g, ' ').toUpperCase()}
                      type="number"
                      value={value}
                      onChange={(e) => handleParamChange(key, Number(e.target.value))}
                      inputProps={{ step: 'any' }}
                    />
                  </Grid>
                ))}
              </>
            )}

            {/* Error Alert */}
            {error && (
              <Grid item xs={12}>
                <Alert severity="error" onClose={() => setError(null)}>
                  {error}
                </Alert>
              </Grid>
            )}

            {/* Loading State */}
            {loading && (
              <Grid item xs={12}>
                <LinearProgress />
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ mt: 1, display: 'block' }}
                >
                  Отправка конфигурации на сервер...
                </Typography>
              </Grid>
            )}

            {/* Submit Button */}
            <Grid item xs={12}>
              <Stack direction="row" spacing={2} justifyContent="flex-end">
                <Button
                  type="submit"
                  variant="contained"
                  size="large"
                  startIcon={loading ? <CircularProgress size={20} /> : <PlayArrowIcon />}
                  disabled={loading}
                >
                  {loading ? 'Запуск...' : 'Запустить бэктест'}
                </Button>
              </Stack>
            </Grid>
          </Grid>
        </form>
      </CardContent>
    </Card>
  );
};

export default CreateBacktestForm;
