type Handler = (active: number) => void;

let active = 0;
let handler: Handler | undefined;

export function setProgressHandler(h?: Handler) {
  handler = h;
  handler?.(active);
}

export function incRequests() {
  active += 1;
  if (active < 0) active = 0;
  handler?.(active);
}

export function decRequests() {
  active -= 1;
  if (active < 0) active = 0;
  handler?.(active);
}

export function getActiveRequests() {
  return active;
}
