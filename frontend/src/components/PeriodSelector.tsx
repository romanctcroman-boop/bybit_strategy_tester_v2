import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  ButtonGroup,
  Grid,
  Paper,
  TextField,
  Typography,
  Popover,
} from '@mui/material';
import CalendarTodayIcon from '@mui/icons-material/CalendarToday';

export interface PeriodRange {
  startDate: string; // YYYY-MM-DD
  endDate: string; // YYYY-MM-DD
}

interface PeriodSelectorProps {
  value: PeriodRange;
  onChange: (range: PeriodRange) => void;
  label?: string;
  minDate?: string; // Minimum allowed date
  maxDate?: string; // Maximum allowed date (default: today)
}

// Calculate date range from current date
function calculatePeriod(
  type: 'month' | '3months' | '6months' | 'year' | '3years' | 'all'
): PeriodRange {
  const now = new Date();
  const endDate = now.toISOString().split('T')[0]; // Today

  let startDate: Date;
  switch (type) {
    case 'month':
      startDate = new Date(now);
      startDate.setMonth(now.getMonth() - 1);
      break;
    case '3months':
      startDate = new Date(now);
      startDate.setMonth(now.getMonth() - 3);
      break;
    case '6months':
      startDate = new Date(now);
      startDate.setMonth(now.getMonth() - 6);
      break;
    case 'year':
      startDate = new Date(now);
      startDate.setFullYear(now.getFullYear() - 1);
      break;
    case '3years':
      startDate = new Date(now);
      startDate.setFullYear(now.getFullYear() - 3);
      break;
    case 'all':
      // Default: start from 2020-06-01 (Bybit perpetual launch)
      startDate = new Date('2020-06-01');
      break;
  }

  return {
    startDate: startDate.toISOString().split('T')[0],
    endDate,
  };
}

const PeriodSelector: React.FC<PeriodSelectorProps> = ({
  value,
  onChange,
  label = 'Период',
  minDate = '2020-01-01',
  maxDate,
}) => {
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const [customStart, setCustomStart] = useState(value.startDate);
  const [customEnd, setCustomEnd] = useState(value.endDate);

  const maxDateValue = maxDate || new Date().toISOString().split('T')[0];

  useEffect(() => {
    setCustomStart(value.startDate);
    setCustomEnd(value.endDate);
  }, [value]);

  const handlePresetClick = (type: 'month' | '3months' | '6months' | 'year' | '3years' | 'all') => {
    const range = calculatePeriod(type);
    onChange(range);
    setAnchorEl(null);
  };

  const handleCustomApply = () => {
    if (customStart && customEnd) {
      onChange({ startDate: customStart, endDate: customEnd });
      setAnchorEl(null);
    }
  };

  const formatDateRange = (range: PeriodRange) => {
    const start = new Date(range.startDate);
    const end = new Date(range.endDate);
    const diffTime = Math.abs(end.getTime() - start.getTime());
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

    return `${range.startDate} — ${range.endDate} (${diffDays} дней)`;
  };

  return (
    <Box>
      <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
        {label}
      </Typography>
      <Button
        variant="outlined"
        startIcon={<CalendarTodayIcon />}
        onClick={(e) => setAnchorEl(e.currentTarget)}
        fullWidth
        sx={{ justifyContent: 'flex-start', textAlign: 'left' }}
      >
        {formatDateRange(value)}
      </Button>

      <Popover
        open={Boolean(anchorEl)}
        anchorEl={anchorEl}
        onClose={() => setAnchorEl(null)}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'left',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'left',
        }}
      >
        <Paper sx={{ p: 2, minWidth: 350 }}>
          <Typography variant="subtitle2" sx={{ mb: 2 }}>
            Быстрый выбор периода
          </Typography>

          <ButtonGroup orientation="vertical" fullWidth sx={{ mb: 2 }}>
            <Button onClick={() => handlePresetClick('month')}>Месяц (30 дней)</Button>
            <Button onClick={() => handlePresetClick('3months')}>3 месяца (90 дней)</Button>
            <Button onClick={() => handlePresetClick('6months')}>6 месяцев (180 дней)</Button>
            <Button onClick={() => handlePresetClick('year')}>Год (365 дней)</Button>
            <Button onClick={() => handlePresetClick('3years')}>3 года</Button>
            <Button onClick={() => handlePresetClick('all')}>Весь период</Button>
          </ButtonGroup>

          <Typography variant="subtitle2" sx={{ mb: 1, mt: 2 }}>
            Произвольный период
          </Typography>

          <Grid container spacing={2}>
            <Grid item xs={6}>
              <TextField
                label="Начало"
                type="date"
                value={customStart}
                onChange={(e) => setCustomStart(e.target.value)}
                fullWidth
                size="small"
                InputLabelProps={{ shrink: true }}
                inputProps={{
                  min: minDate,
                  max: customEnd || maxDateValue,
                }}
              />
            </Grid>
            <Grid item xs={6}>
              <TextField
                label="Конец"
                type="date"
                value={customEnd}
                onChange={(e) => setCustomEnd(e.target.value)}
                fullWidth
                size="small"
                InputLabelProps={{ shrink: true }}
                inputProps={{
                  min: customStart || minDate,
                  max: maxDateValue,
                }}
              />
            </Grid>
            <Grid item xs={12}>
              <Button
                variant="contained"
                fullWidth
                onClick={handleCustomApply}
                disabled={!customStart || !customEnd || customStart > customEnd}
              >
                Применить
              </Button>
            </Grid>
          </Grid>
        </Paper>
      </Popover>
    </Box>
  );
};

export default PeriodSelector;
