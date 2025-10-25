import React, { useEffect } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Container,
  Paper,
  Typography,
  Stack,
  Button,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
} from '@mui/material';
import { useBacktestsStore } from '../store/backtests';
import type { Backtest } from '../types/api';

const BacktestsPage: React.FC = () => {
  const { items, total, loading, error, fetchAll } = useBacktestsStore();

  useEffect(() => {
    void fetchAll({ limit: 50, offset: 0 });
  }, [fetchAll]);

  return (
    <Container>
      <Typography variant="h4" gutterBottom>
        Backtests
      </Typography>
      <Paper sx={{ p: 2 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
          <Typography variant="subtitle1">Всего: {total}</Typography>
          <Button
            variant="outlined"
            onClick={() => fetchAll({ limit: 50, offset: 0 })}
            disabled={loading}
          >
            Обновить
          </Button>
        </Stack>
        {error && (
          <Typography color="error" sx={{ mb: 2 }}>
            {error}
          </Typography>
        )}
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>ID</TableCell>
              <TableCell>Стратегия</TableCell>
              <TableCell>Символ</TableCell>
              <TableCell>Таймфрейм</TableCell>
              <TableCell>Период</TableCell>
              <TableCell>Статус</TableCell>
              <TableCell align="right">Действия</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {items.map((bt: Backtest) => (
              <TableRow key={bt.id} hover>
                <TableCell>{bt.id}</TableCell>
                <TableCell>{bt.strategy_id}</TableCell>
                <TableCell>{bt.symbol}</TableCell>
                <TableCell>{bt.timeframe}</TableCell>
                <TableCell>
                  {bt.start_date} → {bt.end_date}
                </TableCell>
                <TableCell>{bt.status}</TableCell>
                <TableCell align="right">
                  <Button
                    size="small"
                    variant="contained"
                    component={RouterLink}
                    to={`/backtest/${bt.id}`}
                  >
                    Открыть
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {items.length === 0 && !loading && (
              <TableRow>
                <TableCell colSpan={7} align="center">
                  Нет данных
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Paper>
    </Container>
  );
};

export default BacktestsPage;
