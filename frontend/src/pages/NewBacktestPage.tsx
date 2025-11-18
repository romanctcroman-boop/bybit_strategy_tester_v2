/**
 * New Backtest Page
 *
 * Страница для создания нового бэктеста с формой и навигацией к результатам
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Container, Typography, Box, Paper, Button, Stack } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import CreateBacktestForm from '../components/CreateBacktestForm';

const NewBacktestPage: React.FC = () => {
  const navigate = useNavigate();

  const handleBacktestSuccess = (backtestId: number) => {
    // Navigate to backtest detail page
    setTimeout(() => {
      navigate(`/backtest/${backtestId}`);
    }, 1500);
  };

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 3 }}>
        {/* Header */}
        <Stack direction="row" alignItems="center" spacing={2} sx={{ mb: 3 }}>
          <Button
            startIcon={<ArrowBackIcon />}
            onClick={() => navigate('/backtests')}
            variant="outlined"
          >
            Назад к списку
          </Button>
          <Typography variant="h4" component="h1">
            Новый бэктест
          </Typography>
        </Stack>

        {/* Description */}
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="body1" paragraph>
            Запустите бэктест торговой стратегии на исторических данных. Выберите торговую пару,
            таймфрейм, стратегию и параметры.
          </Typography>
          <Typography variant="body2" color="text.secondary">
            <strong>Доступные стратегии:</strong>
          </Typography>
          <ul>
            <li>
              <strong>Bollinger Bands Mean Reversion:</strong> Mean reversion стратегия на основе
              полос Боллинджера. Входит в позицию при касании нижней/верхней границы, выход при
              возврате к средней линии.
            </li>
            <li>
              <strong>EMA Crossover:</strong> Классическая стратегия на пересечении быстрой и
              медленной экспоненциальной скользящей средней (Golden Cross / Death Cross).
            </li>
            <li>
              <strong>RSI Strategy:</strong> Торговля на основе индикатора RSI, вход при
              перепроданности (&lt;30) или перекупленности (&gt;70).
            </li>
          </ul>
        </Paper>

        {/* Create Form */}
        <CreateBacktestForm onSuccess={handleBacktestSuccess} />
      </Box>
    </Container>
  );
};

export default NewBacktestPage;
