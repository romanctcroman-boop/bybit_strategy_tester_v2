import React, { useEffect, useState } from 'react';
import { Chip, Tooltip } from '@mui/material';
import WSClient from '../services/ws';

const WS_URL = (window as any).__env?.REACT_APP_WS_URL || 'ws://localhost:8000/ws';
const ws = new WSClient(WS_URL);

export const WsIndicator: React.FC = () => {
  const [connected, setConnected] = useState(false);
  const [last, setLast] = useState<any>(null);

  useEffect(() => {
    ws.connect();
    const unsub = ws.onMessage((m) => setLast(m));
    const interval = setInterval(() => {
      setConnected(Boolean((ws as any).ws && (ws as any).ws.readyState === WebSocket.OPEN));
    }, 500);
    return () => {
      unsub();
      clearInterval(interval);
      ws.close();
    };
  }, []);

  return (
    <Tooltip title={last ? JSON.stringify(last) : 'No messages yet'}>
      <Chip label={connected ? 'Live' : 'Offline'} color={connected ? 'success' : 'default'} />
    </Tooltip>
  );
};
