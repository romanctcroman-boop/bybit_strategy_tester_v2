import React, { useEffect, useRef, useState } from 'react';
import { Chip, Tooltip } from '@mui/material';

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

const ApiHealthIndicator: React.FC<{ intervalMs?: number }> = ({ intervalMs = 10000 }) => {
  const [ok, setOk] = useState<boolean | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);
  const timerRef = useRef<number | null>(null);

  const check = async () => {
    try {
      // Use fetch to avoid axios global interceptors / error toasts
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 5000);
      // Check real exchange connectivity via backend probe
      const res = await fetch('/api/v1/exchangez', { signal: ctrl.signal });
      clearTimeout(t);
      if (res.ok) {
        setOk(true);
        setLastError(null);
      } else {
        setOk(false);
        setLastError(`HTTP ${res.status}`);
      }
    } catch (e: any) {
      setOk(false);
      setLastError(e?.message || 'Network error');
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      await check();
      while (!cancelled) {
        await sleep(intervalMs);
        await check();
      }
    })();
    return () => {
      cancelled = true;
      if (timerRef.current) {
        window.clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [intervalMs]);

  const label = ok === null ? 'API: …' : ok ? 'API: OK' : 'API: DOWN';
  const color: 'default' | 'success' | 'warning' | 'error' =
    ok == null ? 'warning' : ok ? 'success' : 'error';
  const tip = lastError || (ok ? 'Bybit reachable' : 'Bybit unreachable');

  return (
    <Tooltip title={tip}>
      <Chip size="small" label={label} color={color} />
    </Tooltip>
  );
};

export default ApiHealthIndicator;
