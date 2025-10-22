import React, { useEffect, useState } from 'react';
import { Chip, Tooltip } from '@mui/material';
import WSClient from '../services/ws';

const defaultWsUrl = (() => {
  const envUrl = (window as any).__env?.REACT_APP_WS_URL as string | undefined;
  if (envUrl) return envUrl;
  // Prefer same-origin ws via Vite proxy when available
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${window.location.host}/ws`;
})();

const WS_URL = defaultWsUrl;
const ws = new WSClient(WS_URL);

export const WsIndicator: React.FC = () => {
  const [connected, setConnected] = useState(false);
  const [last, setLast] = useState<any>(null);

  useEffect(() => {
    ws.connect();
    const unsub = ws.onMessage((m) => setLast(m));
    const unsubStatus = ws.onStatus((s) => setConnected(s === 'open'));
    return () => {
      unsub();
      unsubStatus();
      ws.close();
    };
  }, []);

  return (
    <Tooltip title={last ? JSON.stringify(last) : 'No messages yet'}>
      <Chip label={connected ? 'Live' : 'Offline'} color={connected ? 'success' : 'default'} />
    </Tooltip>
  );
};
