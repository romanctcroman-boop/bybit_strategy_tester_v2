import React, { useEffect, useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  FormControlLabel,
  Checkbox,
  Stack,
} from '@mui/material';
import type { Strategy } from '../types/api';

export interface StrategyDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (payload: Partial<Strategy>) => Promise<void> | void;
  initial?: Partial<Strategy> | null;
}

const StrategyDialog: React.FC<StrategyDialogProps> = ({ open, onClose, onSubmit, initial }) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [strategyType, setStrategyType] = useState('');
  const [isActive, setIsActive] = useState(true);
  const [config, setConfig] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setName(initial?.name || '');
      setDescription(initial?.description || '');
      setStrategyType(initial?.strategy_type || '');
      setIsActive(initial?.is_active ?? true);
      setConfig(initial?.config ? JSON.stringify(initial.config, null, 2) : '');
      setErrors({});
      setSubmitting(false);
    }
  }, [open, initial]);

  const validate = () => {
    const e: Record<string, string> = {};
    if (!name.trim()) e.name = 'Name is required';
    if (!strategyType.trim()) e.strategy_type = 'Type is required';
    if (config.trim()) {
      try {
        JSON.parse(config);
      } catch {
        e.config = 'Config must be valid JSON';
      }
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const submit = async () => {
    if (!validate()) return;
    setSubmitting(true);
    try {
      const payload: Partial<Strategy> = {
        name: name.trim(),
        description: description.trim() || undefined,
        strategy_type: strategyType.trim(),
        is_active: !!isActive,
        config: config.trim() ? JSON.parse(config) : {},
      } as any;
      await onSubmit(payload);
      onClose();
    } catch {
      // errors handled by caller via notifications
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{initial?.id ? 'Edit Strategy' : 'New Strategy'}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <TextField
            label="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            error={!!errors.name}
            helperText={errors.name || ' '}
          />
          <TextField
            label="Type"
            value={strategyType}
            onChange={(e) => setStrategyType(e.target.value)}
            error={!!errors.strategy_type}
            helperText={errors.strategy_type || 'e.g. rsi_ema'}
          />
          <TextField
            label="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <FormControlLabel
            control={<Checkbox checked={isActive} onChange={(_, v) => setIsActive(v)} />}
            label="Active"
          />
          <TextField
            label="Config (JSON)"
            value={config}
            onChange={(e) => setConfig(e.target.value)}
            error={!!errors.config}
            helperText={errors.config || 'Optional JSON config'}
            multiline
            minRows={4}
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={submit} variant="contained" disabled={submitting}>
          {submitting ? 'Saving…' : 'Save'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default StrategyDialog;
