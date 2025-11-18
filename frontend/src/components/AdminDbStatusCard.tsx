import React, { useEffect, useState } from 'react';
import { Card, CardContent, Typography, TextField, Button, Stack, Alert, Tooltip } from '@mui/material';

type Status = { ok: boolean; connectivity: boolean; alembic_version?: string | null; info?: string | null };

const AdminDbStatusCard: React.FC = () => {
  const [user, setUser] = useState('admi');
  const [pass, setPass] = useState('admin');
  const [remember, setRemember] = useState(false);
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
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
  }, []);

  const fetchStatus = async () => {
    setLoading(true); setError(null);
    try {
      const hdrs: Record<string, string> = { 'Accept': 'application/json' };
      const b64 = btoa(`${user}:${pass}`);
      hdrs['Authorization'] = `Basic ${b64}`;
      // Try same-origin first (dev proxy), then fallback to localhost:8000
      let res = await fetch('/api/v1/admin/db/status', { headers: hdrs });
      if (!res.ok) {
        res = await fetch('http://localhost:8000/api/v1/admin/db/status', { headers: hdrs });
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const js: Status = await res.json();
      setStatus(js);
      if (remember) {
        try { localStorage.setItem('adminCreds', JSON.stringify({ user, pass })); } catch {}
      } else {
        try { localStorage.removeItem('adminCreds'); } catch {}
      }
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card variant="outlined" sx={{ maxWidth: 420 }}>
      <CardContent>
        <Stack spacing={1}>
          <Typography variant="h6">DB Status</Typography>
          <Stack direction="row" spacing={1}>
            <TextField size="small" label="User" value={user} onChange={(e) => setUser(e.target.value)} sx={{ width: 120 }} />
            <TextField size="small" label="Pass" type="password" value={pass} onChange={(e) => setPass(e.target.value)} sx={{ width: 160 }} />
            <Tooltip title="Persist credentials in localStorage for dev only">
              <Button variant={remember ? 'contained' : 'outlined'} size="small" onClick={() => setRemember((v) => !v)}>
                {remember ? 'Remember' : 'No Save'}
              </Button>
            </Tooltip>
            <Button variant="contained" size="small" onClick={fetchStatus} disabled={loading}>Check</Button>
          </Stack>
          {error && <Alert severity="error">{error}</Alert>}
          {status && (
            <Stack spacing={0.5} sx={{ fontFamily: 'monospace', fontSize: 13 }}>
              <div>ok: {String(status.ok)}</div>
              <div>connectivity: {String(status.connectivity)}</div>
              <div>alembic_version: {status.alembic_version || 'n/a'}</div>
              {status.info ? <div>info: {status.info}</div> : null}
            </Stack>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
};

export default AdminDbStatusCard;
