import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Container, Typography, Paper } from '@mui/material';
import TradingViewWidget from '../components/TradingViewWidget';
import { Button, ButtonGroup } from '@mui/material';
import { useBacktestsStore } from '../store/backtests';
import { Backtest, Trade } from '../types/api';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

const TradesTable: React.FC<{ trades: Trade[] }> = ({ trades }) => {
  const cols: GridColDef[] = [
    { field: 'id', headerName: 'ID', width: 80 },
    { field: 'entry_time', headerName: 'Entry', width: 180, valueGetter: (p: any) => new Date(p.row.entry_time).toLocaleString() },
    { field: 'exit_time', headerName: 'Exit', width: 180, valueGetter: (p: any) => p.row.exit_time ? new Date(p.row.exit_time).toLocaleString() : '' },
    { field: 'side', headerName: 'Side', width: 100 },
    { field: 'price', headerName: 'Price', width: 120 },
    { field: 'qty', headerName: 'Qty', width: 100 },
    { field: 'pnl', headerName: 'PnL', width: 120 },
  ];

  return (
    <div style={{ height: 400, width: '100%' }}>
      <DataGrid rows={trades} columns={cols} getRowId={(r: any) => r.id} />
    </div>
  );
};

const BacktestDetailPage: React.FC = () => {
  const { id } = useParams();
  const backtestId = Number(id || 0);
  const { fetchTrades } = useBacktestsStore();
  const [trades, setTrades] = useState<Trade[]>([]);
  const [series, setSeries] = useState<any[]>([]);
  const [candles, setCandles] = useState<any[]>([]);
  const [useTradingView, setUseTradingView] = useState(false);

  useEffect(() => {
    (async () => {
      const t = await fetchTrades(backtestId);
      if (t) {
        setTrades(t);
        setSeries(t.map((x) => ({ time: new Date(x.entry_time).toISOString(), pnl: x.pnl ?? 0 })));
        // create simple OHLC candles from trades for demo
        setCandles(t.map((x, i) => ({ time: Math.floor(new Date(x.entry_time).getTime() / 1000), open: x.price, high: x.price * 1.01, low: x.price * 0.99, close: x.price })) );
      }
    })();
  }, [id]);

  return (
    <Container>
      <Typography variant="h4">Backtest #{id}</Typography>
      <Paper sx={{ mt: 2, p: 2 }}>
        <Typography variant="h6">Equity curve</Typography>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={series}>
            <CartesianGrid stroke="#ccc" />
            <XAxis dataKey="time" tickFormatter={(v: any) => new Date(v).toLocaleTimeString()} />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="pnl" stroke="#8884d8" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </Paper>

      <Paper sx={{ mt: 2, p: 2 }}>
        <Typography variant="h6">Trades</Typography>
        <TradesTable trades={trades} />
      </Paper>

      <Paper sx={{ mt: 2, p: 2 }}>
        <Typography variant="h6">Chart</Typography>
        <ButtonGroup variant="outlined" sx={{ mb: 2 }}>
          <Button onClick={() => setUseTradingView(false)} disabled={!useTradingView}>Lightweight</Button>
          <Button onClick={() => setUseTradingView(true)} disabled={useTradingView}>TradingView</Button>
        </ButtonGroup>
        {useTra