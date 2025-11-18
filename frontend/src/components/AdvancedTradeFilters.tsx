/**
 * AdvancedTradeFilters - Enhanced filtering for backtest trades
 *
 * Features:
 * - Filter by side (Long/Short)
 * - Filter by PnL range
 * - Filter by date range
 * - Filter by signal type
 * - Sort by multiple criteria
 */

import React from 'react';
import {
  Stack,
  TextField,
  MenuItem,
  Chip,
  Box,
  Typography,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  FormControl,
  InputLabel,
  Select,
  SelectChangeEvent,
} from '@mui/material';
import { ExpandMore as ExpandMoreIcon, FilterList as FilterIcon } from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { ru } from 'date-fns/locale';

export interface TradeFilters {
  side: '' | 'buy' | 'sell';
  pnlMin?: number;
  pnlMax?: number;
  dateFrom?: Date | null;
  dateTo?: Date | null;
  signal?: string;
  sortBy: 'entry_time' | 'exit_time' | 'pnl' | 'pnl_pct' | 'duration';
  sortOrder: 'asc' | 'desc';
}

interface AdvancedTradeFiltersProps {
  filters: TradeFilters;
  onFiltersChange: (filters: TradeFilters) => void;
  availableSignals?: string[];
}

const AdvancedTradeFilters: React.FC<AdvancedTradeFiltersProps> = ({
  filters,
  onFiltersChange,
  availableSignals = [],
}) => {
  const handleChange = (key: keyof TradeFilters, value: any) => {
    onFiltersChange({ ...filters, [key]: value });
  };

  const handleSelectChange = (event: SelectChangeEvent<string>) => {
    const { name, value } = event.target;
    handleChange(name as keyof TradeFilters, value);
  };

  const activeFiltersCount = [
    filters.side && 'side',
    (filters.pnlMin !== undefined || filters.pnlMax !== undefined) && 'pnl',
    (filters.dateFrom || filters.dateTo) && 'date',
    filters.signal && 'signal',
  ].filter(Boolean).length;

  const clearFilters = () => {
    onFiltersChange({
      side: '',
      pnlMin: undefined,
      pnlMax: undefined,
      dateFrom: null,
      dateTo: null,
      signal: undefined,
      sortBy: 'entry_time',
      sortOrder: 'desc',
    });
  };

  return (
    <Accordion defaultExpanded={false}>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Stack direction="row" spacing={1.5} alignItems="center">
          <FilterIcon />
          <Typography variant="subtitle1" fontWeight={600}>
            Расширенные фильтры
          </Typography>
          {activeFiltersCount > 0 && (
            <Chip
              label={`${activeFiltersCount} активных`}
              size="small"
              color="primary"
              sx={{ height: 24 }}
            />
          )}
        </Stack>
      </AccordionSummary>
      <AccordionDetails>
        <Stack spacing={3}>
          {/* Row 1: Side, Signal */}
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <FormControl fullWidth>
              <InputLabel>Направление</InputLabel>
              <Select
                name="side"
                value={filters.side}
                onChange={handleSelectChange}
                label="Направление"
              >
                <MenuItem value="">Все</MenuItem>
                <MenuItem value="buy">Long</MenuItem>
                <MenuItem value="sell">Short</MenuItem>
              </Select>
            </FormControl>

            {availableSignals.length > 0 && (
              <FormControl fullWidth>
                <InputLabel>Сигнал</InputLabel>
                <Select
                  name="signal"
                  value={filters.signal || ''}
                  onChange={handleSelectChange}
                  label="Сигнал"
                >
                  <MenuItem value="">Все</MenuItem>
                  {availableSignals.map((signal) => (
                    <MenuItem key={signal} value={signal}>
                      {signal}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}
          </Stack>

          {/* Row 2: PnL Range */}
          <Box>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>
              Диапазон PnL (USDT)
            </Typography>
            <Stack direction="row" spacing={2}>
              <TextField
                label="Минимум"
                type="number"
                value={filters.pnlMin ?? ''}
                onChange={(e) =>
                  handleChange('pnlMin', e.target.value ? Number(e.target.value) : undefined)
                }
                size="small"
                fullWidth
              />
              <TextField
                label="Максимум"
                type="number"
                value={filters.pnlMax ?? ''}
                onChange={(e) =>
                  handleChange('pnlMax', e.target.value ? Number(e.target.value) : undefined)
                }
                size="small"
                fullWidth
              />
            </Stack>
          </Box>

          {/* Row 3: Date Range */}
          <Box>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>
              Период
            </Typography>
            <LocalizationProvider dateAdapter={AdapterDateFns} adapterLocale={ru}>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
                <DatePicker
                  label="От"
                  value={filters.dateFrom}
                  onChange={(date) => handleChange('dateFrom', date)}
                  slotProps={{ textField: { size: 'small', fullWidth: true } }}
                />
                <DatePicker
                  label="До"
                  value={filters.dateTo}
                  onChange={(date) => handleChange('dateTo', date)}
                  slotProps={{ textField: { size: 'small', fullWidth: true } }}
                />
              </Stack>
            </LocalizationProvider>
          </Box>

          {/* Row 4: Sorting */}
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <FormControl fullWidth>
              <InputLabel>Сортировка</InputLabel>
              <Select
                name="sortBy"
                value={filters.sortBy}
                onChange={handleSelectChange}
                label="Сортировка"
              >
                <MenuItem value="entry_time">По времени входа</MenuItem>
                <MenuItem value="exit_time">По времени выхода</MenuItem>
                <MenuItem value="pnl">По PnL (абсолютное)</MenuItem>
                <MenuItem value="pnl_pct">По PnL (%)</MenuItem>
                <MenuItem value="duration">По длительности</MenuItem>
              </Select>
            </FormControl>

            <FormControl fullWidth>
              <InputLabel>Порядок</InputLabel>
              <Select
                name="sortOrder"
                value={filters.sortOrder}
                onChange={handleSelectChange}
                label="Порядок"
              >
                <MenuItem value="desc">По убыванию</MenuItem>
                <MenuItem value="asc">По возрастанию</MenuItem>
              </Select>
            </FormControl>
          </Stack>

          {/* Clear Filters Button */}
          {activeFiltersCount > 0 && (
            <Box>
              <Chip
                label="Очистить все фильтры"
                onClick={clearFilters}
                onDelete={clearFilters}
                color="default"
                variant="outlined"
              />
            </Box>
          )}
        </Stack>
      </AccordionDetails>
    </Accordion>
  );
};

export default AdvancedTradeFilters;
