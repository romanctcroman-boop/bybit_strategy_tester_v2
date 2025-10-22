import React, { useEffect, useRef, useState } from 'react';
import { adminBackfill, adminTaskStatus, adminListRuns, adminGetProgress, adminResetProgress, adminGetRun, adminArchive, adminRestore, adminListArchives, adminDeleteArchive } from '../services/adminApi';
import { useNotify } from '../components/NotificationsProvider';

const AdminBackfillPage: React.FC = () => {
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [interval, setInterval] = useState('1');
  const [lookback, setLookback] = useState(60);
  const [mode, setMode] = useState<'sync' | 'async'>('async');
  const [user, setUser] = useState('admi');
  const [pass, setPass] = useState('admin');
  const [remember, setRemember] = useState<boolean>(false);
  const [result, setResult] = useState<any>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<any>(null);
  const timerRef = useRef<number | null>(null);
  const [runs, setRuns] = useState<any[]>([]);
  const [runsTimer, setRunsTimer] = useState<number | null>(null);
  const [progress, setProgress] = useState<any>(null);
  const [liveRun, setLiveRun] = useState<any>(null);
  const [metrics, setMetrics] = useState<Record<string, number>>({});
  const [statusCounts, setStatusCounts] = useState<Record<string, number>>({});
  const [metricsTimer, setMetricsTimer] = useState<number | null>(null);
  const notify = useNotify();
  // Archive/Restore UI state
  const [archiveDir, setArchiveDir] = useState<string>('archives');
  const [archiveBeforeIso, setArchiveBeforeIso] = useState<string>('');
  const [archiveSymbol, setArchiveSymbol] = useState<string>('');
  const [archiveIntervalForPartition, setArchiveIntervalForPartition] = useState<string>('1');
  const [archiveBatchSize, setArchiveBatchSize] = useState<number>(5000);
  const [archiveMode, setArchiveMode] = useState<'sync' | 'async'>('sync');
  const [archiveResult, setArchiveResult] = useState<any>(null);

  const [restoreDir, setRestoreDir] = useState<string>('archives');
  const [restoreMode, setRestoreMode] = useState<'sync' | 'async'>('sync');
  const [restoreResult, setRestoreResult] = useState<any>(null);
  const [archivesDir, setArchivesDir] = useState<string>('archives');
  const [archives, setArchives] = useState<Array<{ path: string; size: number; modified: number }>>([]);

  useEffect(() => {
    // Restore creds from localStorage if present
    try {
      const raw = localStorage.getItem('adminCreds');
      if (raw) {
        const obj = JSON.parse(raw);
        if (obj && typeof obj.user === 'string' && typeof obj.pass === 'string') {
          setUser(obj.user);
          setPass(obj.pass);
          setRemember(true);
        }
      }
    } catch {}
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
      if (runsTimer) window.clearInterval(runsTimer);
      if (metricsTimer) window.clearInterval(metricsTimer);
    };
  }, []);

  const trigger = async () => {
    // Basic validation
    if (!symbol.trim()) {
      notify({ message: 'Symbol is required', severity: 'warning' });
      return;
    }
    if (!interval) {
      notify({ message: 'Interval is required', severity: 'warning' });
      return;
    }
    if (!user || !pass) {
      notify({ message: 'Admin credentials are required', severity: 'warning' });
      return;
    }
    setResult(null);
    setStatus(null);
    setTaskId(null);
    setProgress(null);
    try {
      const auth = { user, pass };
      // Save creds if remember checked
      try {
        if (remember) {
          localStorage.setItem('adminCreds', JSON.stringify(auth));
        } else {
          localStorage.removeItem('adminCreds');
        }
      } catch {}
      const payload = await adminBackfill({ symbol, interval, lookback_minutes: lookback, mode }, auth);
      setResult(payload);
      notify({ message: 'Backfill triggered', severity: 'success' });
      // Fetch current progress for the symbol/interval
      try {
        const pg = await adminGetProgress(symbol, interval, auth);
        setProgress(pg);
      } catch {}
      if (payload?.task_id) {
        setTaskId(payload.task_id);
        // start polling
        timerRef.current = window.setInterval(async () => {
          try {
            const s = await adminTaskStatus(payload.task_id, auth);
            setStatus(s);
            // If we have a run_id, also refresh its details
            if (payload.run_id) {
              try { setLiveRun(await adminGetRun(payload.run_id, auth)); } catch {}
            }
            if (s?.ready) {
              if (timerRef.current) window.clearInterval(timerRef.current);
              timerRef.current = null;
            }
          } catch (e) {
            // stop on error
            if (timerRef.current) window.clearInterval(timerRef.current);
            timerRef.current = null;
            notify({ message: 'Task polling error', severity: 'error' });
          }
        }, 1500) as unknown as number;
      }
    } catch (e: any) {
      setResult({ error: e?.message || String(e) });
      notify({ message: `Backfill error: ${e?.message || e}`, severity: 'error' });
    }
  };

  const refreshRuns = async () => {
    try {
      const auth = { user, pass };
      const list = await adminListRuns(50, auth);
      setRuns(list);
    } catch {}
  };

  useEffect(() => {
    refreshRuns();
    const t = window.setInterval(() => { refreshRuns(); }, 5000) as unknown as number;
    setRunsTimer(t);
    return () => { if (t) window.clearInterval(t); };
  }, [user, pass]);

  const doResetProgress = async () => {
    const auth = { user, pass };
    await adminResetProgress(symbol, interval, auth);
    const pg = await adminGetProgress(symbol, interval, auth);
    setProgress(pg);
    notify({ message: 'Progress reset', severity: 'success' });
  };

  const fetchMetrics = async () => {
    try {
      let text: string | null = null;
      let res: Response | null = null;
      try {
        res = await fetch('/metrics');
        if (res.ok) text = await res.text();
      } catch {}
      if (!text) {
        // dev fallback when proxy isn't configured for /metrics
        try {
          res = await fetch('http://localhost:8000/metrics');
          if (res.ok) text = await res.text();
        } catch {}
      }
      if (!text) return;
      const lines = text.split(/\r?\n/);
      const totals: Record<string, number> = {};
      const runsByStatus: Record<string, number> = {};
      for (const line of lines) {
        if (!line || line.startsWith('#')) continue;
        const m = line.match(/^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{[^}]*\})?\s+([0-9\.]+)/);
        if (!m) continue;
        const name = m[1];
        const labels = m[2] || '';
        const val = Number(m[3]);
        if (Number.isNaN(val)) continue;
        totals[name] = (totals[name] || 0) + val;
        if (name === 'backfill_runs_total' && labels) {
          const lm = labels.match(/status=\"([^\"]+)\"/);
          if (lm) {
            const st = lm[1].toUpperCase();
            runsByStatus[st] = (runsByStatus[st] || 0) + val;
          }
        }
      }
      setMetrics(totals);
      setStatusCounts(runsByStatus);
    } catch {}
  };

  useEffect(() => {
    fetchMetrics();
    const t = window.setInterval(() => { fetchMetrics(); }, 5000) as unknown as number;
    setMetricsTimer(t);
    return () => { if (t) window.clearInterval(t); };
  }, []);

  const refreshArchives = async () => {
    try {
      const auth = { user, pass };
      const res = await adminListArchives(archivesDir, auth);
      setArchives(res.files || []);
    } catch (e) {}
  };

  return (
    <div style={{ padding: 16 }}>
      <h2>Admin Backfill</h2>
      <div style={{ display: 'grid', gridTemplateColumns: '160px 1fr', gap: 8, maxWidth: 560 }}>
        <label>Symbol</label>
        <input value={symbol} onChange={(e) => setSymbol(e.target.value)} />
        <label>Interval</label>
        <select value={interval} onChange={(e) => setInterval(e.target.value)}>
          {['1','3','5','15','30','60','240','D','W'].map((i) => (
            <option key={i} value={i}>{i}</option>
          ))}
        </select>
        <label>Lookback (min)</label>
        <input type="number" value={lookback} onChange={(e) => setLookback(Number(e.target.value || 0))} />
        <label>Mode</label>
        <select value={mode} onChange={(e) => setMode(e.target.value as any)}>
          <option value="sync">sync</option>
          <option value="async">async</option>
        </select>
        <label>Admin user</label>
        <input value={user} onChange={(e) => setUser(e.target.value)} />
        <label>Admin pass</label>
        <input type="password" value={pass} onChange={(e) => setPass(e.target.value)} />
        <div />
        <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
          Remember credentials (localStorage)
        </label>
      </div>
      <div style={{ marginTop: 12 }}>
        <button onClick={trigger}>Run Backfill</button>
        <button style={{ marginLeft: 8 }} onClick={doResetProgress}>Reset Progress</button>
        <button style={{ marginLeft: 8 }} onClick={() => adminGetProgress(symbol, interval, { user, pass }).then(setProgress)}>Refresh Progress</button>
      </div>
      {result && (
        <div style={{ marginTop: 16 }}>
          <h3>Response</h3>
          <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
      {taskId && (
        <div style={{ marginTop: 16 }}>
          <h3>Task status</h3>
          <div>taskId: {taskId}</div>
          <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(status, null, 2)}</pre>
        </div>
      )}
      {(result?.eta_sec !== undefined || status?.result?.eta_sec !== undefined) && (
        <div style={{ marginTop: 16 }}>
          <h3>Progress</h3>
          <div>ETA (sec): {result?.eta_sec ?? status?.result?.eta_sec ?? 'n/a'}</div>
          <div>Est pages left: {result?.est_pages_left ?? status?.result?.est_pages_left ?? 'n/a'}</div>
        </div>
      )}
      {progress && (
        <div style={{ marginTop: 16 }}>
          <h3>Cursor</h3>
          <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(progress, null, 2)}</pre>
        </div>
      )}
      <div style={{ marginTop: 24 }}>
        <h3>Metrics</h3>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <Badge label="upserts_total" value={metrics['backfill_upserts_total'] || 0} />
          <Badge label="pages_total" value={metrics['backfill_pages_total'] || 0} />
          <Badge label="runs_total" value={metrics['backfill_runs_total'] || 0} />
          <Badge label="runs_succeeded" value={statusCounts['SUCCEEDED'] || 0} />
          <Badge label="runs_failed" value={statusCounts['FAILED'] || 0} />
          <Badge label="runs_running" value={statusCounts['RUNNING'] || 0} />
        </div>
      </div>
      <div style={{ marginTop: 24 }}>
        <h3>Recent runs</h3>
        <table style={{ borderCollapse: 'collapse', width: '100%', maxWidth: 900 }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 4 }}>ID</th>
              <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 4 }}>Symbol</th>
              <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 4 }}>Interval</th>
              <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 4 }}>Status</th>
              <th style={{ textAlign: 'right', borderBottom: '1px solid #ccc', padding: 4 }}>Upserts</th>
              <th style={{ textAlign: 'right', borderBottom: '1px solid #ccc', padding: 4 }}>Pages</th>
              <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 4 }}>Started</th>
              <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 4 }}>Finished</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.id}>
                <td style={{ padding: 4 }}>
                  <a href="#" onClick={async (e) => { e.preventDefault(); try { const auth = { user, pass }; setLiveRun(await adminGetRun(r.id, auth)); } catch {} }}>{r.id}</a>
                </td>
                <td style={{ padding: 4 }}>{r.symbol}</td>
                <td style={{ padding: 4 }}>{r.interval}</td>
                <td style={{ padding: 4 }}>{r.status}</td>
                <td style={{ padding: 4, textAlign: 'right' }}>{r.upserts}</td>
                <td style={{ padding: 4, textAlign: 'right' }}>{r.pages}</td>
                <td style={{ padding: 4 }}>{r.started_at}</td>
                <td style={{ padding: 4 }}>{r.finished_at || ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {liveRun && (
        <div style={{ marginTop: 16 }}>
          <h3>Run details</h3>
          <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(liveRun, null, 2)}</pre>
        </div>
      )}

      <hr style={{ margin: '24px 0' }} />
      <h2>Archival</h2>
      <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr', gap: 8, maxWidth: 640 }}>
        <label>Output dir</label>
        <input value={archiveDir} onChange={(e) => setArchiveDir(e.target.value)} />
        <label>Before (ISO)</label>
        <input placeholder="e.g. 2025-01-02T00:00:00Z" value={archiveBeforeIso} onChange={(e) => setArchiveBeforeIso(e.target.value)} />
        <label>Symbol (optional)</label>
        <input placeholder="e.g. BTCUSDT" value={archiveSymbol} onChange={(e) => setArchiveSymbol(e.target.value)} />
        <label>Partition interval</label>
        <select value={archiveIntervalForPartition} onChange={(e) => setArchiveIntervalForPartition(e.target.value)}>
          {['1','3','5','15','30','60','240','D','W'].map((i) => (
            <option key={i} value={i}>{i}</option>
          ))}
        </select>
        <label>Batch size</label>
        <input type="number" value={archiveBatchSize} onChange={(e) => setArchiveBatchSize(Number(e.target.value || 0))} />
        <label>Mode</label>
        <select value={archiveMode} onChange={(e) => setArchiveMode(e.target.value as any)}>
          <option value="sync">sync</option>
          <option value="async">async</option>
        </select>
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <button onClick={async () => {
          try {
            const payload = await adminArchive({
              output_dir: archiveDir,
              before_iso: archiveBeforeIso || undefined,
              symbol: archiveSymbol || undefined,
              interval_for_partition: archiveIntervalForPartition,
              batch_size: archiveBatchSize,
              mode: archiveMode,
            }, { user, pass });
            setArchiveResult(payload);
            notify({ message: 'Archive triggered', severity: 'success' });
            // If async, start polling task status
            if (payload?.mode === 'async' && payload?.task_id) {
              const auth = { user, pass };
              let localTimer: number | null = null;
              localTimer = window.setInterval(async () => {
                try {
                  const st = await adminTaskStatus(payload.task_id, auth);
                  setArchiveResult(st);
                  if (st.ready) {
                    if (localTimer) window.clearInterval(localTimer);
                    localTimer = null;
                  }
                } catch (e) {
                  if (localTimer) window.clearInterval(localTimer);
                  localTimer = null;
                }
              }, 1500) as unknown as number;
            }
          } catch (e: any) {
            notify({ message: `Archive error: ${e?.message || e}`, severity: 'error' });
          }
        }}>Run archive</button>
      </div>
      {archiveResult && (
        <div style={{ marginTop: 8 }}>
          <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(archiveResult, null, 2)}</pre>
        </div>
      )}

      <h2 style={{ marginTop: 24 }}>Restore</h2>
      <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr', gap: 8, maxWidth: 640 }}>
        <label>Input dir</label>
        <input value={restoreDir} onChange={(e) => setRestoreDir(e.target.value)} />
        <label>Mode</label>
        <select value={restoreMode} onChange={(e) => setRestoreMode(e.target.value as any)}>
          <option value="sync">sync</option>
          <option value="async">async</option>
        </select>
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <button onClick={async () => {
          try {
            const payload = await adminRestore({ input_dir: restoreDir, mode: restoreMode }, { user, pass });
            setRestoreResult(payload);
            notify({ message: 'Restore triggered', severity: 'success' });
            if (payload?.mode === 'async' && payload?.task_id) {
              const auth = { user, pass };
              let localTimer: number | null = null;
              localTimer = window.setInterval(async () => {
                try {
                  const st = await adminTaskStatus(payload.task_id, auth);
                  setRestoreResult(st);
                  if (st.ready) {
                    if (localTimer) window.clearInterval(localTimer);
                    localTimer = null;
                  }
                } catch (e) {
                  if (localTimer) window.clearInterval(localTimer);
                  localTimer = null;
                }
              }, 1500) as unknown as number;
            }
          } catch (e: any) {
            notify({ message: `Restore error: ${e?.message || e}`, severity: 'error' });
          }
        }}>Run restore</button>
      </div>
      {restoreResult && (
        <div style={{ marginTop: 8 }}>
          <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(restoreResult, null, 2)}</pre>
        </div>
      )}

      <h2 style={{ marginTop: 24 }}>Archives Browser</h2>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <input style={{ width: 360 }} value={archivesDir} onChange={(e) => setArchivesDir(e.target.value)} placeholder="archives" />
        <button onClick={refreshArchives}>Refresh</button>
      </div>
      <div style={{ marginTop: 12, maxHeight: 300, overflow: 'auto', border: '1px solid #ddd' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 4 }}>Path</th>
              <th style={{ textAlign: 'right', borderBottom: '1px solid #ccc', padding: 4 }}>Size</th>
              <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 4 }}>Modified</th>
              <th style={{ textAlign: 'left', borderBottom: '1px solid #ccc', padding: 4 }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {archives.map((f) => (
              <tr key={f.path}>
                <td style={{ padding: 4, fontFamily: 'monospace' }}>{f.path}</td>
                <td style={{ padding: 4, textAlign: 'right' }}>{(f.size/1024).toFixed(1)} KB</td>
                <td style={{ padding: 4 }}>{new Date(f.modified*1000).toLocaleString()}</td>
                <td style={{ padding: 4 }}>
                  <button onClick={async () => {
                    try {
                      await adminDeleteArchive(f.path, { user, pass });
                      notify({ message: 'Deleted', severity: 'success' });
                      refreshArchives();
                    } catch (e: any) {
                      notify({ message: `Delete failed: ${e?.message || e}`, severity: 'error' });
                    }
                  }}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const Badge: React.FC<{ label: string; value: number }> = ({ label, value }) => (
  <span style={{ padding: '4px 8px', borderRadius: 12, background: '#eee', fontSize: 12 }}>
    <strong>{label}:</strong> {value}
  </span>
);

export default AdminBackfillPage;
