import React from 'react';
import { Box, Typography } from '@mui/material';

export interface PriceProgressBarProps {
  min: number;
  entry: number; // red
  nextOpen: number; // blue
  target: number; // green at the far right
  current?: number; // optional current price marker
  side?: 'LONG' | 'SHORT';
}

// Utility to map value to percent in [min, max]
function toPct(value: number, min: number, max: number) {
  const span = Math.max(1e-9, max - min);
  return ((value - min) / span) * 100;
}

const PriceProgressBar: React.FC<PriceProgressBarProps> = ({
  min,
  entry,
  nextOpen,
  target,
  current,
  side: _side = 'LONG',
}) => {
  const max = Math.max(target, entry, nextOpen, current ?? target, min);
  const entryP = toPct(entry, min, max);
  const nextP = toPct(nextOpen, min, max);
  const targP = toPct(target, min, max);
  const currP = current !== undefined ? toPct(current, min, max) : undefined;

  const redStart = Math.min(entryP, nextP);
  const redWidth = Math.abs(nextP - entryP);

  const primaryRed = '#b71c1c';
  const lightBg = 'rgba(0,0,0,0.06)';
  const blue = '#3949ab';
  const green = '#2e7d32';

  return (
    <Box sx={{ position: 'relative', height: 38, display: 'flex', alignItems: 'center' }}>
      {/* Track */}
      <Box
        sx={{
          position: 'absolute',
          left: 0,
          right: 0,
          height: 8,
          bgcolor: lightBg,
          borderRadius: 2,
        }}
      />
      {/* Red segment between entry and nextOpen */}
      <Box
        sx={{
          position: 'absolute',
          left: `${redStart}%`,
          width: `${redWidth}%`,
          height: 8,
          bgcolor: primaryRed,
          borderRadius: 2,
        }}
      />

      {/* Entry marker (thin) */}
      <Box
        sx={{
          position: 'absolute',
          left: `${entryP}%`,
          transform: 'translateX(-1px)',
          width: 2,
          height: 16,
          bgcolor: primaryRed,
        }}
      />
      {/* Next open marker */}
      <Box
        sx={{
          position: 'absolute',
          left: `${nextP}%`,
          transform: 'translateX(-1px)',
          width: 2,
          height: 16,
          bgcolor: blue,
        }}
      />
      {/* Target marker (green) */}
      <Box
        sx={{
          position: 'absolute',
          left: `${targP}%`,
          transform: 'translateX(-1px)',
          width: 2,
          height: 22,
          bgcolor: green,
        }}
      />
      {/* Current marker (if any) */}
      {currP !== undefined && (
        <Box
          sx={{
            position: 'absolute',
            left: `${currP}%`,
            transform: 'translateX(-1px)',
            width: 2,
            height: 16,
            bgcolor: '#455a64',
          }}
        />
      )}

      {/* Labels (top small) */}
      <Typography
        variant="caption"
        sx={{
          position: 'absolute',
          left: `${entryP}%`,
          transform: 'translate(-50%, -140%)',
          color: primaryRed,
        }}
      >
        {entry}
      </Typography>
      <Typography
        variant="caption"
        sx={{
          position: 'absolute',
          left: `${nextP}%`,
          transform: 'translate(-50%, -140%)',
          color: blue,
        }}
      >
        {nextOpen}
      </Typography>
      <Typography
        variant="caption"
        sx={{
          position: 'absolute',
          left: `${targP}%`,
          transform: 'translate(-50%, -140%)',
          color: green,
        }}
      >
        {target}
      </Typography>
      {/* Bottom grey numbers for entry/nextOpen (optional for visual richness) */}
      <Typography
        variant="caption"
        sx={{
          position: 'absolute',
          left: `${entryP}%`,
          transform: 'translate(-50%, 60%)',
          color: 'text.secondary',
        }}
      >
        {entry}
      </Typography>
      <Typography
        variant="caption"
        sx={{
          position: 'absolute',
          left: `${nextP}%`,
          transform: 'translate(-50%, 60%)',
          color: 'text.secondary',
        }}
      >
        {nextOpen}
      </Typography>
    </Box>
  );
};

export default PriceProgressBar;
