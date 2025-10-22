import { useCallback, useState } from 'react';

export type AsyncActionOptions = {
  onError?: (e: any) => void;
  onSuccess?: (res: any) => void;
  autoThrow?: boolean; // rethrow after handling
};

export function useAsyncAction<TArgs extends any[], TResult>(
  fn: (...args: TArgs) => Promise<TResult>,
  opts?: AsyncActionOptions
) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<any>(undefined);

  const run = useCallback(async (...args: TArgs): Promise<TResult | undefined> => {
    setLoading(true);
    setError(undefined);
    try {
      const res = await fn(...args);
      opts?.onSuccess?.(res);
      return res;
    } catch (e: any) {
      setError(e);
      opts?.onError?.(e);
      if (opts?.autoThrow) throw e;
    } finally {
      setLoading(false);
    }
    return undefined;
  }, [fn, opts]);

  return { run, loading, error } as const;
}
