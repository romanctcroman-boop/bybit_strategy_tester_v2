/**
 * useRateLimitedSubmit Hook
 *
 * Защита от частых отправок формы (rate limiting на клиенте)
 */
import { useRef, useCallback } from 'react';

interface UseRateLimitedSubmitOptions {
  cooldownMs?: number; // Время между отправками (default: 2000ms)
  onRateLimitExceeded?: () => void;
}

export const useRateLimitedSubmit = <T extends any[]>(
  callback: (...args: T) => Promise<void>,
  options: UseRateLimitedSubmitOptions = {}
) => {
  const { cooldownMs = 2000, onRateLimitExceeded } = options;

  const lastSubmitTime = useRef<number>(0);
  const isSubmitting = useRef<boolean>(false);

  const rateLimitedCallback = useCallback(
    async (...args: T) => {
      const now = Date.now();
      const timeSinceLastSubmit = now - lastSubmitTime.current;

      // Check if still in cooldown
      if (timeSinceLastSubmit < cooldownMs && lastSubmitTime.current !== 0) {
        if (onRateLimitExceeded) {
          onRateLimitExceeded();
        }
        return;
      }

      // Check if already submitting
      if (isSubmitting.current) {
        return;
      }

      try {
        isSubmitting.current = true;
        lastSubmitTime.current = now;

        await callback(...args);
      } finally {
        isSubmitting.current = false;
      }
    },
    [callback, cooldownMs, onRateLimitExceeded]
  );

  return rateLimitedCallback;
};
