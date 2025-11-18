import axios from './api';

export type StrategyVersion = { id: number; strategy_id: number; name: string };

export async function listStrategyVersions() {
  const r = await axios.get<{ items: StrategyVersion[]; total: number }>(`/wizard/strategy-versions`);
  return r.data;
}

export async function getVersionSchema(id: number) {
  const r = await axios.get<any>(`/wizard/strategy-version/${id}/schema`);
  return r.data;
}

export async function listPresets(versionId?: number) {
  const r = await axios.get<{ items: { id: number; name: string; params: any }[]; total: number }>(`/wizard/presets`, {
    params: versionId ? { version_id: versionId } : undefined,
  });
  return r.data;
}

export async function quickBacktest(payload: any) {
  const r = await axios.post(`/wizard/backtests/quick`, payload);
  return r.data;
}

export async function createBot(payload: any) {
  const r = await axios.post(`/wizard/bots`, payload);
  return r.data;
}
