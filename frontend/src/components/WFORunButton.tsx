/**
 * Walk-Forward Optimization Run Button Component (Task #10)
 *
 * Интеграция с OptimizationDetailPage для запуска WFO
 */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  TextField,
  Stack,
  Alert,
  CircularProgress,
} from '@mui/material';
import TimelineIcon from '@mui/icons-material/Timeline';
import { OptimizationsApi } from '../services/api';
import { useNotify } from './NotificationsProvider';

interface WFORunButtonProps {
  optimizationId: number;
  disabled?: boolean;
}

const WFORunButton: React.FC<WFORunButtonProps> = ({ optimizationId, disabled = false }) => {
  const navigate = useNavigate();
  const notify = useNotify();

  const [open, setOpen] = useState(false);
  const [running, setRunning] = useState(false);

  // WFO Parameters
  const [inSampleSize, setInSampleSize] = useState(252); // 1 year
  const [outSampleSize, setOutSampleSize] = useState(63); // 3 months
  const [stepSize, setStepSize] = useState(63); // 3 months

  const handleOpen = () => setOpen(true);
  const handleClose = () => !running && setOpen(false);

  const handleRun = async () => {
    setRunning(true);

    try {
      const response = await OptimizationsApi.runWalkForward(optimizationId, {
        train_size: inSampleSize,
        test_size: outSampleSize,
        step_size: stepSize,
      });

      notify({
        message: `Walk-Forward Optimization task enqueued: ${response.task_id}`,
        severity: 'success',
      });

      // Navigate to WFO results page
      setTimeout(() => {
        navigate(`/walk-forward/${optimizationId}`);
      }, 1500);
    } catch (error: any) {
      notify({
        message: error?.message || 'Failed to start Walk-Forward Optimization',
        severity: 'error',
      });
      setRunning(false);
      setOpen(false);
    }
  };

  return (
    <>
      <Button
        variant="contained"
        color="secondary"
        startIcon={<TimelineIcon />}
        onClick={handleOpen}
        disabled={disabled}
      >
        Run Walk-Forward
      </Button>

      <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
        <DialogTitle>Walk-Forward Optimization Configuration</DialogTitle>

        <DialogContent>
          <DialogContentText sx={{ mb: 2 }}>
            Защита от переобучения через скользящую оптимизацию. Данные разбиваются на периоды
            In-Sample (оптимизация) и Out-of-Sample (тестирование).
          </DialogContentText>

          <Stack spacing={2}>
            <TextField
              label="In-Sample Size (bars)"
              type="number"
              value={inSampleSize}
              onChange={(e) => setInSampleSize(parseInt(e.target.value, 10))}
              helperText="Количество баров для оптимизации (обычно 252 = 1 год)"
              fullWidth
              disabled={running}
            />

            <TextField
              label="Out-of-Sample Size (bars)"
              type="number"
              value={outSampleSize}
              onChange={(e) => setOutSampleSize(parseInt(e.target.value, 10))}
              helperText="Количество баров для тестирования (обычно 63 = 3 месяца)"
              fullWidth
              disabled={running}
            />

            <TextField
              label="Step Size (bars)"
              type="number"
              value={stepSize}
              onChange={(e) => setStepSize(parseInt(e.target.value, 10))}
              helperText="Шаг сдвига окна (обычно 63 = 3 месяца)"
              fullWidth
              disabled={running}
            />

            <Alert severity="info" sx={{ mt: 1 }}>
              <strong>Пример:</strong>
              <br />
              Period 1: IS [0-252], OOS [252-315]
              <br />
              Period 2: IS [63-315], OOS [315-378]
              <br />
              Period 3: IS [126-378], OOS [378-441]
            </Alert>
          </Stack>
        </DialogContent>

        <DialogActions>
          <Button onClick={handleClose} disabled={running}>
            Cancel
          </Button>
          <Button onClick={handleRun} variant="contained" disabled={running}>
            {running ? <CircularProgress size={24} /> : 'Start Walk-Forward'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default WFORunButton;
