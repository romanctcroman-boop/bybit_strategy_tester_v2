import create from 'zustand';
import { DataApi } from '../services/api';

interface DataUploadState {
  uploading: boolean;
  error?: string;
  upload: (form: FormData) => Promise<any>;
}

export const useDataUploadStore = create<DataUploadState>((set) => ({
  uploading: false,
  error: undefined,
  upload: async (form) => {
    set({ uploading: true, error: undefined });
    try {
      const r = await DataApi.upload(form);
      set({ uploading: false });
      return r;
    } catch (e: any) {
      set({ error: e?.friendlyMessage || e?.message || String(e), uploading: false });
      throw e;
    }
  },
}));
