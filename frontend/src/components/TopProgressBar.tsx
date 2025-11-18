import React, { useEffect, useState } from 'react';
import { LinearProgress } from '@mui/material';
import { setProgressHandler } from '../services/progress';

const TopProgressBar: React.FC = () => {
  const [active, setActive] = useState(0);

  useEffect(() => {
    setProgressHandler((n) => setActive(n));
    return () => setProgressHandler(undefined);
  }, []);

  if (active <= 0) return null;

  return (
    <div style={{ position: 'fixed', top: 0, left: 0, right: 0, zIndex: 2000 }}>
      <LinearProgress color="secondary" />
    </div>
  );
};

export default TopProgressBar;
