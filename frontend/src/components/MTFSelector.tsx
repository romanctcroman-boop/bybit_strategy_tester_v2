/**
 * Multi-Timeframe Selector Component
 * 
 * Allows users to select multiple timeframes for MTF analysis (ТЗ 3.4.2)
 * and configure HTF filters.
 */
import React, { useState } from 'react';
import {
  Box,
  Chip,
  FormControl,
  FormControlLabel,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Switch,
  TextField,
  Typography,
  Tooltip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Button,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import InfoIcon from '@mui/icons-material/Info';

const AVAILABLE_TIMEFRAMES = [
  { value: '1', label: '1m' },
  { value: '3', label: '3m' },
  { value: '5', label: '5m' },
  { value: '15', label: '15m' },
  { value: '30', label: '30m' },
  { value: '60', label: '1h' },
  { value: '120', label: '2h' },
  { value: '240', label: '4h' },
  { value: '360', label: '6h' },
  { value: '720', label: '12h' },
  { value: 'D', label: '1D' },
  { value: 'W', label: '1W' },
];

const HTF_FILTER_TYPES = [
  { value: 'trend_ma', label: 'Trend MA (Price vs MA)' },
  { value: 'ema_direction', label: 'EMA Direction (Rising/Falling)' },
  { value: 'rsi_range', label: 'RSI Range' },
];

const MA_CONDITIONS = [
  { value: 'price_above', label: 'Price Above MA' },
  { value: 'price_below', label: 'Price Below MA' },
];

const EMA_DIRECTIONS = [
  { value: 'rising', label: 'Rising' },
  { value: 'falling', label: 'Falling' },
];

interface HTFFilter {
  id: string;
  timeframe: string;
  type: string;
  params: {
    period?: number;
    condition?: string;
    min?: number;
    max?: number;
  };
}

interface MTFSelectorProps {
  centralTimeframe: string;
  additionalTimeframes: string[];
  htfFilters: HTFFilter[];
  onAdditionalTimeframesChange: (timeframes: string[]) => void;
  onHTFFiltersChange: (filters: HTFFilter[]) => void;
  disabled?: boolean;
}

const MTFSelector: React.FC<MTFSelectorProps> = ({
  centralTimeframe,
  additionalTimeframes,
  htfFilters,
  onAdditionalTimeframesChange,
  onHTFFiltersChange,
  disabled = false,
}) => {
  const [mtfEnabled, setMtfEnabled] = useState(additionalTimeframes.length > 0);

  const handleMTFToggle = (event: React.ChangeEvent<HTMLInputElement>) => {
    const enabled = event.target.checked;
    setMtfEnabled(enabled);
    
    if (!enabled) {
      onAdditionalTimeframesChange([]);
      onHTFFiltersChange([]);
    }
  };

  const handleTimeframeAdd = (tf: string) => {
    if (!additionalTimeframes.includes(tf) && tf !== centralTimeframe) {
      onAdditionalTimeframesChange([...additionalTimeframes, tf]);
    }
  };

  const handleTimeframeRemove = (tf: string) => {
    onAdditionalTimeframesChange(additionalTimeframes.filter((t) => t !== tf));
    
    // Remove filters for this timeframe
    onHTFFiltersChange(htfFilters.filter((f) => f.timeframe !== tf));
  };

  const handleAddFilter = () => {
    const newFilter: HTFFilter = {
      id: Date.now().toString(),
      timeframe: additionalTimeframes[0] || '60',
      type: 'trend_ma',
      params: {
        period: 200,
        condition: 'price_above',
      },
    };
    
    onHTFFiltersChange([...htfFilters, newFilter]);
  };

  const handleRemoveFilter = (id: string) => {
    onHTFFiltersChange(htfFilters.filter((f) => f.id !== id));
  };

  const handleFilterChange = (id: string, updates: Partial<HTFFilter>) => {
    onHTFFiltersChange(
      htfFilters.map((f) => (f.id === id ? { ...f, ...updates } : f))
    );
  };

  const handleFilterParamChange = (id: string, paramKey: string, value: any) => {
    onHTFFiltersChange(
      htfFilters.map((f) =>
        f.id === id
          ? { ...f, params: { ...f.params, [paramKey]: value } }
          : f
      )
    );
  };

  return (
    <Paper elevation={2} sx={{ p: 2 }}>
      <Stack spacing={2}>
        {/* MTF Toggle */}
        <Box display="flex" alignItems="center" justifyContent="space-between">
          <FormControlLabel
            control={
              <Switch
                checked={mtfEnabled}
                onChange={handleMTFToggle}
                disabled={disabled}
              />
            }
            label={
              <Box display="flex" alignItems="center" gap={1}>
                <Typography variant="h6">
                  Multi-Timeframe Analysis
                </Typography>
                <Tooltip title="Use higher timeframes for trend filtering and confirmation">
                  <InfoIcon fontSize="small" color="action" />
                </Tooltip>
              </Box>
            }
          />
          
          {mtfEnabled && (
            <Chip
              label={`Central: ${AVAILABLE_TIMEFRAMES.find((t) => t.value === centralTimeframe)?.label || centralTimeframe}`}
              color="primary"
              variant="outlined"
            />
          )}
        </Box>

        {/* Timeframe Selection */}
        {mtfEnabled && (
          <Box>
            <Typography variant="subtitle2" gutterBottom>
              Additional Timeframes (HTF)
            </Typography>
            
            <Stack direction="row" spacing={1} flexWrap="wrap" gap={1}>
              {additionalTimeframes.map((tf) => (
                <Chip
                  key={tf}
                  label={AVAILABLE_TIMEFRAMES.find((t) => t.value === tf)?.label || tf}
                  onDelete={() => handleTimeframeRemove(tf)}
                  color="secondary"
                  disabled={disabled}
                />
              ))}
              
              <FormControl size="small" sx={{ minWidth: 120 }}>
                <Select
                  value=""
                  displayEmpty
                  onChange={(e) => handleTimeframeAdd(e.target.value)}
                  disabled={disabled}
                >
                  <MenuItem value="" disabled>
                    <em>Add TF...</em>
                  </MenuItem>
                  {AVAILABLE_TIMEFRAMES.filter(
                    (tf) =>
                      tf.value !== centralTimeframe &&
                      !additionalTimeframes.includes(tf.value)
                  ).map((tf) => (
                    <MenuItem key={tf.value} value={tf.value}>
                      {tf.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Stack>
          </Box>
        )}

        {/* HTF Filters */}
        {mtfEnabled && additionalTimeframes.length > 0 && (
          <Accordion defaultExpanded>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="subtitle2">
                HTF Filters ({htfFilters.length})
              </Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Stack spacing={2}>
                {htfFilters.map((filter) => (
                  <Paper key={filter.id} variant="outlined" sx={{ p: 2 }}>
                    <Stack spacing={2}>
                      <Box display="flex" alignItems="center" gap={2}>
                        {/* Timeframe */}
                        <FormControl size="small" sx={{ minWidth: 100 }}>
                          <InputLabel>Timeframe</InputLabel>
                          <Select
                            value={filter.timeframe}
                            label="Timeframe"
                            onChange={(e) =>
                              handleFilterChange(filter.id, {
                                timeframe: e.target.value,
                              })
                            }
                            disabled={disabled}
                          >
                            {additionalTimeframes.map((tf) => (
                              <MenuItem key={tf} value={tf}>
                                {AVAILABLE_TIMEFRAMES.find((t) => t.value === tf)?.label || tf}
                              </MenuItem>
                            ))}
                          </Select>
                        </FormControl>

                        {/* Filter Type */}
                        <FormControl size="small" sx={{ minWidth: 200 }}>
                          <InputLabel>Filter Type</InputLabel>
                          <Select
                            value={filter.type}
                            label="Filter Type"
                            onChange={(e) =>
                              handleFilterChange(filter.id, {
                                type: e.target.value,
                                params: {}, // Reset params on type change
                              })
                            }
                            disabled={disabled}
                          >
                            {HTF_FILTER_TYPES.map((ft) => (
                              <MenuItem key={ft.value} value={ft.value}>
                                {ft.label}
                              </MenuItem>
                            ))}
                          </Select>
                        </FormControl>

                        <Box flex={1} />

                        {/* Delete Button */}
                        <IconButton
                          size="small"
                          onClick={() => handleRemoveFilter(filter.id)}
                          disabled={disabled}
                        >
                          <DeleteIcon />
                        </IconButton>
                      </Box>

                      {/* Filter-specific params */}
                      {filter.type === 'trend_ma' && (
                        <Box display="flex" gap={2}>
                          <TextField
                            label="MA Period"
                            type="number"
                            size="small"
                            value={filter.params.period || 200}
                            onChange={(e) =>
                              handleFilterParamChange(
                                filter.id,
                                'period',
                                parseInt(e.target.value) || 200
                              )
                            }
                            sx={{ width: 150 }}
                            disabled={disabled}
                          />
                          
                          <FormControl size="small" sx={{ minWidth: 200 }}>
                            <InputLabel>Condition</InputLabel>
                            <Select
                              value={filter.params.condition || 'price_above'}
                              label="Condition"
                              onChange={(e) =>
                                handleFilterParamChange(
                                  filter.id,
                                  'condition',
                                  e.target.value
                                )
                              }
                              disabled={disabled}
                            >
                              {MA_CONDITIONS.map((cond) => (
                                <MenuItem key={cond.value} value={cond.value}>
                                  {cond.label}
                                </MenuItem>
                              ))}
                            </Select>
                          </FormControl>
                        </Box>
                      )}

                      {filter.type === 'ema_direction' && (
                        <Box display="flex" gap={2}>
                          <TextField
                            label="EMA Period"
                            type="number"
                            size="small"
                            value={filter.params.period || 50}
                            onChange={(e) =>
                              handleFilterParamChange(
                                filter.id,
                                'period',
                                parseInt(e.target.value) || 50
                              )
                            }
                            sx={{ width: 150 }}
                            disabled={disabled}
                          />
                          
                          <FormControl size="small" sx={{ minWidth: 200 }}>
                            <InputLabel>Direction</InputLabel>
                            <Select
                              value={filter.params.condition || 'rising'}
                              label="Direction"
                              onChange={(e) =>
                                handleFilterParamChange(
                                  filter.id,
                                  'condition',
                                  e.target.value
                                )
                              }
                              disabled={disabled}
                            >
                              {EMA_DIRECTIONS.map((dir) => (
                                <MenuItem key={dir.value} value={dir.value}>
                                  {dir.label}
                                </MenuItem>
                              ))}
                            </Select>
                          </FormControl>
                        </Box>
                      )}

                      {filter.type === 'rsi_range' && (
                        <Box display="flex" gap={2}>
                          <TextField
                            label="Min RSI"
                            type="number"
                            size="small"
                            value={filter.params.min || 0}
                            onChange={(e) =>
                              handleFilterParamChange(
                                filter.id,
                                'min',
                                parseInt(e.target.value) || 0
                              )
                            }
                            sx={{ width: 150 }}
                            disabled={disabled}
                          />
                          
                          <TextField
                            label="Max RSI"
                            type="number"
                            size="small"
                            value={filter.params.max || 100}
                            onChange={(e) =>
                              handleFilterParamChange(
                                filter.id,
                                'max',
                                parseInt(e.target.value) || 100
                              )
                            }
                            sx={{ width: 150 }}
                            disabled={disabled}
                          />
                        </Box>
                      )}
                    </Stack>
                  </Paper>
                ))}

                <Button
                  startIcon={<AddIcon />}
                  onClick={handleAddFilter}
                  disabled={disabled || additionalTimeframes.length === 0}
                  variant="outlined"
                  fullWidth
                >
                  Add HTF Filter
                </Button>
              </Stack>
            </AccordionDetails>
          </Accordion>
        )}
      </Stack>
    </Paper>
  );
};

export default MTFSelector;
