import React, { useState } from 'react';
import { Container, Typography, Button, TextField, Stack } from '@mui/material';
import { useDataUploadStore } from '../store/dataUpload';
import { useNotify } from '../components/NotificationsProvider';
import { useAsyncAction } from '../hooks/useAsyncAction';
import { applyFieldErrors, validateSymbol } from '../utils/forms';

const DataUploadPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [interval, setInterval] = useState('1');
  const { upload, uploading } = useDataUploadStore();
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

  const { run: submit, loading: submitting } = useAsyncAction(async () => {
    if (!validate()) return;
    const fd = new FormData();
    if (file) fd.append('file', file);
    if (symbol) fd.append('symbol', symbol);
    if (interval) fd.append('interval', interval);
    const res = await upload(fd);
    notify({ message: 'Upload complete', severity: 'success' });
    return res;
  }, {
    onError: (e) => {
      applyFieldErrors(setFormErrors, e);
      const msg = e?.friendlyMessage || e?.message || 'Upload failed';
      notify({ message: msg, severity: 'error' });
    }
  });

  return (
    <Container>
      <Typography variant="h4">Upload Market Data</Typography>
      <Stack spacing={2} sx={{ mt: 2 }}>
        <Stack direction="row" spacing={2}>
          <TextField label="Symbol" size="small" value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} sx={{ width: 200 }} error={!!formErrors.symbol} helperText={formErrors.symbol || ' ' } />
          <TextField label="Interval" size="small" value={interval} onChange={(e) => setInterval(e.target.value)} sx={{ width: 200 }} error={!!formErrors.interval} helperText={formErrors.interval || 'Bybit: 1,3,5,15,60,240,D,W'} />
        </Stack>
        <div>
          <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          {formErrors.file && <div style={{ color: 'crimson', marginTop: 4 }}>{formErrors.file}</div>}
        </div>
        <div>
          <Button variant="contained" onClick={() => submit()} disabled={uploading || submitting}>
            {uploading || submitting ? 'Uploading…' : 'Upload'}
          </Button>
        </div>
      </Stack>
    </Container>
  );
};

export default DataUploadPage;
