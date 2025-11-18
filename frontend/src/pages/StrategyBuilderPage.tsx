import React, { useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  Container,
  Divider,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import TradingViewWidget from '../components/TradingViewWidget';

const steps = ['Название', 'API', 'Пара', 'Депозит', 'Фильтры', 'Стратегия', 'Входы', 'Выходы'];

const StepperBar: React.FC<{ activeIndex: number }> = ({ activeIndex }) => {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
      {steps.map((label, i) => (
        <Box key={label} sx={{ display: 'flex', alignItems: 'center' }}>
          <Box
            sx={{
              width: 14,
              height: 14,
              borderRadius: '50%',
              background: i <= activeIndex ? '#2e7d32' : '#bdbdbd',
              boxShadow: i === activeIndex ? '0 0 0 3px rgba(46,125,50,0.2)' : 'none',
            }}
          />
          <Typography variant="caption" sx={{ ml: 1, mr: 2 }}>
            {label}
          </Typography>
          {i < steps.length - 1 && (
            <Box sx={{ width: 24, height: 2, background: '#cfd8dc', mr: 2 }} />
          )}
        </Box>
      ))}
    </Box>
  );
};

const StrategyBuilderPage: React.FC = () => {
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [interval, setInterval] = useState('30');
  const [theme, setTheme] = useState<'light' | 'dark'>('dark');
  const [activeStep, setActiveStep] = useState(2); // 0-based; mock: third step active

  const tvSymbol = useMemo(() => {
    // TradingView expects exchange:symbol format, use Bybit perpetual as a neutral default
    return `${symbol}`.toUpperCase().includes(':')
      ? symbol.toUpperCase()
      : `BYBIT:${symbol.toUpperCase()}`;
  }, [symbol]);

  return (
    <Container maxWidth={false} sx={{ py: 2 }}>
      {/* Top controls bar - "Зона для кнопок" */}
      <Paper sx={{ p: 2, mb: 2, background: '#eeeeee' }}>
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
          <Typography variant="h6" sx={{ mr: 2 }}>
            Зона для кнопок
          </Typography>
          <Button variant="contained" color="primary">
            Сохранить черновик
          </Button>
          <Button variant="outlined">Запустить бэктест</Button>
          <Button variant="outlined">Запустить оптимизацию</Button>
          <Divider flexItem orientation="vertical" sx={{ mx: 1 }} />
          <TextField
            label="Символ"
            size="small"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            sx={{ width: 160 }}
          />
          <TextField
            label="ТФ"
            size="small"
            select
            value={interval}
            onChange={(e) => setInterval(e.target.value)}
            sx={{ width: 120 }}
          >
            {['1', '3', '5', '15', '30', '60', '240', 'D'].map((iv) => (
              <MenuItem key={iv} value={iv}>
                {iv}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="Тема"
            size="small"
            select
            value={theme}
            onChange={(e) => setTheme(e.target.value as any)}
            sx={{ width: 140 }}
          >
            <MenuItem value="light">Светлая</MenuItem>
            <MenuItem value="dark">Тёмная</MenuItem>
          </TextField>
          <Chip label="макет" size="small" sx={{ ml: 'auto' }} />
        </Stack>
      </Paper>

      {/* Main split area */}
      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: 2 }}>
        {/* Left: Chart area */}
        <Paper sx={{ p: 1, minHeight: 520 }}>
          <div style={{ height: 8 }} />
          <TradingViewWidget
            symbol={tvSymbol}
            interval={interval}
            theme={theme}
            allowSymbolChange={false}
          />
        </Paper>

        {/* Right: Steps and dropdown zone */}
        <Paper sx={{ p: 2, background: '#e8f5e9', minHeight: 520 }}>
          <Typography variant="subtitle1" sx={{ mb: 1 }}>
            Конструктор стратегии
          </Typography>
          <StepperBar activeIndex={activeStep} />
          <Divider sx={{ my: 2 }} />
          <Box
            sx={{
              border: '1px dashed #81c784',
              borderRadius: 1,
              p: 2,
              background: '#f1f8e9',
              minHeight: 380,
            }}
          >
            <Typography variant="body2" color="text.secondary">
              зона для выпадающих окон связанных с борам этапов создания стратегии.
            </Typography>
            <Box sx={{ mt: 2, display: 'grid', gap: 1 }}>
              <Button
                size="small"
                variant="contained"
                onClick={() => setActiveStep((s) => Math.max(0, s - 1))}
              >
                Предыдущий шаг
              </Button>
              <Button
                size="small"
                variant="outlined"
                onClick={() => setActiveStep((s) => Math.min(steps.length - 1, s + 1))}
              >
                Следующий шаг
              </Button>
            </Box>
          </Box>
        </Paper>
      </Box>
    </Container>
  );
};

export default StrategyBuilderPage;
