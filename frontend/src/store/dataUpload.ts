import create from 'zustand';
import { DataApi } from '../services/api';

interface DataUploadState {
  uploading: boolean;
  error?: string;
  progress: number;
  upload: (form: FormData) => Promise<any>;
}

export const useDataUploadStore = create<DataUploadState>((set) => ({
  uploading: false,
  error: undefined,
  progress: 0,
  upload: async (form) => {
    set({ uploading: true, error: undefined, progress: 0 });
    try {
      const r = await DataApi.upload(form, (pct) => set({ progress: pct }));
      set({ uploading: false, progress: 100 });
      return r;
    } catch (e: any) {
      set({ error: e?.friendlyMessage || e?.message || String(e), uploading: false });
      throw e;
    }
  },
}));
