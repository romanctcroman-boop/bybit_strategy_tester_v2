/**
 * AutoML Strategy Optimization Dashboard
 *
 * Features:
 * - Create new optimization studies
 * - View study progress & results
 * - Visualize trial history
 * - Inspect Pareto front (multi-objective)
 * - Export study results
 *
 * Phase: 4.4 (ML-Powered Features)
 * Author: Bybit Strategy Tester Team
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';

// ============================================================================
// Types
// ============================================================================

interface Study {
  study_name: string;
  status: 'created' | 'running' | 'completed' | 'failed';
  n_trials: number;
  n_completed: number;
  created_at: string;
  best_params?: Record<string, any>;
  best_values?: Record<string, number>;
}

interface Trial {
  trial_number: number;
  params: Record<string, any>;
  values?: Record<string, number>;
  state: 'COMPLETE' | 'PRUNED' | 'FAIL' | 'RUNNING';
  datetime_start?: string;
  datetime_complete?: string;
  duration_seconds?: number;
}

interface CreateStudyForm {
  strategy_id: number;
  symbol: string;
  timeframe: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  n_trials: number;
  n_jobs: number;
  objectives: string[];
  param_space: Record<string, any>;
  sampler: 'tpe' | 'random' | 'cmaes';
  pruner: 'median' | 'hyperband' | 'none';
}

// ============================================================================
// Main Component
// ============================================================================

const AutoMLDashboard: React.FC = () => {
  const [studies, setStudies] = useState<Study[]>([]);
  const [selectedStudy, setSelectedStudy] = useState<Study | null>(null);
  const [trials, setTrials] = useState<Trial[]>([]);
  const [paretoFront, setParetoFront] = useState<Trial[]>([]);

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch studies on mount
  useEffect(() => {
    fetchStudies();
  }, []);

  // Auto-refresh every 10s
  useEffect(() => {
    const interval = setInterval(fetchStudies, 10000);
    return () => clearInterval(interval);
  }, []);

  // ========================================================================
  // API Calls
  // ========================================================================

  const fetchStudies = async () => {
    try {
      const response = await axios.get<Study[]>('/api/v1/automl/studies');
      setStudies(response.data);
      setError(null);
    } catch (err: any) {
      setError(`Failed to fetch studies: ${err.message}`);
    }
  };

  const fetchTrials = async (studyName: string) => {
    try {
      const response = await axios.get<Trial[]>(
        `/api/v1/automl/studies/${studyName}/trials?limit=100`
      );
      setTrials(response.data);
      setError(null);
    } catch (err: any) {
      setError(`Failed to fetch trials: ${err.message}`);
    }
  };

  const fetchParetoFront = async (studyName: string) => {
    try {
      const response = await axios.get(`/api/v1/automl/studies/${studyName}/pareto`);
      setParetoFront(response.data.pareto_trials || []);
      setError(null);
    } catch {
      // Pareto front only available for multi-objective
      setParetoFront([]);
    }
  };

  const createStudy = async (form: CreateStudyForm) => {
    setLoading(true);
    try {
      await axios.post('/api/v1/automl/studies', form);
      await fetchStudies();
      setShowCreateModal(false);
      setError(null);
    } catch (err: any) {
      setError(`Failed to create study: ${err.response?.data?.detail || err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const startOptimization = async (studyName: string) => {
    setLoading(true);
    try {
      await axios.post(`/api/v1/automl/studies/${studyName}/start`);
      await fetchStudies();
      setError(null);
    } catch (err: any) {
      setError(`Failed to start optimization: ${err.response?.data?.detail || err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const deleteStudy = async (studyName: string) => {
    if (!confirm(`Delete study "${studyName}"? This cannot be undone.`)) {
      return;
    }

    setLoading(true);
    try {
      await axios.delete(`/api/v1/automl/studies/${studyName}`);
      await fetchStudies();
      if (selectedStudy?.study_name === studyName) {
        setSelectedStudy(null);
        setTrials([]);
        setParetoFront([]);
      }
      setError(null);
    } catch (err: any) {
      setError(`Failed to delete study: ${err.response?.data?.detail || err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const exportStudy = async (studyName: string) => {
    try {
      const response = await axios.get(`/api/v1/automl/studies/${studyName}/export`);
      const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${studyName}.json`;
      a.click();
      window.URL.revokeObjectURL(url);
      setError(null);
    } catch (err: any) {
      setError(`Failed to export study: ${err.message}`);
    }
  };

  // ========================================================================
  // Event Handlers
  // ========================================================================

  const handleSelectStudy = async (study: Study) => {
    setSelectedStudy(study);
    await fetchTrials(study.study_name);
    await fetchParetoFront(study.study_name);
  };

  // ========================================================================
  // Render
  // ========================================================================

  return (
    <div style={{ padding: '24px', background: '#0f172a', minHeight: '100vh', color: '#fff' }}>
      {/* Header */}
      <div style={{ marginBottom: '32px' }}>
        <h1 style={{ fontSize: '32px', fontWeight: 'bold', marginBottom: '8px' }}>
          🤖 AutoML Strategy Optimization
        </h1>
        <p style={{ color: '#94a3b8' }}>
          Bayesian hyperparameter optimization with Optuna • Multi-objective • Pruning • Parallel
          execution
        </p>
      </div>

      {/* Error Alert */}
      {error && (
        <div
          style={{
            background: '#7f1d1d',
            border: '1px solid #dc2626',
            padding: '12px 16px',
            borderRadius: '6px',
            marginBottom: '24px',
          }}
        >
          <strong>Error:</strong> {error}
          <button
            onClick={() => setError(null)}
            style={{
              float: 'right',
              background: 'transparent',
              border: 'none',
              color: '#fff',
              cursor: 'pointer',
            }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Actions */}
      <div style={{ marginBottom: '24px', display: 'flex', gap: '12px' }}>
        <button
          onClick={() => setShowCreateModal(true)}
          style={{
            background: '#3b82f6',
            color: '#fff',
            padding: '10px 20px',
            borderRadius: '6px',
            border: 'none',
            cursor: 'pointer',
            fontWeight: '500',
          }}
        >
          ➕ Create Study
        </button>

        <button
          onClick={fetchStudies}
          style={{
            background: '#1e293b',
            color: '#fff',
            padding: '10px 20px',
            borderRadius: '6px',
            border: '1px solid #334155',
            cursor: 'pointer',
          }}
        >
          🔄 Refresh
        </button>
      </div>

      {/* Studies Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '24px' }}>
        {/* Study List */}
        <div>
          <h2 style={{ fontSize: '20px', fontWeight: 'bold', marginBottom: '16px' }}>
            Studies ({studies.length})
          </h2>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {studies.length === 0 && (
              <div style={{ padding: '48px', textAlign: 'center', color: '#64748b' }}>
                No studies yet. Create your first optimization study!
              </div>
            )}

            {studies.map((study) => (
              <StudyCard
                key={study.study_name}
                study={study}
                isSelected={selectedStudy?.study_name === study.study_name}
                onSelect={() => handleSelectStudy(study)}
                onStart={() => startOptimization(study.study_name)}
                onDelete={() => deleteStudy(study.study_name)}
                onExport={() => exportStudy(study.study_name)}
              />
            ))}
          </div>
        </div>

        {/* Study Details */}
        <div>
          {selectedStudy ? (
            <StudyDetails study={selectedStudy} trials={trials} paretoFront={paretoFront} />
          ) : (
            <div
              style={{
                background: '#1e293b',
                padding: '48px',
                borderRadius: '8px',
                textAlign: 'center',
                color: '#64748b',
              }}
            >
              Select a study to view details
            </div>
          )}
        </div>
      </div>

      {/* Create Study Modal */}
      {showCreateModal && (
        <CreateStudyModal
          onClose={() => setShowCreateModal(false)}
          onCreate={createStudy}
          loading={loading}
        />
      )}
    </div>
  );
};

// ============================================================================
// Study Card Component
// ============================================================================

interface StudyCardProps {
  study: Study;
  isSelected: boolean;
  onSelect: () => void;
  onStart: () => void;
  onDelete: () => void;
  onExport: () => void;
}

const StudyCard: React.FC<StudyCardProps> = ({
  study,
  isSelected,
  onSelect,
  onStart,
  onDelete,
  onExport,
}) => {
  const statusColors: Record<string, string> = {
    created: '#3b82f6',
    running: '#eab308',
    completed: '#10b981',
    failed: '#ef4444',
  };

  return (
    <div
      onClick={onSelect}
      style={{
        background: isSelected ? '#1e40af20' : '#1e293b',
        border: `2px solid ${isSelected ? '#3b82f6' : '#334155'}`,
        padding: '16px',
        borderRadius: '8px',
        cursor: 'pointer',
        transition: 'all 0.2s',
      }}
    >
      {/* Status Badge */}
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
        <div
          style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            background: statusColors[study.status],
            marginRight: '8px',
          }}
        />
        <span style={{ fontSize: '12px', color: '#94a3b8', textTransform: 'uppercase' }}>
          {study.status}
        </span>
      </div>

      {/* Study Name */}
      <h3
        style={{
          fontSize: '14px',
          fontWeight: '600',
          marginBottom: '8px',
          wordBreak: 'break-word',
        }}
      >
        {study.study_name}
      </h3>

      {/* Progress */}
      <div style={{ marginBottom: '12px' }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: '12px',
            marginBottom: '4px',
          }}
        >
          <span style={{ color: '#94a3b8' }}>Trials</span>
          <span style={{ color: '#fff' }}>
            {study.n_completed} / {study.n_trials}
          </span>
        </div>
        <div style={{ width: '100%', height: '4px', background: '#334155', borderRadius: '2px' }}>
          <div
            style={{
              width: `${(study.n_completed / study.n_trials) * 100}%`,
              height: '100%',
              background: '#3b82f6',
              borderRadius: '2px',
            }}
          />
        </div>
      </div>

      {/* Best Values */}
      {study.best_values && (
        <div style={{ marginBottom: '12px' }}>
          {Object.entries(study.best_values).map(([key, value]) => (
            <div key={key} style={{ fontSize: '12px', color: '#94a3b8' }}>
              <span style={{ textTransform: 'capitalize' }}>{key.replace(/_/g, ' ')}: </span>
              <span style={{ color: '#10b981', fontWeight: '600' }}>
                {typeof value === 'number' ? value.toFixed(3) : value}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Actions */}
      <div style={{ display: 'flex', gap: '8px' }}>
        {study.status === 'created' && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onStart();
            }}
            style={{
              flex: 1,
              background: '#10b981',
              color: '#fff',
              padding: '6px 12px',
              borderRadius: '4px',
              border: 'none',
              cursor: 'pointer',
              fontSize: '12px',
            }}
          >
            ▶ Start
          </button>
        )}

        <button
          onClick={(e) => {
            e.stopPropagation();
            onExport();
          }}
          style={{
            flex: 1,
            background: '#1e293b',
            color: '#fff',
            padding: '6px 12px',
            borderRadius: '4px',
            border: '1px solid #334155',
            cursor: 'pointer',
            fontSize: '12px',
          }}
        >
          📥 Export
        </button>

        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          style={{
            flex: 1,
            background: '#7f1d1d',
            color: '#fff',
            padding: '6px 12px',
            borderRadius: '4px',
            border: 'none',
            cursor: 'pointer',
            fontSize: '12px',
          }}
        >
          🗑️ Delete
        </button>
      </div>
    </div>
  );
};

// ============================================================================
// Study Details Component
// ============================================================================

interface StudyDetailsProps {
  study: Study;
  trials: Trial[];
  paretoFront: Trial[];
}

const StudyDetails: React.FC<StudyDetailsProps> = ({ study, trials, paretoFront }) => {
  const [activeTab, setActiveTab] = useState<'trials' | 'pareto' | 'params'>('trials');

  return (
    <div style={{ background: '#1e293b', padding: '24px', borderRadius: '8px' }}>
      <h2 style={{ fontSize: '20px', fontWeight: 'bold', marginBottom: '16px' }}>
        {study.study_name}
      </h2>

      {/* Tabs */}
      <div
        style={{
          display: 'flex',
          gap: '8px',
          marginBottom: '24px',
          borderBottom: '1px solid #334155',
        }}
      >
        <Tab
          label="Trials"
          count={trials.length}
          active={activeTab === 'trials'}
          onClick={() => setActiveTab('trials')}
        />
        <Tab
          label="Pareto Front"
          count={paretoFront.length}
          active={activeTab === 'pareto'}
          onClick={() => setActiveTab('pareto')}
        />
        <Tab
          label="Best Params"
          active={activeTab === 'params'}
          onClick={() => setActiveTab('params')}
        />
      </div>

      {/* Tab Content */}
      {activeTab === 'trials' && <TrialsTable trials={trials} />}
      {activeTab === 'pareto' && <ParetoFrontTable trials={paretoFront} />}
      {activeTab === 'params' && <BestParamsView study={study} />}
    </div>
  );
};

// ============================================================================
// Tab Component
// ============================================================================

interface TabProps {
  label: string;
  count?: number;
  active: boolean;
  onClick: () => void;
}

const Tab: React.FC<TabProps> = ({ label, count, active, onClick }) => (
  <button
    onClick={onClick}
    style={{
      background: 'transparent',
      border: 'none',
      color: active ? '#3b82f6' : '#94a3b8',
      padding: '8px 16px',
      borderBottom: `2px solid ${active ? '#3b82f6' : 'transparent'}`,
      cursor: 'pointer',
      fontWeight: active ? '600' : '400',
    }}
  >
    {label} {count !== undefined && `(${count})`}
  </button>
);

// ============================================================================
// Trials Table
// ============================================================================

const TrialsTable: React.FC<{ trials: Trial[] }> = ({ trials }) => {
  if (trials.length === 0) {
    return (
      <div style={{ padding: '48px', textAlign: 'center', color: '#64748b' }}>No trials yet</div>
    );
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #334155' }}>
            <th style={{ padding: '12px', textAlign: 'left', color: '#94a3b8', fontSize: '12px' }}>
              Trial #
            </th>
            <th style={{ padding: '12px', textAlign: 'left', color: '#94a3b8', fontSize: '12px' }}>
              State
            </th>
            <th style={{ padding: '12px', textAlign: 'left', color: '#94a3b8', fontSize: '12px' }}>
              Values
            </th>
            <th style={{ padding: '12px', textAlign: 'left', color: '#94a3b8', fontSize: '12px' }}>
              Duration
            </th>
          </tr>
        </thead>
        <tbody>
          {trials.map((trial) => (
            <tr key={trial.trial_number} style={{ borderBottom: '1px solid #334155' }}>
              <td style={{ padding: '12px', fontSize: '14px' }}>#{trial.trial_number}</td>
              <td style={{ padding: '12px' }}>
                <span
                  style={{
                    padding: '4px 8px',
                    borderRadius: '4px',
                    fontSize: '12px',
                    background: trial.state === 'COMPLETE' ? '#10b98120' : '#ef444420',
                    color: trial.state === 'COMPLETE' ? '#10b981' : '#ef4444',
                  }}
                >
                  {trial.state}
                </span>
              </td>
              <td style={{ padding: '12px', fontSize: '12px', color: '#94a3b8' }}>
                {trial.values
                  ? Object.entries(trial.values)
                      .map(([k, v]) => `${k}: ${v.toFixed(3)}`)
                      .join(', ')
                  : '-'}
              </td>
              <td style={{ padding: '12px', fontSize: '12px', color: '#94a3b8' }}>
                {trial.duration_seconds ? `${trial.duration_seconds.toFixed(1)}s` : '-'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

// ============================================================================
// Pareto Front Table
// ============================================================================

const ParetoFrontTable: React.FC<{ trials: Trial[] }> = ({ trials }) => {
  if (trials.length === 0) {
    return (
      <div style={{ padding: '48px', textAlign: 'center', color: '#64748b' }}>
        No Pareto front available (single-objective study or no completed trials)
      </div>
    );
  }

  return (
    <div>
      <p style={{ color: '#94a3b8', marginBottom: '16px', fontSize: '14px' }}>
        These {trials.length} trials represent the Pareto-optimal solutions (non-dominated)
      </p>
      <TrialsTable trials={trials} />
    </div>
  );
};

// ============================================================================
// Best Params View
// ============================================================================

const BestParamsView: React.FC<{ study: Study }> = ({ study }) => {
  if (!study.best_params) {
    return (
      <div style={{ padding: '48px', textAlign: 'center', color: '#64748b' }}>
        No best params yet
      </div>
    );
  }

  return (
    <div>
      <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '16px' }}>Best Parameters</h3>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px' }}>
        {Object.entries(study.best_params).map(([key, value]) => (
          <div key={key} style={{ background: '#0f172a', padding: '12px', borderRadius: '6px' }}>
            <div style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '4px' }}>{key}</div>
            <div style={{ fontSize: '16px', fontWeight: '600', color: '#fff' }}>
              {typeof value === 'number' ? value.toFixed(4) : String(value)}
            </div>
          </div>
        ))}
      </div>

      {study.best_values && (
        <div style={{ marginTop: '24px' }}>
          <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '16px' }}>Best Values</h3>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px' }}>
            {Object.entries(study.best_values).map(([key, value]) => (
              <div
                key={key}
                style={{ background: '#0f172a', padding: '12px', borderRadius: '6px' }}
              >
                <div style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '4px' }}>
                  {key.replace(/_/g, ' ').toUpperCase()}
                </div>
                <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#10b981' }}>
                  {typeof value === 'number' ? value.toFixed(3) : String(value)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// ============================================================================
// Create Study Modal
// ============================================================================

interface CreateStudyModalProps {
  onClose: () => void;
  onCreate: (form: CreateStudyForm) => void;
  loading: boolean;
}

const CreateStudyModal: React.FC<CreateStudyModalProps> = ({ onClose, onCreate, loading }) => {
  const [form, setForm] = useState<CreateStudyForm>({
    strategy_id: 1,
    symbol: 'BTCUSDT',
    timeframe: '1h',
    start_date: '2024-01-01T00:00:00Z',
    end_date: '2024-12-31T23:59:59Z',
    initial_capital: 10000,
    n_trials: 100,
    n_jobs: 4,
    objectives: ['sharpe_ratio'],
    param_space: {
      ema_short: { type: 'int', low: 5, high: 50 },
      ema_long: { type: 'int', low: 20, high: 200 },
    },
    sampler: 'tpe',
    pruner: 'median',
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onCreate(form);
  };

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0,0,0,0.7)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: '#1e293b',
          padding: '24px',
          borderRadius: '8px',
          width: '600px',
          maxHeight: '80vh',
          overflowY: 'auto',
        }}
      >
        <h2 style={{ fontSize: '20px', fontWeight: 'bold', marginBottom: '24px' }}>
          Create Optimization Study
        </h2>

        <form
          onSubmit={handleSubmit}
          style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}
        >
          <div>
            <label
              style={{ display: 'block', marginBottom: '8px', fontSize: '14px', color: '#94a3b8' }}
            >
              Strategy ID
            </label>
            <input
              type="number"
              value={form.strategy_id}
              onChange={(e) => setForm({ ...form, strategy_id: Number(e.target.value) })}
              style={{
                width: '100%',
                padding: '8px 12px',
                background: '#0f172a',
                border: '1px solid #334155',
                borderRadius: '6px',
                color: '#fff',
              }}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div>
              <label
                style={{
                  display: 'block',
                  marginBottom: '8px',
                  fontSize: '14px',
                  color: '#94a3b8',
                }}
              >
                Symbol
              </label>
              <input
                type="text"
                value={form.symbol}
                onChange={(e) => setForm({ ...form, symbol: e.target.value })}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  background: '#0f172a',
                  border: '1px solid #334155',
                  borderRadius: '6px',
                  color: '#fff',
                }}
              />
            </div>

            <div>
              <label
                style={{
                  display: 'block',
                  marginBottom: '8px',
                  fontSize: '14px',
                  color: '#94a3b8',
                }}
              >
                Timeframe
              </label>
              <select
                value={form.timeframe}
                onChange={(e) => setForm({ ...form, timeframe: e.target.value })}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  background: '#0f172a',
                  border: '1px solid #334155',
                  borderRadius: '6px',
                  color: '#fff',
                }}
              >
                <option value="1m">1m</option>
                <option value="5m">5m</option>
                <option value="15m">15m</option>
                <option value="1h">1h</option>
                <option value="4h">4h</option>
                <option value="1d">1d</option>
              </select>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div>
              <label
                style={{
                  display: 'block',
                  marginBottom: '8px',
                  fontSize: '14px',
                  color: '#94a3b8',
                }}
              >
                Trials
              </label>
              <input
                type="number"
                value={form.n_trials}
                onChange={(e) => setForm({ ...form, n_trials: Number(e.target.value) })}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  background: '#0f172a',
                  border: '1px solid #334155',
                  borderRadius: '6px',
                  color: '#fff',
                }}
              />
            </div>

            <div>
              <label
                style={{
                  display: 'block',
                  marginBottom: '8px',
                  fontSize: '14px',
                  color: '#94a3b8',
                }}
              >
                Parallel Jobs
              </label>
              <input
                type="number"
                value={form.n_jobs}
                onChange={(e) => setForm({ ...form, n_jobs: Number(e.target.value) })}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  background: '#0f172a',
                  border: '1px solid #334155',
                  borderRadius: '6px',
                  color: '#fff',
                }}
              />
            </div>
          </div>

          <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
            <button
              type="submit"
              disabled={loading}
              style={{
                flex: 1,
                background: '#3b82f6',
                color: '#fff',
                padding: '10px 20px',
                borderRadius: '6px',
                border: 'none',
                cursor: loading ? 'not-allowed' : 'pointer',
                fontWeight: '500',
                opacity: loading ? 0.5 : 1,
              }}
            >
              {loading ? '⏳ Creating...' : '✅ Create Study'}
            </button>

            <button
              type="button"
              onClick={onClose}
              style={{
                flex: 1,
                background: '#1e293b',
                color: '#fff',
                padding: '10px 20px',
                borderRadius: '6px',
                border: '1px solid #334155',
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AutoMLDashboard;
