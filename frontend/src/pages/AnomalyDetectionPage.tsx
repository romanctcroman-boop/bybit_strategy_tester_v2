/**
 * Anomaly Detection Dashboard
 *
 * Features:
 * - Train Isolation Forest model on Bybit historical data
 * - Real-time anomaly detection visualization
 * - Anomaly alert history with severity levels
 * - Detection statistics and charts
 * - Model information and configuration
 *
 * Phase: 4.4 (ML-Powered Features)
 * Task: 6 - Anomaly Detection Dashboard
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  Box,
  Container,
  Grid,
  Typography,
  Button,
  Card,
  CardContent,
  Chip,
  Alert,
  CircularProgress,
  TextField,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
  Tooltip,
  LinearProgress,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  ModelTraining as TrainIcon,
  Warning as WarningIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  Delete as DeleteIcon,
  Timeline as TimelineIcon,
} from '@mui/icons-material';
import {
  PieChart,
  Pie,
  Cell,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

// ============================================================================
// Types
// ============================================================================

interface ModelInfo {
  status: string;
  is_trained: boolean;
  model_version: string;
  contamination: number;
  n_features: number;
  feature_names: string[];
  severity_thresholds: {
    info: number;
    warning: number;
    critical: number;
  };
  model_path: string | null;
}

interface TrainingMetrics {
  training_samples: number;
  n_features: number;
  n_anomalies_detected: number;
  anomaly_rate: number;
  score_mean: number;
  score_std: number;
  score_min: number;
  score_max: number;
  training_duration_seconds: number;
  model_version: string;
}

interface DetectionResult {
  status: string;
  n_samples: number;
  n_anomalies: number;
  anomaly_rate: number;
  score_mean: number;
  score_min: number;
  score_max: number;
  latency_ms: number;
  model_version: string;
  timestamps?: string[];
  predictions?: number[];
  scores?: number[];
  severities?: string[];
  is_anomaly?: boolean[];
}

interface AnomalyStats {
  status: string;
  total_detections: number;
  total_anomalies: number;
  anomaly_rate: number;
  by_severity: {
    info: number;
    warning: number;
    critical: number;
  };
  by_symbol: Record<string, number>;
  recent_24h: number;
  recent_7d: number;
}

interface TrainFormData {
  symbol: string;
  timeframe: string;
  lookback_days: number;
  contamination: number;
  save_model: boolean;
  force_retrain: boolean;
}

// ============================================================================
// Constants
// ============================================================================

const SEVERITY_COLORS = {
  normal: '#4caf50',
  info: '#2196f3',
  warning: '#ff9800',
  critical: '#f44336',
};

// ============================================================================
// Main Component
// ============================================================================

const AnomalyDetectionDashboard: React.FC = () => {
  // State
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null);
  const [stats, setStats] = useState<AnomalyStats | null>(null);
  const [trainingMetrics, setTrainingMetrics] = useState<TrainingMetrics | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [showTrainDialog, setShowTrainDialog] = useState(false);
  const [trainForm, setTrainForm] = useState<TrainFormData>({
    symbol: 'BTCUSDT',
    timeframe: '15',
    lookback_days: 365,
    contamination: 0.05,
    save_model: true,
    force_retrain: false,
  });

  const [autoRefresh, setAutoRefresh] = useState(true);

  // ========================================================================
  // API Calls
  // ========================================================================

  const fetchAllData = async () => {
    await Promise.all([fetchModelInfo(), fetchStats()]);
  };

  // ========================================================================
  // Effects
  // ========================================================================

  useEffect(() => {
    fetchAllData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      fetchModelInfo();
      fetchStats();
    }, 10000); // Refresh every 10 seconds

    return () => clearInterval(interval);
  }, [autoRefresh]);

  const fetchModelInfo = async () => {
    try {
      const response = await axios.get<ModelInfo>('/api/v1/anomalies/model/info');
      setModelInfo(response.data);
      setError(null);
    } catch (err: any) {
      console.error('Failed to fetch model info:', err);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await axios.get<AnomalyStats>('/api/v1/anomalies/stats');
      setStats(response.data);
      setError(null);
    } catch (err: any) {
      console.error('Failed to fetch stats:', err);
    }
  };

  const trainModel = async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const response = await axios.post('/api/v1/anomalies/train', trainForm);
      setTrainingMetrics(response.data.metrics);
      setSuccess(`Model trained successfully! Version: ${response.data.model_version}`);
      setShowTrainDialog(false);

      // Refresh data
      await fetchAllData();
    } catch (err: any) {
      setError(`Training failed: ${err.response?.data?.detail || err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const deleteModel = async () => {
    if (!confirm('Delete trained model? This cannot be undone.')) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await axios.delete('/api/v1/anomalies/model');
      setSuccess('Model deleted successfully');
      setModelInfo(null);
      setTrainingMetrics(null);
      await fetchAllData();
    } catch (err: any) {
      setError(`Failed to delete model: ${err.response?.data?.detail || err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // ========================================================================
  // Chart Data Preparation
  // ========================================================================

  const getSeverityChartData = () => {
    if (!stats) return [];

    return [
      { name: 'Info', value: stats.by_severity.info, color: SEVERITY_COLORS.info },
      { name: 'Warning', value: stats.by_severity.warning, color: SEVERITY_COLORS.warning },
      { name: 'Critical', value: stats.by_severity.critical, color: SEVERITY_COLORS.critical },
    ];
  };

  // ========================================================================
  // Render Helpers
  // ========================================================================

  const renderModelStatus = () => {
    if (!modelInfo) {
      return (
        <Card>
          <CardContent>
            <Box display="flex" alignItems="center" gap={2}>
              <WarningIcon color="warning" />
              <Box>
                <Typography variant="h6">Model Not Trained</Typography>
                <Typography variant="body2" color="text.secondary">
                  Train a model to start detecting anomalies
                </Typography>
              </Box>
              <Box ml="auto">
                <Button
                  variant="contained"
                  color="primary"
                  startIcon={<TrainIcon />}
                  onClick={() => setShowTrainDialog(true)}
                >
                  Train Model
                </Button>
              </Box>
            </Box>
          </CardContent>
        </Card>
      );
    }

    return (
      <Card>
        <CardContent>
          <Box display="flex" alignItems="center" gap={2}>
            <CheckIcon style={{ color: SEVERITY_COLORS.normal }} />
            <Box flex={1}>
              <Typography variant="h6">Model Active</Typography>
              <Typography variant="body2" color="text.secondary">
                Version: {modelInfo.model_version}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Features: {modelInfo.n_features} | Contamination:{' '}
                {(modelInfo.contamination * 100).toFixed(1)}%
              </Typography>
            </Box>
            <Box display="flex" gap={1}>
              <Button
                variant="outlined"
                color="primary"
                startIcon={<TrainIcon />}
                onClick={() => {
                  setTrainForm({ ...trainForm, force_retrain: true });
                  setShowTrainDialog(true);
                }}
              >
                Retrain
              </Button>
              <Button
                variant="outlined"
                color="error"
                startIcon={<DeleteIcon />}
                onClick={deleteModel}
                disabled={loading}
              >
                Delete
              </Button>
            </Box>
          </Box>
        </CardContent>
      </Card>
    );
  };

  const renderStats = () => {
    if (!stats) {
      return (
        <Card>
          <CardContent>
            <Typography variant="body2" color="text.secondary">
              No statistics available
            </Typography>
          </CardContent>
        </Card>
      );
    }

    return (
      <Grid container spacing={2}>
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography variant="body2" color="text.secondary">
                Total Detections
              </Typography>
              <Typography variant="h4">{stats.total_detections.toLocaleString()}</Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography variant="body2" color="text.secondary">
                Total Anomalies
              </Typography>
              <Typography variant="h4" color="error">
                {stats.total_anomalies.toLocaleString()}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {(stats.anomaly_rate * 100).toFixed(2)}% rate
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography variant="body2" color="text.secondary">
                Recent 24h
              </Typography>
              <Typography variant="h4">{stats.recent_24h}</Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Typography variant="body2" color="text.secondary">
                Recent 7d
              </Typography>
              <Typography variant="h4">{stats.recent_7d}</Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    );
  };

  const renderSeverityDistribution = () => {
    const data = getSeverityChartData();

    if (data.every((d) => d.value === 0)) {
      return (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Severity Distribution
            </Typography>
            <Typography variant="body2" color="text.secondary">
              No anomalies detected yet
            </Typography>
          </CardContent>
        </Card>
      );
    }

    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Severity Distribution
          </Typography>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <RechartsTooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    );
  };

  const renderTrainingMetrics = () => {
    if (!trainingMetrics) return null;

    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Last Training Results
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={6} md={3}>
              <Typography variant="body2" color="text.secondary">
                Samples
              </Typography>
              <Typography variant="h6">
                {trainingMetrics.training_samples.toLocaleString()}
              </Typography>
            </Grid>
            <Grid item xs={6} md={3}>
              <Typography variant="body2" color="text.secondary">
                Features
              </Typography>
              <Typography variant="h6">{trainingMetrics.n_features}</Typography>
            </Grid>
            <Grid item xs={6} md={3}>
              <Typography variant="body2" color="text.secondary">
                Anomalies Found
              </Typography>
              <Typography variant="h6">
                {trainingMetrics.n_anomalies_detected.toLocaleString()}
              </Typography>
            </Grid>
            <Grid item xs={6} md={3}>
              <Typography variant="body2" color="text.secondary">
                Duration
              </Typography>
              <Typography variant="h6">
                {trainingMetrics.training_duration_seconds.toFixed(1)}s
              </Typography>
            </Grid>
          </Grid>
          <Box mt={2}>
            <Typography variant="body2" color="text.secondary">
              Score Range
            </Typography>
            <Box display="flex" alignItems="center" gap={2}>
              <Typography variant="body2">Min: {trainingMetrics.score_min.toFixed(3)}</Typography>
              <LinearProgress variant="determinate" value={50} style={{ flex: 1 }} />
              <Typography variant="body2">Max: {trainingMetrics.score_max.toFixed(3)}</Typography>
            </Box>
            <Typography variant="caption" color="text.secondary">
              Mean: {trainingMetrics.score_mean.toFixed(3)} ± {trainingMetrics.score_std.toFixed(3)}
            </Typography>
          </Box>
        </CardContent>
      </Card>
    );
  };

  const renderTrainDialog = () => {
    return (
      <Dialog
        open={showTrainDialog}
        onClose={() => setShowTrainDialog(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Train Anomaly Detection Model</DialogTitle>
        <DialogContent>
          <Box display="flex" flexDirection="column" gap={2} mt={2}>
            <TextField
              select
              label="Symbol"
              value={trainForm.symbol}
              onChange={(e) => setTrainForm({ ...trainForm, symbol: e.target.value })}
              fullWidth
            >
              <MenuItem value="BTCUSDT">BTCUSDT</MenuItem>
              <MenuItem value="ETHUSDT">ETHUSDT</MenuItem>
              <MenuItem value="SOLUSDT">SOLUSDT</MenuItem>
              <MenuItem value="BNBUSDT">BNBUSDT</MenuItem>
            </TextField>

            <TextField
              select
              label="Timeframe (minutes)"
              value={trainForm.timeframe}
              onChange={(e) => setTrainForm({ ...trainForm, timeframe: e.target.value })}
              fullWidth
            >
              <MenuItem value="1">1 minute</MenuItem>
              <MenuItem value="5">5 minutes</MenuItem>
              <MenuItem value="15">15 minutes</MenuItem>
              <MenuItem value="60">1 hour</MenuItem>
              <MenuItem value="240">4 hours</MenuItem>
            </TextField>

            <TextField
              type="number"
              label="Lookback Days"
              value={trainForm.lookback_days}
              onChange={(e) =>
                setTrainForm({ ...trainForm, lookback_days: parseInt(e.target.value) })
              }
              fullWidth
              helperText="Number of days of historical data to load (30-730)"
            />

            <TextField
              type="number"
              label="Contamination"
              value={trainForm.contamination}
              onChange={(e) =>
                setTrainForm({ ...trainForm, contamination: parseFloat(e.target.value) })
              }
              fullWidth
              helperText="Expected anomaly rate (0.01-0.10)"
              inputProps={{ step: 0.01, min: 0.01, max: 0.1 }}
            />

            <Alert severity="info">
              <Typography variant="body2">
                Training will load {trainForm.lookback_days} days of {trainForm.symbol} data (
                {trainForm.timeframe}-minute candles) from Bybit API. This may take 20-60 seconds
                depending on the amount of data.
              </Typography>
            </Alert>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowTrainDialog(false)} disabled={loading}>
            Cancel
          </Button>
          <Button
            onClick={trainModel}
            variant="contained"
            color="primary"
            disabled={loading}
            startIcon={loading ? <CircularProgress size={20} /> : <TrainIcon />}
          >
            {loading ? 'Training...' : 'Train Model'}
          </Button>
        </DialogActions>
      </Dialog>
    );
  };

  // ========================================================================
  // Main Render
  // ========================================================================

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" gutterBottom>
            Anomaly Detection
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Real-time anomaly detection using Isolation Forest on Bybit historical data
          </Typography>
        </Box>
        <Box display="flex" gap={1}>
          <Tooltip title={autoRefresh ? 'Auto-refresh enabled' : 'Auto-refresh disabled'}>
            <IconButton
              color={autoRefresh ? 'primary' : 'default'}
              onClick={() => setAutoRefresh(!autoRefresh)}
            >
              <TimelineIcon />
            </IconButton>
          </Tooltip>
          <IconButton onClick={fetchAllData} disabled={loading}>
            <RefreshIcon />
          </IconButton>
          {!modelInfo?.is_trained && (
            <Button
              variant="contained"
              color="primary"
              startIcon={<TrainIcon />}
              onClick={() => setShowTrainDialog(true)}
            >
              Train Model
            </Button>
          )}
        </Box>
      </Box>

      {/* Alerts */}
      {error && (
        <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      {success && (
        <Alert severity="success" onClose={() => setSuccess(null)} sx={{ mb: 2 }}>
          {success}
        </Alert>
      )}

      {/* Model Status */}
      <Box mb={3}>{renderModelStatus()}</Box>

      {/* Statistics */}
      <Box mb={3}>{renderStats()}</Box>

      {/* Charts */}
      <Grid container spacing={3} mb={3}>
        <Grid item xs={12} md={6}>
          {renderSeverityDistribution()}
        </Grid>
        <Grid item xs={12} md={6}>
          {renderTrainingMetrics()}
        </Grid>
      </Grid>

      {/* Model Details */}
      {modelInfo?.is_trained && (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Model Configuration
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <Typography variant="body2" color="text.secondary">
                  Model Version
                </Typography>
                <Typography variant="body1">{modelInfo.model_version}</Typography>
              </Grid>
              <Grid item xs={12} md={6}>
                <Typography variant="body2" color="text.secondary">
                  Contamination
                </Typography>
                <Typography variant="body1">
                  {(modelInfo.contamination * 100).toFixed(1)}%
                </Typography>
              </Grid>
              <Grid item xs={12} md={6}>
                <Typography variant="body2" color="text.secondary">
                  Number of Features
                </Typography>
                <Typography variant="body1">{modelInfo.n_features}</Typography>
              </Grid>
              <Grid item xs={12} md={6}>
                <Typography variant="body2" color="text.secondary">
                  Model Path
                </Typography>
                <Typography variant="body1" style={{ fontSize: '0.8rem', wordBreak: 'break-all' }}>
                  {modelInfo.model_path || 'N/A'}
                </Typography>
              </Grid>
            </Grid>

            <Box mt={3}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Severity Thresholds
              </Typography>
              <Box display="flex" gap={2}>
                <Chip
                  icon={<InfoIcon />}
                  label={`Info: ${modelInfo.severity_thresholds.info}`}
                  style={{ backgroundColor: SEVERITY_COLORS.info, color: 'white' }}
                />
                <Chip
                  icon={<WarningIcon />}
                  label={`Warning: ${modelInfo.severity_thresholds.warning}`}
                  style={{ backgroundColor: SEVERITY_COLORS.warning, color: 'white' }}
                />
                <Chip
                  icon={<ErrorIcon />}
                  label={`Critical: ${modelInfo.severity_thresholds.critical}`}
                  style={{ backgroundColor: SEVERITY_COLORS.critical, color: 'white' }}
                />
              </Box>
            </Box>

            <Box mt={3}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Features ({modelInfo.feature_names.length})
              </Typography>
              <Box display="flex" flexWrap="wrap" gap={1}>
                {modelInfo.feature_names.slice(0, 15).map((feature, index) => (
                  <Chip key={index} label={feature} size="small" variant="outlined" />
                ))}
                {modelInfo.feature_names.length > 15 && (
                  <Chip
                    label={`+${modelInfo.feature_names.length - 15} more`}
                    size="small"
                    variant="outlined"
                  />
                )}
              </Box>
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Train Dialog */}
      {renderTrainDialog()}
    </Container>
  );
};

export default AnomalyDetectionDashboard;
