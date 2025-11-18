import React, { useEffect, useState } from 'react';
import { Container, Typography, Button, TextField, Stack, MenuItem } from '@mui/material';
import { useDataUploadStore } from '../store/dataUpload';
import { useNotify } from '../components/NotificationsProvider';
import { useAsyncAction } from '../hooks/useAsyncAction';
import { applyFieldErrors, validateSymbol } from '../utils/forms';
import api, { DataApi } from '../services/api';
import { TIMEFRAMES } from '../constants/timeframes';

const DataUploadPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [interval, setInterval] = useState('1');
  const { upload, uploading, progress, error: uploadError } = useDataUploadStore();
  const notify = useNotify();

  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  const validate = () => {
    const errs: Record<string, string> = {};
    if (!file) errs.file = 'Select a file';
    const symErr = validateSymbol(symbol);
    if (symErr) errs.symbol = symErr;
    if (!interval) errs.interval = 'Interval required';
    setFormErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const [lastResult, setLastResult] = useState<any | null>(null);
  const [uploads, setUploads] = useState<any[]>([]);

  useEffect(() => {
    (async () => {
      try {
        const r = await api.get('/marketdata/uploads');
        setUploads(r.data?.items || []);
      } catch {}
    })();
  }, []);

  const { run: submit, loading: submitting } = useAsyncAction(
    async () => {
      if (!validate()) return;
      const fd = new FormData();
      if (file) fd.append('file', file);
      if (symbol) fd.append('symbol', symbol);
      if (interval) fd.append('interval', interval);
      const res = await upload(fd);
      notify({ message: 'Upload complete', severity: 'success' });
      setLastResult(res);
      try {
        const r = await api.get('/marketdata/uploads');
        setUploads(r.data?.items || []);
      } catch {}
      return res;
    },
    {
      onError: (e) => {
        applyFieldErrors(setFormErrors, e);
        const msg = e?.friendlyMessage || e?.message || 'Upload failed';
        notify({ message: msg, severity: 'error' });
      },
    }
  );

  return (
    <Container>
      <Typography variant="h4">Upload Market Data</Typography>
      <Stack spacing={2} sx={{ mt: 2 }}>
        <Stack direction="row" spacing={2}>
          <TextField
            label="Symbol"
            size="small"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            sx={{ width: 200 }}
            error={!!formErrors.symbol}
            helperText={formErrors.symbol || ' '}
          />
          <TextField
            label="Interval"
            size="small"
            select
            value={interval}
            onChange={(e) => setInterval(e.target.value)}
            sx={{ width: 200 }}
            error={!!formErrors.interval}
            helperText={formErrors.interval || 'Bybit supported intervals'}
          >
            {TIMEFRAMES.map((tf) => (
              <MenuItem key={tf.value} value={tf.value}>
                {tf.label}
              </MenuItem>
            ))}
          </TextField>
        </Stack>
        <div>
          <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          {formErrors.file && (
            <div style={{ color: 'crimson', marginTop: 4 }}>{formErrors.file}</div>
          )}
        </div>
        {uploading && (
          <div style={{ height: 4, background: '#eee', position: 'relative' }}>
            <div
              style={{
                position: 'absolute',
                left: 0,
                top: 0,
                bottom: 0,
                width: `${progress}%`,
                background: '#1976d2',
                transition: 'width 120ms linear',
              }}
            />
          </div>
        )}
        {uploadError && <div style={{ color: 'crimson' }}>{uploadError}</div>}
        {lastResult && (
          <div style={{ background: '#f5f5f5', padding: 12, borderRadius: 8 }}>
            <div>
              <strong>Upload ID:</strong> {lastResult.upload_id}
            </div>
            <div>
              <strong>Filename:</strong> {lastResult.filename}
            </div>
            <div>
              <strong>Size:</strong> {lastResult.size} bytes
            </div>
            <div>
              <strong>Symbol:</strong> {lastResult.symbol}
            </div>
            <div>
              <strong>Interval:</strong> {lastResult.interval}
            </div>
            <div>
              <strong>Stored path:</strong> {lastResult.stored_path}
            </div>
          </div>
        )}
        <div>
          <Button variant="contained" onClick={() => submit()} disabled={uploading || submitting}>
            {uploading || submitting ? 'Uploading…' : 'Upload'}
          </Button>
        </div>
        <div>
          <Button
            size="small"
            variant="outlined"
            onClick={async () => {
              try {
                const r = await api.get('/marketdata/uploads');
                setUploads(r.data?.items || []);
              } catch (e: any) {
                notify({
                  message: e?.friendlyMessage || e?.message || 'Failed to load uploads',
                  severity: 'error',
                });
              }
            }}
          >
            Refresh uploads
          </Button>
        </div>
        {uploads.length > 0 && (
          <div>
            <Typography variant="h6" sx={{ mt: 1 }}>
              Recent uploads
            </Typography>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '2fr 1fr 1fr auto',
                gap: 8,
                alignItems: 'center',
              }}
            >
              <strong>Filename</strong>
              <strong>Size</strong>
              <strong>Upload ID</strong>
              <div />
              {uploads.map((u) => (
                <React.Fragment key={u.upload_id}>
                  <div>{u.filename}</div>
                  <div>{u.size}</div>
                  <div style={{ fontFamily: 'monospace' }}>{u.upload_id}</div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <Button
                      size="small"
                      variant="contained"
                      onClick={async () => {
                        try {
                          const res = await DataApi.ingestUpload(
                            u.upload_id,
                            symbol,
                            interval,
                            'csv'
                          );
                          notify({
                            message: `Ingested ${res.ingested} rows (WS updated: ${res.updated_working_set ?? 0})`,
                            severity: 'success',
                          });
                        } catch (e: any) {
                          notify({
                            message: e?.friendlyMessage || e?.message || 'Ingest failed',
                            severity: 'error',
                          });
                        }
                      }}
                    >
                      Ingest
                    </Button>
                    <Button
                      size="small"
                      color="error"
                      onClick={async () => {
                        try {
                          await api.delete(
                            `/marketdata/uploads/${encodeURIComponent(u.upload_id)}`
                          );
                          setUploads((arr) => arr.filter((x) => x.upload_id !== u.upload_id));
                          notify({ message: 'Deleted', severity: 'success' });
                        } catch (e: any) {
                          notify({
                            message: e?.friendlyMessage || e?.message || 'Delete failed',
                            severity: 'error',
                          });
                        }
                      }}
                    >
                      Delete
                    </Button>
                  </div>
                </React.Fragment>
              ))}
            </div>
          </div>
        )}
      </Stack>
    </Container>
  );
};

export default DataUploadPage;
