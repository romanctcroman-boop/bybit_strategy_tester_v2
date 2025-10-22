import React, { useEffect, useState } from 'react';
import { Box, Typography, Alert, CircularProgress } from '@mui/material';
import { DataApi } from '../services/api';

const DebugPage: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        console.log('[Debug] Fetching klines...');
        const result = await DataApi.bybitKlines('BTCUSDT', '1', 10, 0);
        console.log('[Debug] Got result:', result);
        setData(result);
      } catch (e: any) {
        console.error('[Debug] Error:', e);
        setError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5">Debug Page</Typography>
      
      {loading && <CircularProgress />}
      {error && <Alert severity="error">{error}</Alert>}
      
      {data && (
        <>
          <Typography>Got {data.length} candles</Typography>
          <pre style={{ 
            backgroundColor: '#f5f5f5', 
            padding: 12, 
            overflow: 'auto',
            maxHeight: '400px'
          }}>
            {JSON.stringify(data, null, 2)}
          </pre>
        </>
      )}
    </Box>
  );
};

export default DebugPage;
