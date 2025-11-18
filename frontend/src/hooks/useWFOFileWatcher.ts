import { useEffect, useState } from 'react';
import * as chokidar from 'chokidar';
import { WFOResults } from './useWFOResults';

/**
 * Hook для отслеживания изменений в WFO файлах
 * Автоматически обновляет данные при изменении JSON файлов
 */
export const useWFOFileWatcher = (strategy: string, enabled: boolean = true) => {
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [watchedFile, setWatchedFile] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) return;

    // Определяем путь к файлу
    const fileMap: Record<string, string> = {
      ema_crossover: 'wfo_ema_22_cycles',
      sr_mean_reversion: 'wfo_sr_22_cycles',
      bb_mean_reversion: 'wfo_bb_22_cycles',
      sr_rsi: 'wfo_sr_rsi_22_cycles',
    };

    const fileName = fileMap[strategy];
    if (!fileName) return;

    // Путь к results директории
    const resultsPath = '../results'; // Относительно frontend

    // Создаем watcher
    const watcher = chokidar.watch(`${resultsPath}/${fileName}*.json`, {
      persistent: true,
      ignoreInitial: true,
      awaitWriteFinish: {
        stabilityThreshold: 2000,
        pollInterval: 100,
      },
    });

    watcher.on('change', (path) => {
      console.log(`[FileWatcher] File changed: ${path}`);
      setWatchedFile(path);
      setLastUpdate(new Date());
    });

    watcher.on('add', (path) => {
      console.log(`[FileWatcher] New file added: ${path}`);
      setWatchedFile(path);
      setLastUpdate(new Date());
    });

    watcher.on('error', (error) => {
      console.error('[FileWatcher] Error:', error);
    });

    return () => {
      watcher.close();
    };
  }, [strategy, enabled]);

  return { lastUpdate, watchedFile };
};

/**
 * Hook для периодического опроса WFO результатов (fallback если file watching не работает)
 */
export const useWFOPolling = (
  strategy: string,
  interval: number = 5000,
  enabled: boolean = false
) => {
  const [data, setData] = useState<WFOResults | null>(null);
  const [lastPoll, setLastPoll] = useState<Date | null>(null);

  useEffect(() => {
    if (!enabled) return;

    const poll = async () => {
      try {
        const fileMap: Record<string, string> = {
          ema_crossover: 'wfo_ema_22_cycles',
          sr_mean_reversion: 'wfo_sr_22_cycles',
          bb_mean_reversion: 'wfo_bb_22_cycles',
          sr_rsi: 'wfo_sr_rsi_22_cycles',
        };

        const fileName = fileMap[strategy];
        if (!fileName) return;

        const response = await fetch(`/results/${fileName}_latest.json?t=${Date.now()}`);
        if (response.ok) {
          const json = await response.json();
          setData(json);
          setLastPoll(new Date());
        }
      } catch (error) {
        console.error('[Polling] Error:', error);
      }
    };

    // Initial poll
    poll();

    // Setup interval
    const intervalId = setInterval(poll, interval);

    return () => {
      clearInterval(intervalId);
    };
  }, [strategy, interval, enabled]);

  return { data, lastPoll };
};
