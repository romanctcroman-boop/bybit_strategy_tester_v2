export type Severity = 'success' | 'info' | 'warning' | 'error';
export type Notification = { message: string; severity?: Severity };

let notifier: ((n: Notification) => void) | undefined;

export function setGlobalNotifier(fn?: (n: Notification) => void) {
  notifier = fn;
}

export function emitNotification(n: Notification) {
  try {
    notifier?.(n);
  } catch {
    // no-op
  }
}
