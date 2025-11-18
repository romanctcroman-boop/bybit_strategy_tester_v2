import React from 'react';
import {
  Box,
  Button,
  Container,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Step,
  StepLabel,
  Stepper,
  TextField,
  Typography,
} from '@mui/material';
import { listPresets, listStrategyVersions, quickBacktest, createBot } from '../services/wizard';
import { emitNotification } from '../services/notifications';

const steps = ['Стратегия', 'Параметры', 'Риск', 'Быстрый бэктест', 'Подтверждение'];

const WizardCreateBot: React.FC = () => {
  const [active, setActive] = React.useState(0);
  const [versions, setVersions] = React.useState<{ id: number; name: string }[]>([]);
  const [versionId, setVersionId] = React.useState<number | ''>('');
  const [presets, setPresets] = React.useState<{ id: number; name: string; params: any }[]>([]);
  const [params, setParams] = React.useState<any>({});
  const [risk, setRisk] = React.useState({ deposit: 100, leverage: 5 });
  const [preview, setPreview] = React.useState<any | null>(null);
  const [loading, setLoading] = React.useState(false);

  React.useEffect(() => {
    (async () => {
      try {
        const res = await listStrategyVersions();
        setVersions(res.items.map((x) => ({ id: x.id, name: x.name })));
      } catch {}
    })();
  }, []);

  const onPickVersion = async (id: number) => {
    setVersionId(id);
    const p = await listPresets(id);
    setPresets(p.items);
    // default params from first preset if any
    setParams(p.items[0]?.params || {});
  };

  const next = async () => {
    if (active === 3) {
      // run quick backtest again (optional)
      await runPreview();
    }
    setActive((s) => Math.min(s + 1, steps.length - 1));
  };
  const back = () => setActive((s) => Math.max(s - 1, 0));

  const runPreview = async () => {
    if (!versionId) return;
    setLoading(true);
    try {
      const res = await quickBacktest({ strategy_version_id: versionId, params, risk });
      setPreview(res);
    } catch {
      emitNotification({ message: 'Не удалось выполнить быстрый бэктест', severity: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const finish = async () => {
    if (!versionId) return;
    setLoading(true);
    try {
      const res = await createBot({
        name: 'New Bot',
        strategy_version_id: versionId,
        params,
        risk,
      });
      emitNotification({ message: `Бот создан (id=${res.bot_id})`, severity: 'success' });
    } catch {
      emitNotification({ message: 'Ошибка при создании бота', severity: 'error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="md" sx={{ py: 3 }}>
      <Typography variant="h5" sx={{ fontWeight: 700, mb: 2 }}>
        Создание бота
      </Typography>
      <Stepper activeStep={active} sx={{ mb: 3 }}>
        {steps.map((s) => (
          <Step key={s}>
            <StepLabel>{s}</StepLabel>
          </Step>
        ))}
      </Stepper>

      {/* Step content */}
      {active === 0 && (
        <Stack spacing={2}>
          <FormControl fullWidth>
            <InputLabel id="version-label">Версия стратегии</InputLabel>
            <Select
              labelId="version-label"
              label="Версия стратегии"
              value={versionId}
              onChange={(e) => onPickVersion(e.target.value as number)}
            >
              {versions.map((v) => (
                <MenuItem key={v.id} value={v.id}>
                  {v.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Stack>
      )}

      {active === 1 && (
        <Stack spacing={2}>
          <FormControl fullWidth>
            <InputLabel id="preset-label">Пресет</InputLabel>
            <Select
              labelId="preset-label"
              label="Пресет"
              value=""
              onChange={(e) => {
                const found = presets.find((p) => String(p.id) === String(e.target.value));
                if (found) setParams(found.params);
              }}
            >
              {presets.map((p) => (
                <MenuItem key={p.id} value={p.id}>
                  {p.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          {/* Простейшая форма параметров (ключ-значение) */}
          {Object.entries(params).map(([k, v]) => (
            <TextField
              key={k}
              label={k}
              value={String(v)}
              onChange={(e) => setParams({ ...params, [k]: Number(e.target.value) })}
            />
          ))}
        </Stack>
      )}

      {active === 2 && (
        <Stack spacing={2}>
          <TextField
            label="Депозит (USDT)"
            type="number"
            value={risk.deposit}
            onChange={(e) => setRisk({ ...risk, deposit: Number(e.target.value) })}
          />
          <TextField
            label="Плечо"
            type="number"
            value={risk.leverage}
            onChange={(e) => setRisk({ ...risk, leverage: Number(e.target.value) })}
          />
        </Stack>
      )}

      {active === 3 && (
        <Stack spacing={2}>
          <Button variant="outlined" onClick={runPreview} disabled={loading}>
            Запустить быстрый бэктест
          </Button>
          <Box sx={{ p: 2, border: '1px dashed', borderColor: 'divider', borderRadius: 1 }}>
            <Typography variant="subtitle2">Предпросмотр метрик</Typography>
            <pre style={{ margin: 0 }}>
              {preview ? JSON.stringify(preview, null, 2) : 'Нет данных'}
            </pre>
          </Box>
        </Stack>
      )}

      {active === 4 && (
        <Stack spacing={1}>
          <Typography>Проверьте параметры и подтвердите создание.</Typography>
          <pre style={{ margin: 0 }}>{JSON.stringify({ versionId, params, risk }, null, 2)}</pre>
        </Stack>
      )}

      <Stack direction="row" spacing={1.5} mt={3}>
        <Button onClick={back} disabled={active === 0}>
          Назад
        </Button>
        {active < steps.length - 1 && (
          <Button variant="contained" onClick={next} disabled={active === 3 && loading}>
            Далее
          </Button>
        )}
        {active === steps.length - 1 && (
          <Button variant="contained" color="success" onClick={finish} disabled={loading}>
            Создать бота
          </Button>
        )}
      </Stack>
    </Container>
  );
};

export default WizardCreateBot;
