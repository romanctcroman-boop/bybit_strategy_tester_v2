import React from 'react';
import { Box, IconButton, Tooltip } from '@mui/material';
import MouseIcon from '@mui/icons-material/Mouse';
import TimelineIcon from '@mui/icons-material/Timeline';
import HorizontalRuleIcon from '@mui/icons-material/HorizontalRule';
import HeightIcon from '@mui/icons-material/Height';
import UndoIcon from '@mui/icons-material/Undo';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import NavigationIcon from '@mui/icons-material/Navigation';
import FormatAlignLeftIcon from '@mui/icons-material/FormatAlignLeft';
import AutoGraphIcon from '@mui/icons-material/AutoGraph';
import CropSquareIcon from '@mui/icons-material/CropSquare';
import StraightenIcon from '@mui/icons-material/Straighten';
import ViewStreamIcon from '@mui/icons-material/ViewStream';
import PushPinIcon from '@mui/icons-material/PushPin';
import type { Tool } from './types';

export type DrawToolbarProps = {
  tool: Tool;
  onChange: (t: Tool) => void;
  onUndo: () => void;
  onClear: () => void;
  onDelete?: () => void;
  selected?: boolean;
  variant?: 'overlay' | 'sidebar';
  magnetEnabled?: boolean;
  onToggleMagnet?: () => void;
};

const DrawToolbar: React.FC<DrawToolbarProps> = ({
  tool,
  onChange,
  onUndo,
  onClear,
  onDelete,
  selected,
  variant = 'overlay',
  magnetEnabled = false,
  onToggleMagnet,
}) => {
  const baseColor = '#fff';
  const btn = (active: boolean) =>
    variant === 'overlay'
      ? {
          color: active ? 'primary.main' : baseColor,
          bgcolor: active ? 'rgba(25,118,210,0.1)' : 'transparent',
        }
      : {
          color: baseColor,
          bgcolor: active ? 'rgba(25,118,210,0.16)' : 'transparent',
          '&:hover': { bgcolor: 'rgba(255,255,255,0.1)' },
        };

  return (
    <Box
      sx={
        variant === 'overlay'
          ? {
              position: 'absolute',
              left: 8,
              top: 8,
              display: 'flex',
              flexDirection: 'column',
              gap: 0.5,
              p: 0.5,
              bgcolor: 'rgba(17,24,39,0.7)',
              borderRadius: 1,
              border: '1px solid rgba(255,255,255,0.08)',
              zIndex: 3,
              color: baseColor,
            }
          : {
              width: 44,
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 0.5,
              p: 0.5,
              bgcolor: 'rgba(17,24,39,0.9)',
              borderRight: '1px solid rgba(255,255,255,0.08)',
              color: baseColor,
            }
      }
    >
      <Tooltip title="Pointer / Select">
        <IconButton size="small" onClick={() => onChange('select')} sx={btn(tool === 'select')}>
          <MouseIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Tooltip title="Trend Line">
        <IconButton
          size="small"
          onClick={() => onChange('trendline')}
          sx={btn(tool === 'trendline')}
        >
          <TimelineIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Tooltip title="Ray">
        <IconButton size="small" onClick={() => onChange('ray')} sx={btn(tool === 'ray')}>
          <NavigationIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Tooltip title="Fibonacci Retracement">
        <IconButton size="small" onClick={() => onChange('fib')} sx={btn(tool === 'fib')}>
          <AutoGraphIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Tooltip title="Rectangle">
        <IconButton size="small" onClick={() => onChange('rect')} sx={btn(tool === 'rect')}>
          <CropSquareIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Tooltip title="Parallel Channel">
        <IconButton size="small" onClick={() => onChange('channel')} sx={btn(tool === 'channel')}>
          <ViewStreamIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Tooltip title="Ruler">
        <IconButton size="small" onClick={() => onChange('ruler')} sx={btn(tool === 'ruler')}>
          <StraightenIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Tooltip title="Horizontal Line">
        <IconButton size="small" onClick={() => onChange('hline')} sx={btn(tool === 'hline')}>
          <HorizontalRuleIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Tooltip title="Horizontal Ray">
        <IconButton size="small" onClick={() => onChange('hray')} sx={btn(tool === 'hray')}>
          <FormatAlignLeftIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Tooltip title="Vertical Line">
        <IconButton size="small" onClick={() => onChange('vline')} sx={btn(tool === 'vline')}>
          <HeightIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Box sx={{ my: 0.5, borderTop: '1px solid rgba(255,255,255,0.08)' }} />
      <Tooltip title="Undo">
        <IconButton size="small" onClick={onUndo}>
          <UndoIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Tooltip title="Delete Selected">
        <span>
          <IconButton size="small" onClick={onDelete} disabled={!selected}>
            <DeleteOutlineIcon fontSize="small" />
          </IconButton>
        </span>
      </Tooltip>
      <Tooltip title="Clear All">
        <IconButton size="small" onClick={onClear}>
          <DeleteOutlineIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Box sx={{ my: 0.5, borderTop: '1px solid rgba(255,255,255,0.08)', width: '100%' }} />
      <Tooltip title={magnetEnabled ? 'Disable Magnet Snap' : 'Enable Magnet Snap'}>
        <IconButton
          size="small"
          onClick={() => onToggleMagnet?.()}
          sx={{ color: magnetEnabled ? 'primary.main' : baseColor }}
        >
          <PushPinIcon fontSize="small" />
        </IconButton>
      </Tooltip>
    </Box>
  );
};

export default DrawToolbar;
