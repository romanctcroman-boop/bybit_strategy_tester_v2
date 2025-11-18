export type BackfillRequest = {
  symbol: string;
  interval?: string;
  lookback_minutes?: number;
  start_at_iso?: string;
  end_at_iso?: string;
  page_limit?: number;
  max_pages?: number;
  mode?: 'sync' | 'async';
};

export async function adminBackfill(req: BackfillRequest, auth?: { user: string; pass: string }) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (auth) {
    const token = btoa(`${auth.user}:${auth.pass}`);
    headers['Authorization'] = `Basic ${token}`;
  }
  const res = await fetch('/api/v1/admin/backfill', {
    method: 'POST',
    headers,
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`backfill failed: ${res.status}`);
  return res.json();
}

export type ArchiveRequest = {
  output_dir?: string;
  before_iso?: string;
  symbol?: string;
  interval_for_partition?: string;
  batch_size?: number;
  mode?: 'sync' | 'async';
};

export async function adminArchive(req: ArchiveRequest, auth?: { user: string; pass: string }) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (auth) {
    const token = btoa(`${auth.user}:${auth.pass}`);
    headers['Authorization'] = `Basic ${token}`;
  }
  const res = await fetch('/api/v1/admin/archive', {
    method: 'POST',
    headers,
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`archive failed: ${res.status}`);
  return res.json();
}

export type RestoreRequest = {
  input_dir?: string;
  mode?: 'sync' | 'async';
};

export async function adminRestore(req: RestoreRequest, auth?: { user: string; pass: string }) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (auth) {
    const token = btoa(`${auth.user}:${auth.pass}`);
    headers['Authorization'] = `Basic ${token}`;
  }
  const res = await fetch('/api/v1/admin/restore', {
    method: 'POST',
    headers,
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`restore failed: ${res.status}`);
  return res.json();
}

export async function adminListArchives(dir = 'archives', auth?: { user: string; pass: string }) {
  const headers: Record<string, string> = {};
  if (auth) {
    const token = btoa(`${auth.user}:${auth.pass}`);
    headers['Authorization'] = `Basic ${token}`;
  }
  const res = await fetch(`/api/v1/admin/archives?dir=${encodeURIComponent(dir)}`, { headers });
  if (!res.ok) throw new Error(`archives list failed: ${res.status}`);
  return res.json();
}

export async function adminDeleteArchive(path: string, auth?: { user: string; pass: string }) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (auth) {
    const token = btoa(`${auth.user}:${auth.pass}`);
    headers['Authorization'] = `Basic ${token}`;
  }
  const res = await fetch(`/api/v1/admin/archives`, { method: 'DELETE', headers, body: JSON.stringify({ path }) });
  if (!res.ok) throw new Error(`archive delete failed: ${res.status}`);
  return res.json();
}

export async function adminTaskStatus(taskId: string, auth?: { user: string; pass: string }) {
  const headers: Record<string, string> = {};
  if (auth) {
    const token = btoa(`${auth.user}:${auth.pass}`);
    headers['Authorization'] = `Basic ${token}`;
  }
  const res = await fetch(`/api/v1/admin/task/${encodeURIComponent(taskId)}`, { headers });
  if (!res.ok) throw new Error(`status failed: ${res.status}`);
  return res.json();
}

export async function adminListRuns(limit = 50, auth?: { user: string; pass: string }) {
  const headers: Record<string, string> = {};
  if (auth) {
    const token = btoa(`${auth.user}:${auth.pass}`);
    headers['Authorization'] = `Basic ${token}`;
  }
  const res = await fetch(`/api/v1/admin/backfill/runs?limit=${limit}`, { headers });
  if (!res.ok) throw new Error(`runs failed: ${res.status}`);
  return res.json();
}

export async function adminGetRun(id: number, auth?: { user: string; pass: string }) {
  const headers: Record<string, string> = {};
  if (auth) {
    const token = btoa(`${auth.user}:${auth.pass}`);
    headers['Authorization'] = `Basic ${token}`;
  }
  const res = await fetch(`/api/v1/admin/backfill/runs/${id}`, { headers });
  if (!res.ok) throw new Error(`run failed: ${res.status}`);
  return res.json();
}

export async function adminGetProgress(symbol: string, interval: string, auth?: { user: string; pass: string }) {
  const headers: Record<string, string> = {};
  if (auth) {
    const token = btoa(`${auth.user}:${auth.pass}`);
    headers['Authorization'] = `Basic ${token}`;
  }
  const qp = new URLSearchParams({ symbol, interval });
  const res = await fetch(`/api/v1/admin/backfill/progress?${qp.toString()}`, { headers });
  if (!res.ok) throw new Error(`progress failed: ${res.status}`);
  return res.json();
}

export async function adminResetProgress(symbol: string, interval: string, auth?: { user: string; pass: string }) {
  const headers: Record<string, string> = {};
  if (auth) {
    const token = btoa(`${auth.user}:${auth.pass}`);
    headers['Authorization'] = `Basic ${token}`;
  }
  const qp = new URLSearchParams({ symbol, interval });
  const res = await fetch(`/api/v1/admin/backfill/progress?${qp.toString()}`, { method: 'DELETE', headers });
  if (!res.ok) throw new Error(`progress reset failed: ${res.status}`);
  return res.json();
}
