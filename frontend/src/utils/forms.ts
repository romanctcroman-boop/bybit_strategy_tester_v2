export type FieldErrors = Record<string, string>;

export function applyFieldErrors(
  setter: (u: FieldErrors | ((prev: FieldErrors) => FieldErrors)) => void,
  error: any
) {
  const fe = error?.fieldErrors as FieldErrors | undefined;
  if (fe && typeof fe === 'object') {
    setter((prev: FieldErrors) => ({ ...prev, ...fe }));
  }
}

export function validateIsoUtc(value: string | undefined, required = true): string | undefined {
  if (!value) return required ? 'Value is required' : undefined;
  const t = Date.parse(value);
  if (Number.isNaN(t)) return 'Invalid ISO date';
  // Optional: enforce 'Z' suffix for UTC
  if (!/[zZ]$/.test(value)) return 'Must be UTC (end with Z)';
  return undefined;
}

export function validateSymbol(value: string | undefined, required = true): string | undefined {
  if (!value) return required ? 'Symbol is required' : undefined;
  const v = value.trim().toUpperCase();
  if (!/^([A-Z0-9]{3,15})$/.test(v)) return 'Invalid symbol (A-Z0-9, 3-15)';
  return undefined;
}
